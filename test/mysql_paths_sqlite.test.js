// CPU 를 줄이려고 MySQL 에서만 다르게 읽는 곳(/stats/batters·pitchers)이
// D1 길과 같은 응답을 내는지 SQLite 로 봅니다.
//
// 같은 SQLite 표에 대고 env.DB_BACKEND 만 바꿔 두 길을 돌립니다. MySQL 길의
// SQL(창 함수 ROW_NUMBER, JSON_ARRAY)은 SQLite 도 받습니다.
// SQLite 와 MySQL 의 정렬·숫자 글자 차이는 여기서 보지 않고, 실제 MySQL 은
// 스테이징 ↔ 운영 응답 대조(scripts/api_compare.mjs)로 확인합니다. 이 시험은
// 두 길의 JS 조립(행 순서·열 순서·이름 겹침)이 같은지 봅니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

import {
  statsBatters, statsPitchers, BATTER_STAT_COLUMNS, PITCHER_STAT_COLUMNS,
} from '../src/routes/stats.js';

/**
 * MySQL 만 받는 GROUP_CONCAT 문법을 SQLite 문법으로 바꿉니다(시험에서만).
 * `GROUP_CONCAT(x ORDER BY y SEPARATOR ',')` -> `group_concat(x, ',' ORDER BY y)`.
 * SET_VAR 힌트(/*+ ... *\/)는 SQLite 에서 주석입니다.
 */
function sqliteDialect(sql) {
  return sql.replace(/GROUP_CONCAT\((.+?) ORDER BY (.+?) SEPARATOR ','\)/g, "group_concat($1, ',' ORDER BY $2)");
}

/** node:sqlite 를 D1 처럼(prepare/bind/all/first/raw) 감쌉니다. */
function d1(sqlite) {
  return {
    prepare(rawSql) {
      const sql = sqliteDialect(rawSql);
      let params = [];
      return {
        bind(...p) { params = p; return this; },
        async all() { return { results: sqlite.prepare(sql).all(...params).map((r) => ({ ...r })) }; },
        async first() {
          const r = sqlite.prepare(sql).get(...params);
          return r ? { ...r } : null;
        },
        async raw() { return sqlite.prepare(sql).all(...params).map((r) => Object.values(r)); },
      };
    },
  };
}

