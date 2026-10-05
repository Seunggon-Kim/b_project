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
// wOBA 분모의 SF 입니다. KBO 공식 기록 sacrifice_fly 합과 맞습니다(2019 505 = 501 + 실책 4).
const SF = ['희생플라이', '희생플라이 실책'];
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

// 던지기 전 볼카운트 12가지('0-0' ~ '3-2'). cnt 와 같은 자르기를 씁니다(2026-10-05).
const BC = 'CASE WHEN pbp.balls IS NULL OR pbp.strikes IS NULL THEN NULL '
  + `ELSE CONCAT(${B}, '-', ${S}) END`;

const PFX = 'pbp.pfx_x IS NOT NULL AND pbp.pfx_z IS NOT NULL';
const LOC = 'pbp.px IS NOT NULL AND pbp.pz IS NOT NULL';

// 선구(Plate Discipline) 개수입니다(2026-10-05). 화면이 비율을 계산합니다.
// 공 결과 분류(운영 2016~ 정규시즌 7가지 모두 덮음). 그 밖의 결과(고의 볼,
// 피치클락 위반, 빈 값)는 어느 개수에도 넣지 않습니다. 번트 시도도 스윙입니다(Savant).
const SWING = ['타격', '파울', '헛스윙', '번트파울', '번트헛스윙'];
const WHIFF = ['헛스윙', '번트헛스윙'];
const CONTACT = ['타격', '파울', '번트파울'];
const LOOK = ['스트라이크'];
const BALL = ['볼'];
const res = (xs) => `pbp.pitch_result IN (${list(xs)})`;
const PD = res([...SWING, ...LOOK, ...BALL]);
const SW = res(SWING);
const CT = res(CONTACT);

// 존은 투구 분포 화면(arsenal gameZone·attackZone)과 같은 규칙입니다. 폭은
// 홈플레이트 17인치 + 공 반지름 = 20인치(10/12 ft). 높이는 그 공의 sz_top·sz_bot
// (둘 다 있고 top > bot), 아니면 3.5·1.5 ft. 실수 나눗셈은 e0 로 DOUBLE 로 둡니다
// (MySQL div_precision_increment=4 로 DECIMAL 이 잘리지 않게).
const SZ_OK = 'pbp.sz_top IS NOT NULL AND pbp.sz_bot IS NOT NULL AND pbp.sz_top > pbp.sz_bot';
const TOP = `(CASE WHEN ${SZ_OK} THEN pbp.sz_top ELSE 3.5e0 END)`;
const BOT = `(CASE WHEN ${SZ_OK} THEN pbp.sz_bot ELSE 1.5e0 END)`;
const HALF_W = '(10e0 / 12e0)';
const IN_ZONE = `${LOC} AND ABS(pbp.px) <= 10e0 / 12e0 AND pbp.pz >= ${BOT} AND pbp.pz <= ${TOP}`;
const OUT_ZONE = `${LOC} AND NOT (ABS(pbp.px) <= 10e0 / 12e0 AND pbp.pz >= ${BOT} AND pbp.pz <= ${TOP})`;
// 엣지(Savant Edge%, Tango Shadow): 존 가장자리에서 안쪽·바깥쪽 1/3 띠.
const EDGE_R = `GREATEST(ABS(pbp.px) / ${HALF_W}, ABS(pbp.pz - (${TOP} + ${BOT}) / 2e0) / ((${TOP} - ${BOT}) / 2e0))`;
const EDGE = `${LOC} AND ${EDGE_R} >= 0.67e0 AND ${EDGE_R} < 1.33e0`;
const FIRST = 'pbp.balls = 0 AND pbp.strikes = 0';
// 합은 MySQL 에서 소수 셋째 자리로 맞춥니다(응답을 줄이고 Worker 계산을 없앰).
const sumIf = (cond, col) => `ROUND(COALESCE(SUM(CASE WHEN ${cond} THEN ${col} END), 0), 3)`;

