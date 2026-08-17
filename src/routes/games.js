import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';

/** 원본 api/main.py:599-614 입니다. 시즌 경기 목록을 최근순으로. */
export async function games(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', 2025);
  const limit = queryInt(url, 'limit', 50);

  const { results } = await env.DB.prepare(`
    SELECT g.*, g.game_date as date,
           t1.team_name as home_team, t2.team_name as away_team
    FROM games g
    LEFT JOIN teams t1 ON g.home_team_id = t1.team_id
    LEFT JOIN teams t2 ON g.away_team_id = t2.team_id
    WHERE g.season = ?
    ORDER BY g.game_date DESC
    LIMIT ?
  `).bind(season, limit).all();

  return json({ games: results, season });
}
