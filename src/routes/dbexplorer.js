import { json } from '../lib/respond.js';
import { columnDict } from '../lib/coldict.js';

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
