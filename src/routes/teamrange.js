import { json } from '../lib/respond.js';
import { pyRound } from './leaders.js';

// 기간별 팀 성적입니다. 원본 api/main.py:448-596.
//
// games 와 play_by_play 를 조인해 타석 단위로 세고, 아웃과 실점은 따로
// 합산합니다. 자책점을 가릴 수 없어 ERA 대신 RA/9 를 냅니다.

// --- pa_result 분류 (원본 448-461) ---------------------------------------
//
// 한글 문자열을 한 글자도 바꾸면 안 됩니다. `몸에 맞는 볼` 과 `몸에 맞는 공`
// 처럼 표기가 둘인 것들이 있습니다.

const TR_H1 = new Set(['안타', '내야안타', '번트 안타']);
const TR_D2 = new Set(['2루타']);
const TR_D3 = new Set(['3루타']);
const TR_HR = new Set(['홈런']);
export const TR_HIT = new Set([...TR_H1, ...TR_D2, ...TR_D3, ...TR_HR]);
export const TR_WALK = new Set(
  ['볼넷', '자동 고의4구', '고의4구', '고의 4구', '자동 고의 4구'],
);
const TR_HBP = new Set(['몸에 맞는 볼', '몸에 맞는 공']);
// 투수 탈삼진 크레딧입니다. 낫아웃 출루는 아웃이 아니지만 탈삼진에 셉니다.
const TR_SOK = new Set(['삼진', '낫아웃 출루']);
const TR_OUTP = new Set(['필드 아웃', '포스 아웃', '병살타', '삼중살', '타구맞음 아웃']);
const TR_ROE = new Set(['실책']);
const TR_FC = new Set(['야수 선택']);
const TR_SACB = new Set(['희생번트', '희생번트 야수선택']);
const TR_SACF = new Set(['희생플라이']);
export const TR_AB = new Set([
  ...TR_HIT, '삼진', '낫아웃 출루', ...TR_OUTP, ...TR_ROE, ...TR_FC,
]);

const TOP = '초'; // inning_topbot 이 이 값이면 원정팀 공격입니다.

/** 원본 `_tr_norm_date`(464-466). YYYY-MM-DD 나 YYYYMMDD 를 정수로. */
export function trNormDate(s) {
  const t = String(s === null || s === undefined ? '' : s)
    .trim()
    .split('-')
    .join('')
    .split('/')
    .join('');
  return /^\d{8}$/.test(t) ? Number.parseInt(t, 10) : null;
}

/** 원본 `rnd`(562-563). 값이 없으면 null 입니다. */
function rnd(x, digits) {
  if (x === null || x === undefined) return null;
  const f = 10 ** digits;
  return pyRound(x * f) / f;
}

/** 원본 `blank()`(482-485). 팀 하나의 집계 그릇입니다. */
export function blankTeam(team) {
  return {
    team, G: 0, PA: 0, AB: 0, H: 0, '2B': 0, '3B': 0, HR: 0,
    BB: 0, HBP: 0, SF: 0, SH: 0, SO: 0, R: 0,
    outs: 0, Hd: 0, BBd: 0, SOd: 0, HRd: 0, ABf: 0, Rd: 0,
  };
}

function getTeam(teams, t) {
  if (!teams.has(t)) teams.set(t, blankTeam(t));
  return teams.get(t);
}

/**
 * 원본 512-543 의 타석 단위 집계입니다.
 *
 * `inning_topbot` 이 `초` 면 원정팀 공격이라 타자는 away, 투수는 home 입니다.
 * 접미사 d 가 붙은 항목(Hd, BBd 등)은 그 팀이 **내준** 수치입니다.
 */
