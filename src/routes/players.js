import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';
import { shardOf, seasonDateRange } from '../lib/shard.js';

/**
 * 바깥 `p` 행의 가장 최근 시즌 소속을 뽑는 조각입니다.
 *
 * 타자와 투수를 합쳐서 시즌이 가장 큰 것을 고릅니다. 한쪽만 보면
 * 두 가지를 다 한 선수의 소속이 엉뚱한 해로 잡힙니다.
 */
export const LATEST_TEAM_SQL = `
  SELECT player_team FROM (
    SELECT season, player_team FROM kbo_official_batter_stats
     WHERE player_id = p.player_id AND player_team IS NOT NULL
    UNION ALL
    SELECT season, player_team FROM kbo_official_pitcher_stats
     WHERE player_id = p.player_id AND player_team IS NOT NULL
  ) ORDER BY season DESC LIMIT 1`;

/** 바깥 `p` 행이 마지막으로 기록을 남긴 시즌입니다. */
export const LATEST_SEASON_SQL = `
  SELECT MAX(season) FROM (
    SELECT season FROM kbo_official_batter_stats WHERE player_id = p.player_id
    UNION ALL
    SELECT season FROM kbo_official_pitcher_stats WHERE player_id = p.player_id
  )`;

/**
 * 공식 기록이 있는 가장 최근 시즌입니다.
 *
 * `is_active` 를 여기에 기대어 계산합니다. `players` 표에는 그 컬럼이
 * **없습니다.** 원본에는 있었지만 D1 으로 옮길 때 넘어오지 않았습니다
 * (backfill_player_flags.py 가 만들던 값입니다). 그래서 화면이
 * `player.is_active` 를 보는 다섯 곳이 전부 undefined 를 받아
 * **모든 선수를 은퇴 선수로 취급**했습니다. 소속도 등번호도 팀 색도
 * 나오지 않았습니다.
 *
 * 컬럼을 새로 만들지 않는 이유는 team_id 와 같습니다. 아무도 갱신하지
 * 않는 컬럼은 곧 낡습니다. 그해 공식 기록에 이름이 있으면 현역으로
 * 봅니다. 매일 적재와 함께 저절로 최신이 됩니다.
 *
 * 한계도 적어 둡니다. 로스터에는 있는데 아직 한 경기도 안 뛴 선수는
 * 비현역으로 잡힙니다. 시즌 초에 그런 선수가 늘어납니다.
 */
export async function currentSeason(db) {
  const row = await db.prepare(
    'SELECT MAX(s) AS s FROM ('
    + 'SELECT MAX(season) AS s FROM kbo_official_batter_stats'
    + ' UNION ALL SELECT MAX(season) FROM kbo_official_pitcher_stats)',
  ).first();
  return row && row.s != null ? Number(row.s) : null;
}

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
  // 상세 페이지와 같은 이유로 소속을 그 시즌 기록에서 가져옵니다.
  // `players.team_id` 는 아무도 채우지 않아 대부분 비어 있습니다.
  // 검색 결과만 '-' 로 남으면 상세 페이지와 어긋나 보입니다.
  const cur = await currentSeason(env.DB);
  const { results } = await env.DB
    .prepare(
      `SELECT p.*, COALESCE((${LATEST_TEAM_SQL}), p.team_id) AS team_id,
              CASE WHEN (${LATEST_SEASON_SQL}) >= ? THEN 1 ELSE 0 END AS is_active
       FROM players p WHERE p.player_name LIKE ? LIMIT 50`)
    .bind(cur == null ? 9999 : cur, `%${q}%`)
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

  // `players.team_id` 는 **아무 작업도 채우지 않는 컬럼**입니다.
  // player_info_scraper 의 INSERT 문에 team_id 가 없어서, 새로 넣은
  // 선수는 전부 비어 있습니다(1,745명 중 1,160명). 화면에 소속이
  // '-' 로 나옵니다. 있는 값도 최초 적재 이후 갱신되지 않아 낡았습니다
  // (강백호가 한화인데 KT 로 남아 있었습니다).
  //
  // 그 시즌 기록 행에는 player_team 이 있습니다. 가장 최근 시즌 것을
  // 씁니다. 현역은 올해 소속이 되고 은퇴 선수는 마지막 소속이 됩니다.
  // 리더보드·기록실과 같은 규칙입니다(routes/leaders.js, routes/stats.js).
  const cur = await currentSeason(db);

  // 지금 1군에 등록돼 있는지입니다.
  //
  // `is_active` 와 다릅니다. `is_active` 는 "올 시즌 기록이 있나" 이고
  // 이것은 "지금 1군 엔트리에 있나" 입니다. 어제 말소된 선수는
  // is_active 는 1 이지만 1군에는 없습니다.
  //
  // `kbo_roster` 는 daily 가 KBO 등록 현황에서 매일 새로 받습니다.
  // 그 표가 없거나(옛 스냅샷) 못 찾으면 null 입니다. 화면은 그때
  // 배지를 안 보여 줍니다. "말소" 로 단정하면 안 됩니다. 2군에
  // 있는 것과 표가 없는 것은 다릅니다.
  let roster = null;
  let rosterSize = 0;
  try {
    roster = await db.prepare(
      'SELECT team, back_number, role, as_of, league FROM kbo_roster '
      + 'WHERE player_id = ? LIMIT 1',
    ).bind(dbPid).first();
    // 명단을 믿어도 되는 날인지 봅니다. 한 행만 읽습니다.
    const size = await db.prepare(
      'SELECT COUNT(*) AS n FROM kbo_roster').first();
    rosterSize = size ? Number(size.n) : 0;
  } catch {
    // 표가 아직 없는 환경입니다.
  }

  return json({
    ...player,
    // 1군 등록 현황이 가장 최신 소속입니다. daily 가 매일 새로 받습니다.
    // 기록의 소속은 그 시즌 것이라 시즌 중 이적이 늦게 반영됩니다.
    team_id: (roster && roster.team)
      || latestTeam(batter.results, pitcher.results)
      || player.team_id,
    is_active: isActive(batter.results, pitcher.results, cur, roster,
                        rosterSize, player.back_number) ? 1 : 0,
    // 1군 등록 상태입니다. null 이면 "모름" 이지 "말소" 가 아닙니다.
    // **1군 등록 배지는 1군 명단일 때만입니다.** 퓨처스 명단에 있는
    // 선수에게 '1군 등록' 을 붙이면 틀린 말이 됩니다.
    first_team: (roster && roster.league !== '퓨처스') ? {
      team: roster.team,
      back_number: roster.back_number,
      role: roster.role,
      as_of: roster.as_of,
    } : null,
    batter_seasons: batter.results,
    pitcher_seasons: pitcher.results,
  });
}

