import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';

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

/**
 * 원본 api/main.py:214-248 입니다. 투수의 구종 데이터입니다.
 *
 * play_by_play 를 투수 하나로 걸러 읽습니다. idx_pbp_pitcher 를 타므로
 * 전체 스캔이 아닙니다. 실측에서 한 투수당 2,209행이었습니다.
 */
export async function playerArsenal(request, env, ctx, params) {
  const playerId = params.id;
  try {
    const db = env.DB;
    const player = await robustPlayerLookup(db, playerId);
    if (!player) {
      // 원본은 404 가 아니라 200 + error 를 돌려줍니다.
      return json({ error: 'Player not found' });
    }
    const season = queryInt(new URL(request.url), 'season', 2026);

    const { results } = await db.prepare(`
      SELECT pbp.pitch_type, pbp.px, pbp.pz, pbp.speed, pbp.pitch_result,
             pbp.pfx_x, pbp.pfx_z, pbp.game_date, pbp.x0, pbp.z0,
             pbp.sz_top, pbp.sz_bot
      FROM play_by_play pbp
      WHERE pbp.pitcher_ID = ?
      AND substr(pbp.gameID,1,4) = CAST(? AS TEXT)
      AND pbp.px IS NOT NULL
      AND pbp.pz IS NOT NULL
      AND pbp.pitch_type IS NOT NULL
      AND pbp.pitch_type NOT IN ('', '-', 'null')
    `).bind(player.player_id, season).all();

    // 원본은 요청받은 player_id 를 그대로 돌려줍니다. DB 에서 찾은 것이
    // 아닙니다. 문자열과 정수가 섞여 있어 값이 다를 수 있습니다.
    return json({ player_id: playerId, arsenal: results, count: results.length });
  } catch (err) {
    return json({
      error: String(err && err.message ? err.message : err),
      traceback: String((err && err.stack) || ''),
    });
  }
}
