import { json } from '../lib/respond.js';
import { queryInt, sqlLimit } from '../lib/router.js';
import { pyRound } from './leaders.js';
import { tableExists } from '../lib/schema.js';
import { isMysql } from '../lib/backendflag.js';
import { jsonRowsOnce } from '../lib/jsonrows.js';

// K%·BB% 는 저장된 컬럼이 아니라 셀 때마다 계산합니다.
//
// `strikeout_per_pa`·`base_on_balls_per_pa` 는 **2025 에만 값이 있고**
// 나머지 열한 시즌은 전부 NULL 입니다. KBO 기록실이 이 값을 주지 않아
// 수집기가 채울 수 없습니다. 2025 값은 옛 파이프라인이 남긴 것입니다.
//
// 상대타자(TBF)로 나누면 그대로 나옵니다. 2025 저장값과 대조해
// 확인했습니다(폰세 36.2 vs 36.155, 라일리 30.5 vs 30.465).
// `ps.*` 뒤에 같은 이름으로 내보내므로 화면은 고칠 것이 없습니다.
const KPCT = 'CASE WHEN ps.total_batters_faced > 0 '
  + 'THEN ps.strikeout * 100.0e0 / ps.total_batters_faced END';
const BBPCT = 'CASE WHEN ps.total_batters_faced > 0 '
  + 'THEN ps.base_on_balls * 100.0e0 / ps.total_batters_faced END';

// MySQL 의 시즌 기록 표 열입니다. `b.*`·`ps.*` 가 내는 순서 그대로입니다
// (migration/mysql/schema.sql 의 CREATE TABLE 순서). MySQL 길은 행을 JSON
// 배열로 받으려고 열을 하나씩 적어야 해서 여기 둡니다. 표에 열이 늘면 이
// 목록도 늘려야 응답이 D1 길(`*`)과 같습니다. test/stats_columns.test.js 가
// schema.sql 과 대조합니다.
export const BATTER_STAT_COLUMNS = [
  'player_id', 'season', 'player_name', 'player_team', 'batting_average', 'games',
  'plate_appearance', 'at_bat', 'run', 'single', 'double', 'triple', 'home_run',
  'total_bases', 'run_batted_in', 'sacrifice_bunts', 'sacrifice_fly', 'base_on_balls',
  'intentional_base_on_balls', 'hit_by_pitch', 'strikeout', 'ground_into_double_play',
  'slugging_percentage', 'on_base_percentage', 'on_base_plus_slugging', 'multi_hits',
  'runners_in_scoring_position', 'pinch_hit_batting_average', 'extra_base_hits',
  'ground_outs', 'air_outs', 'go_ao', 'gw_rbi', 'strikeout_per_pa', 'base_on_balls_per_pa',
  'bb_k', 'p_pa', 'isop', 'extended_runs', 'gross_production_average',
  'created_at', 'updated_at',
];

export const PITCHER_STAT_COLUMNS = [
  'player_id', 'season', 'player_name', 'player_team', 'earned_run_average', 'games',
  'wins', 'losses', 'save', 'hold', 'winning_percentage', 'innings_pitched', 'hits',
  'home_run', 'base_on_balls', 'hit_by_pitch', 'strikeout', 'run', 'earned_run',
  'walks_plus_hits_per_inning_pitched', 'complete_game', 'shutout', 'quality_start',
  'blown_save', 'total_batters_faced', 'number_of_pitchers', 'batting_average', 'double',
  'triple', 'sacrifice_bunts', 'sacrifice_fly', 'intentional_base_on_balls', 'wild_pitch',
  'balk', 'games_started', 'wins_game_started', 'wins_game_relieved', 'games_finished',
  'save_opportunity', 'total_saves', 'ground_into_double_play', 'ground_outs', 'air_outs',
  'go_ao', 'batting_average_on_balls_in_play', 'p_g', 'p_ip', 'k_9', 'bb_9',
  'strikeout_per_pa', 'base_on_balls_per_pa', 'k_bb', 'on_base_percentage',
  'slugging_percentage', 'on_base_plus_slugging', 'created_at', 'updated_at',
];

// 두 표의 DATETIME 열입니다. JSON 으로 받으면 소수 초가 붙어 글자로 바꿉니다.
const STAT_DATETIME_COLUMNS = new Set(['created_at', 'updated_at']);

