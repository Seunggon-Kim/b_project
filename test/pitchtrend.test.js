import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  pitchTrend, PITCH_TREND_SQL, PITCH_TREND_JSON_SQL, PITCH_TREND_VALUES_SQL, TREND_KEYS,
  shapeTrendRows, shapeTrendValues, trendFromJson,
} from '../src/routes/pitchTrend.js';
import { regularSeasonSql } from '../src/lib/gametype.js';

function fakeDb(handler) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() { calls.push({ sql, params: this.params }); return { results: handler(sql, this.params) || [] }; },
        async first() { calls.push({ sql, params: this.params }); return (handler(sql, this.params) || [])[0] || null; },
      };
    },
  };
}

const req = (path) => new Request(`https://x.test${path}`);
const PLAYER = { player_id: '65933' };

// 같은 행을 보통 질의 객체와 JSON 배열 글자로 적습니다.
// 선구 개수(끝 14개)는 0 으로 채웁니다.
const PDZ = { pd_n: 0, sw: 0, wh: 0, ct: 0, cs: 0, z_n: 0, o_n: 0, z_sw: 0, o_sw: 0, z_ct: 0, o_ct: 0, edge_n: 0, fp_n: 0, fp_str: 0 };
const OBJ = { ...PDZ, season: 2026, pitch_type: '직구', bat_side: 'R', cnt: 'even', n: 2, pa: 1, ab: 1, h: 1, b1: 1, b2: 0, b3: 0, hr: 0, bbe: 1, bb: 0, so: 0, spd_sum: 290.5, spd_n: 2, pfx_x_sum: -1.25, pfx_z_sum: 20, pfx_n: 2, px_sum: 0, pz_sum: 5.5, loc_n: 2 };
const OBJ2 = { ...OBJ, bat_side: null, cnt: 'full', n: 3 };
const JSON_TEXT = [OBJ, OBJ2].map((o) => JSON.stringify(TREND_KEYS.map((k) => o[k]))).join(',');

// --- 질의 ---

test('정규시즌·2016 이후 한 투수의 공을 시즌·구종·타자 손·카운트로 묶습니다', () => {
  assert.ok(PITCH_TREND_SQL.includes(regularSeasonSql('pbp')));
  assert.match(PITCH_TREND_SQL, /WHERE pbp\.pitcher_ID = \? AND pbp\.game_date >= \? AND pbp\.game_date < \?/);
  assert.match(PITCH_TREND_SQL, /GROUP BY season, pbp\.pitch_type, bat_side, cnt/);
  assert.match(PITCH_TREND_SQL, /CAST\(FLOOR\(pbp\.game_date \/ 10000\) AS SIGNED\) AS season/);
  assert.match(PITCH_TREND_SQL, /pitch_type NOT IN \('', '-', 'null'\)/);
  // px 가 없는 공도 셉니다(구사율 API 와 같은 공).
  const where = PITCH_TREND_SQL.slice(PITCH_TREND_SQL.indexOf('FROM play_by_play'));
  assert.doesNotMatch(where, /px IS NOT NULL/);
});

test('카운트는 볼 3·스트라이크 2 로 자른 뒤 full·ahead·behind·even 입니다', () => {
  assert.match(PITCH_TREND_SQL, /LEAST\(pbp\.balls, 3\) = 3 AND LEAST\(pbp\.strikes, 2\) = 2 THEN 'full'/);
  assert.match(PITCH_TREND_SQL, /LEAST\(pbp\.strikes, 2\) > LEAST\(pbp\.balls, 3\) THEN 'ahead'/);
  assert.match(PITCH_TREND_SQL, /LEAST\(pbp\.balls, 3\) > LEAST\(pbp\.strikes, 2\) THEN 'behind'/);
  assert.match(PITCH_TREND_SQL, /ELSE 'even'/);
});

test('타석 결과 분류: 안타 넷, 볼넷, 삼진, 타수·타구에서 뺄 것', () => {
  for (const v of ['안타', '내야안타', '번트 안타', '2루타', '3루타', '홈런',
    '볼넷', '고의4구', '자동 고의4구', '삼진', '낫아웃 출루', '낫아웃 다른 주자 수비',
    '몸에 맞는 볼', '희생번트', '희생번트 실책', '희생번트 야수선택', '희생플라이', '희생플라이 실책', '타격방해']) {
    assert.ok(PITCH_TREND_SQL.includes(`'${v}'`), v);
  }
  assert.match(PITCH_TREND_SQL, /pbp\.pa_result IS NOT NULL AND pbp\.pa_result <> ''/);
});

test('구종 가치는 표에서 그 투수의 모든 시즌을 읽습니다', () => {
  assert.match(PITCH_TREND_VALUES_SQL, /FROM pitch_run_value/);
  assert.match(PITCH_TREND_VALUES_SQL, /WHERE pitcher_ID = \?/);
});

