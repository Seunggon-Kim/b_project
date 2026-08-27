import { json } from '../lib/respond.js';

/**
 * 원본 api/main.py:109-116 입니다. teams 전체를 이름순으로 돌려줍니다.
 *
 * `?season=` 을 주면 **그 시즌에 실제로 있던 팀**을 돌려줍니다.
 *
 * 1982~2014 기록을 넣고 나서 필요해졌습니다. `teams` 표는 현재 10팀만
 * 담고 시간 개념이 없어서, 1982 시즌을 열어도 팀 필터에 KT·NC·키움이
 * 뜨고 정작 삼미·MBC 는 고를 수 없었습니다. 화면에서 발견됐습니다.
 *
 * 리그는 6팀으로 시작해 지금 10팀입니다.
 *
 *   1982~1985  6팀   MBC·OB·롯데·삼미·삼성·해태
 *   1986~1990  7팀   빙그레 합류
 *   1991~1999  8팀   쌍방울 합류
 *   2013~2014  9팀   NC 합류
 *   2015~      10팀  KT 합류
 *
 * 이름은 **그 시즌 표기명**입니다(1982 는 두산이 아니라 OB). 기록의
 * `player_team` 과 같은 값이라야 필터가 걸립니다.
 *
 * 인자가 없으면 예전처럼 현재 팀 전부입니다. 다른 화면이 그대로
 * 동작해야 합니다.
 */
export async function teams(request, env) {
  const season = new URL(request.url).searchParams.get('season');
  if (!season || !/^\d{4}$/.test(season)) {
    const { results } = await env.DB
      .prepare('SELECT * FROM teams ORDER BY team_name')
      .all();
    return json({ teams: results });
  }

  // team_seasons 는 그 시즌 표기명을, franchises 는 지금 어느 팀인지를
  // 압니다. `teams` 를 LEFT 로 붙여 색·연고 같은 것을 이어 주되,
  // 해체팀(현대·쌍방울)은 현재 팀이 없어 NULL 로 둡니다.
  const { results } = await env.DB.prepare(`
    SELECT ts.team_name AS team_id,
           ts.team_name AS team_name,
           ts.franchise_id,
           f.current_name,
           t.team_name_en, t.city, t.stadium
    FROM team_seasons ts
    JOIN franchises f ON f.franchise_id = ts.franchise_id
    LEFT JOIN teams t ON t.team_id = f.current_name
    WHERE ts.season = ?
    ORDER BY ts.team_name
  `).bind(Number(season)).all();

  // 그 시즌 표가 없으면(아직 안 채운 시즌) 현재 팀으로 물러섭니다.
  // 빈 목록을 주면 필터가 통째로 비어 아무것도 못 고릅니다.
  if (!results.length) {
    const all = await env.DB
      .prepare('SELECT * FROM teams ORDER BY team_name').all();
    return json({ teams: all.results, season: Number(season), fallback: true });
  }
  return json({ teams: results, season: Number(season) });
}
