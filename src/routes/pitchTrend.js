// 투수의 시즌별 구종 추이입니다(2026-10-05).
//
// 선수 분석 화면의 "시즌별 구종" 선 그래프 카드가 부릅니다. 지표·타자 손·
// 카운트를 화면에서 고르므로, 한 투수의 2016~올해 공을 (시즌, 구종, 타자 손,
// 카운트)로 묶은 합계를 한 번에 주고 화면이 나눕니다. 평균은 화면이 합쳐서
// 나누므로 합과 개수로 줍니다.
//
//     GET /players/65933/pitch_trend
//     → { player_id, rows: [ { season, pitch_type, bat_side, cnt, n, pa, ab, h, ... } ],
//         values: [ { season, pitch_type, n_l, rv_l, n_r, rv_r } ] }
//
// 공 기준은 구사율(/players/:id/usage)과 같습니다. 정규시즌, 구종이 있는 공,
// px 가 없어도 셉니다. values 는 /players/:id/pitch_values 와 같은 값을 모든
// 시즌에 걸쳐 줍니다(카운트별 값은 없음). 집계는 MySQL 이 합니다(CPU 10ms).
import { json, dbError } from '../lib/respond.js';
import { regularSeasonSql } from '../lib/gametype.js';
import { pbpLastSeason, seasonDateRange } from '../lib/pbpseasons.js';
import { robustPlayerLookup } from './players.js';
import { movementCacheControl } from './movementAvg.js';

export const PITCH_TREND_FIRST_SEASON = 2016;

const list = (xs) => xs.map((x) => `'${x}'`).join(', ');

// 타석 결과 분류입니다. 운영 2016~ 정규시즌에 나오는 값 25가지(2026-10-05
// 확인)를 모두 덮습니다. 띄어쓰기만 다른 표기도 함께 둡니다.
const B1 = ['안타', '내야안타', '번트 안타'];
const BB = ['볼넷', '고의4구', '자동 고의4구', '고의 4구', '자동 고의 4구'];
const SO = ['삼진', '낫아웃 출루', '낫아웃 다른 주자 수비'];
const HBP = ['몸에 맞는 볼', '몸에 맞는 공'];
const SAC = ['희생번트', '희생번트 실책', '희생번트 야수선택', '희생플라이', '희생플라이 실책'];
const CI = ['타격방해'];
const HIT = [...B1, '2루타', '3루타', '홈런'];

const PA = "pbp.pa_result IS NOT NULL AND pbp.pa_result <> ''";
const inPa = (xs) => `pbp.pa_result IN (${list(xs)})`;
const count = (cond) => `SUM(CASE WHEN ${cond} THEN 1 ELSE 0 END)`;

// 타자 손은 arsenal 과 같은 규칙입니다(src/routes/players.js ARSENAL_EXPR).
const BAT_SIDE = "CASE pbp.stands WHEN '좌' THEN 'L' WHEN '우' THEN 'R' "
  + "WHEN '양' THEN (CASE pbp.throws WHEN '우' THEN 'L' WHEN '좌' THEN 'R' END) END";

// 던지기 전 카운트. 원천에 드물게 있는 볼 4·스트라이크 3 은 3·2 로 봅니다.
const B = 'LEAST(pbp.balls, 3)';
const S = 'LEAST(pbp.strikes, 2)';
const CNT = 'CASE WHEN pbp.balls IS NULL OR pbp.strikes IS NULL THEN NULL '
  + `WHEN ${B} = 3 AND ${S} = 2 THEN 'full' `
  + `WHEN ${S} > ${B} THEN 'ahead' `
  + `WHEN ${B} > ${S} THEN 'behind' `
  + "ELSE 'even' END";

const PFX = 'pbp.pfx_x IS NOT NULL AND pbp.pfx_z IS NOT NULL';
const LOC = 'pbp.px IS NOT NULL AND pbp.pz IS NOT NULL';
// 합은 MySQL 에서 소수 셋째 자리로 맞춥니다(응답을 줄이고 Worker 계산을 없앰).
const sumIf = (cond, col) => `ROUND(COALESCE(SUM(CASE WHEN ${cond} THEN ${col} END), 0), 3)`;

