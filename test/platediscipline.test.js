import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  plateDiscipline, shapeDiscipline, PLATE_DISCIPLINE_SQL, DISCIPLINE_KEYS,
} from '../src/routes/plateDiscipline.js';
import { TREND_KEYS } from '../src/routes/pitchTrend.js';

function fakeDb(handler) {
  return {
    prepare(sql) {
      return { bind() { return this; }, async all() { return { results: handler(sql) }; } };
    },
  };
}

test('키는 pitch_trend 의 같은 이름 키와 같습니다', () => {
  for (const k of DISCIPLINE_KEYS) assert.ok(TREND_KEYS.includes(k), k);
  assert.match(PLATE_DISCIPLINE_SQL, /FROM plate_discipline_league/);
  assert.match(PLATE_DISCIPLINE_SQL, /ORDER BY season/);
});

test('행은 season 다음 정한 순서의 정수입니다', () => {
  const r = Object.fromEntries([['season', '2026'], ...DISCIPLINE_KEYS.map((k, i) => [k, String(i)])]);
  const [o] = shapeDiscipline([r]);
  assert.deepEqual(Object.keys(o), ['season', ...DISCIPLINE_KEYS]);
  assert.equal(o.season, 2026);
  assert.equal(o.mb_sw, 16);
});

test('응답과 캐시, DB 오류는 503·no-store', async () => {
  const row = Object.fromEntries([['season', 2025], ...DISCIPLINE_KEYS.map((k) => [k, 1])]);
  const res = await plateDiscipline(new Request('https://x/stats/plate_discipline'), { MYSQL: fakeDb(() => [row]) });
  assert.equal(res.status, 200);
  assert.equal((await res.json()).seasons[0].season, 2025);
  assert.match(res.headers.get('cache-control'), /s-maxage=86400,/);
  const bad = await plateDiscipline(new Request('https://x/stats/plate_discipline'), { MYSQL: fakeDb(() => { throw new Error('x'); }) });
  assert.equal(bad.status, 503);
  assert.equal(bad.headers.get('cache-control'), 'no-store');
});
