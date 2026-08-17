import { json } from '../lib/respond.js';

/**
 * 원본 robust_player_lookup (api/main.py:45-55) 입니다.
 *
 * players.player_id 에 문자열과 정수가 섞여 있어, 문자열로 먼저 찾고
 * 숫자면 정수로 한 번 더 찾습니다.
 */
export async function robustPlayerLookup(db, playerId) {
  let row = await db.prepare('SELECT * FROM players WHERE player_id = ?')
    .bind(playerId).first();
  if (row) return row;
  if (/^\d+$/.test(String(playerId))) {
    row = await db.prepare('SELECT * FROM players WHERE player_id = ?')
      .bind(Number.parseInt(playerId, 10)).first();
  }
  return row || null;
}

/** 원본 api/main.py:118-125 입니다. 이름 부분일치 최대 50명. */
export async function playersSearch(request, env) {
  const q = new URL(request.url).searchParams.get('q');
  // 원본은 q 가 필수라 없으면 FastAPI 가 422 를 냅니다.
  if (q === null) {
    return json({
      detail: [{
        type: 'missing',
        loc: ['query', 'q'],
        msg: 'Field required',
        input: null,
      }],
    }, 422);
  }
  const { results } = await env.DB
    .prepare('SELECT * FROM players WHERE player_name LIKE ? LIMIT 50')
    .bind(`%${q}%`)
    .all();
  return json({ players: results });
}

/**
 * 원본 api/main.py:127-148 입니다.
 *
 * players 행에 타자·투수 시즌 기록을 붙여 **평평한 객체 하나**를 돌려줍니다.
 * 다른 엔드포인트처럼 감싸지 않습니다.
 */
export async function playerDetail(request, env, ctx, params) {
  const db = env.DB;
  const player = await robustPlayerLookup(db, params.id);
  if (!player) {
    // 원본은 HTTPException(404, "Player not found") 를 던집니다.
    return json({ detail: 'Player not found' }, 404);
  }

  const dbPid = player.player_id;

  // 원본이 SELECT * 에 별칭 컬럼을 덧붙입니다. hits 와 ops, whip 입니다.
  const batter = await db.prepare(
    'SELECT *, single as hits, on_base_plus_slugging as ops '
    + 'FROM kbo_official_batter_stats WHERE player_id = ? ORDER BY season DESC',
  ).bind(dbPid).all();

  const pitcher = await db.prepare(
    'SELECT *, walks_plus_hits_per_inning_pitched as whip '
    + 'FROM kbo_official_pitcher_stats WHERE player_id = ? ORDER BY season DESC',
  ).bind(dbPid).all();

  return json({
    ...player,
    batter_seasons: batter.results,
    pitcher_seasons: pitcher.results,
  });
}
