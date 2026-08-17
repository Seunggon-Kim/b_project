import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  TR_AB, TR_HIT, TR_WALK,
  accumulatePa, blankTeam, buildTeamRange, ipText, trNormDate,
} from '../src/routes/teamrange.js';

// --- 분류 집합 ---

test('안타 계열이 셋입니다', () => {
  for (const w of ['안타', '내야안타', '번트 안타']) {
    assert.ok(TR_HIT.has(w), w);
  }
});

test('장타도 안타에 들어갑니다', () => {
  for (const w of ['2루타', '3루타', '홈런']) assert.ok(TR_HIT.has(w), w);
});

test('볼넷 표기 다섯 가지를 모두 담습니다', () => {
  for (const w of ['볼넷', '자동 고의4구', '고의4구', '고의 4구', '자동 고의 4구']) {
    assert.ok(TR_WALK.has(w), w);
  }
});

test('타수에 볼넷은 들어가지 않습니다', () => {
  assert.ok(!TR_AB.has('볼넷'));
  assert.ok(!TR_AB.has('희생플라이'));
});

test('타수에 삼진과 낫아웃 출루가 들어갑니다', () => {
  assert.ok(TR_AB.has('삼진'));
  assert.ok(TR_AB.has('낫아웃 출루'));
});

// --- 날짜 정규화 ---

test('하이픈을 지웁니다', () => {
  assert.equal(trNormDate('2025-04-01'), 20250401);
});

test('슬래시도 지웁니다', () => {
  assert.equal(trNormDate('2025/04/01'), 20250401);
});

test('여덟 자리 숫자를 그대로 받습니다', () => {
  assert.equal(trNormDate('20250401'), 20250401);
});

test('여덟 자리가 아니면 null 입니다', () => {
  for (const v of ['2025-4-1', 'abcdefgh', '', null, undefined, '202504011']) {
    assert.equal(trNormDate(v), null, String(v));
  }
});

// --- 이닝 표기 ---

test('아웃 수를 이닝으로 씁니다', () => {
  assert.equal(ipText(0), '0');
  assert.equal(ipText(3), '1');
  assert.equal(ipText(4), '1 1/3');
  assert.equal(ipText(5), '1 2/3');
  assert.equal(ipText(27), '9');
});

// --- 집계 ---

const pa = (tb, res) => ({
  inning_topbot: tb, pa_result: res,
  home_team_id: 'HOME', away_team_id: 'AWAY',
});

test('초 이면 원정팀이 공격입니다', () => {
  const teams = accumulatePa(new Map(), [pa('초', '안타')]);
  assert.equal(teams.get('AWAY').H, 1);
  assert.equal(teams.get('HOME').Hd, 1); // 홈이 내준 안타
});

test('말 이면 홈팀이 공격입니다', () => {
  const teams = accumulatePa(new Map(), [pa('말', '안타')]);
  assert.equal(teams.get('HOME').H, 1);
  assert.equal(teams.get('AWAY').Hd, 1);
});

test('홈런은 안타와 홈런 둘 다 셉니다', () => {
  const teams = accumulatePa(new Map(), [pa('초', '홈런')]);
  const b = teams.get('AWAY');
  assert.equal(b.H, 1);
  assert.equal(b.HR, 1);
  assert.equal(teams.get('HOME').HRd, 1);
});

test('볼넷은 타수에 안 들어갑니다', () => {
  const teams = accumulatePa(new Map(), [pa('초', '볼넷')]);
  const b = teams.get('AWAY');
  assert.equal(b.PA, 1);
  assert.equal(b.AB, 0);
  assert.equal(b.BB, 1);
});

test('낫아웃 출루는 탈삼진이지만 아웃이 아닙니다', () => {
  const teams = accumulatePa(new Map(), [pa('초', '낫아웃 출루')]);
  assert.equal(teams.get('AWAY').SO, 1);
  assert.equal(teams.get('HOME').SOd, 1);
  // outs 는 이 함수가 건드리지 않습니다. 별도 집계입니다.
  assert.equal(teams.get('HOME').outs, 0);
});

// --- 파생 지표 ---

test('타율과 출루율과 장타율을 냅니다', () => {
  const t = blankTeam('LG');
  Object.assign(t, { AB: 4, H: 2, '2B': 1, BB: 1, HBP: 0, SF: 0 });
  const { batting } = buildTeamRange(new Map([['LG', t]]));
  const b = batting[0];
  assert.equal(b.AVG, 0.5); // 2/4
  assert.equal(b.TB, 3); // 2 + 1
  assert.equal(b.SLG, 0.75); // 3/4
  assert.equal(b.OBP, 0.6); // (2+1+0)/(4+1+0+0)
});

test('타수가 0 이면 0 을 냅니다. null 이 아닙니다', () => {
  const { batting } = buildTeamRange(new Map([['LG', blankTeam('LG')]]));
  assert.equal(batting[0].AVG, 0);
  assert.equal(batting[0].OPS, 0);
});

test('OPS 내림차순으로 정렬합니다', () => {
  const a = blankTeam('A');
  Object.assign(a, { AB: 10, H: 1 });
  const b = blankTeam('B');
  Object.assign(b, { AB: 10, H: 5 });
  const { batting } = buildTeamRange(new Map([['A', a], ['B', b]]));
  assert.deepEqual(batting.map((x) => x.team), ['B', 'A']);
});

test('RA9 오름차순이고 등판 없는 팀은 뒤로 갑니다', () => {
  const a = blankTeam('A');
  Object.assign(a, { outs: 27, Rd: 9 }); // RA9 = 9
  const b = blankTeam('B');
  Object.assign(b, { outs: 27, Rd: 3 }); // RA9 = 3
  const c = blankTeam('C'); // 등판 없음
  const { pitching } = buildTeamRange(new Map([['A', a], ['B', b], ['C', c]]));
  assert.deepEqual(pitching.map((x) => x.team), ['B', 'A', 'C']);
});

test('WHIP 과 RA9 를 냅니다', () => {
  const t = blankTeam('LG');
  Object.assign(t, { outs: 27, Hd: 6, BBd: 3, Rd: 4, SOd: 9, ABf: 30 });
  const { pitching } = buildTeamRange(new Map([['LG', t]]));
  const p = pitching[0];
  assert.equal(p.IP, 9);
  assert.equal(p.IP_text, '9');
  assert.equal(p.WHIP, 1); // (6+3)*3/27
  assert.equal(p.RA9, 4); // 4*27/27
  assert.equal(p.K9, 9);
  assert.equal(p.AVG_against, 0.2); // 6/30
});