// 묶는 값은 (투수 ID, 첫 시즌 첫날, 올해 다음 해 첫날)입니다.
const groupedSql = (byCount) => `
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
         ${count(LOC)} AS loc_n,
         ${count(PD)} AS pd_n,
         ${count(SW)} AS sw,
         ${count(res(WHIFF))} AS wh,
         ${count(CT)} AS ct,
         ${count(res(LOOK))} AS cs,
         ${count(`${PD} AND ${IN_ZONE}`)} AS z_n,
         ${count(`${PD} AND ${OUT_ZONE}`)} AS o_n,
         ${count(`${SW} AND ${IN_ZONE}`)} AS z_sw,
         ${count(`${SW} AND ${OUT_ZONE}`)} AS o_sw,
         ${count(`${CT} AND ${IN_ZONE}`)} AS z_ct,
         ${count(`${CT} AND ${OUT_ZONE}`)} AS o_ct,
         ${count(`${PD} AND ${EDGE}`)} AS edge_n,
         ${count(`${PD} AND ${FIRST}`)} AS fp_n,
         ${count(`${PD} AND ${FIRST} AND NOT ${res(BALL)}`)} AS fp_str,
         ${count(inPa(HBP))} AS hbp,
         ${count(inPa(SF))} AS sf${byCount ? `,
         ${BC} AS bc` : ''}
  FROM play_by_play pbp
  WHERE pbp.pitcher_ID = ? AND pbp.game_date >= ? AND pbp.game_date < ?
  AND ${regularSeasonSql('pbp')}
  AND pbp.pitch_type IS NOT NULL
  AND pbp.pitch_type NOT IN ('', '-', 'null')
  GROUP BY season, pbp.pitch_type, bat_side, cnt${byCount ? ', bc' : ''}`;

/**
 * 응답 rows 의 키입니다. 질의 열과 JSON 배열도 이 순서입니다.
 * hbp·sf 는 wOBA 용입니다(2026-10-05). `?by=count` 이면 끝에 bc 가 붙습니다.
 */
export const TREND_KEYS = ['season', 'pitch_type', 'bat_side', 'cnt', 'n', 'pa', 'ab', 'h',
  'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so', 'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum',
  'pfx_n', 'px_sum', 'pz_sum', 'loc_n',
  'pd_n', 'sw', 'wh', 'ct', 'cs', 'z_n', 'o_n', 'z_sw', 'o_sw', 'z_ct', 'o_ct',
  'edge_n', 'fp_n', 'fp_str', 'hbp', 'sf'];

/** `?by=count` 의 키입니다. 기본 키 뒤에 bc('0-0' ~ '3-2')가 붙습니다. */
export const TREND_COUNT_KEYS = [...TREND_KEYS, 'bc'];

const orderOf = (byCount) => `season, pitch_type, bat_side, cnt${byCount ? ', bc' : ''}`;

/** 보통 질의(묶은 글자를 못 풀 때 물러서는 길)입니다. */
const plainSql = (byCount) => `${groupedSql(byCount)}
  ORDER BY ${orderOf(byCount)}
`;

// 묶은 결과 한 칸의 최대 길이입니다(by=count 로 공이 가장 많은 투수도 20만 바이트 안팎).
const TREND_JSON_MAX = 8 * 1024 * 1024;

/**
 * MySQL 이 묶은 행을 JSON 배열로 이어 글자 한 칸으로 줍니다. 행마다 칸을
 * 해석하면(약 300행 x 23칸) Worker CPU 를 많이 써서, arsenal 처럼 한 번의
 * JSON.parse 로 받습니다. GROUP_CONCAT 의 ORDER BY 는 순서가 보장됩니다.
 */
const jsonSql = (byCount) => `
  SELECT /*+ SET_VAR(group_concat_max_len = ${TREND_JSON_MAX}) */
    COUNT(*) AS n,
    GROUP_CONCAT(JSON_ARRAY(${(byCount ? TREND_COUNT_KEYS : TREND_KEYS).map((k) => `g.${k}`).join(', ')})
                 ORDER BY ${orderOf(byCount).split(', ').map((k) => `g.${k}`).join(', ')} SEPARATOR ',') AS j
  FROM (${groupedSql(byCount)}) AS g
`;

export const PITCH_TREND_SQL = plainSql(false);
export const PITCH_TREND_JSON_SQL = jsonSql(false);
export const PITCH_TREND_COUNT_SQL = plainSql(true);
export const PITCH_TREND_COUNT_JSON_SQL = jsonSql(true);

export const PITCH_TREND_VALUES_SQL = `
  SELECT season, pitch_type, stands, n, rv
  FROM pitch_run_value
  WHERE pitcher_ID = ?
  ORDER BY season, pitch_type, stands
`;

