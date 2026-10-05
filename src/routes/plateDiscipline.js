// KBO 리그 선구(Plate Discipline) 시즌 합계입니다(2026-10-06).
//
// 선수 분석 화면이 투수 값 옆에 리그 평균을 그립니다. 리그 전체 공(시즌당 약
// 22만 개)을 요청 때 모으면 10시즌에 26초가 걸려, 매일 pitch_run_value.py 가
// plate_discipline_league 표에 시즌 합계를 미리 계산해 둡니다. 여기서는 읽기만
// 합니다(Workers 무료 CPU 10ms). 뜻·분류·존 판정은 /players/:id/pitch_trend 의
// 같은 이름 키와 같고, 화면이 비율을 계산합니다.
//
//     GET /stats/plate_discipline → { seasons: [ { season, n, pd_n, sw, ..., mb_sw } ] }
import { json, dbError } from '../lib/respond.js';
import { pbpLastSeason } from '../lib/pbpseasons.js';
import { movementCacheControl } from './movementAvg.js';

export const DISCIPLINE_KEYS = ['n', 'pd_n', 'sw', 'wh', 'ct', 'cs', 'z_n', 'o_n', 'z_sw',
  'o_sw', 'z_ct', 'o_ct', 'edge_n', 'fp_n', 'fp_str', 'mb_n', 'mb_sw'];

export const PLATE_DISCIPLINE_SQL = `
  SELECT season, ${DISCIPLINE_KEYS.join(', ')}
  FROM plate_discipline_league
  ORDER BY season
`;

/** 표의 행을 응답 행으로 바꿉니다. 키 순서는 season 다음 DISCIPLINE_KEYS 입니다. */
export function shapeDiscipline(rows) {
  return (rows || []).map((r) => {
    const out = { season: Number(r.season) };
    for (const k of DISCIPLINE_KEYS) out[k] = Number(r[k]);
    return out;
  });
}

export async function plateDiscipline(request, env) {
  try {
    const { results } = await env.MYSQL.prepare(PLATE_DISCIPLINE_SQL).all();
    const res = json({ seasons: shapeDiscipline(results) });
    // 올 시즌 줄이 매일 바뀌어 하루 캐시입니다(movement_avg 의 올해 규칙).
    res.headers.set('cache-control', movementCacheControl(pbpLastSeason()));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
