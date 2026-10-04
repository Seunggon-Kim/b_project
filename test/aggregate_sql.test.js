// 타석·공을 DB 에서 세어(GROUP BY … COUNT) 받는 두 라우트(team_range, usage)가
// 예전(행을 하나씩 받아 JS 로 세던) 결과와 같은지 SQLite 로 확인합니다.
//
// D1 은 SQLite 라 이 시험이 곧 D1 길의 확인입니다. MySQL 길은 스테이징과
// 운영의 응답 대조(scripts/api_compare.mjs)로 확인합니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { DatabaseSync } from 'node:sqlite';

import { statsTeamRange, accumulatePa, buildTeamRange } from '../src/routes/teamrange.js';
import { playerUsage, summarizeUsage } from '../src/routes/players.js';
import { SHARDS } from '../src/lib/shard.js';

/** node:sqlite 를 D1 처럼(prepare/bind/all/first) 감쌉니다. */
function d1(sqlite) {
  return {
    prepare(sql) {
      let params = [];
      return {
        bind(...p) { params = p; return this; },
        async all() { return { results: sqlite.prepare(sql).all(...params).map((r) => ({ ...r })) }; },
        async first() {
          const r = sqlite.prepare(sql).get(...params);
          return r ? { ...r } : null;
        },
      };
    },
  };
}

function fixture() {
  const db = new DatabaseSync(':memory:');
  db.exec(`
    CREATE TABLE games (game_id TEXT, home_team_id TEXT, away_team_id TEXT,
                        game_date INTEGER, game_type TEXT);
    CREATE TABLE play_by_play (pbp_id INTEGER PRIMARY KEY, gameID TEXT, game_date INTEGER,
                        pitcher_ID TEXT, inning_topbot TEXT, pa_result TEXT, outs_on_play INTEGER,
                        runs_scored INTEGER, pitch_type TEXT, stands TEXT, throws TEXT);
    CREATE TABLE players (player_id TEXT, player_name TEXT);
    INSERT INTO players VALUES ('100', '투수');
  `);
  const games = [
    ['G1', 'HT', 'LG', 20250401, '정규시즌'],
    ['G2', 'LG', 'SS', 20250402, '정규시즌'],
    ['G3', 'SS', 'HT', 20250403, '정규시즌'],
    ['G4', 'HT', 'SS', 20250404, '포스트시즌'],
  ];
  const ins = db.prepare('INSERT INTO games VALUES (?, ?, ?, ?, ?)');
  for (const g of games) ins.run(...g);
  // 결과 분류가 겹치지 않도록 대소문자·공백만 다른 값도 넣습니다(바이트로 묶어야 합니다).
  const results = ['안타', '2루타', '홈런', '볼넷', '고의4구', '고의 4구', '삼진', '낫아웃 출루',
    '필드 아웃', '희생플라이', '희생번트', '몸에 맞는 볼', '실책', 'X', 'x', '', null];
  const types = ['직구', '슬라이더', '커브', '체인지업', '-', '', null, 'Null'];
  const sides = ['좌', '우', '양', '', null];
  const pin = db.prepare('INSERT INTO play_by_play (gameID, game_date, pitcher_ID, inning_topbot, '
    + 'pa_result, outs_on_play, runs_scored, pitch_type, stands, throws) VALUES (?,?,?,?,?,?,?,?,?,?)');
  let k = 0;
  for (const g of games) {
    for (let i = 0; i < 120; i += 1) {
      k += 1;
      pin.run(g[0], g[3], k % 3 ? '100' : '200', [null, '초', '말'][k % 3], results[(k * 7) % results.length],
        k % 3, k % 5 === 0 ? 1 : 0, types[(k * 5) % types.length], sides[(k * 3) % sides.length],
        sides[(k * 11) % sides.length]);
    }
  }
  const env = { DB: d1(db) };
  for (const s of SHARDS) env[s.binding] = env.DB;
  return { db, env };
}

test('team_range: DB 에서 센 타석 집계가 행별 집계와 같습니다(D1)', async () => {
  const { db, env } = fixture();
  const res = await statsTeamRange(new Request('https://x/stats/team_range?start=2025-04-01&end=2025-04-30'), env);
  const body = await res.json();

  // 예전 방식: 타석 행을 하나씩 받아 셉니다.
  const teams = new Map();
  for (const g of db.prepare("SELECT home_team_id, away_team_id FROM games WHERE game_type='정규시즌'").all()) {
    for (const t of [g.home_team_id, g.away_team_id]) {
      if (!teams.has(t)) teams.set(t, null);
    }
  }
  const rows = db.prepare(
    'SELECT p.inning_topbot, p.pa_result, gm.home_team_id, gm.away_team_id '
    + 'FROM play_by_play p JOIN games gm ON gm.game_id = p.gameID '
    + "WHERE gm.game_type='정규시즌' AND p.pa_result IS NOT NULL AND p.pa_result<>''",
  ).all().map((r) => ({ ...r }));
  assert.ok(rows.length > 100);
  const expected = accumulatePa(new Map(), rows);
  const want = buildTeamRange(expected);
  // 실점·아웃·경기 수는 바꾸지 않은 질의라 비교에서 뺍니다.
  const strip = (list, keys) => list.map((x) => Object.fromEntries(keys.map((key) => [key, x[key]])))
    .sort((a, b) => (a.team < b.team ? -1 : 1));
  const BAT = ['team', 'PA', 'AB', 'H', '2B', '3B', 'HR', 'BB', 'HBP', 'SO', 'SH', 'SF', 'TB'];
  const PIT = ['team', 'H', 'BB', 'SO', 'HR', 'AB_against'];
  assert.deepEqual(strip(body.batting, BAT), strip(want.batting, BAT));
  assert.deepEqual(strip(body.pitching, PIT), strip(want.pitching, PIT));
});

test('usage: DB 에서 센 구사율이 공별 집계와 같습니다(D1)', async () => {
  const { db, env } = fixture();
  const res = await playerUsage(new Request('https://x/players/100/usage?season=2025'), env, {}, { id: '100' });
  const body = await res.json();

  const rows = db.prepare(
    'SELECT pitch_type, stands, throws FROM play_by_play WHERE pitcher_ID = ? '
    + 'AND game_date >= 20250000 AND game_date < 20260000 '
    + "AND pitch_type IS NOT NULL AND pitch_type NOT IN ('', '-', 'null')",
  ).all('100').map((r) => ({ ...r }));
  assert.ok(rows.length > 50);
  const { result, totalAll, totalL, totalR } = summarizeUsage(rows);
  assert.deepEqual(body, {
    player_id: '100', total_pitches: totalAll, total_l: totalL, total_r: totalR, usage: result,
  });
});

test('accumulatePa 는 n 만큼 셉니다(n 이 글자여도)', () => {
  const one = { inning_topbot: '초', pa_result: '홈런', home_team_id: 'H', away_team_id: 'A' };
  const a = accumulatePa(new Map(), [one, one, one]);
  const b = accumulatePa(new Map(), [{ ...one, n: 3 }]);
  const c = accumulatePa(new Map(), [{ ...one, n: '3' }]);
  assert.deepEqual(b, a);
  assert.deepEqual(c, a);
});
