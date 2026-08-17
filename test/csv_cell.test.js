import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  csvCell, csvExportPlan, csvRow, isRealType,
} from '../src/lib/csv.js';

// 파이썬 csv.writer 의 QUOTE_MINIMAL 규칙을 그대로 따라야 합니다.
// 정답지가 SHA-256 으로 대조하므로 규칙이 하나만 달라도 불일치입니다.

test('평범한 값은 그대로 씁니다', () => {
  assert.equal(csvCell('LG'), 'LG');
  assert.equal(csvCell('김도영'), '김도영');
});

test('숫자를 문자열로 바꿉니다', () => {
  assert.equal(csvCell(0), '0');
  assert.equal(csvCell(3.14), '3.14');
});

test('null 과 undefined 는 빈 칸입니다', () => {
  assert.equal(csvCell(null), '');
  assert.equal(csvCell(undefined), '');
});

test('0 은 빈 칸이 아닙니다', () => {
  // !value 로 거르면 0 이 사라집니다.
  assert.equal(csvCell(0), '0');
});

test('쉼표가 있으면 따옴표로 감쌉니다', () => {
  assert.equal(csvCell('가,나'), '"가,나"');
});

test('따옴표는 두 번 반복해 이스케이프합니다', () => {
  assert.equal(csvCell('그는 "말했다"'), '"그는 ""말했다"""');
});

test('개행이 있으면 감쌉니다', () => {
  assert.equal(csvCell('첫줄\n둘째줄'), '"첫줄\n둘째줄"');
  assert.equal(csvCell('첫줄\r\n둘째줄'), '"첫줄\r\n둘째줄"');
});

test('감쌀 이유가 없으면 감싸지 않습니다', () => {
  // QUOTE_MINIMAL 입니다. QUOTE_ALL 이 아닙니다.
  assert.equal(csvCell('공백 있음'), '공백 있음');
  assert.equal(csvCell("작은따옴표'"), "작은따옴표'");
});

test('행 끝은 CRLF 입니다', () => {
  // 파이썬 csv.writer 의 기본 lineterminator 가 \r\n 입니다.
  assert.equal(csvRow(['a', 'b']), 'a,b\r\n');
});

test('행 안의 빈 값도 자리를 지킵니다', () => {
  assert.equal(csvRow(['a', null, 'c']), 'a,,c\r\n');
});

test('한 칸만 있어도 됩니다', () => {
  assert.equal(csvRow(['x']), 'x\r\n');
});

// --- REAL 컬럼 표기 ---

test('REAL 컬럼의 정수값에 .0 을 붙입니다', () => {
  // SQLite REAL 에 든 150.0 을 파이썬은 150.0 으로 씁니다.
  // JS 는 정수와 실수를 구분하지 않아 그냥 두면 150 이 되어 해시가 어긋납니다.
  assert.equal(csvCell(150, true), '150.0');
  assert.equal(csvCell(892, true), '892.0');
  assert.equal(csvCell(0, true), '0.0');
});

test('REAL 컬럼이라도 소수는 그대로 씁니다', () => {
  assert.equal(csvCell(150.5, true), '150.5');
  assert.equal(csvCell(0.3331229297588591, true), '0.3331229297588591');
});

test('정수 컬럼은 .0 을 붙이지 않습니다', () => {
  assert.equal(csvCell(150, false), '150');
  assert.equal(csvCell(150), '150');
});

test('REAL 컬럼이어도 null 은 빈 칸입니다', () => {
  assert.equal(csvCell(null, true), '');
});

test('REAL 컬럼이어도 문자열은 건드리지 않습니다', () => {
  assert.equal(csvCell('150', true), '150');
});

test('행 단위로 컬럼별 타입을 적용합니다', () => {
  // 첫째는 정수 컬럼, 둘째는 REAL 컬럼입니다.
  assert.equal(csvRow([3, 150], [false, true]), '3,150.0\r\n');
});

test('타입 배열이 없으면 전부 정수처럼 씁니다', () => {
  assert.equal(csvRow([3, 150]), '3,150\r\n');
});

test('isRealType 은 SQLite 표기 여러 가지를 받습니다', () => {
  for (const t of ['REAL', 'real', 'FLOAT', 'DOUBLE', 'DOUBLE PRECISION']) {
    assert.ok(isRealType(t), t);
  }
  for (const t of ['INTEGER', 'TEXT', 'BLOB', '', null, undefined]) {
    assert.ok(!isRealType(t), String(t));
  }
});

// --- 내보내기 계획 ---
// 스트림을 연 뒤에는 HTTP 상태를 되돌릴 수 없습니다. 잘린 CSV 를 200 으로
// 내주면 사용자는 그것이 전량인 줄 알고 씁니다. 열기 전에 판단해야 합니다.

test('한도 안이면 전량을 보냅니다', () => {
  const p = csvExportPlan(500, 0, 0, 20000);
  assert.equal(p.willSend, 500);
  assert.equal(p.tooLarge, false);
  assert.equal(p.startAt, 0);
});

test('한도를 넘으면 tooLarge 입니다', () => {
  const p = csvExportPlan(229667, 0, 0, 20000);
  assert.equal(p.tooLarge, true);
  assert.equal(p.parts, 12);
});

test('limit 이 한도 안이면 큰 표라도 보냅니다', () => {
  // 표가 커도 요청이 작으면 막을 이유가 없습니다.
  const p = csvExportPlan(229667, 5, 0, 20000);
  assert.equal(p.willSend, 5);
  assert.equal(p.tooLarge, false);
});

test('limit 0 은 끝까지라는 뜻입니다', () => {
  // 원본 api/main.py 와 같은 약속입니다. 0 을 "0행"으로 읽으면 안 됩니다.
  assert.equal(csvExportPlan(500, 0, 0, 20000).willSend, 500);
});

test('offset 이 남은 행 수를 줄입니다', () => {
  const p = csvExportPlan(25000, 0, 20000, 20000);
  assert.equal(p.willSend, 5000);
  assert.equal(p.tooLarge, false);
});

test('offset 이 총 행 수를 넘으면 0행입니다', () => {
  const p = csvExportPlan(100, 0, 500, 20000);
  assert.equal(p.willSend, 0);
  assert.equal(p.tooLarge, false);
});

test('음수 offset 은 0 으로 봅니다', () => {
  assert.equal(csvExportPlan(100, 0, -5, 20000).startAt, 0);
});

test('limit 이 남은 행보다 크면 남은 만큼입니다', () => {
  const p = csvExportPlan(25000, 20000, 20000, 20000);
  assert.equal(p.willSend, 5000);
});

test('빈 표도 조각 수는 1 입니다', () => {
  // 0 이면 "0번에 나눠 받으라"는 안내가 나옵니다.
  assert.equal(csvExportPlan(0, 0, 0, 20000).parts, 1);
});

test('경계에서 정확히 한도만큼은 통과합니다', () => {
  assert.equal(csvExportPlan(20000, 0, 0, 20000).tooLarge, false);
  assert.equal(csvExportPlan(20001, 0, 0, 20000).tooLarge, true);
});
