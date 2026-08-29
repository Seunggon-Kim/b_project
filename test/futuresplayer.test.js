import { test } from 'node:test';
import assert from 'node:assert/strict';

import {
  parseProfile, parseSeasonRow, parseRecentGames,
} from '../src/routes/futuresplayer.js';

// KBO 퓨처스 선수 상세 페이지의 실제 모양입니다.
//
//     https://www.koreabaseball.com/Futures/Player/HitterDetail.aspx?playerId=56443
//
// 1군 기록이 없는 선수는 우리 `players` 표에 아예 없어서 `/players/:id`
// 가 404 를 돌려주고 선수 분석 화면이 비어 있었습니다. 이 페이지 한
// 장에 프로필과 올 시즌 기록이 다 있어서 그것으로 채웁니다.
const HITTER = `
<html><body>
<div class="player_basic">
  <div><img src="//img.example.com/KBO_IMAGE/person/middle/2026/56443.jpg" alt="김한별" /></div>
  <ul>
    <li class="odd"><strong>선수명: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblName">김한별</span></li>
    <li><strong>등번호: </strong>No.<span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblBackNo">143</span></li>
    <li class="odd"><strong>생년월일: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblBirthday">2002년 06월 04일</span></li>
    <li><strong>포지션: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblPosition">내야수(우투좌타)</span></li>
    <li class="odd"><strong>신장/체중: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblHeightWeight">185cm/87kg</span></li>
    <li><strong>출신교: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblCareer">서울청구초-신월중-서울충암고</span></li>
    <li class="odd"><strong>연봉: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblSalary">3000만원</span></li>
    <li><strong>지명순위: </strong><span id="cphContents_cphContents_cphContents_ucPlayerProfile_lblDraft">26 삼성 육성선수</span></li>
  </ul>
</div>
<table>
  <thead><tr>
    <th>팀명</th><th>AVG</th><th>G</th><th>AB</th><th>R</th><th>H</th>
    <th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>SB</th><th>BB</th>
    <th>HBP</th><th>SO</th><th>SLG</th><th>OBP</th>
  </tr></thead>
  <tbody><tr>
    <td>삼성</td><td>0.329</td><td>85</td><td>207</td><td>42</td><td>68</td>
    <td>13</td><td>2</td><td>5</td><td>36</td><td>5</td><td>17</td>
    <td>9</td><td>35</td><td>0.483</td><td>0.400</td>
  </tr></tbody>
</table>
<table>
  <thead><tr>
    <th>일자</th><th>구분</th><th>상대</th><th>AVG</th><th>AB</th><th>R</th>
    <th>H</th><th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>SB</th>
    <th>BB</th><th>HBP</th><th>SO</th><th>GDP</th>
    <th>합계</th><th>0.333</th><th>21</th>
  </tr></thead>
  <tbody>
    <tr><td>07.27</td><td>홈</td><td>KIA</td><td>1.000</td><td>2</td><td>1</td>
        <td>2</td><td>1</td><td>0</td><td>0</td><td>1</td><td>0</td>
        <td>0</td><td>0</td><td>0</td><td>0</td></tr>
    <tr><td>08.13</td><td>홈</td><td>한화</td><td>0.333</td><td>3</td><td>2</td>
        <td>1</td><td>0</td><td>0</td><td>1</td><td>1</td><td>0</td>
        <td>0</td><td>1</td><td>1</td><td>0</td></tr>
  </tbody>
</table>
</body></html>`;

