import { test } from 'node:test';
import assert from 'node:assert/strict';

import { summarizeUsage } from '../src/routes/players.js';

const p = (pitch_type, stands, throws) => ({ pitch_type, stands, throws });

test('구종별로 셉니다', () => {
  const { result } = summarizeUsage([
    p('직구', '우', '우'), p('직구', '우', '우'), p('슬라이더', '우', '우'),
  ]);
  assert.equal(result.length, 2);
  assert.equal(result[0].pitch_type, '직구');
  assert.equal(result[0].count, 2);
});

test('약어 표를 씁니다', () => {
  const { result } = summarizeUsage([p('직구', '우', '우')]);
  assert.equal(result[0].abbreviation, 'FF');
});

test('표에 없는 구종은 앞 두 글자를 대문자로', () => {
  // 원본: abb_map.get(ptype, ptype[:2].upper())
  const { result } = summarizeUsage([p('포크', '우', '우')]);
  assert.equal(result[0].abbreviation, '포크');
});

test('스위치 타자는 투수 반대편으로 셉니다', () => {
  // 우투수 상대 양타자는 좌타석에 섭니다.
  const { totalL, totalR } = summarizeUsage([p('직구', '양', '우')]);
  assert.equal(totalL, 1);
  assert.equal(totalR, 0);
});

test('좌투수 상대 양타자는 우타로 셉니다', () => {
  const { totalL, totalR } = summarizeUsage([p('직구', '양', '좌')]);
  assert.equal(totalL, 0);
  assert.equal(totalR, 1);
});

test('좌가 아니면 전부 우타입니다', () => {
  // 원본의 else 분기입니다. 값이 비었거나 모르는 문자열이어도 우타입니다.
  const { totalR } = summarizeUsage([
    p('직구', '우', '우'), p('직구', null, null), p('직구', '???', '우'),
  ]);
  assert.equal(totalR, 3);
});

test('구사율은 소수 첫째 자리입니다', () => {
  const { result } = summarizeUsage([
    p('직구', '우', '우'), p('직구', '우', '우'), p('슬라이더', '우', '우'),
  ]);
  assert.equal(result[0].usage_all, 66.7);
  assert.equal(result[1].usage_all, 33.3);
});

test('구사율 높은 순으로 정렬합니다', () => {
  const { result } = summarizeUsage([
    p('슬라이더', '우', '우'),
    p('직구', '우', '우'), p('직구', '우', '우'), p('직구', '우', '우'),
  ]);
  assert.deepEqual(result.map((x) => x.pitch_type), ['직구', '슬라이더']);
});

test('좌타 상대가 없으면 usage_l 은 0 입니다', () => {
  // 원본: 분모가 0 이면 0 을 넣습니다. null 이 아닙니다.
  const { result } = summarizeUsage([p('직구', '우', '우')]);
  assert.equal(result[0].usage_l, 0);
  assert.equal(result[0].usage_r, 100);
});

test('빈 입력은 빈 결과입니다', () => {
  const { result, totalAll } = summarizeUsage([]);
  assert.deepEqual(result, []);
  assert.equal(totalAll, 0);
});

test('좌우 합이 전체와 같습니다', () => {
  const rows = [
    p('직구', '좌', '우'), p('직구', '우', '우'),
    p('커브', '양', '우'), p('커브', '양', '좌'),
  ];
  const { totalAll, totalL, totalR } = summarizeUsage(rows);
  assert.equal(totalL + totalR, totalAll);
  assert.equal(totalAll, 4);
});
