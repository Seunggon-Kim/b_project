import { test } from 'node:test';
import assert from 'node:assert/strict';

import { kstDateOf, kstToday } from '../src/lib/kst.js';

test('UTC 를 9시간 밀어 KST 날짜를 만듭니다', () => {
  // 2026-08-17T00:30Z 는 KST 로 같은 날 09:30 입니다.
  assert.equal(kstDateOf(Date.UTC(2026, 7, 17, 0, 30)), '2026-08-17');
});

test('UTC 자정 직전은 KST 로 다음 날입니다', () => {
  // 2026-08-17T15:30Z 는 KST 2026-08-18 00:30 입니다.
  assert.equal(kstDateOf(Date.UTC(2026, 7, 17, 15, 30)), '2026-08-18');
});

test('월말을 넘깁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 7, 31, 16, 0)), '2026-09-01');
});

test('연말을 넘깁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 11, 31, 16, 0)), '2027-01-01');
});

test('한 자리 월과 일을 0 으로 채웁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 0, 5, 0, 0)), '2026-01-05');
});

test('kstToday 는 YYYY-MM-DD 형태입니다', () => {
  assert.match(kstToday(), /^\d{4}-\d{2}-\d{2}$/);
});

test('며칠 전 한국 날짜를 YYYY-MM-DD 로 줍니다', async () => {
  const { kstDateDaysAgo } = await import('../src/lib/kst.js');
  // 2026-10-03 23:30 KST = 2026-10-03 14:30 UTC
  const now = Date.UTC(2026, 9, 3, 14, 30);
  assert.equal(kstDateDaysAgo(0, now), '2026-10-03');
  assert.equal(kstDateDaysAgo(7, now), '2026-09-26');
  // 2026-10-04 00:30 KST = 2026-10-03 15:30 UTC — 한국은 이미 4일입니다.
  assert.equal(kstDateDaysAgo(0, Date.UTC(2026, 9, 3, 15, 30)), '2026-10-04');
});
