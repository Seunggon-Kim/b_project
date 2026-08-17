import { test } from 'node:test';
import assert from 'node:assert/strict';

import { KBO_TEAM_CODE, parseStandings } from '../src/routes/standings.js';

const PAGE = `
<html><body>
<table summary="팀간승패표 입니다">
  <tbody><tr><td>1</td><td>속임수</td><td>0</td><td>0</td>
  <td>0</td><td>0</td><td>0</td><td>0</td></tr></tbody>
</table>
<table summary="순위 입니다">
  <tbody>
    <tr>
      <td>1</td><td>LG</td><td>144</td><td>90</td><td>50</td><td>4</td>
      <td>0.643</td><td>-</td><td>7-3-0</td><td>2승</td>
    </tr>
    <tr>
      <td>2</td><td>한화</td><td>144</td><td>85</td><td>55</td><td>4</td>
      <td>0.607</td><td>5.0</td><td>5-5-0</td><td>1패</td>
    </tr>
    <tr><td colspan="10">합계 행처럼 숫자가 아닌 첫 칸</td></tr>
  </tbody>
</table>
</body></html>`;

test('순위표만 읽고 팀간승패표는 건너뜁니다', () => {
  const rows = parseStandings(PAGE);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].team, 'LG');
  assert.equal(rows[1].team, '한화');
});

test('첫 칸이 숫자가 아닌 행은 버립니다', () => {
  const rows = parseStandings(PAGE);
  assert.ok(rows.every((r) => typeof r.rank === 'number'));
});

test('rank 는 정수이고 나머지 수치는 문자열입니다', () => {
  // 원본이 rank 만 int() 로 바꾸고 나머지는 문자열로 둡니다.
  // 여기서 타입이 어긋나면 골든 비교가 바로 잡아냅니다.
  const [first] = parseStandings(PAGE);
  assert.equal(first.rank, 1);
  assert.equal(first.games, '144');
  assert.equal(first.pct, '0.643');
  assert.equal(first.gb, '-');
});

test('팀 코드를 붙입니다', () => {
  const [first] = parseStandings(PAGE);
  assert.equal(first.code, 'LG');
});

test('모르는 팀명이면 코드는 빈 문자열입니다', () => {
  const page = PAGE.replace('<td>한화</td>', '<td>없는팀</td>');
  const rows = parseStandings(page);
  assert.equal(rows[1].code, '');
});

test('순위표가 없으면 빈 배열입니다', () => {
  assert.deepEqual(parseStandings('<html></html>'), []);
});

test('칸이 8개 미만인 행은 버립니다', () => {
  const page = `<table summary="순위">
    <tbody><tr><td>1</td><td>LG</td><td>144</td></tr></tbody></table>`;
  assert.deepEqual(parseStandings(page), []);
});

test('last10 과 streak 이 없으면 빈 문자열입니다', () => {
  const page = `<table summary="순위"><tbody><tr>
    <td>1</td><td>LG</td><td>144</td><td>90</td><td>50</td><td>4</td>
    <td>0.643</td><td>-</td></tr></tbody></table>`;
  const [first] = parseStandings(page);
  assert.equal(first.last10, '');
  assert.equal(first.streak, '');
});

test('팀 코드 표가 열 개입니다', () => {
  // 원본 api/main.py:1399-1402 와 같아야 합니다. 하나라도 다르면
  // 로고가 깨지고 /standings 의 code 필드가 어긋납니다.
  assert.equal(Object.keys(KBO_TEAM_CODE).length, 10);
  assert.equal(KBO_TEAM_CODE['두산'], 'OB');
  assert.equal(KBO_TEAM_CODE['KIA'], 'HT');
  assert.equal(KBO_TEAM_CODE['SSG'], 'SK');
  assert.equal(KBO_TEAM_CODE['키움'], 'WO');
  assert.equal(KBO_TEAM_CODE['한화'], 'HH');
});