export function accumulatePa(teams, rows) {
  for (const row of rows) {
    const tb = row.inning_topbot;
    const res = row.pa_result;
    const bat = tb === TOP ? row.away_team_id : row.home_team_id;
    const pit = tb === TOP ? row.home_team_id : row.away_team_id;
    const b = getTeam(teams, bat);
    const pp = getTeam(teams, pit);

    b.PA += 1;
    if (TR_AB.has(res)) {
      b.AB += 1;
      pp.ABf += 1;
    }
    if (TR_HIT.has(res)) {
      b.H += 1;
      pp.Hd += 1;
      if (TR_D2.has(res)) b['2B'] += 1;
      else if (TR_D3.has(res)) b['3B'] += 1;
      else if (TR_HR.has(res)) {
        b.HR += 1;
        pp.HRd += 1;
      }
    }
    if (TR_WALK.has(res)) {
      b.BB += 1;
      pp.BBd += 1;
    }
    if (TR_HBP.has(res)) b.HBP += 1;
    if (TR_SACF.has(res)) b.SF += 1;
    if (TR_SACB.has(res)) b.SH += 1;
    if (TR_SOK.has(res)) {
      b.SO += 1;
      pp.SOd += 1;
    }
  }
  return teams;
}

/** 원본 586 의 이닝 표기입니다. `12 1/3` 처럼 씁니다. */
export function ipText(outs) {
  const whole = Math.floor(outs / 3);
  return outs % 3 ? `${whole} ${outs % 3}/3` : `${whole}`;
}

/** 원본 565-592 의 파생 지표 계산과 정렬입니다. */
export function buildTeamRange(teams) {
  const batting = [];
  const pitching = [];

  for (const d of teams.values()) {
    const AB = d.AB;
    const H = d.H;
    const TB = H + d['2B'] + 2 * d['3B'] + 3 * d.HR;
    const obpden = AB + d.BB + d.HBP + d.SF;
    const avg = AB ? H / AB : 0;
    const obp = obpden ? (H + d.BB + d.HBP) / obpden : 0;
    const slg = AB ? TB / AB : 0;

    batting.push({
      team: d.team, G: d.G, PA: d.PA, AB, R: d.R, H,
      '2B': d['2B'], '3B': d['3B'], HR: d.HR, BB: d.BB, HBP: d.HBP,
      SO: d.SO, SH: d.SH, SF: d.SF, TB,
      AVG: rnd(avg, 3), OBP: rnd(obp, 3), SLG: rnd(slg, 3),
      OPS: rnd(obp + slg, 3),
    });

    const outs = d.outs;
    pitching.push({
      team: d.team, G: d.G, IP_outs: outs, IP: rnd(outs / 3, 1),
      IP_text: ipText(outs),
      H: d.Hd, R: d.Rd, BB: d.BBd, SO: d.SOd, HR: d.HRd,
      AB_against: d.ABf,
      WHIP: rnd(outs ? ((d.Hd + d.BBd) * 3) / outs : 0, 3),
      RA9: rnd(outs ? (d.Rd * 27) / outs : 0, 2),
      K9: rnd(outs ? (d.SOd * 27) / outs : 0, 2),
      BB9: rnd(outs ? (d.BBd * 27) / outs : 0, 2),
      AVG_against: rnd(d.ABf ? d.Hd / d.ABf : 0, 3),
    });
  }

  // 원본: batting.sort(key=lambda x: (x["OPS"] is None, -(x["OPS"] or 0)))
  // null 을 뒤로 보내고 OPS 내림차순입니다.
  batting.sort((a, b) => {
    const an = a.OPS === null ? 1 : 0;
    const bn = b.OPS === null ? 1 : 0;
    if (an !== bn) return an - bn;
    return (b.OPS || 0) - (a.OPS || 0);
  });

  // 원본: pitching.sort(key=lambda x: (x["IP_outs"] == 0, x["RA9"] or 9e9))
  // 등판이 없는 팀을 뒤로 보내고 RA9 오름차순입니다.
  pitching.sort((a, b) => {
    const az = a.IP_outs === 0 ? 1 : 0;
    const bz = b.IP_outs === 0 ? 1 : 0;
    if (az !== bz) return az - bz;
    const ar = a.RA9 === null ? 9e9 : a.RA9;
    const br = b.RA9 === null ? 9e9 : b.RA9;
    return ar - br;
  });

  return { batting, pitching };
}

