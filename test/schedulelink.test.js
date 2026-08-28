// 일정 카드의 투수 이름이 선수 페이지로 이어지게 지킵니다.
//
// 카드의 투수 이름은 `이름 + 팀` 으로 players 를 뒤져 player_id 를
// 찾고, 찾은 것만 링크가 됩니다. 못 찾으면 그냥 글자로 나옵니다.
//
//     <span class="pp home">시라카와</span>
//
// 오류가 아니라 링크가 없는 것뿐이라 화면에서 눈에 잘 안 띕니다.
// 사용자가 "클릭이 안 되는 선수가 있다" 고 알려 주기 전에는 몰랐습니다.
//
// 원인은 `players.team_id` 였습니다. 아무 작업도 채우지 않는 컬럼이라
// 1,745명 중 1,160명이 비어 있고, 그 선수들은 이름+팀 키가 안 맞습니다.
//
//     곽빈      team_id 두산  -> 링크 됨
//     시라카와  team_id NULL  -> 안 됨
//     비슬리    team_id NULL  -> 안 됨
//
// 리더보드·기록실·선수 상세는 먼저 고쳤는데 일정 카드가 빠져 있었습니다.
// 네 번째가 나오지 않게 여기서 막습니다.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

const SRC = 'src/routes/schedule.js';

test('투수 짝짓기가 명단 소속만 보지 않습니다', () => {
  const src = readFileSync(SRC, 'utf8');
  assert.ok(src.includes('LATEST_TEAM_SQL'),
    '시즌 기록의 소속을 쓰지 않습니다. 소속이 빈 선수는 링크가 안 됩니다.');
  assert.match(src, /COALESCE\(\(\$\{LATEST_TEAM_SQL\}\), p\.team_id\)/,
    '시즌 소속을 먼저 쓰고 명단 소속으로 물러서야 합니다.');
});

test('players.team_id 를 그대로 키로 쓰지 않습니다', () => {
  const src = readFileSync(SRC, 'utf8');
  const bad = src.split('\n').filter((line, i) => {
    if (line.trim().startsWith('//')) return false;
    // `SELECT ... team_id ...` 에서 COALESCE 없이 뽑는 모양입니다.
    return /SELECT[^']*\bteam_id\b/.test(line) && !/COALESCE/.test(line);
  });
  assert.deepEqual(bad, [],
    `소속을 그대로 읽습니다:\n${bad.join('\n')}`);
});

test('이름과 팀이 다 있어야 짝짓습니다', () => {
  // 하나라도 없으면 엉뚱한 선수로 이어질 수 있습니다.
  const src = readFileSync(SRC, 'utf8');
  assert.match(src, /if \(!name \|\| !code\) return \[\];/);
});

test('동명이인은 투수 한 명으로 좁혀질 때만 잇습니다', () => {
  const src = readFileSync(SRC, 'utf8');
  assert.match(src, /position \|\| ''\) === '투수'/);
  assert.match(src, /if \(pitchers\.length === 1\) return pitchers\[0\]\.player_id;/);
});

// 같은 팀에 같은 이름 투수가 둘이면 포지션으로도 못 가립니다.
// 2026 기준 두 건입니다.
//
//     박준영 한화   52731(96번)  56709(68번)
//     이승현 삼성   51454(57번)  60146(20번)
//
// 여기서 아무나 고르면 절반은 남의 기록으로 보냅니다. 등번호를 보면
// 갈리고, 그 값은 네이버 relay 의 lineup 에 있습니다.
test('같은 팀 동명이인 투수는 등번호로 가립니다', () => {
  const src = readFileSync(SRC, 'utf8');
  assert.ok(src.includes('back_number'),
    '등번호를 읽지 않습니다. 같은 팀 동명이인을 못 가립니다.');
  assert.match(src, /pitcherBacknums/,
    'relay 에서 등번호를 가져오지 않습니다.');
  assert.match(src, /backnum/,
    'relay 응답의 backnum 을 읽지 않습니다.');
});

