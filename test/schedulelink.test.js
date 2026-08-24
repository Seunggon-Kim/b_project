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
  assert.match(src, /if \(!name \|\| !code\) return null;/);
});

test('동명이인은 투수 한 명으로 좁혀질 때만 잇습니다', () => {
  const src = readFileSync(SRC, 'utf8');
  assert.match(src, /position \|\| ''\) === '투수'/);
  assert.match(src, /pitchers\.length === 1 \? pitchers\[0\]\.player_id : null/);
});

test('키 구분자는 이름에 못 들어가는 문자입니다', () => {
  // 공백을 쓰면 외국인 등록명에서 키가 어긋납니다.
  const src = readFileSync(SRC, 'utf8');
  assert.ok(src.includes("'\\u0000'"),
    '이름·팀 키에 NUL 구분자를 쓰지 않습니다.');
});
