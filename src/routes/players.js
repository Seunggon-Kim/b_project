import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import { shardOf, seasonDateRange } from '../lib/shard.js';

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

    // play_by_play 는 시즌별 D1 에 나뉘어 있습니다. 이 질의는 시즌
    // 하나만 보므로 담당 DB 한 개만 두드립니다.
    const pdb = shardOf(env, season);
    const range = seasonDateRange(season);
    if (!pdb || !range) {
      // 배정에 없는 시즌입니다. 빈 결과를 주면 "그 해엔 안 던졌다"로
      // 보여 데이터가 없는 것을 알 수 없습니다.
      return json({ player_id: playerId, arsenal: [], count: 0 });
    }

    const { results } = await pdb.prepare(`
      SELECT pbp.pitch_type, pbp.px, pbp.pz, pbp.speed, pbp.pitch_result,
             pbp.pfx_x, pbp.pfx_z, pbp.game_date, pbp.x0, pbp.z0,
             pbp.sz_top, pbp.sz_bot
      FROM play_by_play pbp
      WHERE pbp.pitcher_ID = ?
      AND pbp.game_date >= ? AND pbp.game_date < ?
      AND pbp.px IS NOT NULL
      AND pbp.pz IS NOT NULL
      AND pbp.pitch_type IS NOT NULL
      AND pbp.pitch_type NOT IN ('', '-', 'null')
    `).bind(player.player_id, range.from, range.to).all();

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

// 원본 api/main.py:280-284 의 구종 약어 표입니다. 한글 구종명 -> 두 글자 코드.
// 없는 구종은 이름 앞 두 글자를 대문자로 씁니다.
const PITCH_ABBR = {
  너클볼: 'KN', 스위퍼: 'ST', 슬라이더: 'SL', 슬러브: 'SV',
  싱커: 'SI', 직구: 'FF', 체인지업: 'CH', 커브: 'CU',
  커터: 'FC', 투심: 'SI', 스플리터: 'FS',
};

/**
 * 원본 api/main.py:291-325 의 집계입니다. 순수 함수로 떼어 테스트합니다.
 *
 * 좌우 타자 판정에 한 가지 요령이 있습니다. 스위치 타자(`양`)는 투수의
 * 반대편에 서므로, 우투수면 좌타석·좌투수면 우타석으로 셉니다.
 *
 * 그리고 `좌` 가 아닌 것은 전부 우타로 셉니다. 값이 비었거나 모르는
 * 문자열이어도 우타입니다. 원본의 else 분기를 그대로 옮긴 것입니다.
 */
export function summarizeUsage(rows) {
  const counts = new Map();
  let totalL = 0;
  let totalR = 0;
  let totalAll = 0;

  for (const row of rows) {
    const ptype = row.pitch_type;
    const stands = row.stands || '우';
    const throws = row.throws || '우';

    let actual = stands;
    if (stands === '양') {
      if (throws === '우') actual = '좌';
      else if (throws === '좌') actual = '우';
    }

    if (!counts.has(ptype)) counts.set(ptype, { L: 0, R: 0, Total: 0 });
    const c = counts.get(ptype);
    c.Total += 1;
    totalAll += 1;

    if (actual === '좌') {
      c.L += 1;
      totalL += 1;
    } else {
      c.R += 1;
      totalR += 1;
    }
  }

  const result = [];
  for (const [ptype, c] of counts) {
    result.push({
      pitch_type: ptype,
      abbreviation: PITCH_ABBR[ptype] || String(ptype).slice(0, 2).toUpperCase(),
      count: c.Total,
      usage_all: totalAll > 0 ? round1(c.Total / totalAll * 100) : 0,
      usage_l: totalL > 0 ? round1(c.L / totalL * 100) : 0,
      usage_r: totalR > 0 ? round1(c.R / totalR * 100) : 0,
    });
  }

  // 원본: result.sort(key=lambda x: x['usage_all'], reverse=True)
  // 파이썬 sort 는 안정 정렬이라 동률이면 넣은 순서가 유지됩니다.
  // JS sort 도 안정 정렬이라 같습니다.
  result.sort((a, b) => b.usage_all - a.usage_all);

  return { result, totalAll, totalL, totalR };
}

/** 파이썬 round(x, 1) 입니다. .5 에서 짝수 쪽으로 갑니다. */
function round1(x) {
  const y = x * 10;
  const floor = Math.floor(y);
  const r = (y - floor === 0.5)
    ? (floor % 2 === 0 ? floor : floor + 1)
    : Math.round(y);
  return r / 10;
}

/** 원본 api/main.py:250-335 입니다. 투수의 구종 구사율입니다. */
export async function playerUsage(request, env, ctx, params) {
  const playerId = params.id;
  try {
    const db = env.DB;
    const player = await robustPlayerLookup(db, playerId);
    if (!player) return json({ error: 'Player not found' });

    const season = queryInt(new URL(request.url), 'season', 2026);

    const pdb = shardOf(env, season);
    const range = seasonDateRange(season);
    if (!pdb || !range) {
      return json({ player_id: playerId, usage: [] });
    }

    const { results } = await pdb.prepare(`
      SELECT pbp.pitch_type, pbp.stands, pbp.throws
      FROM play_by_play pbp
      WHERE pbp.pitcher_ID = ?
      AND pbp.game_date >= ? AND pbp.game_date < ?
      AND pbp.pitch_type IS NOT NULL
      AND pbp.pitch_type NOT IN ('', '-', 'null')
    `).bind(player.player_id, range.from, range.to).all();

    // 원본은 행이 없으면 usage 만 있는 짧은 응답을 돌려줍니다.
    // total_pitches 같은 키가 아예 없습니다.
    if (!results.length) {
      return json({ player_id: playerId, usage: [] });
    }

    const { result, totalAll, totalL, totalR } = summarizeUsage(results);
    return json({
      player_id: playerId,
      total_pitches: totalAll,
      total_l: totalL,
      total_r: totalR,
      usage: result,
    });
  } catch (err) {
    return json({
      error: String(err && err.message ? err.message : err),
      traceback: String((err && err.stack) || ''),
    });
  }
}
