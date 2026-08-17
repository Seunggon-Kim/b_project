import { json } from '../lib/respond.js';
import { queryInt, queryStr } from '../lib/router.js';
import { pyRound } from './leaders.js';

// wRC+ 계열 여섯 개입니다. 모두 wrc_plus_comparison 과 규정타석 계산을
// 공유해 한 파일에 둡니다.
//
// 원본: api/main.py 818-1031 (_eff_min_pa 와 /wrc/* 여섯 개)

/**
 * 원본 `_eff_min_pa`(818-826) 안의 계산만 떼어 낸 순수 함수입니다.
 *
 *   qual = int(round(3.1 * round(2.0 * g / 10.0)))
 *
 * g 는 해당 시즌 play_by_play 의 경기 수입니다. 리그 전체 경기라 10 팀으로
 * 나눠 두 배 하면 팀당 경기 수가 됩니다.
 *
 * 반올림이 두 번 나오는데 둘 다 파이썬 `round` 라 .5 에서 짝수 쪽으로
 * 갑니다. `Math.round` 를 쓰면 특정 경기 수에서 1 어긋나 순위가 통째로
 * 달라집니다.
 */
export function qualPaOf(games) {
  const teamGames = pyRound((2.0 * games) / 10.0);
  return pyRound(3.1 * teamGames);
}

/**
 * 원본 `_eff_min_pa` 전체입니다.
 * 진행 중 시즌은 규정타석으로 임계값을 낮추고, 아니면 요청값을 그대로 씁니다.
 */
export async function effMinPa(db, season, requested) {
  let g = 0;
  try {
    const row = await db.prepare(
      'SELECT COUNT(DISTINCT gameID) AS g FROM play_by_play '
      + 'WHERE substr(gameID,1,4) = ?',
    ).bind(String(season)).first();
    g = (row && row.g) || 0;
  } catch {
    g = 0;
  }
  const qual = qualPaOf(g);
  return qual > 0 ? Math.min(requested, qual) : requested;
}

// 원본 900-901 의 정렬 키 표입니다. 값이 SQL 에 그대로 들어가는 자리라
// 화이트리스트 밖은 전부 기본값으로 떨어뜨립니다.
const SORT_COLUMNS = {
  home: 'wRC_home',
  half: 'wRC_half',
  weighted: 'wRC_weighted',
  wOBA: 'wOBA',
};

export function sortColumnOf(sort) {
  return SORT_COLUMNS[sort] || 'wRC_half';
}

/**
 * 원본 856-865 의 표준편차입니다. **표본** 표준편차라 분모가 n-1 이고,
 * 소수 둘째 자리로 반올림합니다. 값이 하나 이하면 null 입니다.
 */
export function stdDelta(deltas) {
  const n = deltas.length;
  if (n <= 1) return null;
  const mean = deltas.reduce((a, b) => a + b, 0) / n;
  const varSum = deltas.reduce((a, d) => a + (d - mean) ** 2, 0);
  return Math.round(Math.sqrt(varSum / (n - 1)) * 100) / 100;
}

// 여러 곳이 함께 쓰는 조인입니다. 원본이 같은 모양을 반복해 씁니다.
const WRC_JOIN = `
  FROM wrc_plus_comparison wrc
  JOIN weighted_pf_by_batter_season wpf
    ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
  LEFT JOIN kbo_official_batter_stats b
    ON b.player_id = CAST(wrc.batter_ID AS TEXT) AND b.season = wrc.season`;

