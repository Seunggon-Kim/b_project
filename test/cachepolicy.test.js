import { test } from 'node:test';
import assert from 'node:assert/strict';

import { cacheControlFor, withCache } from '../src/lib/cachepolicy.js';

// 캐시에 맞으면 Worker 가 실행되지 않아 D1 읽기가 0 이 됩니다.
// 반대로 잘못 걸면 오래된 값이나 오류가 굳습니다.

test('라이브 데이터는 짧게 잡습니다', () => {
  // 원본 lib/cache.js 의 TTL 과 같아야 화면 갱신이 늦지 않습니다.
  assert.match(cacheControlFor('/schedule'), /max-age=30\b/);
  assert.match(cacheControlFor('/standings'), /max-age=300\b/);
  assert.match(cacheControlFor('/leaders'), /max-age=600\b/);
});

test('하위 경로도 같은 정책을 따릅니다', () => {
  assert.match(cacheControlFor('/schedule/futures'), /max-age=30\b/);
});

test('로고는 길게 잡습니다', () => {
  assert.match(cacheControlFor('/logo/LG'), /max-age=604800/);
});

test('나머지는 엣지 한 시간, 브라우저 1분입니다', () => {
  // max-age 하나만 쓰면 브라우저도 한 시간을 들고 있어서, 적재 뒤
  // 캐시를 비워도 사용자 화면이 안 바뀝니다. 실제로 겪었습니다.
  const v = cacheControlFor('/wrc/seasons');
  assert.match(v, /(^|[ ,])max-age=60,/);
  assert.match(v, /s-maxage=3600,/);
  assert.match(v, /stale-while-revalidate=86400/);
});

test('브라우저 수명이 엣지 수명보다 짧아야 합니다', () => {
  // 뒤집히면 캐시를 비워도 사용자에게 닿지 않습니다.
  const v = cacheControlFor('/teams');
  const browser = Number(/(?:^|[ ,])max-age=(\d+)/.exec(v)[1]);
  const edge = Number(/s-maxage=(\d+)/.exec(v)[1]);
  assert.ok(browser < edge, `브라우저 ${browser}초 >= 엣지 ${edge}초`);
});

test('접두사가 겹치는 다른 경로를 라이브로 오인하지 않습니다', () => {
  // '/games' 는 라이브지만 '/gamesomething' 은 아닙니다.
  assert.match(cacheControlFor('/games'), /max-age=300\b/);
  assert.match(cacheControlFor('/gameslist'), /s-maxage=3600/);
});

test('200 에만 붙입니다', () => {
  // 404 나 500 이 굳으면 고친 뒤에도 옛 응답이 나갑니다.
  for (const status of [404, 413, 422, 500]) {
    const res = withCache(new Response('x', { status }), '/teams');
    assert.equal(res.headers.get('cache-control'), null, String(status));
  }
});

test('200 이면 붙입니다', () => {
  const res = withCache(new Response('x', { status: 200 }), '/teams');
  assert.match(res.headers.get('cache-control'), /s-maxage=3600/);
});

test('이미 정해 둔 값이 있으면 건드리지 않습니다', () => {
  // logo.js 처럼 라우트가 자체 정책을 가진 경우입니다.
  const res = withCache(new Response('x', {
    status: 200,
    headers: { 'cache-control': 'public, max-age=86400' },
  }), '/logo/LG');
  assert.equal(res.headers.get('cache-control'), 'public, max-age=86400');
});

test('원래 헤더를 잃지 않습니다', () => {
  const res = withCache(new Response('{}', {
    status: 200,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
    },
  }), '/teams');
  assert.equal(res.headers.get('content-type'), 'application/json; charset=utf-8');
  assert.equal(res.headers.get('access-control-allow-origin'), '*');
});

test('본문을 그대로 넘깁니다', async () => {
  const res = withCache(new Response('hello', { status: 200 }), '/teams');
  assert.equal(await res.text(), 'hello');
});
