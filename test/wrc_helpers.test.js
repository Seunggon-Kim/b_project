import { test } from 'node:test';
import assert from 'node:assert/strict';

import { qualPaOf, sortColumnOf, stdDelta } from '../src/routes/wrc.js';

// --- 규정타석 ---

test('경기 수에서 규정타석을 냅니다', () => {
  // 원본 _eff_min_pa: int(round(3.1 * round(2.0 * g / 10.0)))
  // g=720 -> round(144.0)=144 -> round(446.4)=446
  assert.equal(qualPaOf(720), 446);
});

test('경기가 없으면 0 입니다', () => {
  assert.equal(qualPaOf(0), 0);
});

test('은행가 반올림을 씁니다', () => {
  // g=375 -> round(75.0)=75 -> 3.1*75 = 232.5
  // Python round 는 232, Math.round 는 233 입니다.
  assert.equal(qualPaOf(375), 232);
});

test('바깥 반올림도 은행가 방식입니다', () => {
  // g=25 -> 2.0*25/10 = 5.0 -> round=5 -> 3.1*5 = 15.5 -> Python round 는 16
  // (15.5 는 이진수로 정확하고 15 가 홀수라 16 으로 갑니다)
  assert.equal(qualPaOf(25), 16);
});

// --- 정렬 컬럼 ---

test('지원하는 정렬 키 네 가지', () => {
  assert.equal(sortColumnOf('home'), 'wRC_home');
  assert.equal(sortColumnOf('half'), 'wRC_half');
  assert.equal(sortColumnOf('weighted'), 'wRC_weighted');
  assert.equal(sortColumnOf('wOBA'), 'wOBA');
});

test('모르는 정렬 키는 half 로 떨어집니다', () => {
  // 원본이 dict.get(sort, "wRC_half") 를 씁니다.
  assert.equal(sortColumnOf('nope'), 'wRC_half');
  assert.equal(sortColumnOf(''), 'wRC_half');
  assert.equal(sortColumnOf(undefined), 'wRC_half');
});

test('정렬 키는 화이트리스트만 통과합니다', () => {
  // SQL 에 그대로 끼워 넣는 자리라, 임의 문자열이 새어 들어가면 안 됩니다.
  assert.equal(sortColumnOf('wRC_half; DROP TABLE players'), 'wRC_half');
});

// --- 표준편차 ---

test('표본 표준편차입니다. 분모가 n-1 입니다', () => {
  // 원본: (sum((d-mean)**2) / (n-1))**0.5
  // [1,2,3,4] 평균 2.5, 편차제곱합 5, /3 = 1.6667, 루트 1.29
  assert.equal(stdDelta([1, 2, 3, 4]), 1.29);
});

test('소수 둘째 자리로 반올림합니다', () => {
  assert.equal(stdDelta([0, 1]), 0.71);
});

test('값이 하나뿐이면 null 입니다', () => {
  // 원본: n > 1 일 때만 계산하고 아니면 None
  assert.equal(stdDelta([5]), null);
});

test('빈 배열도 null 입니다', () => {
  assert.equal(stdDelta([]), null);
});

test('모두 같은 값이면 0 입니다', () => {
  assert.equal(stdDelta([3, 3, 3]), 0);
});