// 투수 페이지는 컬럼만 다르고 뼈대가 같습니다.
const PITCHER = `
<html><body>
  <ul>
    <li><strong>선수명: </strong><span id="x_ucPlayerProfile_lblName">박세진</span></li>
    <li><strong>포지션: </strong><span id="x_ucPlayerProfile_lblPosition">투수(좌투좌타)</span></li>
  </ul>
<table>
  <thead><tr>
    <th>팀명</th><th>ERA</th><th>G</th><th>W</th><th>L</th><th>SV</th>
    <th>HLD</th><th>WPCT</th><th>IP</th><th>H</th><th>HR</th><th>BB</th>
    <th>HBP</th><th>SO</th><th>R</th><th>ER</th><th>AVG</th>
  </tr></thead>
  <tbody><tr>
    <td>롯데</td><td>1.96</td><td>17</td><td>10</td><td>1</td><td>0</td>
    <td>1</td><td>0.909</td><td>82 2/3</td><td>62</td><td>1</td><td>18</td>
    <td>4</td><td>82</td><td>20</td><td>18</td><td>0.208</td>
  </tr></tbody>
</table>
</body></html>`;

// 기록이 아직 없는 선수입니다. 표는 있는데 안이 비어 있습니다.
const EMPTY = `
<html><body>
  <ul><li><strong>선수명: </strong><span id="x_ucPlayerProfile_lblName">홍길동</span></li></ul>
  <table><thead><tr><th>팀명</th><th>AVG</th></tr></thead><tbody></tbody></table>
</body></html>`;

test('프로필을 읽습니다', () => {
  const p = parseProfile(HITTER);
  assert.equal(p.name, '김한별');
  assert.equal(p.back_number, '143');
  assert.equal(p.birthday, '2002년 06월 04일');
  assert.equal(p.position, '내야수(우투좌타)');
  assert.equal(p.height_weight, '185cm/87kg');
  assert.equal(p.salary, '3000만원');
  assert.equal(p.draft, '26 삼성 육성선수');
});

test('생년월일을 YYYYMMDD 로도 돌려줍니다', () => {
  // 화면이 나이를 계산할 때 쓰는 형식입니다. 1군 players.birthday 와
  // 같은 모양이라 화면 코드를 그대로 쓸 수 있습니다.
  assert.equal(parseProfile(HITTER).birthday_ymd, '20020604');
});

test('선수 사진 주소를 절대 주소로 만듭니다', () => {
  // KBO 가 `//host/...` 로 줍니다. 그대로 쓰면 화면에서 깨집니다.
  assert.equal(
    parseProfile(HITTER).photo,
    'https://img.example.com/KBO_IMAGE/person/middle/2026/56443.jpg',
  );
});

test('없는 값은 null 입니다', () => {
  const p = parseProfile(EMPTY);
  assert.equal(p.name, '홍길동');
  assert.equal(p.position, null);
  assert.equal(p.birthday_ymd, null);
  assert.equal(p.photo, null);
});

test('시즌 요약을 컬럼과 함께 읽습니다', () => {
  const s = parseSeasonRow(HITTER);
  assert.equal(s.columns[0], '팀명');
  assert.equal(s.columns.length, 16);
  assert.equal(s.cells[0], '삼성');
  assert.equal(s.cells[1], '0.329');
  assert.equal(s.cells[8], '5'); // HR
});

test('투수 시즌 요약도 같은 방식으로 읽습니다', () => {
  const s = parseSeasonRow(PITCHER);
  assert.equal(s.columns[1], 'ERA');
  assert.equal(s.cells[1], '1.96');
  assert.equal(s.cells[8], '82 2/3'); // IP
});

test('기록이 없으면 빈 표입니다', () => {
  const s = parseSeasonRow(EMPTY);
  assert.deepEqual(s.cells, []);
});

test('최근 경기 표에서 합계 열을 잘라 냅니다', () => {
  // KBO 가 헤더 행에 합계까지 붙여 놓습니다. 그대로 쓰면 컬럼이
  // 데이터보다 많아져 화면이 밀립니다.
  const g = parseRecentGames(HITTER);
  assert.equal(g.columns.length, 16);
  assert.equal(g.columns[0], '일자');
  assert.equal(g.columns[15], 'GDP');
  assert.ok(!g.columns.includes('합계'));
});

test('최근 경기 행을 읽습니다', () => {
  const g = parseRecentGames(HITTER);
  assert.equal(g.rows.length, 2);
  assert.deepEqual(g.rows[0].slice(0, 4), ['07.27', '홈', 'KIA', '1.000']);
});