test('등번호를 봐도 모호하면 링크를 걸지 않습니다', () => {
  // 찍으면 절반이 틀립니다. 링크 없는 글자가 낫습니다.
  const src = readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n');
  const from = src.indexOf('function resolvePitcherId');
  const body = src.slice(from, src.indexOf('\n}\n', from));
  assert.match(body, /hit\.length === 1/,
    '등번호가 정확히 하나로 좁혀질 때만 이어야 합니다.');
  const last = body.split('\n').map((l) => l.trim())
    .filter((l) => l && !l.startsWith('//')).pop();
  assert.equal(last, 'return null;',
    `모호할 때 null 이 아니라 "${last}" 로 끝납니다.`);
});

// 등번호 조회는 **필요할 때만** 합니다. 하루 5경기면 매번 5번을 더
// 부르게 되는데, 그 값이 필요한 경기는 동명이인이 등판한 날뿐입니다.
test('등번호 조회는 모호한 경기에서만 합니다', () => {
  const src = readFileSync(SRC, 'utf8');
  assert.match(src, /needRelay/,
    '모든 경기에서 부르면 호출이 두 배가 됩니다.');
  assert.match(src, /candidatesOf\([^)]*\)\.length > 1/,
    '후보가 둘 이상일 때만 불러야 합니다.');
});

// 함수 이름을 바꾸면서 호출부를 안 고쳐 `relayBacknums is not defined`
// 로 죽을 뻔했습니다. 테스트가 문자열만 보고 있어서 못 잡았습니다.
// 선언과 호출이 실제로 이어지는지 봅니다.
test('부르는 함수가 실제로 선언돼 있습니다', () => {
  const src = readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n');
  const code = src.split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n');
  const declared = new Set(
    [...code.matchAll(/(?:async\s+)?function\s+([A-Za-z_$][\w$]*)/g)]
      .map((m) => m[1]),
  );
  const known = new Set([...declared,
    // 밖에서 들여오거나 표준으로 있는 것들입니다.
    'fetch', 'Promise', 'Map', 'Set', 'String', 'Boolean', 'Number',
    'JSON', 'Array', 'Object', 'URL', 'AbortSignal', 'Error', 'json',
    'ttlCache', 'kstToday', 'require', 'catch', 'if', 'for', 'while',
    'switch', 'return', 'filter', 'some', 'map', 'get', 'set', 'has',
  ]);
  const called = [...code.matchAll(/\b([A-Za-z_$][\w$]*)\s*\(/g)]
    .map((m) => m[1]);
  const missing = [...new Set(called)].filter(
    (n) => /Backnums|PitcherId|candidatesOf|pitcherPairsOf/.test(n)
      && !known.has(n),
  );
  assert.deepEqual(missing, [],
    `선언되지 않은 함수를 부릅니다: ${missing.join(', ')}`);
});

test('벤치 명단이 아니라 등판 명단에서 등번호를 읽습니다', () => {
  // homeEntry/awayEntry 는 backnum 이 null 입니다. 등판한 선수만
  // 번호가 있고, 우리가 풀 대상은 전부 등판한 선수입니다.
  const src = readFileSync(SRC, 'utf8').replace(/\r\n/g, '\n');
  // 주석은 뺍니다. 설명에 entry 를 적을 수 있습니다.
  const code = src.split('\n')
    .filter((l) => !l.trim().startsWith('//') && !l.trim().startsWith('*'))
    .join('\n');
  assert.match(code, /'homeLineup', 'awayLineup'/,
    'lineup 이 아니라 entry 를 읽으면 등번호가 전부 null 입니다.');
  assert.ok(!/\bhomeEntry\b|\bawayEntry\b/.test(code),
    'entry 는 backnum 이 없습니다.');
});

test('키 구분자는 이름에 못 들어가는 문자입니다', () => {
  // 공백을 쓰면 외국인 등록명에서 키가 어긋납니다.
  const src = readFileSync(SRC, 'utf8');
  assert.ok(src.includes("'\\u0000'"),
    '이름·팀 키에 NUL 구분자를 쓰지 않습니다.');
});
