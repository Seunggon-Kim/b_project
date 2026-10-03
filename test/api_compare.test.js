import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  diffJson, parseUrlLine, compareResponses, canonicalize, canonicalKey,
} from '../scripts/api_compare.mjs';

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

test('키 있음은 상속이 아니라 자기 속성으로 봅니다(Object.hasOwn)', () => {
  // JSON 에서 온 'constructor'·'toString' 키도 B 에 없으면 없다고 해야 합니다.
  assert.deepEqual(diffJson({ constructor: 1 }, {}), ['$.constructor: B 에 없음']);
  assert.deepEqual(diffJson({}, { toString: 2 }), ['$.toString: A 에 없음']);
  const parsed = JSON.parse('{"__proto__": 1}');
  assert.deepEqual(diffJson(parsed, {}), ['$.__proto__: B 에 없음']);
});

test('기본(순서 있음)은 배열 순서가 다르면 차이입니다', () => {
  assert.ok(diffJson([1, 2, 3], [3, 2, 1]).length > 0);
  const r = (body) => ({ status: 200, body });
  assert.ok(compareResponses(r([1, 2]), r([2, 1])).length > 0);
});

test('--unordered 는 배열을 다중집합으로 견줍니다(중첩 배열·키 순서 포함)', () => {
  const r = (body) => ({ status: 200, body });
  const a = { rows: [{ id: 1, tags: ['x', 'y'] }, { id: 2, tags: [] }] };
  const b = { rows: [{ tags: [], id: 2 }, { tags: ['y', 'x'], id: 1 }] };
  assert.deepEqual(compareResponses(r(a), r(b), 200, { unordered: true }), []);
  assert.ok(compareResponses(r(a), r(b), 200).length > 0);
  assert.deepEqual(compareResponses(r([[1, 2], [3]]), r([[3], [2, 1]]), 200, { unordered: true }), []);
});

test('--unordered 도 개수는 셉니다(다중집합)', () => {
  const r = (body) => ({ status: 200, body });
  assert.ok(compareResponses(r([1, 1, 2]), r([1, 2, 2]), 200, { unordered: true }).length > 0);
  assert.ok(compareResponses(r([1, 2]), r([1, 2, 2]), 200, { unordered: true }).length > 0);
});

test('--unordered 도 실수의 아주 작은 차이는 허용합니다', () => {
  const r = (body) => ({ status: 200, body });
  // 정렬 키가 실수 끝자리로 갈리면 짝이 어긋납니다. 키에서는 실수를 반올림합니다.
  const a = [{ v: 0.30000000000000004, w: 1 }, { v: 0.3, w: 2 }];
  const b = [{ v: 0.3, w: 2 }, { v: 0.3, w: 1 }];
  assert.deepEqual(compareResponses(r(a), r(b), 200, { unordered: true }), []);
});

test('canonicalize 는 객체 키와 배열을 정해진 순서로 둡니다', () => {
  assert.equal(canonicalKey({ b: 1, a: [2, 1] }), canonicalKey({ a: [1, 2], b: 1 }));
  assert.notEqual(canonicalKey([1, 2]), canonicalKey([1, 2, 2]));
  assert.deepEqual(canonicalize({ b: [3, { y: 1, x: [2, 1] }], a: null }),
    { a: null, b: [3, { x: [1, 2], y: 1 }] });
  // 원본은 바꾸지 않습니다.
  const v = [3, 1, 2];
  canonicalize(v);
  assert.deepEqual(v, [3, 1, 2]);
});

test('URL 목록은 125개 이하이고 줄마다 읽힙니다', async () => {
  const { readFileSync } = await import('node:fs');
  const text = readFileSync(new URL('../scripts/api_compare_urls.txt', import.meta.url), 'utf8');
  const urls = text.split(/\r?\n/).map((s) => s.trim())
    .filter((s) => s && !s.startsWith('#')).map(parseUrlLine);
  assert.ok(urls.length <= 125, `URL ${urls.length}개`);
  for (const u of urls) assert.ok(u.path.startsWith('/'), u.path);
  assert.ok(urls.some((u) => u.path === '/players/73153x' && u.expect === 404));
  assert.ok(urls.some((u) => u.path === '/stats/batters?season=2025&limit=-1' && u.expect === 200));
});
