import { kboTosGone } from '../lib/respond.js';

// 1군 등록·말소 현황과 1군 명단입니다.
//
// 예전에는 daily 가 KBO 사이트의 등록 현황을 매일 받아 `kbo_roster`·
// `kbo_roster_moves` 에 쌓았고, 이 두 경로가 그 표를 내보냈습니다.
//
// **2026-10-14 시행 KBO 이용약관 제14조 차항(자동 수집·재배포 금지)에 따라
// 수집을 멈췄고, 멈춘 표도 더 내보내지 않습니다.** 두 경로 모두 표를 읽지 않고
// 410 을 돌려줍니다(futures.js·futuresrecord.js 와 같은 방식).

/**
 * 등록·말소입니다. KBO 이용약관(2026-10-14 시행)에 따라 410 을 돌려줍니다.
 */
export function rosterMoves() {
  return kboTosGone();
}

/**
 * 1군 명단입니다. KBO 이용약관(2026-10-14 시행)에 따라 410 을 돌려줍니다.
 */
export function roster() {
  return kboTosGone();
}
