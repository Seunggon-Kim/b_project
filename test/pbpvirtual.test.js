import { test } from 'node:test';
import assert from 'node:assert/strict';

import { planSlice, isSharded } from '../src/lib/pbpvirtual.js';

// 데이터 탐색기의 페이지 넘기기입니다. 표가 네 DB 에 나뉘었지만
// 화면에는 한 표로 보여야 합니다. 경계 계산이 틀리면 행이 빠지거나
// 두 번 나옵니다.

const counts = [
  { binding: 'a', db: {}, n: 100 },
  { binding: 'b', db: {}, n: 200 },
  { binding: 'c', db: {}, n: 50 },
];

test('첫 샤드 안에서 끝나면 한 곳만 읽습니다', () => {
  assert.deepEqual(planSlice(counts, 0, 50).map((p) => [p.binding, p.offset, p.limit]),
    [['a', 0, 50]]);
});

test('경계를 걸치면 두 샤드에서 나눠 읽습니다', () => {
  assert.deepEqual(planSlice(counts, 90, 30).map((p) => [p.binding, p.offset, p.limit]),
    [['a', 90, 10], ['b', 0, 20]]);
});

test('세 샤드를 걸쳐도 맞습니다', () => {
  assert.deepEqual(planSlice(counts, 90, 250).map((p) => [p.binding, p.offset, p.limit]),
    [['a', 90, 10], ['b', 0, 200], ['c', 0, 40]]);
});

test('앞 샤드는 아예 묻지 않습니다', () => {
  // 건너뛴 행도 D1 은 읽은 것으로 셉니다. 질의 자체를 안 보내야 합니다.
  const p = planSlice(counts, 150, 10);
  assert.equal(p.length, 1);
  assert.deepEqual([p[0].binding, p[0].offset, p[0].limit], ['b', 50, 10]);
});

test('마지막 샤드를 넘어가면 있는 만큼만 줍니다', () => {
  assert.deepEqual(planSlice(counts, 340, 50).map((p) => [p.binding, p.offset, p.limit]),
    [['c', 40, 10]]);
});

test('전체를 넘은 offset 은 빈 계획입니다', () => {
  assert.deepEqual(planSlice(counts, 1000, 10), []);
  assert.deepEqual(planSlice(counts, 350, 10), []);
});

test('limit 0 이면 아무 데도 묻지 않습니다', () => {
  assert.deepEqual(planSlice(counts, 0, 0), []);
});

test('음수는 0 으로 봅니다', () => {
  assert.deepEqual(planSlice(counts, -5, 10).map((p) => [p.offset, p.limit]),
    [[0, 10]]);
  assert.deepEqual(planSlice(counts, 0, -1), []);
});

test('빈 샤드는 건너뜁니다', () => {
  // 아직 안 채운 샤드가 있어도 뒤 샤드를 정상적으로 읽어야 합니다.
  const c = [
    { binding: 'a', db: {}, n: 0 },
    { binding: 'b', db: {}, n: 10 },
  ];
  assert.deepEqual(planSlice(c, 0, 5).map((p) => [p.binding, p.offset, p.limit]),
    [['b', 0, 5]]);
});

test('조각 합이 요청한 limit 과 같습니다', () => {
  // 행이 빠지거나 겹치지 않는지 무작위로 확인합니다.
  const total = counts.reduce((a, c) => a + c.n, 0);
  for (let off = 0; off < total; off += 7) {
    for (const lim of [1, 13, 99]) {
      const plan = planSlice(counts, off, lim);
      const got = plan.reduce((a, p) => a + p.limit, 0);
      assert.equal(got, Math.min(lim, total - off), `off=${off} lim=${lim}`);
    }
  }
});

test('나뉜 표만 특별 취급합니다', () => {
  assert.equal(isSharded('play_by_play'), true);
  assert.equal(isSharded('games'), false);
  assert.equal(isSharded('players'), false);
});
