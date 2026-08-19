// 데이터 탐색기에서 `play_by_play` 를 한 표처럼 보이게 합니다.
//
// 이 표는 D1 네 개에 시즌별로 나뉘어 있습니다. 화면은 그대로 두어야
// 합니다. 사용자에게는 여전히 표 하나이고, 270만 행이 이어져 보여야
// 합니다.
//
// 행이 나오는 순서입니다.
//
//   - 샤드는 시즌 오름차순으로 늘어놓습니다.
//   - 샤드 안에서는 `pbp_id` 오름차순입니다(INTEGER PRIMARY KEY 라
//     rowid 와 같아, ORDER BY 없이 읽어도 이 순서입니다).
//
// **`pbp_id` 오름차순은 날짜 순이 아닙니다.** 2025·2026 을 먼저 모으고
// 2015~2024 를 나중에 백필해서, `pbp_id` 1~405,416 이 2025·2026 입니다.
// 그래서 마지막 샤드(2024~2026) 안에서는 2025, 2026, 2024 순으로 나옵니다.
//
// 날짜 순으로 맞추려면 `ORDER BY game_date` 가 필요한데, `game_date` 에는
// 인덱스가 없어 페이지를 넘길 때마다 샤드 하나(약 70만 행)를 통째로
// 정렬해야 합니다. 인덱스를 새로 만들면 샤드마다 60만 건 넘는 쓰기와
// 50MB 안팎의 용량이 더 듭니다. 데이터 탐색기는 표를 있는 그대로 보여
// 주는 도구이고 원본도 `ORDER BY` 가 없었으므로, 순서를 바꾸지 않고
// 이대로 둡니다.
//
// 중요한 것은 빠지거나 겹치는 행이 없다는 점입니다. 이건
// `migration/verify_shard_vs_local.py` 가 로컬 단일 표와 대조해
// 확인합니다(offset 70만·100만·210만 등 샤드 경계 포함).

import { SHARDS } from './shard.js';
import { countOf } from './counts.js';

/** 샤드에 나뉘어 있는 표 이름입니다. */
export const SHARDED_TABLES = new Set(['play_by_play']);

export function isSharded(table) {
  return SHARDED_TABLES.has(table);
}

/** 시즌 순으로 늘어놓은 [{binding, db}] 입니다. */
export function shardDbs(env) {
  return SHARDS.map((s) => ({ binding: s.binding, db: env[s.binding] }))
    .filter((x) => x.db);
}

/**
 * 샤드별 행 수를 시즌 순으로 돌려줍니다.
 *
 * 메타 표에서 읽습니다. `COUNT(*)` 는 인덱스로 줄지 않아 270만 행을
 * 그대로 읽습니다(lib/counts.js 주석 참조).
 */
export async function shardCounts(env, table) {
  const parts = shardDbs(env);
  const ns = await Promise.all(parts.map((p) => countOf(p.db, table)));
  return parts.map((p, i) => ({
    ...p, n: typeof ns[i] === 'number' ? ns[i] : 0,
  }));
}

/**
 * 전체를 이어 놓았을 때의 offset·limit 이 어느 샤드의 어디인지 계산합니다.
 *
 * 경계를 걸치면 조각이 여러 개 나옵니다. 순수 함수라 따로 시험합니다.
 */
export function planSlice(counts, offset, limit) {
  const plan = [];
  let skip = Math.max(0, offset);
  let need = Math.max(0, limit);
  for (const c of counts) {
    if (need <= 0) break;
    if (skip >= c.n) {
      // 이 샤드는 통째로 건너뜁니다. **질의하지 않습니다.**
      // 건너뛴 행도 D1 은 읽은 것으로 셉니다.
      skip -= c.n;
      continue;
    }
    const take = Math.min(need, c.n - skip);
    plan.push({ binding: c.binding, db: c.db, offset: skip, limit: take });
    need -= take;
    skip = 0;
  }
  return plan;
}

/**
 * 샤드 경계를 넘어 한 페이지를 읽어 옵니다.
 */
export async function sliceRows(env, table, offset, limit) {
  const counts = await shardCounts(env, table);
  const plan = planSlice(counts, offset, limit);
  const parts = await Promise.all(plan.map(async (p) => {
    const { results } = await p.db
      .prepare(`SELECT * FROM "${table}" LIMIT ? OFFSET ?`)
      .bind(p.limit, p.offset).all();
    return results;
  }));
  return parts.flat();
}

/**
 * 스키마를 읽습니다. 어느 샤드든 같으므로 첫 번째에서 읽습니다.
 */
export async function shardTableInfo(env, table) {
  const parts = shardDbs(env);
  if (!parts.length) return { results: [] };
  return parts[0].db.prepare(`PRAGMA table_info("${table}")`).all();
}
