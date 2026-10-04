import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  withBackend, closeAfterBody, finalizeResponse,
} from '../src/lib/backend.js';

test('요청마다 MySQL 어댑터를 만들어 env 사본의 DB 에 끼웁니다', async () => {
  let closed = false;
  const fake = { close: async () => { closed = true; } };
  const env = { HYPERDRIVE: {}, ADMIN_TOKEN: 'x' };
  let made = 0;
  const b = withBackend(env, (e) => { made += 1; assert.equal(e, env); return fake; });
  assert.equal(made, 1);
  assert.equal(b.env.DB, fake);
  assert.equal(b.env.ADMIN_TOKEN, 'x');
  assert.equal(b.db, fake);
  // 원래 env 는 바꾸지 않습니다.
  assert.equal(env.DB, undefined);
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