/** 원본 829-867. 시즌 목록과 요약입니다. **배열**을 돌려줍니다. */
export async function wrcSeasons(request, env) {
  const url = new URL(request.url);
  const minPa = queryInt(url, 'min_pa', 300);
  const db = env.DB;

  const { results: rows } = await db.prepare(`
    WITH gp AS (
      SELECT CAST(substr(gameID,1,4) AS INT) AS season, COUNT(DISTINCT gameID) AS g
      FROM play_by_play WHERE substr(gameID,1,4) BETWEEN '2015' AND '2026' GROUP BY 1
    ),
    thr AS (
      SELECT season, MIN(?, CAST(ROUND(3.1 * ROUND(2.0*g/10.0)) AS INT)) AS t FROM gp
    )
    SELECT w.season,
           (SELECT t FROM thr WHERE thr.season = w.season) AS min_pa,
           COUNT(*) AS n_batters,
           ROUND(AVG(w.wRC_home), 2) AS mean_wrc_home,
           ROUND(AVG(w.wRC_half), 2) AS mean_wrc_half,
           ROUND(AVG(w.wRC_weighted), 2) AS mean_wrc_weighted,
           ROUND(AVG(w.wRC_weighted - w.wRC_half), 2) AS mean_delta
    FROM wrc_plus_comparison w
    JOIN thr ON thr.season = w.season
    WHERE w.PA >= thr.t
    GROUP BY w.season
    ORDER BY w.season
  `).bind(minPa).all();

  // 원본은 행마다 쿼리를 한 번 더 날려 편차 목록을 받아 표준편차를 냅니다.
  // 시즌 수만큼이라(최대 12) D1 의 호출당 50개 한도 안입니다.
  for (const r of rows) {
    const { results } = await db.prepare(
      'SELECT (wRC_weighted - wRC_half) AS d FROM wrc_plus_comparison '
      + 'WHERE PA>=? AND season=?',
    ).bind(r.min_pa, r.season).all();
    r.std_delta = stdDelta(results.map((x) => x.d));
  }
  return json(rows);
}

/** 원본 870-895. 구장별 평균입니다. */
export async function wrcByStadium(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', null);
  if (season === null) return missingSeason();
  const minPa = await effMinPa(env.DB, season, queryInt(url, 'min_pa', 300));

  const { results } = await env.DB.prepare(`
    SELECT wpf.home_stadium AS home_stadium,
           sd.primary_team,
           COUNT(*) AS n,
           ROUND(AVG(wpf.home_run_pf), 1) AS home_pf,
           ROUND(AVG(wpf.wpf_run), 1) AS weighted_pf,
           ROUND(AVG(wrc.wRC_home), 2) AS mean_home,
           ROUND(AVG(wrc.wRC_half), 2) AS mean_half,
           ROUND(AVG(wrc.wRC_weighted), 2) AS mean_weighted,
           ROUND(AVG(wrc.wRC_weighted - wrc.wRC_half), 2) AS delta_mean
    FROM wrc_plus_comparison wrc
    JOIN weighted_pf_by_batter_season wpf
      ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
    LEFT JOIN stadium_dim sd ON sd.full_name = wpf.home_stadium
    WHERE wrc.PA >= ? AND wrc.season = ?
    GROUP BY wpf.home_stadium, sd.primary_team
    ORDER BY mean_half DESC
  `).bind(minPa, season).all();
  return json(results);
}

/** 원본 898-930. 리더보드입니다. */
export async function wrcLeaderboard(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', null);
  if (season === null) return missingSeason();
  const sortCol = sortColumnOf(queryStr(url, 'sort', 'half'));
  const n = queryInt(url, 'n', 50);
  const minPa = await effMinPa(env.DB, season, queryInt(url, 'min_pa', 300));

  const { results } = await env.DB.prepare(`
    SELECT wrc.batter_ID,
           COALESCE(b.player_name, 'Unknown') AS player_name,
           b.player_team,
           wrc.season, wrc.PA,
           ROUND(wrc.wOBA, 4) AS wOBA,
           ROUND(wrc.wRAA_FG, 1) AS wRAA,
           wpf.home_stadium,
           ROUND(wpf.home_run_pf, 1) AS home_pf,
           ROUND(wpf.wpf_run, 1) AS weighted_pf,
           ROUND(wrc.wRC_home, 1) AS wRC_home,
           ROUND(wrc.wRC_half, 1) AS wRC_half,
           ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
           ROUND(wrc.wRC_weighted - wrc.wRC_half, 2) AS delta_methods
    ${WRC_JOIN}
    WHERE wrc.season = ? AND wrc.PA >= ?
    ORDER BY ${sortCol} DESC
    LIMIT ?
  `).bind(season, minPa, n).all();
  return json(results);
}

