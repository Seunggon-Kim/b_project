import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import {
  SHARDS, allSeasons, shardOf, groupBySeason, fanOut, hasSeason,
} from '../src/lib/shard.js';

const planPath = fileURLToPath(new URL('../migration/shard_plan.json', import.meta.url));
const plan = JSON.parse(readFileSync(planPath, 'utf-8'));

// 배정표가 두 곳에 있습니다. 정본은 JSON 이고 shard.js 는 사본입니다.
// 한쪽만 고치면 적재와 조회가 다른 DB 를 보게 되어, 넣은 데이터가
// 화면에서 사라집니다. 그 사고를 여기서 막습니다.
test('shard.js 표가 shard_plan.json 과 같습니다', () => {
  const fromJson = plan.shards.map((s) => ({
    binding: s.binding, seasons: s.seasons,
  }));
  assert.deepEqual(SHARDS, fromJson);
});

test('시즌이 겹치지 않고 빠지지 않습니다', () => {
  // 한 시즌이 두 DB 에 들어가는 것이 가장 흔한 실수입니다.
  const all = allSeasons();
  assert.equal(new Set(all).size, all.length, '겹치는 시즌이 있습니다');
  // 연속이어야 합니다. 중간이 비면 그 시즌 요청이 조용히 빈 결과가 됩니다.
  for (let i = 1; i < all.length; i += 1) {
    assert.equal(all[i], all[i - 1] + 1, `${all[i - 1]} 다음이 비었습니다`);
  }
});

const env = {
  DB_2015_2017: { tag: 'a' },
  DB_2018_2020: { tag: 'b' },
  DB_2021_2023: { tag: 'c' },
  DB_2024_2026: { tag: 'd' },
};

test('시즌으로 DB 를 고릅니다', () => {
  assert.equal(shardOf(env, 2015).tag, 'a');
  assert.equal(shardOf(env, 2020).tag, 'b');
  assert.equal(shardOf(env, 2023).tag, 'c');
  assert.equal(shardOf(env, 2026).tag, 'd');
});

test('문자열 시즌도 받습니다', () => {
  // 쿼리 파라미터는 항상 문자열로 옵니다.
  assert.equal(shardOf(env, '2019').tag, 'b');
});

test('배정에 없는 시즌은 null 입니다', () => {
  assert.equal(shardOf(env, 2014), null);
  assert.equal(shardOf(env, 2027), null);
  assert.equal(shardOf(env, 'abc'), null);
  assert.equal(hasSeason(2014), false);
  assert.equal(hasSeason(2019), true);
});

test('필요한 DB 에만 묻습니다', () => {
  // 2019 하나만 보는데 네 DB 를 두드리면 읽기가 네 배입니다.
  const g = groupBySeason(env, [2019]);
  assert.equal(g.length, 1);
  assert.equal(g[0].binding, 'DB_2018_2020');
  assert.deepEqual(g[0].seasons, [2019]);
});

test('여러 시즌은 담당 DB 별로 묶입니다', () => {
  const g = groupBySeason(env, [2016, 2017, 2022]);
  assert.equal(g.length, 2);
  assert.deepEqual(g[0].seasons, [2016, 2017]);
  assert.deepEqual(g[1].seasons, [2022]);
});

test('중복과 순서가 정리됩니다', () => {
  const g = groupBySeason(env, [2022, 2016, 2022]);
  assert.deepEqual(g.map((x) => x.seasons), [[2016], [2022]]);
});

test('배정에 없는 시즌은 묶음에서 빠집니다', () => {
  const g = groupBySeason(env, [2014, 2019, 2030]);
  assert.equal(g.length, 1);
  assert.deepEqual(g[0].seasons, [2019]);
});

test('바인딩이 빠져 있으면 조용히 넘어가지 않습니다', () => {
  // wrangler.toml 을 빠뜨리면 그 시즌만 결과에서 사라집니다.
  // 빈 결과보다 오류가 낫습니다.
  assert.throws(() => groupBySeason({ DB_2015_2017: {} }, [2019]),
    /DB_2018_2020/);
});

test('fanOut 이 시즌 순으로 이어붙입니다', async () => {
  // 나누기 전 한 표였을 때와 순서가 같아야 합니다.
  const out = await fanOut(env, [2025, 2016, 2019], async (db, seasons) =>
    seasons.map((y) => `${db.tag}:${y}`));
  assert.deepEqual(out, ['a:2016', 'b:2019', 'd:2025']);
});

test('fanOut 은 관련 DB 만 부릅니다', async () => {
  const called = [];
  await fanOut(env, [2021], async (db) => { called.push(db.tag); return []; });
  assert.deepEqual(called, ['c']);
});

test('fanOut 은 빈 시즌 목록에 아무 DB 도 부르지 않습니다', async () => {
  const called = [];
  const out = await fanOut(env, [], async (db) => { called.push(db.tag); return []; });
  assert.deepEqual(called, []);
  assert.deepEqual(out, []);
});
