import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// 정렬 값이 같을 때(동점) 행 순서가 DB 엔진마다 달라지지 않도록,
// ORDER BY 의 마지막 키로 유일한 값을 둡니다. 이 시험은 그 꼬리표가
// 소스에서 빠지지 않았는지 글자로 확인합니다.
// 키 앞뒤의 공백·줄바꿈 차이는 무시합니다.

const read = (f) => readFileSync(new URL(`../src/routes/${f}`, import.meta.url), 'utf8')
  .replace(/\s+/g, ' ');

// [파일, 조각] : 조각이 소스에 그대로 들어 있어야 합니다.
const GUARDS = [
  ['games.js', 'ORDER BY g.game_date DESC, g.game_id LIMIT ?'],
  // Top5 순위는 창 함수(ROW_NUMBER)의 ORDER BY 가 매깁니다(batterTopsOnce·wrcTopsOnce).
  ['leaders.js', '`ROW_NUMBER() OVER (ORDER BY b.${c} DESC, b.player_id) AS r${i}`'],
  ['leaders.js', "'ROW_NUMBER() OVER (ORDER BY w.wRC_half DESC, w.batter_ID) AS r0, '"],
  ['leaders.js', "'ROW_NUMBER() OVER (ORDER BY w.wOBA DESC, w.batter_ID) AS r1 '"],
  ['leaders.js', "WHERE ps.season=? ORDER BY ps.player_id'"],
  ['players.js', 'ORDER BY season DESC, player_team LIMIT 1`'],
  ['players.js', "FROM kbo_official_batter_stats WHERE player_id = ? ORDER BY season DESC, player_team'"],
  ['players.js', "FROM kbo_official_pitcher_stats WHERE player_id = ? ORDER BY season DESC, player_team'"],
  ['players.js', 'WHERE p.player_name LIKE ? ORDER BY p.player_name, p.player_id LIMIT 50'],
  ['futuresplayer.js', 'ORDER BY season DESC, player_team LIMIT 1) AS stats_team'],
  ['futuresplayer.js', 'WHERE player_id = ? AND kind = ? ORDER BY season DESC, team\''],
  ['roster.js', "'ORDER BY kind DESC, team, name LIMIT ?'"],
  ['roster.js', "'ORDER BY move_date DESC, kind DESC, team, name LIMIT ?'"],
  ['roster.js', 'CAST(back_number AS SIGNED), name, player_id"'],
  // 행을 고르는 ORDER BY 와 한 칸으로 잇는 ROW_NUMBER(lib/jsonrows.js)가 같은 ORDER 를 씁니다.
  ['stats.js', "const ORDER = 'b.batting_average DESC, b.player_id';"],
  ['stats.js', "const ORDER = 'ps.earned_run_average ASC, ps.player_id';"],
  ['stats.js', 'ORDER BY ${ORDER} LIMIT ?'],
  ['teamrecord.js', 'ORDER BY r.season DESC, r.league, r.team_name`'],
  ['teamrecord.js', "ORDER BY season, team_name'"],
  ['teamrecord.js', "ORDER BY s.season, s.stadium'"],
  ['teamrecord.js', "ORDER BY c.season, c.team_name'"],
  ['teams.js', "'SELECT * FROM teams ORDER BY team_name, team_id'"],
  ['teams.js', 'ORDER BY ts.team_name, ts.franchise_id'],
  ['wrc.js', 'ORDER BY mean_half DESC, wpf.home_stadium, sd.primary_team'],
  ['wrc.js', 'ORDER BY ${sortCol} DESC, wrc.batter_ID LIMIT ?'],
  ['wrc.js', 'ORDER BY (wrc.wRC_weighted - wrc.wRC_half) ${order}, wrc.batter_ID LIMIT ?'],
  ['wrc.js', 'ORDER BY season, pa DESC, stadium'],
  ['wrc.js', "ORDER BY b.season DESC, b.player_name, b.player_id, b.player_team LIMIT 50'"],
];

for (const [file, frag] of GUARDS) {
  test(`${file}: 동점 꼬리표 ${frag.slice(0, 50)}`, () => {
    assert.ok(read(file).includes(frag.replace(/\s+/g, ' ')),
      `${file} 에서 찾지 못했습니다: ${frag}`);
  });
}

test('구사율 동률은 구종 이름으로 고정합니다', () => {
  assert.match(read('players.js'), /usage_all - a\.usage_all\) \|\| \(a\.pitch_type < b\.pitch_type/);
});

test('팀 기록 정렬 동률은 팀 코드로 고정합니다', () => {
  const s = read('teamrange.js');
  assert.match(s, /\|\| cmpTeam\(a, b\)/g);
  assert.equal(s.match(/\|\| cmpTeam\(a, b\)/g).length, 2);
});
