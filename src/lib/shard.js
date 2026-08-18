// 시즌으로 D1 을 고릅니다.
//
// `play_by_play` 한 표가 D1 한 DB 한도(500MB)를 넘습니다. 12시즌이면 약
// 1.5GB 입니다. 표를 쪼갤 수는 없으니 DB 를 나눕니다.
//
// **배정표 정본은 `migration/shard_plan.json` 입니다.** 아래 SHARDS 는
// 사본이고 `test/shard.test.js` 가 두 값이 같은지 강제합니다. 한쪽만
// 고치면 테스트가 실패합니다. 적재 스크립트도 같은 JSON 을 읽습니다.
//
// Worker 에서 JSON 을 직접 import 하지 않는 이유는, 번들러와 node:test 가
// import 속성을 다르게 다뤄 한쪽에서만 깨지기 때문입니다.

export const SHARDS = [
  { binding: 'DB_2015_2017', seasons: [2015, 2016, 2017] },
  { binding: 'DB_2018_2020', seasons: [2018, 2019, 2020] },
  { binding: 'DB_2021_2023', seasons: [2021, 2022, 2023] },
  { binding: 'DB_2024_2026', seasons: [2024, 2025, 2026] },
];

/** 배정표에 있는 시즌 전부를 오름차순으로 돌려줍니다. */
export function allSeasons() {
  return SHARDS.flatMap((s) => s.seasons).sort((a, b) => a - b);
}

/**
 * 시즌 하나가 든 D1 바인딩입니다. 배정에 없는 시즌이면 null 입니다.
 *
 * **null 을 조용히 넘기지 마십시오.** 없는 시즌을 물으면 빈 결과가
 * 나오는데, 그것을 "경기가 없었다"로 보이면 사용자는 데이터가 사라진
 * 줄 모릅니다. 부르는 쪽에서 404 나 명시적 오류로 드러내십시오.
 */
export function shardOf(env, season) {
  const n = Number(season);
  if (!Number.isFinite(n)) return null;
  for (const s of SHARDS) {
    if (s.seasons.includes(n)) return env[s.binding] || null;
  }
  return null;
}

/**
 * 시즌 목록을 담당 DB 별로 묶습니다.
 *
 * **필요 없는 DB 에는 묻지 않기 위해서입니다.** 2019년만 보는 요청에
 * 네 DB 를 다 두드리면 쿼리도 읽기도 네 배가 됩니다. Worker 호출당
 * D1 쿼리 한도가 50개라 이게 곧 한도 문제가 됩니다.
 *
 * 돌려주는 순서는 시즌 오름차순입니다. 결과를 이 순서로 이어붙이면
 * 나누기 전 한 표였을 때와 같은 순서가 됩니다.
 */
export function groupBySeason(env, seasons) {
  const wanted = [...new Set((seasons || []).map(Number))]
    .filter(Number.isFinite)
    .sort((a, b) => a - b);

  const groups = [];
  for (const s of SHARDS) {
    const mine = wanted.filter((y) => s.seasons.includes(y));
    if (!mine.length) continue;
    const db = env[s.binding];
    // 바인딩이 없으면 조용히 건너뛰지 않습니다. wrangler.toml 을
    // 빠뜨린 것이고, 그대로 두면 그 시즌만 결과에서 사라집니다.
    if (!db) {
      throw new Error(`D1 바인딩이 없습니다: ${s.binding}`);
    }
    groups.push({ binding: s.binding, db, seasons: mine });
  }
  return groups;
}

/**
 * 관련 DB 에만 질의하고 결과를 시즌 순으로 이어붙입니다.
 *
 * fn(db, seasons) 은 배열을 돌려줘야 합니다.
 */
export async function fanOut(env, seasons, fn) {
  const groups = groupBySeason(env, seasons);
  // 순차가 아니라 동시에 부릅니다. DB 4개를 줄 세우면 응답이 네 배
  // 느려집니다. 서로 다른 DB 라 순서가 결과에 영향을 주지 않습니다.
  const parts = await Promise.all(groups.map((g) => fn(g.db, g.seasons)));
  return parts.flat();
}

/**
 * 배정된 시즌인지 봅니다. 라우트가 404 를 낼지 판단할 때 씁니다.
 */
export function hasSeason(season) {
  const n = Number(season);
  return SHARDS.some((s) => s.seasons.includes(n));
}