/** 시즌 기록 열들을 jsonRows 의 열 목록으로 만듭니다(`alias.열`). */
export function statColumns(alias, columns) {
  return columns.map((c) => ({
    expr: `${alias}.\`${c}\``,
    name: c,
    datetime: STAT_DATETIME_COLUMNS.has(c),
  }));
}

/** 원본 api/main.py:337-353 입니다. 기록이 있는 시즌 목록을 내림차순으로. */
export async function statsSeasons(request, env) {
  const { results } = await env.DB.prepare(`
    SELECT DISTINCT season FROM (
      SELECT season FROM kbo_official_batter_stats
      UNION
      SELECT season FROM kbo_official_pitcher_stats
    ) AS ss
    WHERE season IS NOT NULL
    ORDER BY season DESC
  `).all();
  return json({ seasons: results.map((r) => r.season) });
}

/**
 * 원본 api/main.py:355-378 입니다.
 *
 * 규정타석 = 3.1 x 팀경기수, 규정이닝 = 1.0 x 팀경기수.
 * 팀경기수는 시즌 내 타자 MAX(games) 입니다.
 *
 * `int(round(3.1 * g))` 의 round 는 파이썬 것이라 .5 에서 짝수 쪽으로 갑니다.
 * Math.round 를 쓰면 특정 경기 수에서 1 어긋납니다. leaders.js 의 pyRound 를
 * 씁니다.
 */
export async function statsRegulation(request, env) {
  const { results } = await env.DB.prepare(`
    SELECT season, MAX(games) AS team_games
    FROM kbo_official_batter_stats
    WHERE season IS NOT NULL AND games IS NOT NULL
    GROUP BY season
  `).all();

  const out = {};
  for (const r of results) {
    const g = r.team_games || 0;
    // 원본이 키를 str(season) 으로 만듭니다. JSON 객체 키라 어차피 문자열입니다.
    out[String(r.season)] = {
      team_games: g,
      qual_pa: pyRound(3.1 * g),
      qual_ip: g,
    };
  }
  return json({ regulation: out });
}

/**
 * `team_ids` 파라미터를 안전한 IN 절로 바꿉니다.
 *
 * 원본은 쉼표로 쪼개 빈 것을 버리고 개수만큼 자리표시자를 만듭니다
 * (api/main.py:404-409). 값을 SQL 에 직접 끼워 넣지 않는 것이 핵심입니다.
 * 돌려주는 것은 (SQL 조각, 바인딩 배열) 입니다.
 */
export function teamIdsClause(teamIds, column) {
  const ids = String(teamIds || '')
    .split(',')
    .map((t) => t.trim())
    .filter(Boolean);
  if (!ids.length) return { sql: '', binds: [] };
  return {
    sql: ` AND ${column} IN (${ids.map(() => '?').join(',')})`,
    binds: ids,
  };
}

