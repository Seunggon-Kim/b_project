import { kboTosGone } from '../lib/respond.js';

// 퓨처스(2군) 팀 순위와 개인 기록입니다.
//
// 1군 순위(`routes/standings.js`)와 같은 방식으로 KBO 사이트를 그때그때
// 읽습니다. D1 에 쌓지 않는 이유는 화면이 늘 최신만 보여 주면 되고,
// 쌓으면 daily 에 단계가 하나 더 늘기 때문입니다.
//
// 퓨처스는 **북부·남부 두 리그**로 나뉩니다. 페이지도 둘입니다.
//
// **2026-10-14 시행 KBO 이용약관 제14조 차항에 따라 KBO 사이트 읽기를
// 멈췄습니다.** 두 경로 모두 외부 호출 없이 410 을 돌려줍니다.

// 퓨처스 팀 -> 엠블럼 코드입니다.
//
// **상무와 울산은 제 로고가 따로 있습니다.** `assets/logos/SM.png`,
// `UL.png` 입니다. 퓨처스 경기 카드가 이미 그 코드를 쓰고 있었는데
// 순위표에서 빠뜨려 상무만 로고가 안 나왔습니다.
//
//     상무   국군체육부대           SM
//     울산   롯데 2군               UL
//     고양   히어로즈 2군           WO (제 로고 없음, 1군 것을 씁니다)
export const FUTURES_TEAM_CODE = {
  LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
  롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
  상무: 'SM', 울산: 'UL', 고양: 'WO',
};

/**
 * 2026-10-14 시행 KBO 이용약관 제14조 차항(자동 수집·재배포 금지)에 따라
 * KBO 사이트를 읽지 않고 410 을 돌려줍니다.
 */
export function futuresStandings() {
  return kboTosGone();
}

/**
 * 2026-10-14 시행 KBO 이용약관 제14조 차항(자동 수집·재배포 금지)에 따라
 * KBO 사이트를 읽지 않고 410 을 돌려줍니다.
 */
export function futuresLeaders() {
  return kboTosGone();
}