/** 원본 933-963. 방식 간 차이가 큰 순서입니다. */
export async function wrcTopChanges(request, env) {
  const url = new URL(request.url);
  const season = queryInt(url, 'season', null);
  if (season === null) return missingSeason();
  const direction = queryStr(url, 'direction', 'up');
  if (direction !== 'up' && direction !== 'down') {
    // 원본: HTTPException(400, "direction must be 'up' or 'down'")
    return json({ detail: "direction must be 'up' or 'down'" }, 400);
  }
  const order = direction === 'up' ? 'DESC' : 'ASC';
  const n = queryInt(url, 'n', 15);
  const minPa = await effMinPa(env.DB, season, queryInt(url, 'min_pa', 300));

  const { results } = await env.DB.prepare(`
    SELECT wrc.batter_ID,
           COALESCE(b.player_name, 'Unknown') AS player_name,
           b.player_team,
           wrc.season, wrc.PA,
           wpf.home_stadium,
           ROUND(wpf.home_run_pf, 1) AS home_pf,
           ROUND(wpf.wpf_run, 1) AS weighted_pf,
           ROUND(wrc.wRC_half, 1) AS wRC_half,
           ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
           ROUND(wrc.wRC_weighted - wrc.wRC_half, 2) AS delta
    ${WRC_JOIN}
    WHERE wrc.season = ? AND wrc.PA >= ?
    ORDER BY (wrc.wRC_weighted - wrc.wRC_half) ${order}
    LIMIT ?
  `).bind(season, minPa, n).all();
  return json(results);
}

/** 원본 966-1007. 선수 한 명의 시즌별 이력과 구장별 타석 분포입니다. */
export async function wrcBatter(request, env, ctx, params) {
  const db = env.DB;
  const batterId = params.id;

  const { results: history } = await db.prepare(`
    SELECT wrc.season, wrc.PA,
           wpf.home_stadium,
           ROUND(wrc.wOBA, 4) AS wOBA,
           ROUND(wrc.wRAA_FG, 1) AS wRAA,
           ROUND(wpf.home_run_pf, 1) AS home_pf,
           ROUND(wpf.wpf_run, 1) AS weighted_pf,
           ROUND(wrc.wRC_home, 1) AS wRC_home,
           ROUND(wrc.wRC_half, 1) AS wRC_half,
           ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
           COALESCE(b.player_name, 'Unknown') AS player_name,
           b.player_team,
           b.batting_average AS AVG, b.on_base_percentage AS OBP,
           b.slugging_percentage AS SLG, b.on_base_plus_slugging AS OPS
    ${WRC_JOIN}
    WHERE wrc.batter_ID = ?
    ORDER BY wrc.season
  `).bind(batterId).all();

  const { results: stadiumDist } = await db.prepare(`
    SELECT substr(gameID,1,4) AS season, stadium, COUNT(*) AS pa
    FROM play_by_play
    WHERE batter_ID = ? AND substr(gameID,1,4) BETWEEN '2015' AND '2026'
    GROUP BY season, stadium
    ORDER BY season, pa DESC
  `).bind(batterId).all();

  // 원본: history 가 비면 None 입니다. 빈 문자열이 아닙니다.
  const name = history.length ? history[0].player_name : null;
  return json({
    batter_id: batterId,
    player_name: name,
    history,
    stadium_distribution: stadiumDist,
  });
}

/** 원본 1010-1029. 타자 이름 검색입니다. season=0 이면 전 시즌입니다. */
export async function wrcBatterSearch(request, env) {
  const url = new URL(request.url);
  const q = queryStr(url, 'q', '');
  const season = queryInt(url, 'season', 0);

  let sql = `
    SELECT DISTINCT b.player_id, b.player_name, b.player_team, b.season
    FROM kbo_official_batter_stats b
    WHERE b.player_name LIKE ?`;
  const binds = [`%${q}%`];
  if (season) {
    sql += ' AND b.season = ?';
    binds.push(season);
  }
  sql += ' ORDER BY b.season DESC, b.player_name LIMIT 50';

  const { results } = await env.DB.prepare(sql).bind(...binds).all();
  return json(results);
}

/**
 * season 은 기본값이 없는 필수 파라미터입니다. FastAPI 가 없으면 422 를
 * 냅니다. leaders.js 와 같은 형태로 맞춥니다.
 */
function missingSeason() {
  return json({
    detail: [{
      type: 'missing',
      loc: ['query', 'season'],
      msg: 'Field required',
      input: null,
    }],
  }, 422);
}