// --- 모양 ---

test('rows 는 정한 키 순서와 숫자로 나갑니다', () => {
  const [r] = shapeTrendRows([{
    season: 2026, pitch_type: '직구', bat_side: 'L', cnt: 'ahead', n: '120', pa: 30, ab: 27,
    h: 7, b1: 5, b2: 1, b3: 0, hr: 1, bbe: 20, bb: 2, so: 6,
    spd_sum: 17160.04, spd_n: 120, pfx_x_sum: 980.123, pfx_z_sum: 1820.4, pfx_n: 118,
    px_sum: -12.346, pz_sum: 300.2, loc_n: 118, ...PDZ,
  }]);
  assert.deepEqual(Object.keys(r), ['season', 'pitch_type', 'bat_side', 'cnt', 'n', 'pa', 'ab', 'h',
    'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so', 'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum', 'pfx_n',
    'px_sum', 'pz_sum', 'loc_n', ...Object.keys(PDZ)]);
  assert.equal(r.n, 120);
  assert.equal(r.pfx_x_sum, 980.123);
  assert.equal(r.px_sum, -12.346);
});

test('values 는 시즌·구종마다 L/R 를 합치고 소수 첫째 자리입니다', () => {
  const out = shapeTrendValues([
    { season: 2025, pitch_type: '직구', stands: 'L', n: 10, rv: 1.26 },
    { season: 2026, pitch_type: '직구', stands: 'R', n: 5, rv: -0.04 },
    { season: 2026, pitch_type: '직구', stands: 'L', n: 3, rv: 0.55 },
  ]);
  assert.deepEqual(out, [
    { season: 2025, pitch_type: '직구', n_l: 10, rv_l: 1.3, n_r: 0, rv_r: 0 },
    { season: 2026, pitch_type: '직구', n_l: 3, rv_l: 0.6, n_r: 5, rv_r: 0 },
  ]);
});

// --- 핸들러 ---

test('응답: 2016 부터 올해(KST)까지 묶고, rows·values 를 줍니다', async () => {
  const db = fakeDb((sql) => {
    if (sql.includes('FROM players')) return [PLAYER];
    if (sql.includes('FROM pitch_run_value')) return [{ season: 2026, pitch_type: '직구', stands: 'R', n: 2, rv: 0.5 }];
    if (sql.includes('GROUP_CONCAT')) return [{ n: 1, j: JSON.stringify(TREND_KEYS.map((k) => OBJ[k])) }];
    throw new Error(`예상 밖 질의: ${sql}`);
  });
  const res = await pitchTrend(req('/players/65933/pitch_trend'), { MYSQL: db }, {}, { id: '65933' });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.player_id, '65933');
  assert.equal(body.rows.length, 1);
  assert.deepEqual(body.values, [{ season: 2026, pitch_type: '직구', n_l: 0, rv_l: 0, n_r: 2, rv_r: 0.5 }]);
  assert.deepEqual(body.rows, [OBJ]);
  const trend = db.calls.find((c) => c.sql.includes('GROUP_CONCAT'));
  assert.equal(trend.params[1], 20160000);
  assert.ok(trend.params[2] >= 20270000);
  assert.match(res.headers.get('cache-control'), /s-maxage=86400,/);
});

test('투수가 아니거나 자료가 없으면 빈 rows·values(200)', async () => {
  const db = fakeDb((sql) => {
    if (sql.includes('FROM players')) return [PLAYER];
    if (sql.includes('GROUP_CONCAT')) return [{ n: 0, j: null }];
    return [];
  });
  const res = await pitchTrend(req('/players/65933/pitch_trend'), { MYSQL: db }, {}, { id: '65933' });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { player_id: '65933', rows: [], values: [] });
});

test('없는 선수는 404, DB 오류는 503·no-store', async () => {
  const none = fakeDb(() => []);
  assert.equal((await pitchTrend(req('/players/1/pitch_trend'), { MYSQL: none }, {}, { id: '1' })).status, 404);
  const boom = fakeDb((sql) => { if (sql.includes('GROUP BY season')) throw new Error('x'); return [PLAYER]; });
  const res = await pitchTrend(req('/players/65933/pitch_trend'), { MYSQL: boom }, {}, { id: '65933' });
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
});

test('JSON 한 칸으로 묶어 정해진 순서로 받습니다', () => {
  assert.match(PITCH_TREND_JSON_SQL, /SET_VAR\(group_concat_max_len = \d+\)/);
  assert.match(PITCH_TREND_JSON_SQL, /ORDER BY g\.season, g\.pitch_type, g\.bat_side, g\.cnt SEPARATOR ','/);
  assert.ok(PITCH_TREND_JSON_SQL.includes(PITCH_TREND_SQL.split('ORDER BY')[0].trim()));
});

