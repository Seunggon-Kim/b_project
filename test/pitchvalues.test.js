import { test } from 'node:test';
import assert from 'node:assert/strict';

import { pitchValues, shapePitchValues, PITCH_VALUES_SQL } from '../src/routes/pitchValues.js';

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

test('L/R 를 한 줄로 합치고 소수 첫째 자리로 맞춥니다', () => {
  const out = shapePitchValues([
    { pitch_type: '직구', stands: 'L', n: 512, rv: 3.14 },
    { pitch_type: '직구', stands: 'R', n: 940, rv: -1.26 },
    { pitch_type: '커브', stands: 'R', n: 30, rv: 0.04 },
  ]);
  assert.deepEqual(out, [
    { pitch_type: '직구', n_l: 512, rv_l: 3.1, n_r: 940, rv_r: -1.3, n: 1452, rv: 1.9 },
    { pitch_type: '커브', n_l: 0, rv_l: 0, n_r: 30, rv_r: 0, n: 30, rv: 0 },
  ]);
});

test('공이 많은 구종부터, 같으면 이름 순입니다', () => {
  const out = shapePitchValues([
    { pitch_type: '커브', stands: 'R', n: 10, rv: 0 },
    { pitch_type: '슬라이더', stands: 'R', n: 10, rv: 0 },
    { pitch_type: '직구', stands: 'L', n: 50, rv: 0 },
  ]);
  assert.deepEqual(out.map((r) => r.pitch_type), ['직구', '슬라이더', '커브']);
});

test('질의는 표에서 투수·시즌으로 읽기만 합니다', () => {
  assert.match(PITCH_VALUES_SQL, /FROM pitch_run_value/);
  assert.match(PITCH_VALUES_SQL, /WHERE pitcher_ID = \? AND season = \?/);
});

test('응답 모양과 캐시', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER]
    : [{ pitch_type: '직구', stands: 'R', n: 3, rv: 0.25 }]));
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), {
    player_id: '65933', season: 2025,
    rows: [{ pitch_type: '직구', n_l: 0, rv_l: 0, n_r: 3, rv_r: 0.3, n: 3, rv: 0.3 }],
  });
  assert.match(res.headers.get('cache-control'), /s-maxage=/);
});

test('season 형식 오류 400, 2016 전 404, 선수 없음 404', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER] : []));
  const env = { DB: db, DB_BACKEND: 'mysql' };
  assert.equal((await pitchValues(req('/players/65933/pitch_values?season=x'), env, {}, { id: '65933' })).status, 400);
  assert.equal((await pitchValues(req('/players/65933/pitch_values'), env, {}, { id: '65933' })).status, 400);
  assert.equal((await pitchValues(req('/players/65933/pitch_values?season=2015'), env, {}, { id: '65933' })).status, 404);
  const none = fakeDb(() => []);
  assert.equal((await pitchValues(req('/players/1/pitch_values?season=2025'), { DB: none, DB_BACKEND: 'mysql' }, {}, { id: '1' })).status, 404);
});

test('그 시즌 공이 없으면 빈 rows', async () => {
  const db = fakeDb((sql) => (sql.includes('FROM players') ? [PLAYER] : []));
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.deepEqual((await res.json()).rows, []);
});

test('DB 오류는 503·no-store', async () => {
  const db = fakeDb((sql) => { if (sql.includes('pitch_run_value')) throw new Error('boom'); return [PLAYER]; });
  const res = await pitchValues(req('/players/65933/pitch_values?season=2025'), { DB: db, DB_BACKEND: 'mysql' }, {}, { id: '65933' });
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
});
