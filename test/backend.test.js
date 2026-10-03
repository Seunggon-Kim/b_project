import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  isMysql, withBackend, closeAfterBody, finalizeResponse,
} from '../src/lib/backend.js';
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

test('CSV 는 본문을 다 보낸 뒤에 연결을 닫습니다', async () => {
  let closed = false;
  const waits = [];
  const ctx = { waitUntil: (p) => waits.push(p) };
  const orig = new Response('abc', {
    status: 200, headers: { 'x-a': '1', 'content-type': 'text/csv; charset=utf-8' },
  });
  const res = closeAfterBody(orig, async () => { closed = true; }, ctx);
  assert.notEqual(res, orig);
  assert.equal(closed, false);
  assert.equal(await res.text(), 'abc');
  await Promise.all(waits);
  assert.equal(closed, true);
  assert.equal(res.headers.get('x-a'), '1');
});

test('D1 이면 db 가 null 이고, mysql 이면 어댑터를 그대로 내놓습니다', () => {
  const d1 = withBackend({ DB: 'd1' }, () => { throw new Error('부르면 안 됩니다'); });
  assert.equal(d1.db, null);
  const fake = { close: async () => {} };
  const my = withBackend({ DB: 'd1', DB_BACKEND: 'mysql' }, () => fake);
  assert.equal(my.db, fake);
});

test('finalizeResponse: D1 이면 응답을 그대로(같은 객체) 돌려줍니다', () => {
  const res = new Response('{}', { status: 200 });
  const b = withBackend({ DB: 'd1' });
  assert.equal(finalizeResponse(res, b), res);
});

test('finalizeResponse: MySQL 이 멀쩡하면 응답을 그대로 돌려줍니다', () => {
  const res = new Response('{}', { status: 200 });
  assert.equal(finalizeResponse(res, { env: {}, done: async () => {}, db: { failed: null } }), res);
});

test('finalizeResponse: MySQL 연결이 끊겼으면 503·no-store 로 바꿉니다', async () => {
  let cancelled = false;
  const body = new ReadableStream({ cancel() { cancelled = true; } });
  const res = new Response(body, { status: 200 });
  const failed = new Error('connect ETIMEDOUT');
  const out = finalizeResponse(res, { env: {}, done: async () => {}, db: { failed } });
  assert.notEqual(out, res);
  assert.equal(out.status, 503);
  assert.equal(out.headers.get('cache-control'), 'no-store');
  assert.deepEqual(await out.json(), { detail: 'connect ETIMEDOUT' });
  // 버린 원래 본문(CSV 스트림 등)은 닫아 더 읽지 않게 합니다.
  assert.equal(cancelled, true);
});

test('JSON 은 감싸지 않고 바로 닫기를 예약합니다(같은 객체)', async () => {
  let closed = false;
  const waits = [];
  const ctx = { waitUntil: (p) => waits.push(p) };
  const orig = new Response('{"a":1}', {
    status: 200, headers: { 'content-type': 'application/json; charset=utf-8' },
  });
  const res = closeAfterBody(orig, async () => { closed = true; }, ctx);
  assert.equal(res, orig);
  assert.equal(waits.length, 1);
  await Promise.all(waits);
  assert.equal(closed, true);
  assert.deepEqual(await res.json(), { a: 1 });
});

test('이미지(로고)처럼 CSV 가 아닌 본문도 감싸지 않습니다', async () => {
  const waits = [];
  const orig = new Response(new Uint8Array([1, 2, 3]), { headers: { 'content-type': 'image/png' } });
  const res = closeAfterBody(orig, async () => {}, { waitUntil: (p) => waits.push(p) });
  assert.equal(res, orig);
  assert.equal(waits.length, 1);
});
