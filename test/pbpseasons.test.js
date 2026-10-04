import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  PBP_FIRST_SEASON, hasPbpSeason, pbpLastSeason,
  seasonDateRange, seasonsBetween,
} from '../src/lib/pbpseasons.js';

// 마지막 시즌은 한국 날짜의 올해이고 2026 아래로는 내려가지 않습니다.
// 2026 에는 예전 D1 샤드 배정표(2008~2026)와 같아 응답이 바뀌지 않습니다.
test('마지막 시즌은 한국 날짜의 올해이고 2026 이상입니다', () => {
  assert.equal(PBP_FIRST_SEASON, 2008);
  assert.equal(pbpLastSeason('2026-10-05'), 2026);
  assert.equal(pbpLastSeason('2025-12-31'), 2026);
  assert.equal(pbpLastSeason('2027-01-01'), 2027);
  assert.equal(pbpLastSeason('2031-03-20'), 2031);
  // 날짜를 못 읽으면 2026 으로 둡니다(모든 시즌이 사라지지 않게).
  assert.equal(pbpLastSeason('x'), 2026);
});

test('있는 시즌인지 봅니다(문자열 시즌도 받습니다)', () => {
  const today = '2026-10-05';
  assert.equal(hasPbpSeason(2008, today), true);
  assert.equal(hasPbpSeason(2019, today), true);
  assert.equal(hasPbpSeason('2026', today), true);
  assert.equal(hasPbpSeason(' 2026 ', today), true);
  // 2007 이하는 네이버에 PBP 가 없고, 2027 은 아직 안 왔습니다.
  assert.equal(hasPbpSeason(2007, today), false);
  assert.equal(hasPbpSeason(2027, today), false);
  assert.equal(hasPbpSeason('abc', today), false);
  assert.equal(hasPbpSeason(null, today), false);
  assert.equal(hasPbpSeason('', today), false);
  assert.equal(hasPbpSeason(2026.5, today), false);
  // 해가 바뀌면 손대지 않아도 새 시즌을 봅니다.
  assert.equal(hasPbpSeason(2027, '2027-03-08'), true);
});

// --- game_date 로 시즌을 고릅니다 ------------------------------------

test('시즌의 game_date 범위를 만듭니다', () => {
  assert.deepEqual(seasonDateRange(2017), { from: 20170000, to: 20180000 });
  assert.deepEqual(seasonDateRange('2026'), { from: 20260000, to: 20270000 });
  assert.equal(seasonDateRange('x'), null);
});

test('포스트시즌 경기가 범위 안에 들어옵니다', () => {
  // 33331008NCLT02017 은 gameID 앞 4자가 '3333' 이지만
  // game_date 는 20171008 이라 2017 범위에 들어옵니다.
  const r = seasonDateRange(2017);
  for (const gd of [20171008, 20171009, 20170401, 20171130]) {
    assert.ok(gd >= r.from && gd < r.to, String(gd));
  }
  // 옆 시즌으로 새지 않습니다.
  assert.ok(!(20180401 >= r.from && 20180401 < r.to));
});

test('기간이 걸치는 시즌을 모두 찾습니다', () => {
  assert.deepEqual(seasonsBetween(20170401, 20170930), [2017]);
  assert.deepEqual(seasonsBetween(20171001, 20190501), [2017, 2018, 2019]);
  assert.deepEqual(seasonsBetween(20120101, 20140101), [2012, 2013, 2014]);
});

test('play_by_play 가 없는 연도는 기간에서 빠집니다', () => {
  // 2007 이하를 물어도 오류가 아니라 빈 결과입니다. 네이버가 2008
  // 부터만 줍니다.
  assert.deepEqual(seasonsBetween(20050101, 20070101), []);
  assert.deepEqual(seasonsBetween(20070101, 20080501), [2008]);
  assert.deepEqual(seasonsBetween(20261001, 20270501, '2026-10-05'), [2026]);
  assert.deepEqual(seasonsBetween(20261001, 20270501, '2027-04-01'), [2026, 2027]);
});

test('뒤집힌 기간은 빈 목록입니다', () => {
  assert.deepEqual(seasonsBetween(20190501, 20170401), []);
  assert.deepEqual(seasonsBetween('a', 20170401), []);
});
