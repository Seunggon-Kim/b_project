import { json } from '../lib/respond.js';

// 팀 기록실입니다. 프랜차이즈 하나를 통째로 돌려줍니다.
//
// ## 프랜차이즈가 단위입니다
//
// 팀 이름은 시대에 따라 바뀝니다. 해태가 KIA 가 되고 OB 가 두산이
// 됩니다. `franchises`(정체성 12개)와 `team_seasons`(그 시즌 표기명
// 380행)가 그 계보를 담고 있어서 그대로 씁니다.
//
// **이어지지 않는 것도 있습니다.**
//
//     HD  1982~2007  삼미 -> 청보 -> 태평양 -> 현대   (해체)
//     WO  2008~      우리 -> 히어로즈 -> 넥센 -> 키움  (별개 구단)
//     SB  1991~1999  쌍방울                          (해체)
//     SK  2000~      SK -> SSG                       (별개 구단)
//
// 현대는 2007년에 해체됐고 이듬해 히어로즈가 창단했습니다. 선수단만
// 이어졌지 같은 구단이 아닙니다. 쌍방울과 SK 도 마찬가지입니다.
// 표가 이미 그렇게 되어 있어 손대지 않습니다.
//
// ## 한 번에 다 돌려줍니다
//
// 페이지가 열릴 때 네 덩어리가 모두 필요합니다(개요·올 시즌·시즌별·
// 홈구장). 요청을 넷으로 나누면 화면이 네 번 그려지고 D1 도 네 번
// 두드립니다. 캐시가 걸리므로 한 번에 주는 편이 낫습니다.

/**
 * 이닝 합계를 구하는 SQL 조각입니다.
 *
 * **공식 기록의 이닝은 텍스트입니다.**
 *
 *     '98 1/3'   98와 3분의 1
 *     '9 2/3'    9와 3분의 2
 *     '5'        5
 *
 * 그대로 SUM 하면 SQLite 가 앞 숫자만 읽어 '98 1/3' 이 98 이 됩니다.
 * 팀 ERA 가 그만큼 낮게 나옵니다. 정수부와 분수부를 나눠 더합니다.
 */
export function inningsExpr(col) {
  return `(
    CASE
      WHEN ${col} LIKE '% %'
        THEN CAST(SUBSTR(${col}, 1, INSTR(${col}, ' ') - 1) AS REAL)
      WHEN ${col} LIKE '%/%' THEN 0
      ELSE CAST(${col} AS REAL)
    END
    + CASE
        WHEN ${col} LIKE '%1/3' THEN 1.0/3.0
        WHEN ${col} LIKE '%2/3' THEN 2.0/3.0
        ELSE 0
      END)`;
}

/**
 * 한국시리즈 우승을 정리합니다.
 *
 * `rows` 는 `{ season, note }` 입니다. 우승 횟수와 우승 연도, 그리고
 * 한국시리즈 없이 우승한 해가 몇 번인지 함께 돌려줍니다.
 *
 * **1985년은 한국시리즈가 열리지 않았습니다.** 삼성이 전기·후기를
 * 모두 1위로 끝내 통합우승했습니다. 우승으로는 세되 화면에서 그
 * 사실을 밝힐 수 있도록 따로 셉니다. 밝히지 않으면 삼성의 우승이
 * 8회인지 7회인지를 두고 헷갈립니다.
 */
export function championsOf(rows, seasons) {
  // `seasons` 를 주면 그 안에 든 해만 셉니다. 옛 이름을 골랐을 때
  // 씁니다. 청보는 우승이 없고 현대는 네 번입니다. 계보로 세면
  // 청보 화면에도 4회가 떠서 틀립니다.
  const keep = seasons ? new Set(seasons) : null;
  const kept = (rows || []).filter((r) => !keep || keep.has(r.season));
  const list = kept.map((r) => r.season).sort((a, b) => a - b);
  const noSeries = kept.filter((r) => r.note).map((r) => r.season);
  return { count: list.length, seasons: list, no_series: noSeries };
}

/**
 * 통산 성적입니다. 승률은 무승부를 빼고 셉니다(KBO 방식).
 *
 * `first_place` 는 정규시즌 1위 횟수입니다. **한국시리즈 우승과
 * 다릅니다.** 화면에서 그렇게 밝혀야 합니다.
 */
