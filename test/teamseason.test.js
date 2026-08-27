// 팀 필터가 그 시즌 팀을 보여 주게 지킵니다.
//
// 1982~2014 기록을 넣고 화면에서 드러났습니다. 1982 시즌을 열어도
// 팀 필터에는 KT·NC·키움이 뜨고, 정작 그 해에 있던 삼미·MBC 는
// 고를 수 없었습니다.
//
// `/teams` 가 `teams` 표(현재 10팀)만 돌려주고, 화면은 페이지를 열 때
// 한 번 부른 뒤 시즌이 바뀌어도 다시 부르지 않았기 때문입니다.
//
// 리그는 6팀으로 시작해 지금 10팀입니다.
//
//   1982~1985  6팀   MBC·OB·롯데·삼미·삼성·해태
//   1986~1990  7팀   빙그레 합류
//   1991~1999  8팀   쌍방울 합류
//   2013~2014  9팀   NC 합류
//   2015~      10팀  KT 합류
//
// 팀 이름은 **그 시즌 표기명**이어야 합니다. 기록의 `player_team` 과
// 같은 값이라야 필터가 실제로 걸립니다(1982 는 두산이 아니라 OB).
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

const ROUTE = 'src/routes/teams.js';
const API = 'dashboard_js/js/api.js';
const PAGE = 'dashboard_js/pages/player-stats.html';

test('시즌을 주면 그 시즌 팀을 봅니다', () => {
  const src = readFileSync(ROUTE, 'utf8');
  assert.ok(src.includes('team_seasons'),
    '시즌별 팀 표를 읽지 않습니다. 1982 에 KT 가 뜹니다.');
  assert.match(src, /searchParams\.get\('season'\)/,
    'season 인자를 받지 않습니다.');
});

test('그 시즌 표기명을 team_id 로 내보냅니다', () => {
  // 기록의 player_team 과 같은 값이라야 필터가 걸립니다.
  const src = readFileSync(ROUTE, 'utf8');
  assert.match(src, /ts\.team_name AS team_id/,
    '현재 팀명을 내보내면 옛 시즌 필터가 아무것도 못 거릅니다.');
});

test('시즌이 없으면 예전대로 현재 팀입니다', () => {
  const src = readFileSync(ROUTE, 'utf8');
  assert.match(src, /if \(!season \|\| !\/\^\\d\{4\}\$\/\.test\(season\)\)/,
    '인자가 없을 때의 하위 호환 경로가 없습니다.');
});

test('그 시즌 표가 비면 현재 팀으로 물러섭니다', () => {
  // 빈 목록을 주면 필터가 통째로 비어 아무것도 못 고릅니다.
  const src = readFileSync(ROUTE, 'utf8');
  assert.match(src, /if \(!results\.length\)/, '빈 결과 방어가 없습니다.');
  assert.ok(src.includes('fallback: true'), '폴백을 알리지 않습니다.');
});

test('해체팀은 현재 팀 없이도 나옵니다', () => {
  // 현대·쌍방울은 지금 없어서 teams 에 없습니다. 이너로 조인하면
  // 그 시즌 팀 목록에서 통째로 빠집니다.
  const src = readFileSync(ROUTE, 'utf8');
  assert.match(src, /LEFT JOIN teams t/,
    'teams 를 이너로 조인하면 해체팀이 사라집니다.');
});

test('화면이 시즌을 넘깁니다', () => {
  const api = readFileSync(API, 'utf8');
  assert.match(api, /static async getTeams\(season\)/,
    'getTeams 가 시즌을 받지 않습니다.');
  assert.match(api, /season \? `\?season=\$\{encodeURIComponent\(season\)\}`/,
    '시즌을 질의로 붙이지 않습니다.');

  const page = readFileSync(PAGE, 'utf8');
  assert.match(page, /API\.getTeams\(getSelectedSeason\(\)\)/,
    '화면이 시즌 없이 팀을 부릅니다.');
});

test('시즌을 바꾸면 팀 목록을 다시 받습니다', () => {
  const page = readFileSync(PAGE, 'utf8');
  const i = page.indexOf('function onSeasonChange()');
  assert.ok(i > 0, 'onSeasonChange 가 없습니다.');
  const body = page.slice(i, i + 600);
  assert.ok(body.includes('await loadTeams()'),
    '시즌만 바뀌고 팀 목록은 그대로라 없는 팀으로 거르게 됩니다.');
  assert.ok(body.indexOf('await loadTeams()') < body.indexOf('refreshStats()'),
    '팀 목록보다 데이터를 먼저 부르면 한 박자 늦습니다.');
});