test('JSON 으로 받은 행과 보통 질의 행이 같습니다', () => {
  assert.deepEqual(trendFromJson({ n: 2, j: JSON_TEXT }), shapeTrendRows([OBJ, OBJ2]));
  assert.deepEqual(trendFromJson({ n: 2, j: JSON_TEXT })[1].bat_side, null);
});

test('trendFromJson: 없으면 빈 배열, 잘렸거나 수가 다르면 null', () => {
  assert.deepEqual(trendFromJson({ n: 0, j: null }), []);
  assert.equal(trendFromJson({ n: 3, j: JSON_TEXT }), null);
  assert.equal(trendFromJson({ n: 2, j: JSON_TEXT.slice(0, 40) }), null);
  assert.equal(trendFromJson(null), null);
});

test('묶은 글자를 못 풀면 보통 질의로 다시 읽습니다', async () => {
  const db = fakeDb((sql) => {
    if (sql.includes('FROM players')) return [PLAYER];
    if (sql.includes('GROUP_CONCAT')) return [{ n: 2, j: JSON_TEXT.slice(0, 40) }];
    if (sql.includes('FROM pitch_run_value')) return [];
    return [OBJ, OBJ2];
  });
  const warn = console.warn;
  const warned = [];
  console.warn = (...a) => warned.push(a);
  try {
    const res = await pitchTrend(req('/players/65933/pitch_trend'), { MYSQL: db }, {}, { id: '65933' });
    assert.deepEqual((await res.json()).rows, shapeTrendRows([OBJ, OBJ2]));
  } finally {
    console.warn = warn;
  }
  assert.equal(warned.length, 1);
});

// --- 선구(Plate Discipline) 개수(2026-10-05) ---

const PD_KEYS = ['pd_n', 'sw', 'wh', 'ct', 'cs', 'z_n', 'o_n', 'z_sw', 'o_sw', 'z_ct', 'o_ct',
  'edge_n', 'fp_n', 'fp_str'];

test('선구 개수 14개를 기존 키 뒤에 붙입니다', () => {
  assert.deepEqual(TREND_KEYS.slice(-PD_KEYS.length), PD_KEYS);
  assert.deepEqual(TREND_KEYS.slice(0, 23), ['season', 'pitch_type', 'bat_side', 'cnt', 'n', 'pa', 'ab', 'h',
    'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so', 'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum', 'pfx_n',
    'px_sum', 'pz_sum', 'loc_n']);
  for (const k of PD_KEYS) assert.match(PITCH_TREND_SQL, new RegExp(`AS ${k},?\n`), k);
});

test('선구 분류: 스윙·헛스윙·컨택·루킹·볼, 그 밖의 결과는 빼고 셉니다', () => {
  const sql = PITCH_TREND_SQL;
  for (const v of ['타격', '파울', '헛스윙', '번트파울', '번트헛스윙', '스트라이크', '볼']) {
    assert.ok(sql.includes(`'${v}'`), v);
  }
  // 고의 볼·피치클락 위반은 어느 묶음에도 없습니다.
  assert.ok(!sql.includes("'고의 볼'"));
});

test('존: 폭 10/12 ft, 높이는 공의 sz(없거나 뒤집히면 3.5·1.5), 엣지는 0.67 <= r < 1.33', () => {
  const sql = PITCH_TREND_SQL;
  assert.match(sql, /ABS\(pbp\.px\) <= 10e0 \/ 12e0/);
  assert.match(sql, /pbp\.sz_top > pbp\.sz_bot THEN pbp\.sz_top ELSE 3\.5e0 END/);
  assert.match(sql, /pbp\.sz_top > pbp\.sz_bot THEN pbp\.sz_bot ELSE 1\.5e0 END/);
  assert.match(sql, /GREATEST\(ABS\(pbp\.px\) \/ \(10e0 \/ 12e0\)/);
  assert.match(sql, />= 0\.67e0 AND .* < 1\.33e0/);
});

test('초구는 던지기 전 0-0, 초구 스트라이크는 그중 볼이 아닌 공입니다', () => {
  assert.match(PITCH_TREND_SQL, /pbp\.balls = 0 AND pbp\.strikes = 0/);
});

test('JSON 길과 보통 길이 선구 키까지 같은 값을 냅니다', () => {
  const o = { ...OBJ, pd_n: 2, sw: 1, wh: 0, ct: 1, cs: 1, z_n: 1, o_n: 1, z_sw: 1, o_sw: 0, z_ct: 1, o_ct: 0, edge_n: 1, fp_n: 1, fp_str: 1 };
  const text = JSON.stringify(TREND_KEYS.map((k) => o[k]));
  assert.deepEqual(trendFromJson({ n: 1, j: text }), shapeTrendRows([o]));
  assert.equal(trendFromJson({ n: 1, j: text })[0].fp_str, 1);
});