// 묶는 값은 (투수 ID, 첫 시즌 첫날, 올해 다음 해 첫날)입니다.
const GROUPED_SQL = `
  SELECT CAST(FLOOR(pbp.game_date / 10000) AS SIGNED) AS season,
         pbp.pitch_type AS pitch_type,
         ${BAT_SIDE} AS bat_side,
         ${CNT} AS cnt,
         COUNT(*) AS n,
         ${count(PA)} AS pa,
         ${count(`${PA} AND pbp.pa_result NOT IN (${list([...BB, ...HBP, ...SAC, ...CI])})`)} AS ab,
         ${count(inPa(HIT))} AS h,
         ${count(inPa(B1))} AS b1,
         ${count(inPa(['2루타']))} AS b2,
         ${count(inPa(['3루타']))} AS b3,
         ${count(inPa(['홈런']))} AS hr,
         ${count(`${PA} AND pbp.pa_result NOT IN (${list([...SO, ...BB, ...HBP, ...CI])})`)} AS bbe,
         ${count(inPa(BB))} AS bb,
         ${count(inPa(SO))} AS so,
         ${sumIf('pbp.speed > 0', 'pbp.speed')} AS spd_sum,
         ${count('pbp.speed > 0')} AS spd_n,
         ${sumIf(PFX, 'pbp.pfx_x')} AS pfx_x_sum,
         ${sumIf(PFX, 'pbp.pfx_z')} AS pfx_z_sum,
         ${count(PFX)} AS pfx_n,
         ${sumIf(LOC, 'pbp.px')} AS px_sum,
         ${sumIf(LOC, 'pbp.pz')} AS pz_sum,
         ${count(LOC)} AS loc_n
  FROM play_by_play pbp
  WHERE pbp.pitcher_ID = ? AND pbp.game_date >= ? AND pbp.game_date < ?
  AND ${regularSeasonSql('pbp')}
  AND pbp.pitch_type IS NOT NULL
  AND pbp.pitch_type NOT IN ('', '-', 'null')
  GROUP BY season, pbp.pitch_type, bat_side, cnt`;

/** 응답 rows 의 키입니다. 질의 열과 JSON 배열도 이 순서입니다. */
export const TREND_KEYS = ['season', 'pitch_type', 'bat_side', 'cnt', 'n', 'pa', 'ab', 'h',
  'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so', 'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum',
  'pfx_n', 'px_sum', 'pz_sum', 'loc_n'];

const ORDER = 'season, pitch_type, bat_side, cnt';

/** 보통 질의(묶은 글자를 못 풀 때 물러서는 길)입니다. */
export const PITCH_TREND_SQL = `${GROUPED_SQL}
  ORDER BY ${ORDER}
`;

// 묶은 결과 한 칸의 최대 길이입니다(공이 가장 많은 투수도 10만 바이트 안팎).
const TREND_JSON_MAX = 8 * 1024 * 1024;

/**
 * MySQL 이 묶은 행을 JSON 배열로 이어 글자 한 칸으로 줍니다. 행마다 칸을
 * 해석하면(약 300행 x 23칸) Worker CPU 를 많이 써서, arsenal 처럼 한 번의
 * JSON.parse 로 받습니다. GROUP_CONCAT 의 ORDER BY 는 순서가 보장됩니다.
 */
export const PITCH_TREND_JSON_SQL = `
  SELECT /*+ SET_VAR(group_concat_max_len = ${TREND_JSON_MAX}) */
    COUNT(*) AS n,
    GROUP_CONCAT(JSON_ARRAY(${TREND_KEYS.map((k) => `g.${k}`).join(', ')})
                 ORDER BY ${ORDER.split(', ').map((k) => `g.${k}`).join(', ')} SEPARATOR ',') AS j
  FROM (${GROUPED_SQL}) AS g
`;