test('최근 경기 표가 없으면 빈 값입니다', () => {
  const g = parseRecentGames(PITCHER);
  assert.deepEqual(g.rows, []);
});

// --- 1군과 같은 모양으로 맞추기 -------------------------------------
//
// 화면(player-analytics)은 1군 `players` 행을 그리도록 짜여 있습니다.
// 퓨처스 값을 같은 모양으로 바꿔 주면 화면 코드를 그대로 쓸 수 있습니다.
//
//     내야수(우투좌타)  ->  position 내야수, throw R, bat L
//     185cm/87kg        ->  height 185, weight 87
//     3000만원          ->  salary 30000000

test('포지션에서 투타를 갈라 냅니다', () => {
  const p = parseProfile(HITTER);
  assert.equal(p.position_name, '내야수');
  assert.equal(p.throw, 'R');
  assert.equal(p.bat, 'L');
});

test('좌투좌타·양손도 읽습니다', () => {
  const one = parseProfile(PITCHER);
  assert.equal(one.position_name, '투수');
  assert.equal(one.throw, 'L');
  assert.equal(one.bat, 'L');
});

test('신장과 체중을 숫자로 돌려줍니다', () => {
  const p = parseProfile(HITTER);
  assert.equal(p.height, 185);
  assert.equal(p.weight, 87);
});

test('연봉을 원 단위 숫자로 바꿉니다', () => {
  assert.equal(parseProfile(HITTER).salary_won, 30000000);
});

test('없는 값은 숫자도 null 입니다', () => {
  const p = parseProfile(EMPTY);
  assert.equal(p.height, null);
  assert.equal(p.weight, null);
  assert.equal(p.salary_won, null);
  assert.equal(p.throw, null);
  assert.equal(p.position_name, null);
});

// --- 안내 행을 기록으로 세지 않습니다 -------------------------------
//
// 기록이 없는 쪽 페이지에도 표는 있습니다. KBO 가 안내 문구를 한 칸
// 짜리 행으로 넣습니다.
//
//     <tr><td colspan="16">기록이 없습니다.</td></tr>
//
// 이것을 기록으로 세는 바람에 **투수를 타자로 판정했습니다.** 화면에
// 투수 기록 대신 값이 전부 '-' 인 타자 표가 나왔습니다(31048 등
// 외국인 투수 셋). 타자·투수 두 페이지를 다 부르고 기록이 있는 쪽을
// 고르는데, 없는 쪽이 먼저 잡혔습니다.
const NO_RECORD = `
<html><body>
  <ul><li><strong>선수명: </strong><span id="x_ucPlayerProfile_lblName">외국인투수</span></li></ul>
  <table>
    <thead><tr>
      <th>팀명</th><th>AVG</th><th>G</th><th>AB</th><th>R</th><th>H</th>
      <th>2B</th><th>3B</th><th>HR</th><th>RBI</th><th>SB</th><th>BB</th>
      <th>HBP</th><th>SO</th><th>SLG</th><th>OBP</th>
    </tr></thead>
    <tbody><tr><td colspan="16">기록이 없습니다.</td></tr></tbody>
  </table>
</body></html>`;

test('안내 한 줄은 기록이 아닙니다', () => {
  const s = parseSeasonRow(NO_RECORD);
  assert.deepEqual(s.cells, []);
  // 컬럼은 그대로 둡니다. 화면이 어떤 표인지 알 수 있어야 합니다.
  assert.equal(s.columns.length, 16);
});

test('칸이 모자란 행도 기록이 아닙니다', () => {
  // colspan 이 아니어도 칸 수가 안 맞으면 데이터가 아닙니다.
  const short = NO_RECORD.replace('colspan="16"', '');
  assert.deepEqual(parseSeasonRow(short).cells, []);
});

test('칸이 다 찬 행은 그대로 기록입니다', () => {
  assert.equal(parseSeasonRow(HITTER).cells.length, 16);
  assert.equal(parseSeasonRow(PITCHER).cells.length, 17);
});
