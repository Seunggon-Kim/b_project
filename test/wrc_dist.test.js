import { test } from 'node:test';
import assert from 'node:assert/strict';

import { distHistogram, distStats, pyRoundTo } from '../src/routes/wrc.js';

// --- 소수 자리 반올림 ---

test('소수 자리에도 은행가 반올림을 씁니다', () => {
  // Python round(0.125, 2) 는 0.12 입니다. toFixed 는 "0.13" 입니다.
  assert.equal(pyRoundTo(0.125, 2), 0.12);
});

test('반올림 자리가 짝수면 그대로 둡니다', () => {
  assert.equal(pyRoundTo(2.5, 0), 2);
  assert.equal(pyRoundTo(3.5, 0), 4);
});

// --- 분위수 ---

test('중앙값은 v[n // 2] 입니다. 두 값의 평균이 아닙니다', () => {
  // 원본은 statistics.median 을 쓰지 않습니다. 짝수여도 위쪽 값입니다.
  // [1,2,3,4] 의 n//2 = 2 -> v[2] = 3
  assert.equal(distStats([1, 2, 3, 4]).median, 3);
});

test('홀수 개의 중앙값', () => {
  assert.equal(distStats([1, 2, 3]).median, 2);
});

test('분위수를 보간하지 않고 인덱스로 집습니다', () => {
  // v = 1..10, n=10. int(10*0.1)=1 -> v[1]=2, int(10*0.9)=9 -> v[9]=10
  const s = distStats([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
  assert.equal(s.p10, 2);
  assert.equal(s.p90, 10);
});

test('평균은 소수 둘째 자리입니다', () => {
  assert.equal(distStats([1, 2]).mean, 1.5);
});

test('값이 없으면 n 키만 있습니다', () => {
  // 원본: if n == 0: return {"n": 0}
  // mean·p10·median·p90 키가 아예 없습니다.
  assert.deepEqual(distStats([]), { n: 0 });
});

test('null 을 걸러 낸 뒤 셉니다', () => {
  const s = distStats([1, null, 3, undefined]);
  assert.equal(s.n, 2);
});

test('정렬해서 계산합니다', () => {
  // 들어온 순서와 무관해야 합니다.
  assert.deepEqual(distStats([3, 1, 2]), distStats([1, 2, 3]));
});

// --- 히스토그램 ---

test('5점 구간으로 묶습니다', () => {
  const h = distHistogram([100, 101, 104, 105]);
  assert.deepEqual(h, [{ bin: 100, count: 3 }, { bin: 105, count: 1 }]);
});

test('40 아래는 40 으로 자릅니다', () => {
  assert.deepEqual(distHistogram([10, 20, 39]), [{ bin: 40, count: 3 }]);
});

test('200 위는 200 으로 자릅니다', () => {
  assert.deepEqual(distHistogram([250, 300]), [{ bin: 200, count: 2 }]);
});

test('음수는 내림 나눗셈을 씁니다', () => {
  // 파이썬 -3 // 5 = -1 이라 -5 가 되고, 40 으로 잘립니다.
  // Math.trunc 를 쓰면 0 이 되는데 그것도 40 으로 잘려 결과는 같습니다.
  // 그래도 원본과 같은 연산을 씁니다.
  assert.deepEqual(distHistogram([-3]), [{ bin: 40, count: 1 }]);
});

test('구간을 오름차순으로 돌려줍니다', () => {
  const h = distHistogram([150, 60, 100]);
  assert.deepEqual(h.map((x) => x.bin), [60, 100, 150]);
});

test('null 은 세지 않습니다', () => {
  assert.deepEqual(distHistogram([null, 100, undefined]),
                   [{ bin: 100, count: 1 }]);
});

test('빈 배열은 빈 목록입니다', () => {
  assert.deepEqual(distHistogram([]), []);
});
