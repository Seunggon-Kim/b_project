// 선수 소속을 `players.team_id` 하나에만 기대지 않게 지킵니다.
//
// `players.team_id` 는 **아무 작업도 채우지 않는 컬럼**입니다.
// player_info_scraper 의 INSERT 문에 team_id 가 없습니다. 그래서
// 1,745명 중 1,160명(66%)이 비어 있고, 화면에 소속이 '-' 로 나옵니다.
// 남아 있는 값도 최초 적재 이후 갱신되지 않아 낡았습니다(강백호가
// 한화인데 KT 로 남아 있었습니다).
//
// 그 시즌 기록 행의 `player_team` 을 먼저 씁니다. 리더보드·기록실은
// 먼저 고쳤는데 선수 상세와 검색이 빠져 있었고, 사용자가 화면에서
// 먼저 발견했습니다. 세 번째가 나오지 않게 여기서 막습니다.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { latestTeam } from '../src/routes/players.js';

test('선수 상세가 시즌 기록에서 소속을 채웁니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.match(src, /team_id:\s*latestTeam\(/,
    '선수 상세가 players.team_id 를 그대로 내보내고 있습니다.');
});

test('선수 검색도 같은 규칙을 씁니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.ok(src.includes('LATEST_TEAM_SQL'),
    '검색이 players.team_id 만 봅니다. 상세와 값이 어긋납니다.');
  assert.ok(!/SELECT \* FROM players WHERE player_name LIKE/.test(src),
    '검색이 아직 players 만 읽습니다.');
});

test('가장 최근 시즌의 소속을 고릅니다', () => {
  const bat = [
    { season: 2016, player_team: '삼성' },
    { season: 2020, player_team: 'KIA' },
  ];
  assert.equal(latestTeam(bat, []), 'KIA');
});

test('타자와 투수를 합쳐서 가장 최근을 봅니다', () => {
  // 한쪽만 보면 두 가지를 다 한 선수의 소속이 엉뚱한 해로 잡힙니다.
  const bat = [{ season: 2018, player_team: '넥센' }];
  const pit = [{ season: 2024, player_team: '키움' }];
  assert.equal(latestTeam(bat, pit), '키움');
  assert.equal(latestTeam(pit, bat), '키움');
});

test('소속이 비어 있는 행은 건너뜁니다', () => {
  const bat = [
    { season: 2026, player_team: null },
    { season: 2025, player_team: 'LG' },
  ];
  assert.equal(latestTeam(bat, []), 'LG');
});

test('시즌이 문자열로 와도 숫자로 비교합니다', () => {
  // D1 은 숫자를 REAL 로 돌려주기도 하고, CSV 경로에서 문자열이 섞입니다.
  // 문자열로 비교하면 '9' > '10' 이 되어 옛 시즌이 이깁니다.
  const bat = [
    { season: '2009', player_team: '히어로즈' },
    { season: '2010', player_team: '넥센' },
  ];
  assert.equal(latestTeam(bat, []), '넥센');
});

test('기록이 없으면 null 입니다', () => {
  assert.equal(latestTeam([], []), null);
  assert.equal(latestTeam(null, undefined), null);
});
