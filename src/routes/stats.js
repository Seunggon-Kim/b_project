import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import { pyRound } from './leaders.js';

/** 원본 api/main.py:337-353 입니다. 기록이 있는 시즌 목록을 내림차순으로. */
export async function statsSeasons(request, env) {
  const { results } = await env.DB.prepare(`
    SELECT DISTINCT season FROM (
      SELECT season FROM kbo_official_batter_stats
      UNION
      SELECT season FROM kbo_official_pitcher_stats
    )
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
  const hasWrc = await tableExists(env.DB, 'wrc_plus_comparison');
  const wrcSelect = hasWrc
    ? ', ROUND(w.wOBA, 3) AS woba, ROUND(w.wRAA_FG, 1) AS wraa, '
      + 'ROUND(w.wRC_half, 1) AS wrc_plus'
    : ', NULL AS woba, NULL AS wraa, NULL AS wrc_plus';
  const wrcJoin = hasWrc
    ? ' LEFT JOIN wrc_plus_comparison w '
      + 'ON CAST(w.batter_ID AS TEXT) = b.player_id AND w.season = b.season'
    : '';

  const team = teamIdsClause(teamIds, 'p.team_id');
  const sql = `
    SELECT b.*, p.player_name, p.team_id, p.position,
           b.on_base_plus_slugging as ops${wrcSelect}
    FROM kbo_official_batter_stats b
    JOIN players p ON b.player_id = p.player_id${wrcJoin}
    WHERE b.season = ? AND b.plate_appearance >= ?${team.sql}
    ORDER BY b.batting_average DESC LIMIT ?`;

  const { results } = await env.DB.prepare(sql)
    .bind(season, minPa, ...team.binds, limit).all();

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

  const team = teamIdsClause(teamIds, 'p.team_id');
  const sql = `
    SELECT ps.*, p.player_name, p.team_id,
           ps.walks_plus_hits_per_inning_pitched as whip
    FROM kbo_official_pitcher_stats ps
    JOIN players p ON ps.player_id = p.player_id
    WHERE ps.season = ? AND CAST(ps.innings_pitched AS REAL) >= ?${team.sql}
    ORDER BY ps.earned_run_average ASC LIMIT ?`;

  const { results } = await env.DB.prepare(sql)
    .bind(season, minIp, ...team.binds, limit).all();

  return json({
    pitchers: results,
    season,
    min_ip: minIp,
    team_ids: teamIds,
  });
}

/** 원본 _has_table (api/main.py:57-65) 입니다. */
async function tableExists(db, name) {
  try {
    const row = await db.prepare(
      "SELECT 1 AS x FROM sqlite_master WHERE type IN ('table','view') AND name = ?",
    ).bind(name).first();
    return Boolean(row);
  } catch {
    return false;
  }
}
