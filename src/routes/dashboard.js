import { json } from '../lib/respond.js';

/**
 * 원본 api/main.py:82-107 입니다.
 *
 * 원본의 `one(q)` 헬퍼는 쿼리가 실패하면 예외를 삼키고 0 을 돌려줍니다.
 * 표가 없는 DB 에서도 화면이 뜨게 하려는 처리라 그대로 옮깁니다.
 */
async function one(db, sql) {
  try {
    const row = await db.prepare(sql).first();
    if (!row) return 0;
    const v = Object.values(row)[0];
    return v === null || v === undefined ? 0 : v;
  } catch {
    return 0;
  }
}

export async function dashboardStats(request, env) {
  try {
    const db = env.DB;
    // GLOB 은 SQLite 문법이라 D1 에서도 그대로 씁니다.
    const seasonFilter = "WHERE substr(gameID,1,4) GLOB '20[0-2][0-9]'";

    const games = await one(db,
      `SELECT COUNT(DISTINCT gameID) FROM play_by_play ${seasonFilter}`);
    const plays = await one(db, 'SELECT COUNT(*) FROM play_by_play');
    const batters = await one(db,
      'SELECT COUNT(DISTINCT player_id) FROM kbo_official_batter_stats');
    const pitchers = await one(db,
      'SELECT COUNT(DISTINCT player_id) FROM kbo_official_pitcher_stats');
    const players = await one(db, 'SELECT COUNT(*) FROM players');
    const teamsCount = await one(db, 'SELECT COUNT(*) FROM teams');
    const smin = await one(db,
      `SELECT MIN(substr(gameID,1,4)) FROM play_by_play ${seasonFilter}`);
    const smax = await one(db,
      `SELECT MAX(substr(gameID,1,4)) FROM play_by_play ${seasonFilter}`);

    // 원본: seasons = str(smin) if smin == smax else f"{smin}~{smax}"
    // 문자열입니다. 정수가 아닙니다.
    const seasons = smin === smax ? String(smin) : `${smin}~${smax}`;

    return json({
      games,
      plays,
      batters,
      pitchers,
      players,
      teams: teamsCount,
      seasons,
      status: 'ok',
    });
  } catch (err) {
    // 원본은 예외 시 error 와 traceback 을 돌려줍니다. JS 에는 파이썬식
    // traceback 이 없어 스택을 그 자리에 넣습니다.
    return json({
      error: String(err && err.message ? err.message : err),
      traceback: String((err && err.stack) || ''),
    });
  }
}
