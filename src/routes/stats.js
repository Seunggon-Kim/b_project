import { json } from '../lib/respond.js';
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