/** 원본 api/main.py:380-417 입니다. */
export async function statsBatters(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', 2025);
  const limit = queryInt(url, 'limit', 100);
  const minPa = queryInt(url, 'min_pa', 0);
  const teamIds = url.searchParams.get('team_ids');

  // 원본은 wrc_plus_comparison 이 없는 DB 를 위해 NULL 폴백을 둡니다.
  // D1 에는 있으므로 조인하지만, 없을 때의 동작도 그대로 남깁니다.
  const hasWrc = await tableExists(env, 'wrc_plus_comparison');
  const wrcSelect = hasWrc
    ? ', ROUND(w.wOBA, 3) AS woba, ROUND(w.wRAA_FG, 1) AS wraa, '
      + 'ROUND(w.wRC_half, 1) AS wrc_plus'
    : ', NULL AS woba, NULL AS wraa, NULL AS wrc_plus';
  const wrcJoin = hasWrc
    ? ' LEFT JOIN wrc_plus_comparison w '
      + 'ON CAST(w.batter_ID AS CHAR) = b.player_id AND w.season = b.season'
    : '';

  // 팀과 이름은 그 시즌 기록 행의 값을 먼저 씁니다. `players` 는 지금
  // 명단이라 2016 기록에 2026 소속이 붙습니다. 은퇴 선수는 빈칸입니다.
  // 올해도 시즌 중 트레이드된 선수는 두 값이 어긋납니다.
  const TEAM = 'COALESCE(b.player_team, p.team_id)';
  const team = teamIdsClause(teamIds, TEAM);
  const ORDER = 'b.batting_average DESC, b.player_id';
  const from = `
    FROM kbo_official_batter_stats b
    LEFT JOIN players p ON b.player_id = p.player_id${wrcJoin}
    WHERE b.season = ? AND b.plate_appearance >= ?${team.sql}
    ORDER BY ${ORDER} LIMIT ?`;
  const binds = [season, minPa, ...team.binds, sqlLimit(limit)];

  // MySQL 은 모든 행을 JSON 배열로 이은 한 칸으로 받습니다(lib/jsonrows.js
  // jsonRowsOnce). 열과 이름은 아래 D1 질의의 `b.*, ...` 와 같은 순서입니다.
  // (season, player_id) 가 기본 키라 ORDER 가 행 하나를 정합니다.
  const results = isMysql(env)
    ? await jsonRowsOnce(env.DB, [
      ...statColumns('b', BATTER_STAT_COLUMNS),
      { expr: 'COALESCE(p.player_name, b.player_name)', name: 'player_name' },
      { expr: TEAM, name: 'team_id' },
      { expr: 'p.position', name: 'position' },
      { expr: 'b.on_base_plus_slugging', name: 'ops' },
      ...(hasWrc
        ? [
          { expr: 'ROUND(w.wOBA, 3)', name: 'woba' },
          { expr: 'ROUND(w.wRAA_FG, 1)', name: 'wraa' },
          { expr: 'ROUND(w.wRC_half, 1)', name: 'wrc_plus' },
        ]
        : ['woba', 'wraa', 'wrc_plus'].map((name) => ({ expr: 'NULL', name }))),
    ], from, binds, ORDER)
    : (await env.DB.prepare(`
    SELECT b.*, COALESCE(p.player_name, b.player_name) AS player_name,
           ${TEAM} AS team_id, p.position,
           b.on_base_plus_slugging as ops${wrcSelect}${from}`)
      .bind(...binds).all()).results;

  // team_ids 는 받은 그대로 돌려줍니다. 없으면 null 입니다.
  return json({
    batters: results,
    season,
    min_pa: minPa,
    team_ids: teamIds,
  });
}

/** 원본 api/main.py:419-444 입니다. */
export async function statsPitchers(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', 2025);
  const limit = queryInt(url, 'limit', 100);
  const minIp = queryInt(url, 'min_ip', 0);
  const teamIds = url.searchParams.get('team_ids');

  // 타자 쪽과 같은 이유입니다. statsBatters 주석을 보십시오.
  const TEAM = 'COALESCE(ps.player_team, p.team_id)';
  const team = teamIdsClause(teamIds, TEAM);
  const ORDER = 'ps.earned_run_average ASC, ps.player_id';
  const from = `
    FROM kbo_official_pitcher_stats ps
    LEFT JOIN players p ON ps.player_id = p.player_id
    WHERE ps.season = ? AND CAST(ps.innings_pitched AS DOUBLE) >= ?${team.sql}
    ORDER BY ${ORDER} LIMIT ?`;
  const binds = [season, minIp, ...team.binds, sqlLimit(limit)];

  // MySQL 은 모든 행을 JSON 배열로 이은 한 칸으로 받습니다(statsBatters 와 같음).
  const results = isMysql(env)
    ? await jsonRowsOnce(env.DB, [
      ...statColumns('ps', PITCHER_STAT_COLUMNS),
      { expr: 'COALESCE(p.player_name, ps.player_name)', name: 'player_name' },
      { expr: TEAM, name: 'team_id' },
      { expr: 'ps.walks_plus_hits_per_inning_pitched', name: 'whip' },
      // 나눗셈으로 만든 실수는 글자로 받아 mysql2 와 같게 읽습니다(jsonrows.js).
      { expr: KPCT, name: 'strikeout_per_pa', float: true },
      { expr: BBPCT, name: 'base_on_balls_per_pa', float: true },
    ], from, binds, ORDER)
    : (await env.DB.prepare(`
    SELECT ps.*, COALESCE(p.player_name, ps.player_name) AS player_name,
           ${TEAM} AS team_id,
           ps.walks_plus_hits_per_inning_pitched as whip,
           ${KPCT} AS strikeout_per_pa,
           ${BBPCT} AS base_on_balls_per_pa${from}`)
      .bind(...binds).all()).results;

  return json({
    pitchers: results,
    season,
    min_ip: minIp,
    team_ids: teamIds,
  });
}

