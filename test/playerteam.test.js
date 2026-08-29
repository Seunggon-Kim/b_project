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
import { latestTeam, isActive, rosterDecides } from '../src/routes/players.js';

test('선수 상세가 시즌 기록에서 소속을 채웁니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  // `team_id:` 다음에 latestTeam 이 와야 합니다. 그 앞에 1군 등록
  // 현황(roster)이 먼저 올 수는 있습니다. 그쪽이 더 최신입니다.
  assert.match(src, /team_id:[\s\S]{0,140}latestTeam\(/,
    '선수 상세가 players.team_id 를 그대로 내보내고 있습니다.');
  // players.team_id 는 마지막 폴백으로만 남아야 합니다.
  assert.doesNotMatch(src, /team_id:\s*player\.team_id/,
    '선수 상세가 players.team_id 를 먼저 봅니다.');
});

test('소속은 1군 등록 현황을 가장 먼저 봅니다', () => {
  // daily 가 매일 새로 받는 값이라 시즌 중 이적이 바로 반영됩니다.
  // 기록의 소속은 그 시즌 것이라 한 박자 늦습니다.
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.match(src, /team_id:\s*\(roster && roster\.team\)/,
    '소속이 아직 기록만 봅니다.');
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

// --- is_active ---------------------------------------------------------
//
// `players` 표에 `is_active` 컬럼이 없습니다. 원본에는 있었는데 D1 으로
// 옮길 때 넘어오지 않았습니다. 화면은 다섯 곳에서 이 값을 보는데 전부
// undefined 를 받아 **모든 선수를 은퇴 선수로 취급**했습니다. 소속도
// 등번호도 팀 색도 안 나왔습니다. 컬럼이 없다는 것만으로는 아무 데서도
// 오류가 나지 않아, 화면을 직접 보기 전에는 알 수 없었습니다.

test('가장 최근 시즌에 기록이 있으면 현역입니다', () => {
  assert.equal(isActive([{ season: 2026 }], [], 2026), true);
  assert.equal(isActive([], [{ season: 2026 }], 2026), true);
});

test('마지막 기록이 옛 시즌이면 비현역입니다', () => {
  assert.equal(isActive([{ season: 2021 }], [], 2026), false);
});

test('타자와 투수 중 한쪽만 최신이어도 현역입니다', () => {
  assert.equal(isActive([{ season: 2019 }], [{ season: 2026 }], 2026), true);
});

test('시즌이 문자열이어도 숫자로 비교합니다', () => {
  assert.equal(isActive([{ season: '2026' }], [], 2026), true);
  assert.equal(isActive([{ season: '999' }], [], 2026), false);
});

test('기준 시즌을 모르면 현역이라고 하지 않습니다', () => {
  // 빈 DB 에서 전원을 현역으로 칠하는 쪽이 더 나쁩니다.
  assert.equal(isActive([{ season: 2026 }], [], null), false);
});

test('기록이 없으면 비현역입니다', () => {
  assert.equal(isActive([], [], 2026), false);
  assert.equal(isActive(null, undefined, 2026), false);
});

test('상세와 검색 둘 다 is_active 를 내려줍니다', () => {
  const src = readFileSync('src/routes/players.js', 'utf8');
  assert.match(src, /is_active:\s*isActive\(/, '상세가 is_active 를 안 줍니다.');
  assert.ok(src.includes('AS is_active'), '검색이 is_active 를 안 줍니다.');
});

// --- 1군 등록 현황으로 현역 판정을 보완합니다 -----------------------
//
// `isActive` 는 "올 시즌 기록이 있나" 로만 봤습니다. 그래서 올해 아직
// 한 경기도 안 뛴 선수가 비현역으로 잡혔습니다. 화면은 비현역이면
// 소속을 '-' 로 쓰고 팀 색도 입히지 않습니다.
//
// 실제로 이재학(60263)이 그랬습니다. 1군 등록 배지는 붙어 있는데
// 바로 옆 소속은 '-' 이고 배경이 기본 남색이었습니다. 한 화면에서
// 두 값이 서로 어긋나 보입니다.
//
// `kbo_roster` 는 KBO 1군 등록 현황을 daily 가 매일 새로 받습니다.
// **거기 있으면 지금 1군에 있는 선수입니다.** 기록보다 확실합니다.

test('1군 등록 현황에 있으면 올 시즌 기록이 없어도 현역입니다', () => {
  const roster = { team: 'NC', back_number: '39' };
  assert.equal(isActive([{ season: 2024 }], [], 2026, roster), true);
  assert.equal(isActive([], [], 2026, roster), true);
});

test('등록 현황이 없으면 예전과 같이 기록으로 봅니다', () => {
  assert.equal(isActive([{ season: 2026 }], [], 2026, null), true);
  assert.equal(isActive([{ season: 2021 }], [], 2026, null), false);
  // 표가 아직 없는 환경에서는 undefined 로 옵니다.
  assert.equal(isActive([{ season: 2021 }], [], 2026), false);
});

test('현재 시즌을 모르면 등록 현황만으로도 현역입니다', () => {
  // current 가 null 이면 기록으로는 판정할 수 없습니다. 그래도 1군에
  // 등록돼 있으면 현역인 것은 분명합니다.
  assert.equal(isActive([{ season: 2026 }], [], null, { team: 'LG' }), true);
  assert.equal(isActive([{ season: 2026 }], [], null, null), false);
});

// --- 소속은 오늘 구단 명단으로 판정합니다 ---------------------------
//
// 기준이 화면마다 달랐습니다. 1군 화면은 "올 시즌 기록이 있나" 로 봐서
// 방출된 선수도 현역으로 잡혔습니다. 타무라(56218)는 계약이 끝났는데
// 올 시즌 1군 기록(17경기)이 있어 두산 소속으로 나왔습니다.
//
// 이제 `kbo_roster` 가 1군과 퓨처스 명단을 함께 담습니다(628명).
// 거기 있으면 구단 소속이고, 없으면 무소속입니다.
//
// **명단을 못 받은 날을 대비합니다.** 수집이 실패해 표가 비면 전원이
// 무소속이 됩니다. 그건 사고입니다. 명단이 너무 작으면 예전처럼
// 기록으로 판정합니다.

test('명단이 정상이면 명단으로 판정합니다', () => {
  assert.equal(rosterDecides(628), true);
  assert.equal(rosterDecides(300), true);
});

test('명단이 너무 작으면 기록으로 돌아갑니다', () => {
  // 정상이면 600명대입니다. 수집이 반쯤 실패한 날을 거릅니다.
  assert.equal(rosterDecides(0), false);
  assert.equal(rosterDecides(50), false);
  assert.equal(rosterDecides(null), false);
  assert.equal(rosterDecides(undefined), false);
});

test('명단이 정상이면 기록이 있어도 명단에 없으면 비현역입니다', () => {
  // 타무라의 경우입니다.
  assert.equal(isActive([{ season: 2026 }], [], 2026, null, 628), false);
});

test('명단이 정상이면 기록이 없어도 명단에 있으면 현역입니다', () => {
  assert.equal(isActive([], [], 2026, { team: '삼성' }, 628), true);
});

test('명단을 못 믿으면 예전처럼 기록으로 봅니다', () => {
  assert.equal(isActive([{ season: 2026 }], [], 2026, null, 0), true);
  assert.equal(isActive([{ season: 2020 }], [], 2026, null, 0), false);
});

// --- 명단에 없어도 등번호가 있으면 소속입니다 -----------------------
//
// 명단만 보면 **부상으로 빠진 선수가 무소속이 됩니다.** 힐리어드
// (56034)는 부상으로 1군에서 내려갔고 2군 명단에도 없는데 KT 소속
// 입니다. 재활 중이라 어느 명단에도 안 잡힙니다.
//
// 계약 여부를 가르는 것은 **등번호**입니다. KBO 는 계약이 끝나면
// 등번호 자리를 비웁니다.
//
//     힐리어드  등번호 34    명단 없음  -> KT 소속 (부상 이탈)
//     타무라    등번호 없음  명단 없음  -> 무소속 (계약 종료)
//     미야지    등번호 없음  명단 없음  -> 무소속 (계약 종료)
//
// 명단은 "오늘 어디에 있나"(1군/2군), 등번호는 "계약이 있나" 입니다.
// 둘은 다른 질문입니다.

test('오늘 명단에 있으면 현역입니다', () => {
  assert.equal(isActive([], [], 2026, { team: 'KT' }, 628, null), true);
});

test('명단에 없어도 등번호가 있으면 현역입니다', () => {
  // 부상·재활로 잠시 빠진 선수입니다.
  assert.equal(isActive([], [], 2026, null, 628, '34'), true);
  assert.equal(isActive([], [], 2026, null, 628, 34), true);
});

test('등번호 0 과 00 도 등번호입니다', () => {
  // players.back_number 는 INTEGER 라 '00' 이 0 이 됩니다. 값이
  // 있는지만 봐야 합니다. 0 을 거짓으로 읽으면 두 선수가 사라집니다.
  assert.equal(isActive([], [], 2026, null, 628, 0), true);
  assert.equal(isActive([], [], 2026, null, 628, '00'), true);
});

test('등번호도 없고 명단에도 없으면 무소속입니다', () => {
  assert.equal(isActive([{ season: 2026 }], [], 2026, null, 628, null), false);
  assert.equal(isActive([{ season: 2026 }], [], 2026, null, 628, ''), false);
});