// 공격 존별 투수 가치입니다(2026-10-06). pitch_run_value.py 가 매일 같은 공
// 가치로 계산해 둡니다. 위치 없는 공은 어느 존에도 없어 네 존 합이 values(All)와
// 조금 다를 수 있습니다.
export const PITCH_TREND_ZONES_SQL = `
  SELECT season, zone, n, rv
  FROM pitch_run_value_zone
  WHERE pitcher_ID = ?
`;

const ZONE_ORDER = { heart: 0, shadow: 1, chase: 2, waste: 3 };

/** 존 행을 시즌, heart·shadow·chase·waste 순으로, rv 는 소수 첫째 자리로 냅니다. */
export function shapeTrendZones(rows) {
  return (rows || [])
    .map((r) => ({ season: Number(r.season), zone: r.zone, n: Number(r.n), rv: round(r.rv, 1) }))
    .sort((a, b) => (a.season - b.season) || ((ZONE_ORDER[a.zone] ?? 9) - (ZONE_ORDER[b.zone] ?? 9)));
}

function round(v, d) {
  const k = 10 ** d;
  const r = Math.round(Number(v) * k) / k;
  return Object.is(r, -0) ? 0 : r;
}

// 글자 키입니다. 나머지(season, n 부터)는 숫자입니다(합은 MySQL 이 이미 반올림).
const TEXT_KEYS = new Set(['pitch_type', 'bat_side', 'cnt', 'bc']);

function rowOf(keys, get) {
  const out = {};
  for (let i = 0; i < keys.length; i += 1) {
    const v = get(i);
    out[keys[i]] = TEXT_KEYS.has(keys[i]) ? (v === undefined ? null : v) : Number(v);
  }
  return out;
}

/** 보통 질의의 행(객체)을 응답 행으로 바꿉니다. */
export function shapeTrendRows(rows, keys = TREND_KEYS) {
  return (rows || []).map((r) => rowOf(keys, (i) => r[keys[i]]));
}

/**
 * PITCH_TREND_JSON_SQL 의 한 행(n, j)을 응답 행으로 바꿉니다. 행 수가 다르거나
 * 글자가 JSON 이 아니면(잘렸으면) null 입니다. 부르는 쪽이 보통 질의로 읽습니다.
 */
export function trendFromJson(row, keys = TREND_KEYS) {
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
  return arrs.map((a) => rowOf(keys, (i) => a[i]));
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
  // ?by=count 일 때만 볼카운트 12가지로 나눕니다(행 약 2.6배, CPU 약 2배).
  // 기본 응답은 가볍게 둡니다(Workers 무료 CPU 10ms, evan 2026-10-05).
  const by = new URL(request.url).searchParams.get('by');
  if (by !== null && by !== 'count') {
    return json({ detail: "by 는 'count' 만 받습니다" }, 400);
  }
  const byCount = by === 'count';
  const keys = byCount ? TREND_COUNT_KEYS : TREND_KEYS;
  try {
    const db = env.MYSQL;
    const player = await robustPlayerLookup(db, params.id);
    if (!player) return json({ detail: 'Player not found' }, 404);
    const last = pbpLastSeason();
    const from = seasonDateRange(PITCH_TREND_FIRST_SEASON).from;
    const to = seasonDateRange(last).to;
    const pid = Number(player.player_id);
    const binds = [pid, from, to];
    let rows = trendFromJson(
      await db.prepare(byCount ? PITCH_TREND_COUNT_JSON_SQL : PITCH_TREND_JSON_SQL).bind(...binds).first(),
      keys,
    );
    if (!rows) {
      // 응답은 같고 CPU 만 더 듭니다. tail 에서 보이게 남깁니다.
      console.warn('pitch_trend: GROUP_CONCAT 결과를 못 풀어 보통 질의로 읽습니다', pid);
      rows = shapeTrendRows(
        (await db.prepare(byCount ? PITCH_TREND_COUNT_SQL : PITCH_TREND_SQL).bind(...binds).all()).results,
        keys,
      );
    }
    const values = await db.prepare(PITCH_TREND_VALUES_SQL).bind(pid).all();
    const zones = await db.prepare(PITCH_TREND_ZONES_SQL).bind(pid).all();
    const res = json({
      player_id: params.id,
      rows,
      values: shapeTrendValues(values.results),
      zones: shapeTrendZones(zones.results),
    });
    // 올 시즌 공이 매일 늘어 하루 캐시입니다(movement_avg 의 올해 규칙).
    res.headers.set('cache-control', movementCacheControl(last));
    return res;
  } catch (err) {
    return dbError(err);
  }
}
