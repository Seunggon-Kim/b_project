// 표 목록과 열 정보를 백엔드에 맞게 읽습니다.
//
// D1 은 sqlite_master·PRAGMA, MySQL 은 information_schema 입니다. 응답은
// 화면이 이미 쓰는 D1 모양({name, type, pk, notnull}, SQLite 식 타입
// 이름)으로 맞춥니다. CSV 의 실수 열 판단(csv.js isRealType)도 이 type 을
// 봅니다.
import { isMysql } from './backendflag.js';

export function sqliteTypeOf(dataType) {
  const t = String(dataType || '').toLowerCase();
  if (t.includes('int')) return 'INTEGER';
  if (t.includes('double') || t.includes('float') || t.includes('decimal') || t === 'real') return 'REAL';
  if (t.includes('blob') || t.includes('binary')) return 'BLOB';
  return 'TEXT';
}

// D1 은 자체 내부 표(`_cf_KV` 등)를 갖고 있어 함께 거릅니다. `meta_` 로
// 시작하는 표는 읽기량을 줄이려고 만든 내부 표(`meta_table_counts` 등)라
// 사용자에게 보일 이유가 없어 뺍니다.
export async function tableNames(env) {
  if (isMysql(env)) {
    const { results } = await env.DB.prepare(
      'SELECT table_name AS name FROM information_schema.tables '
      + "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE' "
      + "AND table_name NOT LIKE 'meta\\_%' ORDER BY table_name",
    ).all();
    return results.map((r) => r.name);
  }
  const { results } = await env.DB.prepare(
    "SELECT name FROM sqlite_master WHERE type='table' "
    + "AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_cf\\_%' ESCAPE '\\' "
    + "AND name NOT LIKE 'meta\\_%' ESCAPE '\\' "
    + 'ORDER BY name',
  ).all();
  return results.map((r) => r.name);
}

export async function tableColumns(env, table, db = env.DB) {
  if (isMysql(env)) {
    // MySQL 8 은 information_schema 의 열 이름을 대문자로 돌려줍니다
    // (COLUMN_NAME 등). 별칭을 모두 붙여 이름을 고정합니다.
    const { results } = await db.prepare(
      'SELECT column_name AS name, data_type AS dtype, column_key AS ckey, '
      + 'is_nullable AS nullable FROM information_schema.columns '
      + 'WHERE table_schema = DATABASE() AND table_name = ? ORDER BY ordinal_position',
    ).bind(table).all();
    return results.map((r) => ({
      name: r.name,
      type: sqliteTypeOf(r.dtype),
      pk: r.ckey === 'PRI' ? 1 : 0,
      notnull: r.nullable === 'NO' ? 1 : 0,
    }));
  }
  // D1 은 PRAGMA 행을 그대로 돌려줍니다(지금 화면·CSV 가 쓰는 모양).
  const { results } = await db.prepare(`PRAGMA table_info(\`${table}\`)`).all();
  return results;
}

/**
 * 표마다 열 수입니다(이름 -> 수). MySQL 만 한 번의 질의로 셉니다.
 *
 * `/db/tables` 가 표마다 tableColumns 를 부르면 질의가 표 수만큼 나가
 * Worker CPU 가 쌓입니다. 수는 tableColumns(env, 표).length 와 같습니다
 * (같은 information_schema.columns 의 행 수). D1 이면 null 이고, 부르는
 * 쪽이 예전처럼 표마다 셉니다.
 */
export async function columnCounts(env) {
  if (!isMysql(env)) return null;
  const { results } = await env.DB.prepare(
    'SELECT table_name AS name, COUNT(*) AS n FROM information_schema.columns '
    + 'WHERE table_schema = DATABASE() GROUP BY table_name',
  ).all();
  return new Map(results.map((r) => [r.name, Number(r.n)]));
}

export async function tableExists(env, name) {
  try {
    const row = isMysql(env)
      ? await env.DB.prepare(
        'SELECT 1 AS x FROM information_schema.tables '
        + 'WHERE table_schema = DATABASE() AND table_name = ?',
      ).bind(name).first()
      : await env.DB.prepare(
        "SELECT 1 AS x FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
      ).bind(name).first();
    return Boolean(row);
  } catch {
    return false;
  }
}
