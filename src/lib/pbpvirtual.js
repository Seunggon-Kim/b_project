// 데이터 탐색기에서 `play_by_play` 를 한 표처럼 보이게 합니다.
//
// 이 표는 D1 네 개에 시즌별로 나뉘어 있습니다. 화면은 그대로 두어야
// 합니다. 사용자에게는 여전히 표 하나이고, 270만 행이 이어져 보여야
// 합니다.
//
// 순서가 원본과 같은 근거입니다.
//
//   - 샤드는 시즌 오름차순으로 늘어놓습니다.
//   - 샤드 안에서는 `pbp_id` 오름차순입니다(INTEGER PRIMARY KEY 라
//     rowid 와 같아, ORDER BY 없이 읽어도 이 순서입니다).
//   - `pbp_id` 오름차순이 `game_date` 순서를 거스르는 지점이 0개임을
//     확인했습니다.
//
// 그래서 샤드를 순서대로 이어붙이면 나누기 전 한 표였을 때와 같습니다.

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
