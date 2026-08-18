import { test } from 'node:test';
import assert from 'node:assert/strict';

import { purgeCache } from '../src/routes/admin.js';
import { cacheControlFor, withCache } from '../src/lib/cachepolicy.js';

// 이 엔드포인트는 공개 저장소에 있는 공개 Worker 에 붙습니다.
// 아무나 부르면 캐시를 계속 비워 D1 읽기 한도(하루 500만 행)를 태울 수
// 있습니다. 그래서 토큰 검사가 이 파일의 핵심입니다.

function req(headers = {}) {
  return new Request('https://x/admin/purge-cache', { method: 'POST', headers });
}

function fakeCtx() {
  const calls = [];
  return { calls, cache: { purge: async (opts) => { calls.push(opts); } } };
}

test('토큰이 맞으면 캐시를 통째로 비웁니다', async () => {
  const ctx = fakeCtx();
  const res = await purgeCache(
    req({ authorization: 'Bearer s3cret' }), { ADMIN_TOKEN: 's3cret' }, ctx,
  );
  assert.equal(res.status, 200);
  assert.deepEqual(ctx.calls, [{ purgeEverything: true }]);
  assert.equal((await res.json()).purged, true);
});

test('토큰이 틀리면 401 이고 비우지 않습니다', async () => {
  const ctx = fakeCtx();
  const res = await purgeCache(
    req({ authorization: 'Bearer wrong' }), { ADMIN_TOKEN: 's3cret' }, ctx,
  );
  assert.equal(res.status, 401);
  assert.deepEqual(ctx.calls, []);
});

test('헤더가 아예 없으면 401 입니다', async () => {
  const ctx = fakeCtx();
  const res = await purgeCache(req(), { ADMIN_TOKEN: 's3cret' }, ctx);
  assert.equal(res.status, 401);
  assert.deepEqual(ctx.calls, []);
});

test('Bearer 없이 토큰만 보내도 401 입니다', async () => {
  const ctx = fakeCtx();
  const res = await purgeCache(
    req({ authorization: 's3cret' }), { ADMIN_TOKEN: 's3cret' }, ctx,
  );
  assert.equal(res.status, 401);
  assert.deepEqual(ctx.calls, []);
});

test('길이가 다른 토큰도 통과하지 않습니다', async () => {
  // 앞부분만 맞는 값으로 뚫리면 안 됩니다.
  const ctx = fakeCtx();
  const res = await purgeCache(
    req({ authorization: 'Bearer s3c' }), { ADMIN_TOKEN: 's3cret' }, ctx,
  );
  assert.equal(res.status, 401);
  assert.deepEqual(ctx.calls, []);
});

test('시크릿을 안 걸어 뒀으면 503 이고 비우지 않습니다', async () => {
  // **비밀번호가 없을 때 열어 두면 안 됩니다.** 공개 Worker 라
  // 주소만 알면 누구나 부를 수 있습니다.
  const ctx = fakeCtx();
  // 헤더 값은 ByteString 이라 한글을 넣을 수 없습니다(Request 가 거부합니다).
  const res = await purgeCache(req({ authorization: 'Bearer anything' }), {}, ctx);
  assert.equal(res.status, 503);
  assert.deepEqual(ctx.calls, []);
});

test('빈 문자열 시크릿도 없는 것으로 봅니다', async () => {
  const ctx = fakeCtx();
  const res = await purgeCache(
    req({ authorization: 'Bearer ' }), { ADMIN_TOKEN: '' }, ctx,
  );
  assert.equal(res.status, 503);
  assert.deepEqual(ctx.calls, []);
});

test('런타임에 캐시 API 가 없으면 501 로 알립니다', async () => {
  // 조용히 200 을 주면 워크플로가 성공으로 보고 지나갑니다.
  // 그러면 화면이 하루 종일 어제 숫자를 보여 줍니다.
  const res = await purgeCache(
    req({ authorization: 'Bearer s3cret' }), { ADMIN_TOKEN: 's3cret' }, {},
  );
  assert.equal(res.status, 501);
});

test('purge 가 실패하면 500 으로 드러냅니다', async () => {
  const ctx = {
    cache: { purge: async () => { throw new Error('boom'); } },
  };
  const res = await purgeCache(
    req({ authorization: 'Bearer s3cret' }), { ADMIN_TOKEN: 's3cret' }, ctx,
  );
  assert.equal(res.status, 500);
});

test('관리 응답은 캐시하지 않습니다', async () => {
  // 여기가 캐시되면 두 번째 호출부터 Worker 가 실행되지 않아
  // 캐시를 비우는 요청 자체가 캐시에 먹힙니다.
  assert.equal(cacheControlFor('/admin/purge-cache'), null);
  const res = withCache(new Response('{}', { status: 200 }), '/admin/purge-cache');
  assert.equal(res.headers.get('cache-control'), null);
});
