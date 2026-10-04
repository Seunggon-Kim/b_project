// play_by_play 가 있는 시즌과, 시즌을 game_date 범위로 고르는 도우미입니다.
//
// 네이버 문자중계는 2008 년부터 있습니다. 마지막 시즌은 지금 모으는
// 시즌입니다. 다음 시즌을 모으기 시작하면 PBP_LAST_SEASON 을 올려야
// 그 시즌의 구종·구사율·무브먼트·구종 가치·기간 기록이 나옵니다. 올리기
// 전에는 그 시즌을 "없는 시즌"으로 봅니다(빈 결과·404).
//
// 예전에는 D1 샤드 배정표(시즌 -> D1)가 이 범위를 정했습니다. 그 배정표의
// 시즌 목록(2008~2026, 빠짐 없음)을 그대로 옮겼습니다.

export const PBP_FIRST_SEASON = 2008;
export const PBP_LAST_SEASON = 2026;

/** play_by_play 가 있는 시즌 전부입니다(오름차순). */
export const PBP_SEASONS = Object.freeze(Array.from(
  { length: PBP_LAST_SEASON - PBP_FIRST_SEASON + 1 },
  (_, i) => PBP_FIRST_SEASON + i,
));

/**
 * play_by_play 가 있는 시즌인지 봅니다. 문자열 시즌도 받습니다.
 *
 * **거짓을 조용히 넘기지 마십시오.** 없는 시즌을 물으면 빈 결과가
 * 나오는데, 그것을 "경기가 없었다"로 보이면 사용자는 데이터가 사라진
 * 줄 모릅니다. 부르는 쪽에서 404 나 빈 응답으로 드러내십시오.
 */
export function hasPbpSeason(season) {
  return PBP_SEASONS.includes(Number(season));
}

/**
 * `play_by_play` 에서 한 시즌을 고르는 game_date 범위입니다.
 *
 * **`substr(gameID,1,4)` 를 쓰면 안 됩니다.** KBO 는 포스트시즌 gameID
 * 앞 네 자리에 연도 대신 시리즈 코드를 넣습니다.
 *
 *   33331008NCLT02017   3333=플레이오프,   연도는 맨 뒤
 *   44441005SKNC02017   4444=준플레이오프
 *   66661031KTSS02021   6666=와일드카드
 *
 * 앞 네 자로 자르면 이 경기들이 '3333' 시즌이 되어 결과에서 빠집니다.
 * 실제로 11경기 3,288행이 이렇습니다. game_date 는 두 형식 모두
 * YYYYMMDD 이고, 270만 행 전부에서 gameID 연도와 어긋나는 행이
 * 0개임을 확인했습니다.
 *
 * 숫자 비교라 문자열 substr 보다 빠르기도 합니다.
 */
export function seasonDateRange(season) {
  const y = Number(season);
  if (!Number.isFinite(y)) return null;
  return { from: y * 10000, to: (y + 1) * 10000 };
}

/**
 * game_date 범위(YYYYMMDD 정수)가 걸치는 시즌 목록입니다(오름차순).
 *
 * play_by_play 가 없는 연도는 빼므로, 2007 이전을 물어도 빈 목록이
 * 나올 뿐 오류가 아닙니다. 기간 조회는 목록이 비면 play_by_play 를 읽지
 * 않습니다(routes/teamrange.js).
 */
export function seasonsBetween(fromDate, toDate) {
  const a = Number(fromDate);
  const b = Number(toDate);
  if (!Number.isFinite(a) || !Number.isFinite(b) || a > b) return [];
  const out = [];
  for (let y = Math.floor(a / 10000); y <= Math.floor(b / 10000); y += 1) {
    if (hasPbpSeason(y)) out.push(y);
  }
  return out;
}
