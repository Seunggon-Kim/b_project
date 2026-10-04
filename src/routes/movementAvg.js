// 투수 손별 리그 평균 무브먼트입니다(2026-10-04).
//
// 선수 분석 화면의 무브먼트 카드가 "같은 손 투수 평균"을 함께 그리려고
// 부릅니다. 한 시즌의 정규시즌 공을 투구 손·구종으로 묶어 평균을 냅니다.
//
//     GET /stats/movement_avg?season=2026
//     → { season: 2026, rows: [ { throws: 'R', pitch_type: '직구', n: 63588,
//                                 pfx_x: -5.1, pfx_z: 10.5, speed: 147.1 } ] }
//
// - throws 는 play_by_play.throws('우'/'좌')를 R/L 로 바꾼 값입니다.
// - pfx_x·pfx_z 는 인치, 포수 시점입니다(/players/:id/arsenal 과 같은 값).
// - speed 는 km/h 이고 0·빈 값은 평균에서 뺍니다. 그런 공도 n 에는 듭니다.
// - n 은 무브먼트 값(pfx_x·pfx_z)이 둘 다 있는 공 수입니다.
//
// ## 부하
//
// 요청 때 계산합니다. 한 시즌만 보므로 game_date 범위로 한 해치(2026 약
// 42만 행)만 훑고, 묶은 결과(스무 줄 안팎)만 Worker 로 옵니다. MySQL 실측
// 1.6초입니다(idx_pbp_game_date). 그래서 응답 캐시를 길게 둡니다. 지난
// 시즌은 바뀌지 않으므로 엣지 30일, 올해는 하루입니다. 다만 적재 뒤
// /admin/purge-cache 가 엣지를 통째로 비우므로, 실제로는 하루에 한 번씩
// 다시 계산됩니다.
import { json, dbError } from '../lib/respond.js';
import { regularSeasonSql } from '../lib/gametype.js';
import { hasPbpSeason, seasonDateRange } from '../lib/pbpseasons.js';
import { kstToday } from '../lib/kst.js';

/** 무브먼트(PITCHf/x 추적) 값이 처음 나오는 시즌입니다. 첫 공은 2016-06-14 입니다. */
export const MOVEMENT_FIRST_SEASON = 2016;

// DB 의 투구 손 글자 → 응답 글자입니다. 이 둘 말고는 묶지 않습니다.
const THROWS = { 우: 'R', 좌: 'L' };
const THROWS_ORDER = { R: 0, L: 1 };

// 엣지 캐시 수명(초)입니다. 브라우저는 다른 경로처럼 짧게 둡니다
// (lib/cachepolicy.js 의 BROWSER_TTL 설명 참고).
const PAST_EDGE_TTL = 30 * 86400;
const CURRENT_EDGE_TTL = 86400;
const BROWSER_TTL = 60;
const SWR = 86400;

/**
 * 시즌에 붙일 Cache-Control 입니다. 올해(KST) 이후면 하루, 지난 시즌이면 30일입니다.
 *
 * lib/cachepolicy.js 는 경로만 보고 정해 시즌을 모릅니다. 그래서 라우트가
 * 직접 붙이고, withCache 는 이미 붙은 값을 그대로 둡니다.
 */
export function movementCacheControl(season, today = kstToday()) {
  const thisYear = Number(String(today).slice(0, 4));
  const edge = Number(season) >= thisYear ? CURRENT_EDGE_TTL : PAST_EDGE_TTL;
  return `public, max-age=${BROWSER_TTL}, s-maxage=${edge}, `
    + `stale-while-revalidate=${SWR}`;
}

/** 소수 첫째 자리입니다. 값이 없으면 null 입니다. */
function round1(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? Math.round(n * 10) / 10 : null;
}

/**
 * DB 가 준 묶음 행을 응답 행으로 바꿉니다. 순수 함수라 따로 시험합니다.
 *
 * 순서는 R 먼저, 같은 손 안에서는 공이 많은 구종 먼저, 같으면 구종 이름
 * 순입니다. DB 가 주는 순서는 엔진마다 다를 수 있어 여기서 고정합니다.
 */
export function shapeMovementRows(rows) {
  const out = [];
  for (const r of rows || []) {
    const throws = THROWS[r.throws];
    if (!throws) continue;
    out.push({
      throws,
      pitch_type: r.pitch_type,
      n: Number(r.n),
      pfx_x: round1(r.pfx_x),
      pfx_z: round1(r.pfx_z),
      speed: round1(r.speed),
    });
  }
  out.sort((a, b) => (THROWS_ORDER[a.throws] - THROWS_ORDER[b.throws])
    || (b.n - a.n)
    || (a.pitch_type < b.pitch_type ? -1 : a.pitch_type > b.pitch_type ? 1 : 0));
  return out;
}

// D1 에는 빈 글자('')가 섞여 있어(MySQL 로 옮길 때 NULL 로 바꾼 값)
// IS NOT NULL 만으로는 거르지 못합니다. `pfx_x <> ''` 는 MySQL 에서 ''
// 를 0 으로 읽어 0.0 인 공까지 빼므로, 글자로 바꿔 비교합니다(0.0 은
// MySQL '0'·SQLite '0.0' 이라 남습니다). 속도는 실수로 바꿔 0 보다 큰 것만
// 평균에 넣습니다. SQLite 에서 ''·NULL 을 바꾸면 0·NULL 이라 둘 다 빠집니다.
export const MOVEMENT_AVG_SQL = `
  SELECT pbp.throws AS throws, pbp.pitch_type AS pitch_type,
         COUNT(*) AS n,
         AVG(CAST(pbp.pfx_x AS DOUBLE)) AS pfx_x,
         AVG(CAST(pbp.pfx_z AS DOUBLE)) AS pfx_z,
         AVG(CASE WHEN CAST(pbp.speed AS DOUBLE) > 0
                  THEN CAST(pbp.speed AS DOUBLE) END) AS speed
  FROM play_by_play pbp
  WHERE pbp.game_date >= ? AND pbp.game_date < ?
  AND ${regularSeasonSql('pbp')}
  AND pbp.throws IN ('우', '좌')
  AND pbp.pfx_x IS NOT NULL AND CAST(pbp.pfx_x AS CHAR) <> ''
  AND pbp.pfx_z IS NOT NULL AND CAST(pbp.pfx_z AS CHAR) <> ''
  AND pbp.pitch_type IS NOT NULL
  AND pbp.pitch_type NOT IN ('', '-', 'null')
  GROUP BY pbp.throws, pbp.pitch_type
`;

export async function movementAvg(request, env) {
  const raw = new URL(request.url).searchParams.get('season');
  const season = /^\d{4}$/.test(raw || '') ? Number(raw) : null;
  if (season === null) {
    return json({ detail: 'season=YYYY 가 필요합니다' }, 400);
  }

  // 2016 전에는 무브먼트 값이 없습니다. 빈 rows 를 주면 "평균이 없다"와
  // "데이터가 없는 해"를 화면이 가를 수 없어 404 로 드러냅니다.
  const range = season >= MOVEMENT_FIRST_SEASON && hasPbpSeason(season)
    ? seasonDateRange(season) : null;
  if (!range) {
    return json({
      detail: `무브먼트 평균은 ${MOVEMENT_FIRST_SEASON}년부터 수집한 시즌까지만 있습니다`,
    }, 404);
  }

  try {
    const { results } = await env.DB.prepare(MOVEMENT_AVG_SQL)
      .bind(range.from, range.to).all();
    const res = json({ season, rows: shapeMovementRows(results) });
    res.headers.set('cache-control', movementCacheControl(season));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
