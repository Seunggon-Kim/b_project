// CPU 를 줄이려고 한 번에 묶어 읽는 세 곳(leaders, /wrc/seasons,
// /stats/batters·pitchers)이 예전 보통 질의(D1 시절 질의)와 같은 응답을 내는지
// SQLite 로 봅니다.
//
// 예전 질의는 라우트에서 지웠고(D1 을 걷어냄) 이 시험 안에 기준으로 남겨
// 둡니다. 같은 SQLite 표에 대고 라우트(묶어 읽기)와 기준 질의를 돌려 견줍니다.
// 묶어 읽는 SQL(창 함수 ROW_NUMBER, UNION ALL, JSON_ARRAY)은 SQLite 도 받습니다.
// SQLite 와 MySQL 의 정렬·숫자 글자 차이는 여기서 보지 않고, 실제 MySQL 은
// 스테이징 ↔ 운영 응답 대조(scripts/api_compare.mjs)로 확인합니다. 이 시험은
// JS 조립(순위 꺼내기·열 순서·이름 겹침·시즌별 나누기)이 같은지 봅니다.
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { DatabaseSync } from 'node:sqlite';

import {
  leaders, batterTopsOnce, wrcTopsOnce, BATTER_TOP_COLUMNS, pyRound,
} from '../src/routes/leaders.js';
import { wrcSeasons, deltasBySeason, stdDelta } from '../src/routes/wrc.js';
import {
  statsBatters, statsPitchers, BATTER_STAT_COLUMNS, PITCHER_STAT_COLUMNS,
} from '../src/routes/stats.js';
import { jsonRowsOnce } from '../src/lib/jsonrows.js';

/**
 * MySQL 만 받는 GROUP_CONCAT 문법을 SQLite 문법으로 바꿉니다(시험에서만).
 * `GROUP_CONCAT(x ORDER BY y SEPARATOR ',')` -> `group_concat(x, ',' ORDER BY y)`.
 * SET_VAR 힌트(/*+ ... *\/)는 SQLite 에서 주석입니다.
 */
function sqliteDialect(sql) {
  return sql.replace(/GROUP_CONCAT\((.+?) ORDER BY (.+?) SEPARATOR ','\)/g, "group_concat($1, ',' ORDER BY $2)");
}

/** node:sqlite 를 어댑터(lib/mysqldb.js)처럼(prepare/bind/all/first/raw) 감쌉니다. */
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
  // tableExists 는 information_schema.tables 와 DATABASE() 를 봅니다.
  db.function('DATABASE', () => 'main');
  db.exec("ATTACH ':memory:' AS information_schema");
  db.exec('CREATE TABLE information_schema.tables (table_schema TEXT, table_name TEXT, table_type TEXT)');
  const batterCols = ddlColumns('kbo_official_batter_stats');
  const pitcherCols = ddlColumns('kbo_official_pitcher_stats');
  // D1 시절처럼 선수 ID 는 TEXT 입니다.
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
const MY = { MYSQL: DB };

// 한 칸(GROUP_CONCAT) 읽기에 실패해 행마다 읽기로 물러서면 경고를
// 남깁니다. 이 시험에서는 물러서지 않아야 합니다(물러서도 응답은 같아 비교만으로는
// 모릅니다).
const warnings = [];
console.warn = (...a) => warnings.push(a.join(' '));
test.afterEach(() => assert.deepEqual(warnings.splice(0), []));

// 예전(D1) leaders 의 타자 Top5 질의입니다. 지표마다 하나씩 보냈습니다.
function plainBatterTop(col, season, qual) {
  return DB.prepare(
    'SELECT b.player_id AS player_id, COALESCE(p.player_name, b.player_name) AS name, '
    + 'COALESCE(b.player_team, p.team_id) AS team, b.' + col + ' AS val '
    + 'FROM kbo_official_batter_stats b LEFT JOIN players p ON b.player_id=p.player_id '
    + 'WHERE b.season=? AND b.plate_appearance >= ? '
    + 'ORDER BY b.' + col + ' DESC, b.player_id LIMIT 5',
  ).bind(season, qual).all();
}

// 예전(D1) leaders 의 wRC+·wOBA Top5 질의입니다.
function plainWrcTop(col, digits, alias, season, qual) {
  return DB.prepare(
    'SELECT CAST(w.batter_ID AS CHAR) AS player_id, '
    + 'COALESCE(b.player_name, p.player_name) AS name, '
    + 'COALESCE(b.player_team, p.team_id) AS team, '
    + 'ROUND(w.' + col + ', ' + digits + ') AS ' + alias + ' '
    + 'FROM wrc_plus_comparison w '
    + 'LEFT JOIN players p ON p.player_id = CAST(w.batter_ID AS CHAR) '
    + 'LEFT JOIN kbo_official_batter_stats b '
    + 'ON b.player_id = CAST(w.batter_ID AS CHAR) AND b.season = w.season '
    + 'WHERE w.season=? AND w.PA >= ? '
    + 'ORDER BY w.' + col + ' DESC, w.batter_ID LIMIT 5',
  ).bind(season, qual).all();
}

