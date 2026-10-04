// 투수의 구종 가치입니다(2026-10-04).
//
// 공 하나의 가치 = (던진 뒤 기대 득점 − 던지기 전 기대 득점) + 그 공의 득점,
// 투수 쪽 부호(실점을 막으면 +). 매일 data_collection/pitch_run_value.py 가
// MySQL pitch_run_value 표에 미리 계산해 둡니다. 여기서는 읽기만 합니다
// (Workers 무료 CPU 10ms). 설계: docs/superpowers/specs/2026-10-04-pitch-run-value-design.md
//
//     GET /players/65933/pitch_values?season=2025
//     → { player_id, season, rows: [ { pitch_type, n_l, rv_l, n_r, rv_r, n, rv } ] }
import { json, dbError } from '../lib/respond.js';
import { hasPbpSeason } from '../lib/pbpseasons.js';
import { robustPlayerLookup } from './players.js';
import { movementCacheControl } from './movementAvg.js';

export const PITCH_VALUE_FIRST_SEASON = 2016;

export const PITCH_VALUES_SQL = `
  SELECT pitch_type, stands, n, rv
  FROM pitch_run_value
  WHERE pitcher_ID = ? AND season = ?
`;

function round1(v) {
  const r = Math.round(Number(v) * 10) / 10;
  return Object.is(r, -0) ? 0 : r;
}

/** 구종마다 L/R 를 한 줄로 합칩니다. 공이 많은 구종부터, 같으면 이름 순입니다. */
export function shapePitchValues(rows) {
  const by = new Map();
  for (const r of rows || []) {
    if (!by.has(r.pitch_type)) by.set(r.pitch_type, { n_l: 0, rv_l: 0, n_r: 0, rv_r: 0 });
    const acc = by.get(r.pitch_type);
    if (r.stands === 'L') { acc.n_l += Number(r.n); acc.rv_l += Number(r.rv); }
    else { acc.n_r += Number(r.n); acc.rv_r += Number(r.rv); }
  }
  const out = [...by].map(([pitch_type, a]) => ({
    pitch_type,
    n_l: a.n_l, rv_l: round1(a.rv_l),
    n_r: a.n_r, rv_r: round1(a.rv_r),
    n: a.n_l + a.n_r, rv: round1(a.rv_l + a.rv_r),
  }));
  out.sort((a, b) => (b.n - a.n)
    || (a.pitch_type < b.pitch_type ? -1 : a.pitch_type > b.pitch_type ? 1 : 0));
  return out;
}

export async function pitchValues(request, env, ctx, params) {
  const raw = new URL(request.url).searchParams.get('season');
  const season = /^\d{4}$/.test(raw || '') ? Number(raw) : null;
  if (season === null) return json({ detail: 'season=YYYY 가 필요합니다' }, 400);
  if (season < PITCH_VALUE_FIRST_SEASON || !hasPbpSeason(season)) {
    return json({ detail: `구종 가치는 ${PITCH_VALUE_FIRST_SEASON}년부터 수집한 시즌까지만 있습니다` }, 404);
  }
  try {
    const player = await robustPlayerLookup(env.DB, params.id);
    if (!player) return json({ detail: 'Player not found' }, 404);
    const { results } = await env.DB.prepare(PITCH_VALUES_SQL)
      .bind(Number(player.player_id), season).all();
    const res = json({ player_id: params.id, season, rows: shapePitchValues(results) });
    res.headers.set('cache-control', movementCacheControl(season));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