export function careerOf(seasons) {
  const a = (seasons || []).reduce((acc, s) => ({
    games: acc.games + (s.games || 0),
    wins: acc.wins + (s.wins || 0),
    losses: acc.losses + (s.losses || 0),
    draws: acc.draws + (s.draws || 0),
    seasons: acc.seasons + 1,
  }), { games: 0, wins: 0, losses: 0, draws: 0, seasons: 0 });
  const decided = a.wins + a.losses;
  a.pct = decided ? (a.wins / decided) : null;
  a.first_place = (seasons || []).filter((s) => s.rank === 1).length;
  return a;
}

/**
 * 고른 이름으로 시즌을 좁힙니다.
 *
 * '청보' 를 고르면 1985~1987 만 남깁니다. 이름이 없으면 계보 전체를
 * 그대로 돌려줍니다.
 *
 * 왜 필요한가. 계보로 묶은 통산 전적은 '현대' 를 골랐을 때는 맞지만
 * '청보' 를 골랐을 때는 틀립니다. 청보는 세 시즌만 뛰었는데 화면에
 * 1466승이 뜨면 삼미·태평양·현대의 성적까지 얹힌 값입니다.
 */
export function scopeSeasons(seasons, name) {
  if (!name) return seasons || [];
  return (seasons || []).filter((s) => s.team_name === name);
}

/**
 * 고른 이름이 뛴 기간입니다. 없으면 null 입니다.
 *
 * **'창단 연도' 가 아니라 '활동 기간' 입니다.** 청보는 1985년에
 * 창단한 것이 아니라 삼미를 인수해 이름을 바꾼 것입니다. 화면에서도
 * 그렇게 밝혀야 합니다.
 */
export function scopeOf(seasons, name) {
  const rows = scopeSeasons(seasons, name);
  if (!name || !rows.length) return null;
  const years = rows.map((r) => r.season);
  return {
    name,
    first_season: Math.min(...years),
    last_season: Math.max(...years),
  };
}

/**
 * 순위 행에 그 시즌 팀 기록을 붙입니다.
 *
 * 양대리그 해에는 한 시즌에 두 행이 있고 양쪽에 같은 기록이 붙습니다.
 * 그 시즌 팀 전체 기록이라 맞습니다.
 *
 * 기록이 없는 시즌도 순위 행은 남깁니다. 지우면 그 해가 통째로
 * 사라집니다.
 */
export function mergeSeasons(ranks, statsMap) {
  return (ranks || []).map((r) => ({
    ...r,
    ...(statsMap.get(r.season) || {}),
  }));
}

/**
 * 시즌별 팀 성적입니다.
 *
 * 순위·승패는 `team_season_rank`(KBO 기록실, 1982~), 팀 타율·ERA 는
 * 공식 기록에서 그 시즌 소속으로 집계합니다.
 *
 * **공식 기록은 그 시즌 표기명으로 들어 있습니다.** 1983년 행의
 * `player_team` 은 'KIA' 가 아니라 '해태' 입니다. 그래서 프랜차이즈로
 * 묶으려면 `team_seasons` 를 거쳐야 합니다.
 */
async function seasonRows(db, franchiseId) {
  const { results } = await db.prepare(`
    SELECT r.season, r.team_name, r.league, r.rank, r.games,
           r.wins, r.losses, r.draws, r.pct, r.gb
      FROM team_season_rank r
     WHERE r.franchise_id = ?
     ORDER BY r.season DESC, r.league`).bind(franchiseId).all();
  return results || [];
}

/**
 * 시즌별 팀 타격·투구입니다.
 *
 * 선수 행을 그 시즌 소속으로 합칩니다. 타율·ERA 는 합계에서 다시
 * 계산합니다. 선수별 값을 평균 내면 타석 수가 적은 선수가 같은
 * 무게를 갖게 되어 틀립니다.
 */
