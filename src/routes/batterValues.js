// 타자별 시즌 가치·선구 합계입니다(2026-10-11).
//
// 선수 분석 타자 화면의 Percentile Rankings 카드가 그 시즌 모든 타자와 비교하려고
// 시즌 하나에 한 번 부릅니다. 매일 data_collection/pitch_run_value.py 가 MySQL
// batter_run_value 표에 미리 계산해 둡니다. 여기서는 읽기만 합니다(Workers 무료 CPU 10ms).
//
//     GET /stats/batter_values?season=2026
//     → { season, rows: [ { player_id, pa_n, n, rv, pd_n, sw, wh, z_n, o_n, z_sw, o_sw } ] }
//
// rv 는 /players/:id/pitch_values 와 같은 공·같은 값을 타자 쪽 부호(득점을 만들면 +)로
// 더한 Batting Run Value 입니다. 선구 개수는 /players/:id/pitch_trend·/stats/plate_discipline
// 의 같은 이름 키와 같은 분류이고, 화면이 Chase%(o_sw ÷ o_n)·Whiff%(wh ÷ sw)를 계산합니다.
// pa_n 은 문자중계로 센 타석이라 공식 타석(/stats/batters)보다 조금 적을 수 있습니다.
// player_id 는 /stats/batters 처럼 글자입니다.
import { json, dbError } from '../lib/respond.js';
import { hasPbpSeason } from '../lib/pbpseasons.js';
import { movementCacheControl } from './movementAvg.js';

export const BATTER_VALUE_FIRST_SEASON = 2016;

export const BATTER_VALUE_KEYS = ['pa_n', 'n', 'rv', 'pd_n', 'sw', 'wh', 'z_n', 'o_n', 'z_sw', 'o_sw'];

export const BATTER_VALUES_SQL = `
  SELECT batter_ID, ${BATTER_VALUE_KEYS.join(', ')}
  FROM batter_run_value
  WHERE season = ?
  ORDER BY batter_ID
`;

function round1(v) {
  const r = Math.round(Number(v) * 10) / 10;
  return Object.is(r, -0) ? 0 : r;
}

/** 표의 행을 응답 행으로 바꿉니다. rv 는 소수 첫째 자리, 나머지는 정수입니다. */
export function shapeBatterValues(rows) {
  return (rows || []).map((r) => {
    const out = { player_id: String(r.batter_ID) };
    for (const k of BATTER_VALUE_KEYS) out[k] = k === 'rv' ? round1(r[k]) : Number(r[k]);
    return out;
  });
}

export async function batterValues(request, env) {
  const raw = new URL(request.url).searchParams.get('season');
  const season = /^\d{4}$/.test(raw || '') ? Number(raw) : null;
  if (season === null) return json({ detail: 'season=YYYY 가 필요합니다' }, 400);
  if (season < BATTER_VALUE_FIRST_SEASON || !hasPbpSeason(season)) {
    return json({ detail: `타자 가치는 ${BATTER_VALUE_FIRST_SEASON}년부터 수집한 시즌까지만 있습니다` }, 404);
  }
  try {
    const { results } = await env.MYSQL.prepare(BATTER_VALUES_SQL).bind(season).all();
    const res = json({ season, rows: shapeBatterValues(results) });
    // 올 시즌은 매일 바뀌어 하루, 지난 시즌은 길게 캐시합니다(pitch_values 와 같음).
    res.headers.set('cache-control', movementCacheControl(season));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
