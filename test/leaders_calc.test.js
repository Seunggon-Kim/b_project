import { test } from 'node:test';
import assert from 'node:assert/strict';

import { WOBA_CONST, fmt3, ipToOuts } from '../src/routes/leaders.js';

test('정수 이닝을 아웃으로 바꿉니다', () => {
  assert.equal(ipToOuts('68'), 204);
});

test('분수만 있는 이닝을 바꿉니다', () => {
  assert.equal(ipToOuts('1/3'), 1);
});

test('정수와 분수가 섞인 이닝을 바꿉니다', () => {
  assert.equal(ipToOuts('68 1/3'), 205);
  assert.equal(ipToOuts('68 2/3'), 206);
});

test('앞뒤 공백이 있어도 값이 같습니다', () => {
  // Python 의 str.split() 은 빈 조각을 내지 않지만 JS 의 split(/\s+/) 은
  // 앞뒤 공백에서 빈 문자열을 냅니다. 그 빈 조각이 whole 을 0 으로
  // 덮어써서 68 이 사라지는 사고가 납니다.
  assert.equal(ipToOuts(' 68 1/3 '), 205);
  assert.equal(ipToOuts('68  1/3'), 205);
});

test('빈 값은 0 입니다', () => {
  assert.equal(ipToOuts(''), 0);
  assert.equal(ipToOuts(null), 0);
  assert.equal(ipToOuts(undefined), 0);
});

test('숫자가 아닌 값은 0 으로 칩니다', () => {
  assert.equal(ipToOuts('abc'), 0);
});

test('숫자 타입도 받습니다', () => {
  assert.equal(ipToOuts(68), 204);
  assert.equal(ipToOuts(0), 0);
});

test('소수 세 자리로 포맷합니다', () => {
  assert.equal(fmt3(0.3125), '0.313');
  assert.equal(fmt3(0.5), '0.500');
});

test('null 은 하이픈입니다', () => {
  assert.equal(fmt3(null), '-');
  assert.equal(fmt3(undefined), '-');
});

test('0 은 하이픈이 아닙니다', () => {
  // !value 로 거르면 0 이 "-" 가 되어 틀립니다.
  assert.equal(fmt3(0), '0.000');
});

test('wOBA 상수가 2011~2026 열여섯 해입니다', () => {
  const years = Object.keys(WOBA_CONST).map(Number).sort((a, b) => a - b);
  assert.equal(years.length, 16);
  assert.equal(years[0], 2011);
  assert.equal(years[15], 2026);
});

test('wOBA 상수는 연도마다 값 여섯 개입니다', () => {
  // (woba_scale, ebb, single_w, double_w, triple_w, hr_w)
  for (const [year, arr] of Object.entries(WOBA_CONST)) {
    assert.equal(arr.length, 6, `${year} 의 값 개수가 6 이 아닙니다`);
  }
});

test('wOBA 상수 표본값이 원본과 같습니다', () => {
  // api/main.py:1544-1545 에서 옮긴 값입니다.
  assert.deepEqual(WOBA_CONST[2025], [1.173, 0.371, 0.502, 0.801, 1.131, 1.406]);
  assert.deepEqual(WOBA_CONST[2026], [1.191, 0.364, 0.493, 0.802, 1.175, 1.411]);
});
