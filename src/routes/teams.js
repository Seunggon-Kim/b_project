import { json } from '../lib/respond.js';

/** 원본 api/main.py:109-116 입니다. teams 전체를 이름순으로 돌려줍니다. */
export async function teams(request, env) {
  const { results } = await env.DB
    .prepare('SELECT * FROM teams ORDER BY team_name')
    .all();
  return json({ teams: results });
}
