// 표별 행 수를 미리 기록해 둔 것을 읽습니다.
//
// 왜 필요한가. D1 은 스캔한 행 수로 과금하고 무료 한도가 하루 500만
// 행입니다. `COUNT(*)` 는 **인덱스로 줄지 않습니다.** 로컬에서
// `EXPLAIN QUERY PLAN` 을 돌려 확인했습니다.
//
//   SELECT COUNT(*) FROM play_by_play
//   -> SCAN play_by_play USING COVERING INDEX idx_pbp_pitcher
//
// 커버링 인덱스를 타지만 b-tree 를 끝까지 훑으므로 229,667행이 그대로
// 과금됩니다. `/db/tables` 는 표 18개마다 이것을 돌려 한 번에 24만 행을
// 읽었습니다. 12시즌이 되면 표 하나가 276만 행입니다.
//
// 그래서 세지 않고, 적재할 때 적어 둔 값을 읽습니다.

/** 메타 표 이름입니다. 적재 스크립트와 이 값이 같아야 합니다. */
export const COUNTS_TABLE = 'meta_table_counts';

/**
 * 표 하나의 행 수입니다.
 *
 * 메타에 값이 없으면 `COUNT(*)` 로 물러섭니다. 느리지만 틀린 숫자를
 * 보여 주는 것보다 낫습니다. 메타가 아직 없는 표(새로 만든 표, 적재
 * 전)에서도 화면이 동작해야 합니다.
 */
export async function countOf(db, table) {
  try {
    const row = await db
      .prepare(`SELECT n FROM ${COUNTS_TABLE} WHERE name = ?`)
      .bind(table).first();
    if (row && typeof row.n === 'number') return row.n;
  } catch {
    // 메타 표 자체가 없는 경우입니다. 아래로 떨어뜨립니다.
  }
  try {
    const row = await db
      .prepare(`SELECT COUNT(*) AS n FROM "${table}"`).first();
    return row ? row.n : null;
  } catch {
    // 원본도 조회에 실패하면 0 이 아니라 null 을 넣습니다.
    return null;
  }
}

/**
 * 여러 표의 행 수를 한 번에 읽습니다.
 *
 * 표마다 따로 물으면 D1 쿼리가 표 수만큼 나가는데, Worker 호출당 50개가
 * 한도입니다. `/db/tables` 는 표가 18개라 한 번에 가져와야 합니다.
 *
 * 메타에 없는 표는 결과에서 빠집니다. 부르는 쪽이 `countOf` 로 개별
 * 보완하거나 null 로 두어야 합니다.
 */
export async function countsOf(db, tables) {
  const out = new Map();
  if (!tables.length) return out;
  try {
    const marks = tables.map(() => '?').join(',');
    const { results } = await db
      .prepare(`SELECT name, n FROM ${COUNTS_TABLE} WHERE name IN (${marks})`)
      .bind(...tables).all();
    for (const r of results) out.set(r.name, r.n);
  } catch {
    // 메타 표가 없으면 빈 맵입니다. 부르는 쪽이 물러설 길을 가집니다.
  }
  return out;
}

/**
 * 샤드에 나뉜 표의 전체 행 수입니다.
 *
 * `play_by_play` 는 D1 네 개에 나뉘어 있어 한 DB 를 세면 1/4 만 나옵니다.
 * 화면이 "270만 행"이라고 말해야 하는데 "70만 행"이 보이면 사용자는
 * 데이터가 사라진 줄 압니다.
 *
 * 각 샤드의 메타 표에서 읽으므로 `COUNT(*)` 를 돌지 않습니다. 하나라도
 * 값을 못 얻으면 합계가 틀리므로 null 을 돌려줍니다. **틀린 숫자보다
 * 빈칸이 낫습니다.**
 */
export async function shardedCountOf(env, shards, table) {
  const dbs = shards.map((s) => env[s.binding]).filter(Boolean);
  if (dbs.length !== shards.length) return null;
  const parts = await Promise.all(dbs.map((db) => countOf(db, table)));
  if (parts.some((n) => typeof n !== 'number')) return null;
  return parts.reduce((a, b) => a + b, 0);
}
