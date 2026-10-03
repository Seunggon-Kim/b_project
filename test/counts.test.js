import { test } from 'node:test';
import assert from 'node:assert/strict';

import { shardedCountOf } from '../src/lib/counts.js';
import { SHARDS } from '../src/lib/shard.js';

test('mysql 이면 play_by_play 행 수를 한 번만 셉니다', async () => {
  const db = { prepare: () => ({ bind() { return this; }, async first() { return { n: 3983367 }; } }) };
  const env = { DB: db, DB_BACKEND: 'mysql' };
  for (const s of SHARDS) env[s.binding] = db;
  assert.equal(await shardedCountOf(env, SHARDS, 'play_by_play'), 3983367);
});
