import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  movementAvg, shapeMovementRows, movementCacheControl, MOVEMENT_AVG_SQL,
} from '../src/routes/movementAvg.js';
import { regularSeasonSql } from '../src/lib/gametype.js';
import { withCache } from '../src/lib/cachepolicy.js';

// 질의 글자와 묶은 값을 남기는 가짜 DB 입니다.
function fakeDb(rows, { fail = false } = {}) {
  const calls = [];
  return {
    calls,
    prepare(sql) {
      return {
        params: [],
        bind(...p) { this.params = p; return this; },
        async all() {
          calls.push({ sql, params: this.params });
          if (fail) throw new Error('D1_ERROR: boom');
          return { results: rows };
        },
      };
    },
  };
}

function envOf(db) {
  return { DB: db };
}

const req = (qs) => new Request(`https://x.test/stats/movement_avg${qs}`);

// --- 행 모양 ---

test('우/좌 를 R/L 로 바꾸고 소수 첫째 자리로 맞춥니다', () => {
  const out = shapeMovementRows([
    { throws: '우', pitch_type: '직구', n: '63588', pfx_x: -5.0612, pfx_z: 10.4987, speed: 147.13 },
  ]);
  assert.deepEqual(out, [
    { throws: 'R', pitch_type: '직구', n: 63588, pfx_x: -5.1, pfx_z: 10.5, speed: 147.1 },
  ]);
});

test('R 먼저, 같은 손은 공이 많은 순, 같으면 구종 이름 순입니다', () => {
  const out = shapeMovementRows([
    { throws: '좌', pitch_type: '직구', n: 10, pfx_x: 1, pfx_z: 1, speed: 1 },
    { throws: '우', pitch_type: '커브', n: 5, pfx_x: 1, pfx_z: 1, speed: 1 },
    { throws: '우', pitch_type: '직구', n: 20, pfx_x: 1, pfx_z: 1, speed: 1 },
    { throws: '우', pitch_type: '슬라이더', n: 5, pfx_x: 1, pfx_z: 1, speed: 1 },
  ]);
  assert.deepEqual(out.map((r) => `${r.throws}${r.pitch_type}`),
    ['R직구', 'R슬라이더', 'R커브', 'L직구']);
});

test('속도가 모두 비면 speed 는 null 입니다', () => {
  const [r] = shapeMovementRows([
    { throws: '좌', pitch_type: '커브', n: 3, pfx_x: '-3.38', pfx_z: '-4.85', speed: null },
  ]);
  assert.equal(r.speed, null);
  assert.equal(r.pfx_x, -3.4);
});

test('우/좌 가 아닌 손은 버립니다', () => {
  assert.deepEqual(shapeMovementRows([
    { throws: '', pitch_type: '직구', n: 1, pfx_x: 1, pfx_z: 1, speed: 1 },
    { throws: null, pitch_type: '직구', n: 1, pfx_x: 1, pfx_z: 1, speed: 1 },
  ]), []);
});

// --- 질의 ---

test('정규시즌 공·무브먼트 있는 공만 보고 손·구종으로 묶습니다', () => {
  assert.ok(MOVEMENT_AVG_SQL.includes(regularSeasonSql('pbp')));
  assert.match(MOVEMENT_AVG_SQL, /pbp\.pfx_x IS NOT NULL/);
  assert.match(MOVEMENT_AVG_SQL, /pbp\.pfx_z IS NOT NULL/);
  assert.match(MOVEMENT_AVG_SQL, /pitch_type NOT IN \('', '-', 'null'\)/);
  assert.match(MOVEMENT_AVG_SQL, /GROUP BY pbp\.throws, pbp\.pitch_type/);
  // 속도 0·빈 값은 평균에서 뺍니다.
  assert.match(MOVEMENT_AVG_SQL, /CASE WHEN CAST\(pbp\.speed AS DOUBLE\) > 0/);
});

test('시즌 하나의 game_date 범위만 묶습니다', async () => {
  const db = fakeDb([]);
  const res = await movementAvg(req('?season=2019'), envOf(db));
  assert.equal(res.status, 200);
  assert.equal(db.calls.length, 1);
  assert.deepEqual(db.calls[0].params, [20190000, 20200000]);
});

test('묶은 행을 응답 모양으로 돌려줍니다', async () => {
  const db = fakeDb([{ throws: '우', pitch_type: '직구', n: 2, pfx_x: -5, pfx_z: 10, speed: 147 }]);
  const res = await movementAvg(req('?season=2026'), envOf(db));
  assert.deepEqual(await res.json(), {
    season: 2026,
    rows: [{ throws: 'R', pitch_type: '직구', n: 2, pfx_x: -5, pfx_z: 10, speed: 147 }],
  });
});

// --- 입력 검사 ---

test('season 이 없거나 네 자리 숫자가 아니면 400 이고 DB 를 안 읽습니다', async () => {
  const db = fakeDb([]);
  for (const qs of ['', '?season=', '?season=abc', '?season=26', '?season=2026x']) {
    const res = await movementAvg(req(qs), envOf(db));
    assert.equal(res.status, 400, qs);
  }
  assert.equal(db.calls.length, 0);
});

test('2016 전·수집 안 한 시즌은 404 이고 DB 를 안 읽습니다', async () => {
  const db = fakeDb([]);
  for (const s of [2008, 2015, 2027]) {
    const res = await movementAvg(req(`?season=${s}`), envOf(db));
    assert.equal(res.status, 404, String(s));
  }
  assert.equal(db.calls.length, 0);
});

test('DB 오류는 503 이고 캐시하지 않습니다', async () => {
  const res = await movementAvg(req('?season=2026'), envOf(fakeDb([], { fail: true })));
  assert.equal(res.status, 503);
  assert.equal(res.headers.get('cache-control'), 'no-store');
});

// --- 캐시 ---

test('지난 시즌은 엣지 30일, 올해는 하루입니다', () => {
  assert.match(movementCacheControl(2025, '2026-10-04'), /s-maxage=2592000/);
  assert.match(movementCacheControl(2026, '2026-10-04'), /s-maxage=86400,/);
  // 해가 바뀌면 지난 시즌이 됩니다.
  assert.match(movementCacheControl(2026, '2027-01-01'), /s-maxage=2592000/);
  // 브라우저는 다른 경로처럼 1분입니다.
  assert.match(movementCacheControl(2025, '2026-10-04'), /^public, max-age=60,/);
});

test('라우트가 붙인 캐시 수명을 withCache 가 덮지 않습니다', async () => {
  const res = await movementAvg(req('?season=2017'), envOf(fakeDb([])));
  const out = withCache(res, '/stats/movement_avg');
  assert.match(out.headers.get('cache-control'), /s-maxage=2592000/);
});
