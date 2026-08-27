import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';

/**
 * 원본 api/main.py:599-614 입니다. 시즌 경기 목록을 최근순으로.
 *
 * `games.home_team_id` 는 **그 시즌 표기명**입니다(2015 는 키움이
 * 아니라 넥센). 그래서 `teams`(현재 10팀)와 이름으로 조인하면 옛
 * 이름이 안 맞아 팀 이름이 NULL 이 됩니다.
 *
 * 예전에는 경기도 현재 이름으로 담고 있었습니다. 2015년 경기가
 * 화면에 "한화 vs 키움" 으로 나왔는데, 키움은 2019년에 생긴
 * 이름입니다. 1,444건이 그랬습니다. 그 시즌 이름으로 바로잡으면서
 * 이 조회도 함께 고칩니다.
 *
 * `teams` 는 정식 명칭(키움 히어로즈)을 갖고 있어 그대로 두면 화면
 * 표기가 달라집니다. 현재 팀은 예전처럼 정식 명칭을 쓰고, 옛 이름은
 * 그 시즌 표기명을 그대로 보여 줍니다.
 */
export async function games(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', 2025);
  const limit = queryInt(url, 'limit', 50);

  const { results } = await env.DB.prepare(`
    SELECT g.*, g.game_date as date,
           COALESCE(t1.team_name, g.home_team_id) as home_team,
           COALESCE(t2.team_name, g.away_team_id) as away_team
    FROM games g
    LEFT JOIN teams t1 ON g.home_team_id = t1.team_id
    LEFT JOIN teams t2 ON g.away_team_id = t2.team_id
    WHERE g.season = ?
    ORDER BY g.game_date DESC
    LIMIT ?
  `).bind(season, limit).all();

  return json({ games: results, season });
}