/** migration/mysql/schema.sql 의 CREATE TABLE 열 (이름, 형) 목록입니다. */
function ddlColumns(table) {
  const sql = readFileSync(new URL('../migration/mysql/schema.sql', import.meta.url), 'utf8');
  const start = sql.indexOf(`CREATE TABLE \`${table}\` (`);
  assert.ok(start >= 0, table);
  const body = sql.slice(start, sql.indexOf(') ENGINE', start));
  return [...body.matchAll(/^\s+`([^`]+)`\s+([A-Z]+)/gm)].map((m) => ({ name: m[1], type: m[2] }));
}

function sqliteType(t) {
  if (t === 'INT' || t === 'BIGINT') return 'INTEGER';
  if (t === 'DOUBLE') return 'REAL';
  return 'TEXT';
}

test('시즌 기록 열 목록은 schema.sql 의 CREATE TABLE 순서와 같습니다', () => {
  assert.deepEqual(BATTER_STAT_COLUMNS, ddlColumns('kbo_official_batter_stats').map((c) => c.name));
  assert.deepEqual(PITCHER_STAT_COLUMNS, ddlColumns('kbo_official_pitcher_stats').map((c) => c.name));
});

const SEASONS = [2024, 2025];

function fixture() {
  const db = new DatabaseSync(':memory:');
  // MySQL 길의 tableExists 는 information_schema.tables 와 DATABASE() 를 봅니다.
  db.function('DATABASE', () => 'main');
  db.exec("ATTACH ':memory:' AS information_schema");
  db.exec('CREATE TABLE information_schema.tables (table_schema TEXT, table_name TEXT, table_type TEXT)');
  const batterCols = ddlColumns('kbo_official_batter_stats');
  const pitcherCols = ddlColumns('kbo_official_pitcher_stats');
  // D1 처럼 선수 ID 는 TEXT 입니다.
  const colDdl = (cols) => cols.map((c) => `"${c.name}" ${c.name === 'player_id' ? 'TEXT' : sqliteType(c.type)}`).join(', ');
  db.exec(`
    CREATE TABLE players (player_id TEXT, player_name TEXT, team_id TEXT, position TEXT);
    CREATE TABLE kbo_official_batter_stats (${colDdl(batterCols)});
    CREATE TABLE kbo_official_pitcher_stats (${colDdl(pitcherCols)});
    CREATE TABLE wrc_plus_comparison (batter_ID INTEGER, season INTEGER, PA INTEGER, wOBA REAL,
      wRAA_FG REAL, wRC_home REAL, wRC_half REAL, wRC_weighted REAL);
    CREATE TABLE games (game_id TEXT, season INTEGER);
  `);
  for (const t of ['players', 'kbo_official_batter_stats', 'kbo_official_pitcher_stats', 'wrc_plus_comparison', 'games']) {
    db.prepare("INSERT INTO information_schema.tables VALUES ('main', ?, 'BASE TABLE')").run(t);
  }

  let seed = 7;
  const rnd = () => {
    seed = (seed * 1103515245 + 12345) % 2147483648;
    return seed / 2147483648;
  };
  const pick = (a) => a[Math.floor(rnd() * a.length)];
  // 동점이 생기도록 값을 몇 개로 묶습니다. NULL 도 섞습니다.
  const avg = [0.25, 0.3, 0.333, 0.3, 0.275, null];
  const insP = db.prepare('INSERT INTO players VALUES (?, ?, ?, ?)');
  for (let i = 0; i < 70; i += 1) {
    if (i % 9 === 0) continue; // 명단에 없는 옛 선수
    insP.run(String(70000 + i), `선수${i}`, pick(['HT', 'LG', null]), pick(['내야수', '외야수', null]));
  }
  for (const season of SEASONS) {
    seed = 7; // 두 시즌에 같은 값을 넣습니다(leaders 의 시즌 캐시를 피하려고 시즌만 다르게 씁니다).
    for (let i = 0; i < 70; i += 1) {
      const v = {};
      for (const c of batterCols) {
        if (c.type === 'INT') v[c.name] = Math.floor(rnd() * 600);
        else if (c.type === 'DOUBLE') v[c.name] = pick(avg);
        else v[c.name] = pick(['a', 'b', null]);
      }
      Object.assign(v, {
        player_id: String(70000 + i), season, player_name: `기록${i}`,
        player_team: pick(['KIA', 'LG', null]), games: 100 + (i % 44),
        created_at: '2026-10-04 03:12:45', updated_at: pick(['2026-10-04 09:00:01', null]),
      });
      db.prepare(`INSERT INTO kbo_official_batter_stats VALUES (${batterCols.map(() => '?').join(', ')})`)
        .run(...batterCols.map((c) => v[c.name]));
    }
    for (let i = 0; i < 60; i += 1) {
      const v = {};
      for (const c of pitcherCols) {
        if (c.type === 'INT') v[c.name] = Math.floor(rnd() * 200);
        else if (c.type === 'DOUBLE') v[c.name] = pick([1.5, 2.25, 3.875, 4.5, null]);
        else v[c.name] = pick(['x', null]);
      }
      // K%·BB% 가 짧은 소수가 되도록 상대타자 수를 고릅니다(SQLite 의 실수 글자는 15자리라서).
      Object.assign(v, {
        player_id: String(70000 + i), season, player_name: `투수${i}`,
        player_team: pick(['두산', '키움', null]), innings_pitched: pick(['68 1/3', '144', '12 2/3', ' 150 ', '0', null]),
        total_batters_faced: pick([0, 50, 80, 100, 125, 160, 200, 400]), strikeout: Math.floor(rnd() * 50),
        base_on_balls: Math.floor(rnd() * 30), earned_run_average: pick([2.5, 3.25, null, 4.125, 2.5]),
        created_at: '2026-10-04 03:12:45', updated_at: null,
      });
      db.prepare(`INSERT INTO kbo_official_pitcher_stats VALUES (${pitcherCols.map(() => '?').join(', ')})`)
        .run(...pitcherCols.map((c) => v[c.name]));
    }
    for (let i = 0; i < 70; i += 1) {
      db.prepare('INSERT INTO wrc_plus_comparison VALUES (?, ?, ?, ?, ?, ?, ?, ?)').run(
        70000 + i, season, Math.floor(rnd() * 600), pick([0.35, 0.4, 0.375, null]),
        pick([1.5, -2.25]), pick([100, 110.5]), pick([120.25, 99.5, 120.25, 87]), pick([101, 130.75]),
      );
    }
    for (let g = 0; g < 720; g += 1) db.prepare('INSERT INTO games VALUES (?, ?)').run(`${season}-${g}`, season);
  }
  return d1(db);
}

const DB = fixture();
const MY = { DB, DB_BACKEND: 'mysql' };
const D1 = { DB };

// MySQL 길이 한 칸(GROUP_CONCAT) 읽기에 실패해 행마다 읽기로 물러서면 경고를
// 남깁니다. 이 시험에서는 물러서지 않아야 합니다(물러서도 응답은 같아 비교만으로는
// 모릅니다).
const warnings = [];
console.warn = (...a) => warnings.push(a.join(' '));
test.afterEach(() => assert.deepEqual(warnings.splice(0), []));

test('stats: MySQL 의 JSON 배열 길이 D1 의 b.*·ps.* 질의와 같은 응답(열 순서·이름 겹침 포함)을 냅니다', async () => {
  const urls = [
    ['batters', '?season=2025&limit=-1'],
    ['batters', '?season=2024&limit=10&min_pa=100'],
    ['batters', '?season=2025&limit=30&team_ids=KIA,LG'],
    ['pitchers', '?season=2025&limit=-1'],
    ['pitchers', '?season=2024&limit=20&min_ip=10&team_ids=두산'],
  ];
  for (const [kind, q] of urls) {
    const fn = kind === 'batters' ? statsBatters : statsPitchers;
    const a = await (await fn(new Request(`https://x/stats/${kind}${q}`), MY)).text();
    const b = await (await fn(new Request(`https://x/stats/${kind}${q}`), D1)).text();
    assert.equal(a, b, `${kind}${q}`);
    assert.ok(JSON.parse(a)[kind].length > 0, `${kind}${q}`);
  }
});
