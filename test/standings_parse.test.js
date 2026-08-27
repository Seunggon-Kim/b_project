import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  KBO_TEAM_CODE, KBO_CODE_TO_TEAM, parseStandings,
} from '../src/routes/standings.js';

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

test('현재 열 팀이 원본과 같은 코드를 씁니다', () => {
  // 원본 api/main.py:1399-1402 와 같아야 합니다. 하나라도 다르면
  // 로고가 깨지고 /standings 의 code 필드가 어긋납니다.
  const now = {
    LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
    롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
  };
  for (const [team, code] of Object.entries(now)) {
    assert.equal(KBO_TEAM_CODE[team], code, team);
  }
});

test('옛 이름도 같은 프랜차이즈 코드를 씁니다', () => {
  // 1982~2014 기록을 넣으면서 더했습니다. 이게 없으면 홈 화면 개인
  // 순위에서 옛 시즌을 골랐을 때 코드가 빈 문자열이 되어 로고가
  // 조용히 안 나옵니다. 로고 파일은 코드별이라 그대로 씁니다.
  const old = {
    MBC: 'LG', OB: 'OB', 해태: 'HT', 빙그레: 'HH', SK: 'SK',
    우리: 'WO', 히어로즈: 'WO', 넥센: 'WO',
    삼미: 'HD', 청보: 'HD', 태평양: 'HD', 현대: 'HD', 쌍방울: 'SB',
  };
  for (const [team, code] of Object.entries(old)) {
    assert.equal(KBO_TEAM_CODE[team], code, team);
  }
});

test('역매핑은 현재 팀명으로 돌아옵니다', () => {
  // 이름->코드 표를 그대로 뒤집으면 한 코드에 이름이 여럿이라
  // 마지막 것이 이깁니다. 실제로 `LG -> MBC`, `HT -> 해태`,
  // `WO -> 넥센` 이 되었습니다. 그러면 일정 카드가 오늘 경기의
  // 투수를 "MBC 소속" 으로 찾아 링크가 통째로 깨집니다.
  assert.equal(Object.keys(KBO_CODE_TO_TEAM).length, 10);
  assert.equal(KBO_CODE_TO_TEAM['LG'], 'LG');
  assert.equal(KBO_CODE_TO_TEAM['HT'], 'KIA');
  assert.equal(KBO_CODE_TO_TEAM['WO'], '키움');
  assert.equal(KBO_CODE_TO_TEAM['SK'], 'SSG');
  assert.equal(KBO_CODE_TO_TEAM['OB'], '두산');
});

test('역매핑 결과가 다시 같은 코드로 돌아옵니다', () => {
  // 왕복이 어긋나면 링크가 조용히 깨집니다.
  for (const [code, team] of Object.entries(KBO_CODE_TO_TEAM)) {
    assert.equal(KBO_TEAM_CODE[team], code, `${code} -> ${team}`);
  }
});
