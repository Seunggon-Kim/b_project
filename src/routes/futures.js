import { kboTosGone } from '../lib/respond.js';

// KBO 퓨처스리그 일정/결과 (실시간 스코어보드 프록시).
//
// 원본 api/main.py:1230-1371 의 _futures_teams_map / _futures_scoreboard /
// _futures_int / get_futures_schedule 을 옮긴 것입니다.
//
// Schedule.asmx(스케줄 리스트)는 진행 중 경기를 0:0으로만 표시(라이브 스코어
// 없음)하므로, 1군(Naver)처럼 실시간 스코어보드 GetKboGameList(leId=2)를
// 프록시합니다. 라이브 스코어·현재 이닝·등판 투수·승/패/세이브까지 제공하며
// 과거 날짜·교류전도 동일하게 처리합니다.
// (data_collection/futures_schedule.py + futures_games 테이블은 분석용
// 웨어하우스로 별도 유지됩니다.)
//
// **2026-10-14 시행 KBO 이용약관 제14조 차항에 따라 프록시를 멈췄습니다.**
// `/schedule/futures` 는 외부 호출 없이 410 을 돌려줍니다. 아래 두 도우미는
// 테스트가 쓰고 있어 남겨 둡니다.

/**
 * 경기 목록에 나온 선수 이름을 모읍니다(중복·빈 값 제외).
 *
 * 퓨처스 카드의 선수 이름에 링크가 없었습니다. 1군 카드는 선발·승패
 * 투수가 모두 링크인데 퓨처스만 그냥 글자였습니다. KBO 퓨처스 피드가
 * 이름만 주고 선수 ID 를 주지 않기 때문입니다.
 */
export function collectNames(games) {
  const out = [];
  const seen = new Set();
  for (const g of games || []) {
    const d = g.decisions || {};
    for (const v of [d.win, d.lose, d.save, g.currentPitcher, g.currentBatter]) {
      const name = String(v || '').trim();
      if (!name || seen.has(name)) continue;
      seen.add(name);
      out.push(name);
    }
  }
  return out;
}

/**
 * 이름으로 선수 ID 를 고릅니다. 못 고르면 null 입니다.
 *
 * 이름이 겹치면 팀으로 좁힙니다. 팀으로도 못 좁히면 **링크를 걸지
 * 않습니다.** 엉뚱한 선수로 보내느니 글자로 두는 편이 낫습니다.
 */
export function pickPlayerId(candidates, name, teamName) {
  const key = String(name || '').trim();
  if (!key) return null;
  const hits = (candidates || []).filter(
    (c) => String(c.player_name || '').trim() === key);
  if (hits.length === 1) return hits[0].player_id;
  if (!hits.length) return null;
  const team = String(teamName || '').trim();
  if (!team) return null;
  const byTeam = hits.filter((c) => String(c.team || '').trim() === team);
  return byTeam.length === 1 ? byTeam[0].player_id : null;
}

/**
 * 2026-10-14 시행 KBO 이용약관 제14조 차항(자동 수집·재배포 금지)에 따라
 * KBO 사이트를 읽지 않고 410 을 돌려줍니다.
 */
export function futures() {
  return kboTosGone();
}