const KPCT = 'CASE WHEN ps.total_batters_faced > 0 '
  + 'THEN ps.strikeout * 100.0e0 / ps.total_batters_faced END';
const BBPCT = 'CASE WHEN ps.total_batters_faced > 0 '
  + 'THEN ps.base_on_balls * 100.0e0 / ps.total_batters_faced END';
const PIT_FROM = 'FROM kbo_official_pitcher_stats ps LEFT JOIN players p ON ps.player_id=p.player_id '
  + 'WHERE ps.season=? ORDER BY ps.player_id';

test('leaders: 한 번 읽기(창 함수)가 예전 LIMIT 5 질의들과 같은 Top5 행을 냅니다', async () => {
  for (const qual of [0, 300, 450]) {
    const tops = await batterTopsOnce(DB, 2025, qual);
    for (const [i, c] of BATTER_TOP_COLUMNS.entries()) {
      const { results } = await plainBatterTop(c, 2025, qual);
      assert.ok(results.length > 0, c);
      assert.deepEqual(
        tops[i].map((d) => [d.player_id, d.name, d.team, d[`v${i}`]]),
        results.map((d) => [d.player_id, d.name, d.team, d.val]), `${c} ${qual}`);
    }
    const [wrc, woba] = await wrcTopsOnce(DB, 2025, qual);
    for (const [rows, col, digits, alias] of [[wrc, 'wRC_half', 1, 'wrc'], [woba, 'wOBA', 3, 'woba']]) {
      const { results } = await plainWrcTop(col, digits, alias, 2025, qual);
      assert.ok(results.length > 0, col);
      assert.deepEqual(
        rows.map((d) => [d.player_id, d.name, d.team, d[alias]]),
        results.map((d) => [d.player_id, d.name, d.team, d[alias]]), `${col} ${qual}`);
    }
  }
});

test('leaders: 투수 행 한 칸 읽기가 예전 보통 질의와 같습니다(키 순서 포함)', async () => {
  for (const season of SEASONS) {
    const rows = await jsonRowsOnce(DB, [
      { expr: 'ps.player_id', name: 'player_id' },
      { expr: 'COALESCE(p.player_name, ps.player_name)', name: 'name' },
      { expr: 'COALESCE(ps.player_team, p.team_id)', name: 'team' },
      { expr: 'ps.earned_run_average', name: 'era' },
      { expr: 'ps.innings_pitched', name: 'ip' },
      { expr: 'ps.strikeout', name: 'k' },
      { expr: KPCT, name: 'kpct', float: true },
      { expr: BBPCT, name: 'bbpct', float: true },
    ], PIT_FROM, [season], 'ps.player_id');
    const { results } = await DB.prepare(
      'SELECT ps.player_id AS player_id, COALESCE(p.player_name, ps.player_name) AS name, '
      + 'COALESCE(ps.player_team, p.team_id) AS team, ps.earned_run_average AS era, '
      + `ps.innings_pitched AS ip, ps.strikeout AS k, ${KPCT} AS kpct, ${BBPCT} AS bbpct `
      + PIT_FROM,
    ).bind(season).all();
    assert.equal(rows.length, 60);
    assert.equal(JSON.stringify(rows), JSON.stringify(results), String(season));
  }
});

test('leaders: 응답이 위 기준 행들로 조립됩니다', async () => {
  // 시즌 캐시(10분)가 있어 다른 시험과 겹치지 않는 시즌을 씁니다.
  const body = await (await leaders(new Request('https://x/leaders?season=2024'), MY)).json();
  assert.ok(body.batter.avg.length === 5 && body.pitcher.kpct.length === 5);
  const g = await DB.prepare(
    'SELECT MAX(games) AS g FROM kbo_official_batter_stats WHERE season=?').bind(2024).first();
  const qual = pyRound(3.1 * g.g);
  assert.equal(body.qual_pa, qual);
  const { results: avg } = await plainBatterTop('batting_average', 2024, qual);
  assert.deepEqual(body.batter.avg.map((d) => [d.player_id, d.name, d.team, d.value]),
    avg.map((d) => [d.player_id, d.name, d.team, d.val === null ? '-' : Number(d.val).toFixed(3)]));
  const { results: wrc } = await plainWrcTop('wRC_half', 1, 'wrc', 2024, qual);
  assert.deepEqual(body.batter.wrc.map((d) => [d.player_id, d.name, d.team, d.value]),
    wrc.map((d) => [d.player_id, d.name, d.team, d.wrc === null ? '-' : Number(d.wrc).toFixed(1)]));
});

