// 시즌 기록 화면이 `players`(지금 명단)에 끌려가지 않게 지킵니다.
//
// 2015~2024 공식 기록을 넣기 전에는 문제가 드러나지 않았습니다. 한
// 시즌뿐이라 "지금 명단"과 "그 시즌 선수"가 같았기 때문입니다. 12시즌이
// 되면서 두 가지가 갈라집니다.
//
//   1. 이너 조인이면 명단에 없는 옛 선수가 순위에서 통째로 빠집니다.
//      2016 리더보드가 "그해 상위 5명"이 아니라 "지금도 명단에 남은
//      사람 중 상위 5명"이 됩니다. **비어 있는 것보다 나쁩니다.
//      틀렸는데 맞아 보입니다.**
//   2. 팀을 `players.team_id` 에서 가져오면 2016 기록에 2026 소속이
//      붙습니다. 은퇴 선수는 빈칸입니다. 시즌 중 트레이드된 선수는
//      올해 기록에서도 어긋납니다(2026 시즌에 실제로 있습니다).
//
// 그래서 이름과 팀은 기록 행에서 먼저 가져오고, 조인은 LEFT 로 둡니다.
import { test } from 'node:test';
import assert from 'node:assert';
import { readFileSync } from 'node:fs';

const FILES = ['src/routes/leaders.js', 'src/routes/stats.js'];

test('공식 기록에 players 를 이너 조인하지 않습니다', () => {
  const bad = [];
  for (const f of FILES) {
    readFileSync(f, 'utf8').split('\n').forEach((line, i) => {
      // 'LEFT JOIN players' 는 통과, 맨 'JOIN players' 는 걸립니다.
      if (/(?<!LEFT\s)JOIN players\b/.test(line)) {
        bad.push(`${f}:${i + 1}  ${line.trim()}`);
      }
    });
  }
  assert.deepEqual(bad, [], `옛 선수가 순위에서 사라집니다:\n${bad.join('\n')}`);
});

test('팀은 그 시즌 기록 행에서 먼저 가져옵니다', () => {
  for (const f of FILES) {
    const src = readFileSync(f, 'utf8');
    const uses = (src.match(/COALESCE\((?:b|ps)\.player_team,\s*p\.team_id\)/g)
      || []).length;
    assert.ok(uses >= 2,
      `${f} 에 시즌 팀 폴백이 ${uses}곳뿐입니다. 타자와 투수 둘 다 필요합니다.`);
  }
});

test('이름도 시즌 기록 행으로 물러설 수 있습니다', () => {
  for (const f of FILES) {
    const src = readFileSync(f, 'utf8');
    const uses = (src.match(
      /COALESCE\(p\.player_name,\s*(?:b|ps)\.player_name\)/g) || []).length;
    assert.ok(uses >= 2,
      `${f} 에 이름 폴백이 ${uses}곳뿐입니다. 타자와 투수 둘 다 필요합니다.`);
  }
});

test('팀 필터도 같은 값을 걸러야 합니다', () => {
  // 표시는 시즌 팀인데 필터는 명단 팀이면, 고른 팀과 다른 팀이 나옵니다.
  const src = readFileSync('src/routes/stats.js', 'utf8');
  assert.ok(!/teamIdsClause\([^,]+,\s*'p\.team_id'\)/.test(src),
    '팀 필터가 아직 명단 팀(p.team_id)을 봅니다.');
});
