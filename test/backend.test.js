import { test } from 'node:test';
import assert from 'node:assert/strict';

import { isMysql, withBackend, closeAfterBody } from '../src/lib/backend.js';
import { SHARDS } from '../src/lib/shard.js';

test('기본은 D1 이고 env 를 그대로 씁니다', () => {
  const env = { DB: 'd1', DB_BACKEND: undefined };
  const b = withBackend(env, () => { throw new Error('부르면 안 됩니다'); });
  assert.equal(isMysql(env), false);
  assert.equal(b.env, env);
  assert.equal(b.done, null);
});

test('mysql 이면 DB 와 샤드 바인딩을 같은 어댑터로 바꿉니다', async () => {
  let closed = false;
  const fake = { close: async () => { closed = true; } };
  const env = { DB: 'd1', DB_BACKEND: 'mysql', HYPERDRIVE: {} };
  const b = withBackend(env, () => fake);
  assert.equal(b.env.DB, fake);
  for (const s of SHARDS) assert.equal(b.env[s.binding], fake);
  assert.equal(env.DB, 'd1');
  await b.done();
  assert.equal(closed, true);
});

test('응답 본문을 다 보낸 뒤에 연결을 닫습니다', async () => {
  let closed = false;
  const waits = [];
  const ctx = { waitUntil: (p) => waits.push(p) };
  const res = closeAfterBody(new Response('abc', { status: 200, headers: { 'x-a': '1' } }),
    async () => { closed = true; }, ctx);
  assert.equal(closed, false);
  assert.equal(await res.text(), 'abc');
  await Promise.all(waits);
  assert.equal(closed, true);
  assert.equal(res.headers.get('x-a'), '1');
});