test('wrc/seasons: UNION ALL 한 번이 시즌마다 따로 읽은 값 순서와 같습니다', async () => {
  const rows = SEASONS.map((season) => ({ season, min_pa: 200 }));
  const merged = await deltasBySeason(DB, rows);
  for (const r of rows) {
    const { results } = await DB.prepare(
      'SELECT (wRC_weighted - wRC_half) AS d FROM wrc_plus_comparison WHERE PA>=? AND season=?',
    ).bind(r.min_pa, r.season).all();
    assert.deepEqual(merged.get(r.season), results.map((x) => x.d));
  }
  // 라우트 응답의 std_delta 를 예전처럼 시즌마다 따로 읽은 값으로 다시 셈해도
  // 응답 글자가 같습니다.
  for (const q of ['', '?min_pa=0', '?min_pa=450', '?min_pa=10000']) {
    const a = await (await wrcSeasons(new Request(`https://x/wrc/seasons${q}`), MY)).text();
    const want = JSON.parse(a);
    for (const r of want) {
      const { results } = await DB.prepare(
        'SELECT (wRC_weighted - wRC_half) AS d FROM wrc_plus_comparison '
        + 'WHERE PA>=? AND season=?',
      ).bind(r.min_pa, r.season).all();
      r.std_delta = stdDelta(results.map((x) => x.d));
    }
    assert.equal(a, JSON.stringify(want), q);
    if (q !== '?min_pa=10000') assert.ok(want.length === 2 && want[0].std_delta !== null, q);
  }
});

// 예전(D1) /stats/batters·pitchers 질의입니다. 라우트와 같은 FROM·조건·순서입니다.
function teamSql(teamIds, column) {
  const ids = String(teamIds || '').split(',').map((t) => t.trim()).filter(Boolean);
  return { sql: ids.length ? ` AND ${column} IN (${ids.map(() => '?').join(',')})` : '', binds: ids };
}

async function plainStats(kind, url) {
  const u = new URL(url);
  const season = Number(u.searchParams.get('season') ?? 2025);
  const lim = Number(u.searchParams.get('limit') ?? 100);
  const limit = lim < 0 ? Number.MAX_SAFE_INTEGER : lim;
  const teamIds = u.searchParams.get('team_ids');
  if (kind === 'batters') {
    const minPa = Number(u.searchParams.get('min_pa') ?? 0);
    const TEAM = 'COALESCE(b.player_team, p.team_id)';
    const team = teamSql(teamIds, TEAM);
    const { results } = await DB.prepare(`
    SELECT b.*, COALESCE(p.player_name, b.player_name) AS player_name,
           ${TEAM} AS team_id, p.position,
           b.on_base_plus_slugging as ops, ROUND(w.wOBA, 3) AS woba, ROUND(w.wRAA_FG, 1) AS wraa, ROUND(w.wRC_half, 1) AS wrc_plus
    FROM kbo_official_batter_stats b
    LEFT JOIN players p ON b.player_id = p.player_id LEFT JOIN wrc_plus_comparison w ON CAST(w.batter_ID AS CHAR) = b.player_id AND w.season = b.season
    WHERE b.season = ? AND b.plate_appearance >= ?${team.sql}
    ORDER BY b.batting_average DESC, b.player_id LIMIT ?`).bind(season, minPa, ...team.binds, limit).all();
    return JSON.stringify({ batters: results, season, min_pa: minPa, team_ids: teamIds });
  }
  const minIp = Number(u.searchParams.get('min_ip') ?? 0);
  const TEAM = 'COALESCE(ps.player_team, p.team_id)';
  const team = teamSql(teamIds, TEAM);
  const { results } = await DB.prepare(`
    SELECT ps.*, COALESCE(p.player_name, ps.player_name) AS player_name,
           ${TEAM} AS team_id,
           ps.walks_plus_hits_per_inning_pitched as whip,
           ${KPCT} AS strikeout_per_pa,
           ${BBPCT} AS base_on_balls_per_pa
    FROM kbo_official_pitcher_stats ps
    LEFT JOIN players p ON ps.player_id = p.player_id
    WHERE ps.season = ? AND CAST(ps.innings_pitched AS DOUBLE) >= ?${team.sql}
    ORDER BY ps.earned_run_average ASC, ps.player_id LIMIT ?`).bind(season, minIp, ...team.binds, limit).all();
  return JSON.stringify({ pitchers: results, season, min_ip: minIp, team_ids: teamIds });
}

test('stats: JSON 배열 한 칸 읽기가 예전 b.*·ps.* 질의와 같은 응답(열 순서·이름 겹침 포함)을 냅니다', async () => {
  const urls = [
    ['batters', '?season=2025&limit=-1'],
    ['batters', '?season=2024&limit=10&min_pa=100'],
    ['batters', '?season=2025&limit=30&team_ids=KIA,LG'],
    ['pitchers', '?season=2025&limit=-1'],
    ['pitchers', '?season=2024&limit=20&min_ip=10&team_ids=두산'],
  ];
  for (const [kind, q] of urls) {
    const fn = kind === 'batters' ? statsBatters : statsPitchers;
    const url = `https://x/stats/${kind}${q}`;
    const a = await (await fn(new Request(url), MY)).text();
    const b = await plainStats(kind, url);
    assert.equal(a, b, `${kind}${q}`);
    assert.ok(JSON.parse(a)[kind].length > 0, `${kind}${q}`);
  }
});
