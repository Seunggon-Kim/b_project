import { test } from 'node:test';
import assert from 'node:assert/strict';

import { diffJson, parseUrlLine, compareResponses } from '../scripts/api_compare.mjs';

test('같으면 빈 목록, 키 순서는 무시합니다', () => {
  assert.deepEqual(diffJson({ a: 1, b: [1, 2] }, { b: [1, 2], a: 1 }), []);
});

test('실수는 아주 작은 차이를 허용합니다', () => {
  assert.deepEqual(diffJson({ x: 0.30000000000000004 }, { x: 0.3 }), []);
  assert.equal(diffJson({ x: 0.31 }, { x: 0.3 }).length, 1);
});

test('타입이 다르면 차이입니다(글자 ID vs 숫자)', () => {
  assert.deepEqual(diffJson({ id: '72133' }, { id: 72133 }), ['$.id: "72133" ≠ 72133']);
});

test('배열 길이와 빠진 키를 알려 줍니다', () => {
  const d = diffJson({ a: [1, 2], b: 1 }, { a: [1], c: 2 });
  assert.ok(d.some((x) => x.startsWith('$.a: 길이')));
  assert.ok(d.some((x) => x.startsWith('$.b: B 에 없음')));
  assert.ok(d.some((x) => x.startsWith('$.c: A 에 없음')));
});

test('URL 줄은 상태 접두사가 있어도 없어도 읽습니다', () => {
  assert.deepEqual(parseUrlLine('/teams/HT'), { path: '/teams/HT', expect: 200 });
  assert.deepEqual(parseUrlLine('404 /players/1?x=1'), { path: '/players/1?x=1', expect: 404 });
});

test('양쪽이 같은 500 이어도 기대 200 이면 차이입니다', () => {
  const r = { status: 500, body: { error: 'x' } };
  assert.deepEqual(compareResponses(r, r, 200), ['상태 A=500 B=500 (기대 200)']);
});

test('기대 404 에 양쪽이 404 이면 차이가 없습니다', () => {
  const r = { status: 404, body: { detail: 'nf' } };
  assert.deepEqual(compareResponses(r, { ...r }, 404), []);
});

test('상태가 다르면 차이입니다', () => {
  assert.equal(compareResponses({ status: 200, body: {} }, { status: 503, body: {} }).length, 1);
});

test('JSON 이 아닌 본문은 해시로 견줍니다(_head 는 무시)', () => {
  const mk = (sha, head) => ({ status: 200, body: { _type: 'text/csv', _sha256: sha, _bytes: 10, _head: head } });
  assert.deepEqual(compareResponses(mk('aa', 'h1'), mk('aa', 'h2')), []);
  assert.equal(compareResponses(mk('aa', 'h'), mk('bb', 'h')).length, 1);
});
