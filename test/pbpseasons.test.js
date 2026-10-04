import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  PBP_FIRST_SEASON, PBP_LAST_SEASON, PBP_SEASONS, hasPbpSeason,
  seasonDateRange, seasonsBetween,
} from '../src/lib/pbpseasons.js';

// play_by_play 가 있는 시즌입니다. 예전 D1 샤드 배정표의 시즌 목록
// (2008~2026)과 같아야 응답이 바뀌지 않습니다.
test('시즌 목록은 2008~2026 이고 빠지거나 겹치는 해가 없습니다', () => {
  assert.equal(PBP_FIRST_SEASON, 2008);
  assert.equal(PBP_LAST_SEASON, 2026);
  assert.equal(PBP_SEASONS.length, 19);
  for (let i = 1; i < PBP_SEASONS.length; i += 1) {
    assert.equal(PBP_SEASONS[i], PBP_SEASONS[i - 1] + 1);
  }
  assert.ok(Object.isFrozen(PBP_SEASONS));
});

test('있는 시즌인지 봅니다(문자열 시즌도 받습니다)', () => {
  assert.equal(hasPbpSeason(2008), true);
  assert.equal(hasPbpSeason(2019), true);
  assert.equal(hasPbpSeason('2026'), true);
  // 2007 이하는 네이버에 PBP 가 없고, 2027 은 아직 안 왔습니다.
  assert.equal(hasPbpSeason(2007), false);
  assert.equal(hasPbpSeason(2027), false);
  assert.equal(hasPbpSeason('abc'), false);
  assert.equal(hasPbpSeason(null), false);
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
  assert.deepEqual(seasonsBetween(20261001, 20270501), [2026]);
});

test('뒤집힌 기간은 빈 목록입니다', () => {
  assert.deepEqual(seasonsBetween(20190501, 20170401), []);
  assert.deepEqual(seasonsBetween('a', 20170401), []);
});