/** 가장 최근 시즌에 기록이 있으면 현역으로 봅니다. */
export function rosterDecides(rosterSize) {
  // 정상이면 1군 339 + 퓨처스 289 = 628명입니다. 수집이 실패해 표가
  // 비면 전원이 무소속이 되는데 그건 사고입니다. 너무 작으면 예전처럼
  // 기록으로 판정합니다.
  return Number(rosterSize) >= 300;
}

/**
 * 지금 어느 구단에 속해 있는지입니다.
 *
 * **오늘 KBO 구단 명단에 있는가** 로 봅니다. `kbo_roster` 가 1군과
 * 퓨처스 명단을 함께 담습니다. daily 가 매일 새로 받습니다.
 *
 * 예전에는 "올 시즌 기록이 있나" 로 봤습니다. 그래서 방출된 선수도
 * 현역으로 잡혔습니다. 타무라(56218)는 계약이 끝났는데 올 시즌 1군
 * 기록(17경기)이 있어 두산 소속으로 나왔습니다. 기록은 그 시즌 사실
 * 이라 지워지지 않습니다. 소속 판정에 쓸 값이 아닙니다.
 */
export function isActive(batterRows, pitcherRows, current, roster,
                         rosterSize, backNumber) {
  // 오늘 명단에 있으면 두말할 것 없습니다.
  if (roster) return true;

  // **명단에 없어도 등번호가 있으면 소속입니다.** 부상으로 1군에서
  // 내려가고 2군 명단에도 안 오른 선수가 있습니다. 힐리어드(56034)가
  // 그랬습니다. 명단만 보면 무소속이 되는데 KT 소속입니다.
  //
  // 계약 여부를 가르는 것은 등번호입니다. KBO 는 계약이 끝나면 그
  // 자리를 비웁니다. 명단은 "오늘 어디에 있나", 등번호는 "계약이
  // 있나" 입니다. 다른 질문입니다.
  //
  // 0 과 '00' 도 실제 등번호입니다. 값이 있는지만 봅니다.
  if (backNumber !== null && backNumber !== undefined && backNumber !== '') {
    return true;
  }

  if (rosterDecides(rosterSize)) return false;
  // 명단을 못 믿는 날입니다. 예전 방식으로 돌아갑니다.
  if (current == null) return false;
  for (const r of [...(batterRows || []), ...(pitcherRows || [])]) {
    if (r && Number(r.season) >= Number(current)) return true;
  }
  return false;
}

/** 시즌 기록 가운데 가장 최근 시즌의 소속입니다. 없으면 null 입니다. */
export function latestTeam(batterRows, pitcherRows) {
  let best = null;
  for (const r of [...(batterRows || []), ...(pitcherRows || [])]) {
    if (!r || !r.player_team) continue;
    if (!best || Number(r.season) > Number(best.season)) best = r;
  }
  return best ? best.player_team : null;
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