export const PITCH_TREND_VALUES_SQL = `
  SELECT season, pitch_type, stands, n, rv
  FROM pitch_run_value
  WHERE pitcher_ID = ?
  ORDER BY season, pitch_type, stands
`;

function round(v, d) {
  const k = 10 ** d;
  const r = Math.round(Number(v) * k) / k;
  return Object.is(r, -0) ? 0 : r;
}

const NUM_FROM = 4; // n 부터 끝까지 숫자입니다(합은 MySQL 이 이미 반올림).

function rowOf(get) {
  const out = {};
  for (let i = 0; i < TREND_KEYS.length; i += 1) {
    const v = get(i);
    out[TREND_KEYS[i]] = i === 0 || i >= NUM_FROM ? Number(v) : (v === undefined ? null : v);
  }
  return out;
}

/** 보통 질의의 행(객체)을 응답 행으로 바꿉니다. */
export function shapeTrendRows(rows) {
  return (rows || []).map((r) => rowOf((i) => r[TREND_KEYS[i]]));
}

/**
 * PITCH_TREND_JSON_SQL 의 한 행(n, j)을 응답 행으로 바꿉니다. 행 수가 다르거나
 * 글자가 JSON 이 아니면(잘렸으면) null 입니다. 부르는 쪽이 보통 질의로 읽습니다.
 */
export function trendFromJson(row) {
  if (!row) return null;
  const n = Number(row.n);
  if (row.j === null || row.j === undefined) return n === 0 ? [] : null;
  if (typeof row.j !== 'string') return null;
  let arrs;
  try {
    arrs = JSON.parse(`[${row.j}]`);
  } catch {
    return null;
  }
  if (arrs.length !== n) return null;
  return arrs.map((a) => rowOf((i) => a[i]));
}

/** 구종 가치 표의 행을 (시즌, 구종)마다 L/R 한 줄로 합칩니다. */
export function shapeTrendValues(rows) {
  const by = new Map();
  for (const r of rows || []) {
    const key = `${r.season}\u0000${r.pitch_type}`;
    if (!by.has(key)) {
      by.set(key, { season: Number(r.season), pitch_type: r.pitch_type, n_l: 0, rv_l: 0, n_r: 0, rv_r: 0 });
    }
    const acc = by.get(key);
    if (r.stands === 'L') { acc.n_l += Number(r.n); acc.rv_l += Number(r.rv); }
    else { acc.n_r += Number(r.n); acc.rv_r += Number(r.rv); }
  }
  return [...by.values()]
    .map((a) => ({ ...a, rv_l: round(a.rv_l, 1), rv_r: round(a.rv_r, 1) }))
    .sort((a, b) => (a.season - b.season)
      || (a.pitch_type < b.pitch_type ? -1 : a.pitch_type > b.pitch_type ? 1 : 0));
}

export async function pitchTrend(request, env, ctx, params) {
  try {
    const db = env.MYSQL;
    const player = await robustPlayerLookup(db, params.id);
    if (!player) return json({ detail: 'Player not found' }, 404);
    const last = pbpLastSeason();
    const from = seasonDateRange(PITCH_TREND_FIRST_SEASON).from;
    const to = seasonDateRange(last).to;
    const pid = Number(player.player_id);
    const binds = [pid, from, to];
    let rows = trendFromJson(await db.prepare(PITCH_TREND_JSON_SQL).bind(...binds).first());
    if (!rows) {
      // 응답은 같고 CPU 만 더 듭니다. tail 에서 보이게 남깁니다.
      console.warn('pitch_trend: GROUP_CONCAT 결과를 못 풀어 보통 질의로 읽습니다', pid);
      rows = shapeTrendRows((await db.prepare(PITCH_TREND_SQL).bind(...binds).all()).results);
    }
    const values = await db.prepare(PITCH_TREND_VALUES_SQL).bind(pid).all();
    const res = json({
      player_id: params.id,
      rows,
      values: shapeTrendValues(values.results),
    });
    // 올 시즌 공이 매일 늘어 하루 캐시입니다(movement_avg 의 올해 규칙).
    res.headers.set('cache-control', movementCacheControl(last));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
