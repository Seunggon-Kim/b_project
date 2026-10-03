import { test } from 'node:test';
import assert from 'node:assert/strict';

import { diffJson } from '../scripts/api_compare.mjs';

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
