import { json } from '../lib/respond.js';
import { countOf } from '../lib/counts.js';

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

    // 원본은 이 네 값을 play_by_play 풀스캔으로 얻었습니다. 한 번 호출에
    // 229,667 × 4 = 약 92만 행을 읽었고, 이 엔드포인트가 홈·팀통계·데이터
    // 탐색 세 화면에 걸려 있습니다. 12시즌이면 한 번에 약 1,100만 행으로
    // 하루 한도(500만)의 두 배가 됩니다.
    //
    // 경기 수와 시즌 범위는 games(719행)에서 같은 값이 나옵니다.
    // 플레이 수만은 pbp 의 행 수 자체라 games 로 대신할 수 없어, 적재할 때
    // 기록해 두는 meta_table_counts 에서 읽습니다.
    //
    // GLOB 은 SQLite 문법이라 D1 에서도 그대로 씁니다. games 에는 gameID 가
    // 아니라 season(INTEGER)이 있으므로 범위 비교로 바꿉니다. 원본의
    // '20[0-2][0-9]' 는 2000~2029 를 뜻합니다.
    const games = await one(db,
      'SELECT COUNT(*) FROM games WHERE season BETWEEN 2000 AND 2029');
    const plays = await countOf(db, 'play_by_play');
    const batters = await one(db,
      'SELECT COUNT(DISTINCT player_id) FROM kbo_official_batter_stats');
    const pitchers = await one(db,
      'SELECT COUNT(DISTINCT player_id) FROM kbo_official_pitcher_stats');
    const players = await one(db, 'SELECT COUNT(*) FROM players');
    const teamsCount = await one(db, 'SELECT COUNT(*) FROM teams');
    // 원본은 문자열 MIN/MAX(substr(...)) 이었습니다. 값이 같도록 문자열로
    // 돌려줍니다. games.season 은 정수라 그대로 쓰면 타입이 달라집니다.
    const sminRow = await one(db,
      'SELECT MIN(season) FROM games WHERE season BETWEEN 2000 AND 2029');
    const smaxRow = await one(db,
      'SELECT MAX(season) FROM games WHERE season BETWEEN 2000 AND 2029');
    const smin = sminRow === null ? null : String(sminRow);
    const smax = smaxRow === null ? null : String(smaxRow);

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
