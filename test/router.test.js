import { test } from 'node:test';
import assert from 'node:assert/strict';

import { createRouter, matchPath, queryInt, queryStr } from '../src/lib/router.js';

test('고정 경로가 매칭됩니다', () => {
  assert.deepEqual(matchPath('/standings', '/standings'), {});
});

test('경로가 다르면 null 입니다', () => {
  assert.equal(matchPath('/standings', '/schedule'), null);
});

test('자리표시자를 값으로 뽑습니다', () => {
  assert.deepEqual(
    matchPath('/players/:id/news', '/players/50030/news'),
    { id: '50030' },
  );
});

test('자리표시자 개수가 다르면 매칭되지 않습니다', () => {
  assert.equal(matchPath('/players/:id/news', '/players/50030'), null);
});

test('경로 값의 퍼센트 인코딩을 풉니다', () => {
  assert.deepEqual(matchPath('/logo/:code', '/logo/%EB%91%90%EC%82%B0'),
                   { code: '두산' });
});

test('더 긴 경로가 자리표시자에 통째로 들어가지 않습니다', () => {
  // '/db/table/:name' 이 '/db/table/x/csv' 를 먹으면 CSV 라우트가 죽습니다.
  assert.equal(matchPath('/db/table/:name', '/db/table/players/csv'), null);
});

test('queryInt 는 없으면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y');
  assert.equal(queryInt(url, 'season', 2025), 2025);
});

test('queryInt 는 숫자가 아니면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y?season=abc');
  assert.equal(queryInt(url, 'season', 2025), 2025);
});

test('queryInt 는 값을 정수로 바꿉니다', () => {
  const url = new URL('https://x/y?season=2019');
  assert.equal(queryInt(url, 'season', 2025), 2019);
});

test('queryStr 은 빈 문자열을 그대로 돌려줍니다', () => {
  // 원본의 /wrc/batter-search 는 q="" 를 기본값으로 씁니다. 빈 값과 없는 값이 다릅니다.
  const url = new URL('https://x/y?q=');
  assert.equal(queryStr(url, 'q', 'FALLBACK'), '');
});

test('queryStr 은 없으면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y');
  assert.equal(queryStr(url, 'q', 'FALLBACK'), 'FALLBACK');
});

test('먼저 등록한 고정 경로가 자리표시자를 이깁니다', async () => {
  // /players/search 와 /players/:id 가 둘 다 2세그먼트라, 순서가 뒤바뀌면
  // 'search' 가 선수 ID 로 잡혀 검색이 죽습니다.
  const r = createRouter();
  r.add('GET', '/players/search', () => new Response('search'));
  r.add('GET', '/players/:id', () => new Response('detail'));
  const res = await r.handle(new Request('https://x/players/search'), {}, {});
  assert.equal(await res.text(), 'search');
});

test('자리표시자는 다른 값을 받습니다', async () => {
  const r = createRouter();
  r.add('GET', '/players/search', () => new Response('search'));
  r.add('GET', '/players/:id', () => new Response('detail'));
  const res = await r.handle(new Request('https://x/players/50030'), {}, {});
  assert.equal(await res.text(), 'detail');
});

test('등록하지 않은 경로는 404 입니다', async () => {
  const r = createRouter();
  r.add('GET', '/teams', () => new Response('ok'));
  const res = await r.handle(new Request('https://x/nope'), {}, {});
  assert.equal(res.status, 404);
});

test('메서드가 다르면 405 입니다', async () => {
  const r = createRouter();
  r.add('GET', '/teams', () => new Response('ok'));
  const res = await r.handle(
    new Request('https://x/teams', { method: 'POST' }), {}, {});
  assert.equal(res.status, 405);
});
