import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import { columnDict, tableMeta } from '../lib/coldict.js';

/**
 * 원본 list_table_names (api/main.py:622-628) 입니다.
 * sqlite 내부 표를 뺀 이름 목록입니다.
 *
 * D1 은 자체 내부 표(`_cf_KV` 등)를 갖고 있습니다. 원본은 `sqlite_%` 만
 * 걸러 내므로 그대로 두면 목록에 섞입니다. 정답지와 맞추려면 그것도 빼야
 * 합니다. `_cf_` 로 시작하는 것을 함께 거릅니다.
 */
export async function listTableNames(db) {
  const { results } = await db.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' "
    + "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' "
    + 'ORDER BY name',
  ).all();
  return results.map((r) => r.name);
}

/**
 * 원본 api/main.py:646-670 입니다.
 * 표 목록에 행 수·컬럼 수와 사전의 분류·설명·갱신주기를 붙입니다.
 */
export async function dbTables(request, env) {
  const db = env.DB;
  const meta = columnDict();
  const tmeta = meta.tables || {};
  const names = await listTableNames(db);

  const result = [];
  for (const name of names) {
    let n = null;
    try {
      const row = await db.prepare(`SELECT COUNT(*) AS n FROM "${name}"`).first();
      n = row ? row.n : null;
    } catch {
      // 원본도 실패하면 None 을 넣습니다. 0 이 아닙니다.
      n = null;
    }
    const info = await db.prepare(`PRAGMA table_info("${name}")`).all();
    const m = tmeta[name] || {};
    result.push({
      name,
      rows: n,
      columns: info.results.length,
      category: m.category || '',
      table_desc: m.table_desc || '',
      update_freq: m.update_freq || '',
    });
  }

  return json({
    tables: result,
    count: result.length,
    categories: meta.categories || [],
  });
}

/**
 * 원본 api/main.py:673-716 입니다. 표 하나의 스키마와 페이지네이션된 행.
 *
 * 표 이름이 SQL 에 그대로 들어가는 자리라, **반드시 sqlite_master 목록으로
 * 확인한 뒤에만** 조회합니다. 원본이 그렇게 하고 있고 그 확인이 곧 방어입니다.
 */
export async function dbTable(request, env, ctx, params) {
  const db = env.DB;
  const tableName = params.name;

  const names = await listTableNames(db);
  if (!names.includes(tableName)) {
    return json({ detail: 'Table not found' }, 404);
  }

  const url = new URL(request.url);
  // 원본: limit = max(1, min(int(limit), 500)), offset = max(0, int(offset))
  const limit = Math.max(1, Math.min(queryInt(url, 'limit', 50), 500));
  const offset = Math.max(0, queryInt(url, 'offset', 0));

  const tmeta = tableMeta(tableName);
  const cdesc = tmeta.columns || {};

  const info = await db.prepare(`PRAGMA table_info("${tableName}")`).all();
  const schema = info.results.map((c) => ({
    name: c.name,
    type: c.type || '',
    pk: Boolean(c.pk),
    notnull: Boolean(c.notnull),
    desc: cdesc[c.name] || '',
  }));
  const columns = info.results.map((c) => c.name);

  const totalRow = await db
    .prepare(`SELECT COUNT(*) AS n FROM "${tableName}"`).first();
  const { results: rows } = await db
    .prepare(`SELECT * FROM "${tableName}" LIMIT ? OFFSET ?`)
    .bind(limit, offset).all();

  return json({
    table: tableName,
    schema,
    columns,
    rows,
    total: totalRow ? totalRow.n : 0,
    limit,
    offset,
    table_desc: tmeta.table_desc || '',
    update_freq: tmeta.update_freq || '',
    category: tmeta.category || '',
  });
}