const NOTE = '가용 PBP 이벤트 기준 집계입니다. KBO 공식 누적과 정의 차이로 '
  + '미세한 차이가 있을 수 있습니다. 투구는 자책점 구분이 어려워 ERA 대신 '
  + 'RA/9(실점 기준)를 제공합니다.';

/** 원본 api/main.py:469-596 입니다. */
export async function statsTeamRange(request, env) {
  const url = new URL(request.url);
  const startRaw = url.searchParams.get('start');
  const endRaw = url.searchParams.get('end');

  let s = trNormDate(startRaw);
  let e = trNormDate(endRaw);
  if (!s || !e) {
    return json({ detail: 'start/end must be YYYY-MM-DD or YYYYMMDD' }, 400);
  }
  if (s > e) {
    const t = s;
    s = e;
    e = t;
  }

  const db = env.DB;
  const teams = new Map();

  // 경기 수와 날짜 경계
  const { results: gameRows } = await db.prepare(
    'SELECT game_id, home_team_id, away_team_id, game_date FROM games '
    + "WHERE game_date>=? AND game_date<=? AND game_type='정규시즌'",
  ).bind(s, e).all();

  let dmin = null;
  let dmax = null;
  for (const row of gameRows) {
    getTeam(teams, row.home_team_id).G += 1;
    getTeam(teams, row.away_team_id).G += 1;
    const gd = row.game_date;
    if (dmin === null || gd < dmin) dmin = gd;
    if (dmax === null || gd > dmax) dmax = gd;
  }

  // 타석 단위 집계
  const { results: paRows } = await db.prepare(
    'SELECT p.inning_topbot, p.pa_result, gm.home_team_id, gm.away_team_id '
    + 'FROM play_by_play p JOIN games gm ON gm.game_id = p.gameID '
    + "WHERE gm.game_date>=? AND gm.game_date<=? AND gm.game_type='정규시즌' "
    + "AND p.pa_result IS NOT NULL AND p.pa_result<>''",
  ).bind(s, e).all();
  accumulatePa(teams, paRows);

  // 아웃과 실점. 삼진 아웃은 outs_on_play 에 잡히지 않아 따로 셉니다.
  const { results: sumRows } = await db.prepare(
    'SELECT p.inning_topbot, gm.home_team_id, gm.away_team_id, '
    + 'SUM(p.outs_on_play) AS oop, SUM(p.runs_scored) AS runs, '
    + "SUM(CASE WHEN p.pa_result='삼진' THEN 1 ELSE 0 END) AS ko "
    + 'FROM play_by_play p JOIN games gm ON gm.game_id = p.gameID '
    + "WHERE gm.game_date>=? AND gm.game_date<=? AND gm.game_type='정규시즌' "
    + 'GROUP BY p.inning_topbot, gm.home_team_id, gm.away_team_id',
  ).bind(s, e).all();

  for (const row of sumRows) {
    const bat = row.inning_topbot === TOP ? row.away_team_id : row.home_team_id;
    const pit = row.inning_topbot === TOP ? row.home_team_id : row.away_team_id;
    getTeam(teams, bat).R += row.runs || 0;
    const pp = getTeam(teams, pit);
    pp.outs += (row.oop || 0) + (row.ko || 0);
    pp.Rd += row.runs || 0;
  }

  const { batting, pitching } = buildTeamRange(teams);

  // start·end 는 받은 원문을 그대로 돌려줍니다. 정규화한 값이 아닙니다.
  return json({
    start: startRaw,
    end: endRaw,
    date_min: dmin,
    date_max: dmax,
    games: gameRows.length,
    batting,
    pitching,
    note: NOTE,
  });
}
