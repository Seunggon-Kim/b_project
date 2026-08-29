import { json } from '../lib/respond.js';
import { queryInt } from '../lib/router.js';

// 1군 등록·말소 현황입니다.
//
// KBO 는 **오늘 것만** 보여 줍니다. 어제 누가 등록됐는지 묻는 화면이
// 없어서, daily 가 매일 받아 `kbo_roster_moves` 에 쌓습니다. 소급이
// 안 되므로 쌓기 시작한 날부터만 있습니다.

/**
 * 등록·말소입니다. 기본은 **가장 최근 하루**입니다.
 *
 * 예전에는 최근 7일을 줬습니다. 그런데 같은 선수가 날짜만 바뀌어
 * 여러 번 나왔습니다. `move_date` 에 수집일을 넣고 있었기 때문입니다.
 * KBO 등말소는 경기 2~4시간 전에 갱신되므로 새벽에 도는 daily 는
 * 전날 명단을 봅니다. 이제 페이지가 주는 날짜를 쓰므로 같은 내용이
 * 겹치지 않지만, 화면에는 최신 하루만 보이는 편이 읽기 좋습니다.
 *
 * `?days=N` 을 주면 최근 N일입니다. `?limit=N` 은 행 수 상한입니다.
 *
 * **날짜별로 묶어 돌려줍니다.** 화면이 "오늘 / 어제" 로 나눠 보여
 * 주기 때문입니다. 평평한 목록으로 주면 화면에서 다시 묶어야 합니다.
 *
 * `player_id` 는 없을 수 있습니다. 등록 현황 페이지가 이름과 등번호만
 * 주기 때문에, 우리 기록과 짝이 안 지어지면 비웁니다(신인 등).
 * 화면은 그때 링크 없이 이름만 보여 줍니다.
 */
export async function rosterMoves(request, env) {
  const url = new URL(request.url);
  const days = Math.min(Math.max(queryInt(url, 'days', 0), 0), 60);
  const limit = Math.min(Math.max(queryInt(url, 'limit', 60), 1), 300);

  const COLS = 'move_date, kind, team, name, position, player_id';
  let results;
  if (days === 0) {
    // 가장 최근 하루입니다. **오늘 날짜로 자르지 않습니다.** KBO 가
    // 경기 전에 갱신하므로 새벽에는 아직 어제 것이 최신입니다.
    const { results: rows } = await env.DB.prepare(
      `SELECT ${COLS} FROM kbo_roster_moves `
      + 'WHERE move_date = (SELECT MAX(move_date) FROM kbo_roster_moves) '
      + 'ORDER BY kind DESC, team LIMIT ?',
    ).bind(limit).all();
    results = rows;
  } else {
    // move_date 는 'YYYY-MM-DD' 문자열입니다. date() 로 비교하면
    // 인덱스를 못 타므로 문자열 범위로 자릅니다.
    const { results: rows } = await env.DB.prepare(
      `SELECT ${COLS} FROM kbo_roster_moves `
      + "WHERE move_date >= date('now', '+9 hours', ?) "
      + 'ORDER BY move_date DESC, kind DESC, team LIMIT ?',
    ).bind(`-${days} days`, limit).all();
    results = rows;
  }

  // 날짜별로 묶습니다. 순서는 최신 날짜가 먼저입니다.
  //
  // **키는 영어로 둡니다.** D1 에는 '등록'·'말소' 로 저장하지만 JSON
  // 키를 한글로 두면 화면에서 `x.등록` 이 안 되고 `x['등록']` 만
  // 됩니다. 값은 한글 그대로 두어 화면이 그대로 쓰게 합니다.
  const KIND_KEY = { 등록: 'added', 말소: 'removed' };
  const byDate = [];
  const index = new Map();
  for (const r of results) {
    let slot = index.get(r.move_date);
    if (!slot) {
      slot = { date: r.move_date, added: [], removed: [] };
      index.set(r.move_date, slot);
      byDate.push(slot);
    }
    const bucket = slot[KIND_KEY[r.kind]];
    if (bucket) {
      bucket.push({
        team: r.team,
        name: r.name,
        position: r.position,
        playerId: r.player_id,
      });
    }
  }

  return json({ days, count: results.length, dates: byDate });
}

/**
 * 지금 1군 명단입니다. 팀을 주면 그 팀만 돌려줍니다.
 *
 * 이 표는 오늘 상태만 담습니다(이력은 `kbo_roster_moves`). 1군을 떠난
 * 선수는 적재할 때 지웁니다.
 */
export async function roster(request, env) {
  const url = new URL(request.url);
  const team = url.searchParams.get('team');
  // 이 표에는 1군과 퓨처스 명단이 함께 있습니다(소속 판정에 둘 다
  // 필요합니다). 화면이 '1군 명단' 을 부르므로 기본은 1군입니다.
  // 그대로 두면 KIA 가 60명으로 나옵니다.
  const league = url.searchParams.get('league') || '1군';

  const conds = ["league = ?"];
  const binds = [league];
  if (team) {
    conds.push('team = ?');
    binds.push(team);
  }
  const where = `WHERE ${conds.join(' AND ')}`;
  const stmt = env.DB.prepare(
    'SELECT team, name, back_number, role, player_id, as_of '
    + `FROM kbo_roster ${where} `
    // 포지션 순서를 투수·포수·내야수·외야수로 고정합니다. 사전순으로
    // 두면 내야수가 맨 앞에 와서 야구 화면답지 않습니다.
    + "ORDER BY team, CASE role WHEN '투수' THEN 1 WHEN '포수' THEN 2 "
    + "WHEN '내야수' THEN 3 ELSE 4 END, CAST(back_number AS INTEGER)",
  );

  const { results } = await stmt.bind(...binds).all();
  const asOf = results.length ? results[0].as_of : null;
  return json({ team, league, asOf, count: results.length, players: results });
}
