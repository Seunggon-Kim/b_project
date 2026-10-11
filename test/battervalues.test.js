import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  batterValues, shapeBatterValues, BATTER_VALUES_SQL, BATTER_VALUE_KEYS,
} from '../src/routes/batterValues.js';
import { TREND_KEYS } from '../src/routes/pitchTrend.js';

function fakeDb(handler) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() { calls.push({ sql, params: this.params }); return { results: handler(sql) }; },
      };
    },
  };
}

const req = (q) => new Request(`https://x/stats/batter_values${q}`);

test('선구 키는 pitch_trend 의 같은 이름 키와 같습니다', () => {
  for (const k of BATTER_VALUE_KEYS.filter((k) => !['pa_n', 'rv'].includes(k))) {
    assert.ok(TREND_KEYS.includes(k), k);
  }
  assert.match(BATTER_VALUES_SQL, /FROM batter_run_value\s+WHERE season = \?\s+ORDER BY batter_ID/);
});

test('행은 글자 player_id 다음 정한 순서, rv 는 소수 첫째 자리', () => {
  const [o] = shapeBatterValues([{ batter_ID: 67341, pa_n: '512', n: 2001, rv: -0.04, pd_n: 1990,
    sw: 900, wh: 200, z_n: 900, o_n: 1000, z_sw: 600, o_sw: 300 }]);
  assert.deepEqual(Object.keys(o), ['player_id', ...BATTER_VALUE_KEYS]);
  assert.equal(o.player_id, '67341');
  assert.equal(o.pa_n, 512);
  assert.equal(o.rv, 0);
  assert.equal(shapeBatterValues([{ batter_ID: 1, rv: 12.36 }])[0].rv, 12.4);
});

test('응답: 시즌을 묶어 읽고 캐시를 붙입니다', async () => {
  const db = fakeDb(() => [{ batter_ID: 1, pa_n: 1, n: 3, rv: 1.25, pd_n: 3, sw: 1, wh: 0, z_n: 2, o_n: 1, z_sw: 1, o_sw: 0 }]);
  const res = await batterValues(req('?season=2025'), { MYSQL: db });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.season, 2025);
  assert.equal(body.rows[0].rv, 1.3);
  assert.deepEqual(db.calls[0].params, [2025]);
  assert.match(res.headers.get('cache-control'), /s-maxage=/);
});

test('season 이 없거나 틀리면 400, 2016 전·미수집 시즌은 404, DB 오류는 503', async () => {
  const db = fakeDb(() => []);
  assert.equal((await batterValues(req(''), { MYSQL: db })).status, 400);
  assert.equal((await batterValues(req('?season=26'), { MYSQL: db })).status, 400);
  assert.equal((await batterValues(req('?season=2015'), { MYSQL: db })).status, 404);
  assert.equal((await batterValues(req('?season=2999'), { MYSQL: db })).status, 404);
  const bad = await batterValues(req('?season=2025'), { MYSQL: fakeDb(() => { throw new Error('x'); }) });
  assert.equal(bad.status, 503);
  assert.equal(bad.headers.get('cache-control'), 'no-store');
});