async function seasonStats(db, franchiseId) {
  const { results: bat } = await db.prepare(`
    SELECT b.season,
           SUM(b.at_bat) AS ab, SUM(b.single) AS hits,
           SUM(b.home_run) AS hr, SUM(b.run) AS runs,
           SUM(b.run_batted_in) AS rbi
      FROM kbo_official_batter_stats b
      JOIN team_seasons t
        ON t.season = b.season AND t.team_name = b.player_team
     WHERE t.franchise_id = ?
     GROUP BY b.season`).bind(franchiseId).all();

  const { results: pit } = await db.prepare(`
    SELECT p.season,
           SUM(p.earned_run) AS er,
           SUM(${inningsExpr('p.innings_pitched')}) AS ip,
           SUM(p.strikeout) AS so, SUM(p.base_on_balls) AS bb
      FROM kbo_official_pitcher_stats p
      JOIN team_seasons t
        ON t.season = p.season AND t.team_name = p.player_team
     WHERE t.franchise_id = ?
     GROUP BY p.season`).bind(franchiseId).all();

  const out = new Map();
  for (const r of bat || []) {
    out.set(r.season, {
      season: r.season,
      // 타율은 안타/타수입니다. 선수별 타율을 평균 내면 안 됩니다.
      avg: r.ab ? (r.hits / r.ab) : null,
      hits: r.hits, home_run: r.hr, run: r.runs, rbi: r.rbi,
    });
  }
  for (const r of pit || []) {
    const slot = out.get(r.season) || { season: r.season };
    // ERA 는 자책점 x 9 / 이닝입니다.
    slot.era = r.ip ? (r.er * 9 / r.ip) : null;
    slot.strikeout = r.so;
    slot.walks = r.bb;
    out.set(r.season, slot);
  }
  return out;
}

/**
 * 팀 기록실 한 장입니다. `:id` 는 franchise_id 입니다.
 */
export async function teamRecord(request, env, ctx, params) {
  const db = env.DB;
  const id = String(params.id || '').trim().toUpperCase();
  if (!/^[A-Z]{2,4}$/.test(id)) {
    return json({ error: 'bad franchise id' }, 400);
  }
  // 고른 팀 이름입니다. 있으면 통산 성적과 우승을 그 이름일 때로
  // 좁힙니다. 시즌 목록은 계보 전체를 그대로 돌려줍니다. 표를 어디까지
  // 보일지는 화면이 정합니다.
  const picked = String(
    new URL(request.url).searchParams.get('name') || '').trim();

  const franchise = await db.prepare(
    'SELECT franchise_id, current_name, first_season, last_season, note '
    + 'FROM franchises WHERE franchise_id = ?',
  ).bind(id).first();
  if (!franchise) {
    return json({ found: false, franchise_id: id }, 404);
  }

  const [ranks, statsMap] = await Promise.all([
    seasonRows(db, id),
    seasonStats(db, id),
  ]);

  const seasons = mergeSeasons(ranks, statsMap);

  // 이름 변천입니다. 같은 이름이 이어지는 구간을 하나로 묶습니다.
  const { results: names } = await db.prepare(
    'SELECT season, team_name FROM team_seasons '
    + 'WHERE franchise_id = ? ORDER BY season',
  ).bind(id).all();
  const eras = [];
  for (const r of names || []) {
    const last = eras[eras.length - 1];
    if (last && last.team_name === r.team_name) {
      last.to = r.season;
    } else {
      eras.push({ team_name: r.team_name, from: r.season, to: r.season });
    }
  }

  // 홈구장 변천입니다. 그 시즌 표기명으로 들어 있습니다.
  let stadiums = [];
  try {
    const { results } = await db.prepare(
      'SELECT s.season, s.stadium FROM team_stadium_by_season s '
      + 'JOIN team_seasons t ON t.season = s.season '
      + ' AND t.team_name = s.player_team '
      + 'WHERE t.franchise_id = ? ORDER BY s.season',
    ).bind(id).all();
    stadiums = results || [];
  } catch {
    // 표가 없는 환경입니다.
  }

  // 한국시리즈 우승입니다.
  //
  // 우승 표에는 **그 시즌 표기명**이 들어 있습니다('OB' 이지 '두산' 이
  // 아닙니다). 프랜차이즈로 묶으려면 `team_seasons` 를 거쳐야 합니다.
  // 계보 판단이 한 곳에만 있도록 하기 위해서입니다.
  const scope = scopeOf(seasons, picked);
  const scoped = scopeSeasons(seasons, picked);
  const scopedYears = picked ? scoped.map((r) => r.season) : null;

  let champions = { count: 0, seasons: [], no_series: [] };
  try {
    const { results } = await db.prepare(
      'SELECT c.season, c.note FROM korean_series_champion c '
      + 'JOIN team_seasons t ON t.season = c.season '
      + ' AND t.team_name = c.team_name '
      + 'WHERE t.franchise_id = ? ORDER BY c.season',
    ).bind(id).all();
    champions = championsOf(results, scopedYears);
  } catch {
    // 표가 아직 없는 환경입니다. 0회로 둡니다.
  }

  // 통산 성적은 고른 이름일 때만 셉니다. 이름이 없으면 계보 전체입니다.
  const career = careerOf(scoped);

  return json({
    found: true,
    franchise,
    scope,
    eras,
    stadiums,
    champions,
    career,
    seasons,
  });
}
