// 선수 소속·현역 판정을 지킵니다.
//
// 2026-10-18 부터 지금 소속은 `players.team_id` 하나입니다. 네이버 수집
// (data_collection/naver_players.py)이 올 시즌 1군 기록의 팀, 없으면 네이버 선수
// 상세의 올해 소속(은퇴 아님), 그 밖에는 빈 값으로 정합니다(evan 결정).
//
// 예전에는 KBO 1군 등록 현황(kbo_roster)과 등번호로 판정했습니다. KBO 이용약관
// (2026-10-14 시행)으로 등록 현황을 받지 않아 그 표는 멈춘 옛 값이고, 네이버
// 등번호는 은퇴 선수에게도 마지막 번호가 남아 판정에 쓸 수 없습니다.
//
// 지금 소속이 없으면 마지막 시즌 기록의 팀을 내보내고 is_active 는 0 입니다.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { latestTeam, currentTeam } from '../src/routes/players.js';

test('선수 상세는 지금 소속, 없으면 마지막 시즌 기록의 팀을 냅니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.match(src, /team_id:\s*team \|\| latestTeam\(/);
  assert.match(src, /is_active:\s*team \? 1 : 0/);
});

test('선수 상세와 검색이 멈춘 KBO 등록 현황(kbo_roster)을 읽지 않습니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.ok(!/FROM kbo_roster/.test(src), 'players.js 가 아직 kbo_roster 를 읽습니다.');
});

test('선수 검색도 같은 규칙을 씁니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.ok(src.includes("COALESCE(NULLIF(TRIM(p.team_id), ''), (${LATEST_TEAM_SQL})) AS team_id"));
  assert.ok(src.includes("CASE WHEN NULLIF(TRIM(p.team_id), '') IS NOT NULL THEN 1 ELSE 0 END AS is_active"));
});

test('지금 소속은 빈 값이 아닌 team_id 입니다', () => {
  assert.equal(currentTeam({ team_id: '두산' }), '두산');
  assert.equal(currentTeam({ team_id: ' KT ' }), 'KT');
  assert.equal(currentTeam({ team_id: '' }), null);
  assert.equal(currentTeam({ team_id: null }), null);
  assert.equal(currentTeam(null), null);
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
