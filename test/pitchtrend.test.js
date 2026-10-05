import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  pitchTrend, PITCH_TREND_SQL, PITCH_TREND_VALUES_SQL, shapeTrendRows, shapeTrendValues,
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
    spd_sum: 17160.04, spd_n: 120, pfx_x_sum: 980.1234, pfx_z_sum: 1820.4, pfx_n: 118,
    px_sum: -12.3456, pz_sum: 300.2, loc_n: 118,
  }]);
  assert.deepEqual(Object.keys(r), ['season', 'pitch_type', 'bat_side', 'cnt', 'n', 'pa', 'ab', 'h',
    'b1', 'b2', 'b3', 'hr', 'bbe', 'bb', 'so', 'spd_sum', 'spd_n', 'pfx_x_sum', 'pfx_z_sum', 'pfx_n',
    'px_sum', 'pz_sum', 'loc_n']);
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
    return [{ season: 2026, pitch_type: '직구', bat_side: 'R', cnt: 'even', n: 2, pa: 1, ab: 1, h: 1, b1: 1, b2: 0, b3: 0, hr: 0, bbe: 1, bb: 0, so: 0, spd_sum: 290, spd_n: 2, pfx_x_sum: 0, pfx_z_sum: 0, pfx_n: 0, px_sum: 0, pz_sum: 0, loc_n: 0 }];
  });
  const res = await pitchTrend(req('/players/65933/pitch_trend'), { MYSQL: db }, {}, { id: '65933' });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.player_id, '65933');
  assert.equal(body.rows.length, 1);
  assert.deepEqual(body.values, [{ season: 2026, pitch_type: '직구', n_l: 0, rv_l: 0, n_r: 2, rv_r: 0.5 }]);
  const trend = db.calls.find((c) => c.sql.includes('GROUP BY season'));
  assert.equal(trend.params[1], 20160000);
  assert.ok(trend.params[2] >= 20270000);
  assert.match(res.headers.get('cache-control'), /s-maxage=86400,/);
});

test('투수가 아니거나 자료가 없으면 빈 rows·values(200)', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER] : []));
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
