// 경기 ID 로 정규시즌 공만 고르는 SQL 조각입니다.
//
// data_collection/game_type.py 와 같은 규칙입니다. 정규시즌 경기 ID 는
// 날짜(YYYYMMDD)로 시작하고, 포스트시즌은 시리즈 코드로 시작합니다.
//
//     3333 준플레이오프 · 4444 와일드카드 · 5555 플레이오프 · 7777 한국시리즈
//     9999 올스타전(집계 대상 아님)
//     6666 순위결정전은 KBO 가 개인 기록을 정규시즌에 넣으므로 정규시즌입니다.
//
// 시범경기는 수집 단계에서 이미 빠집니다(game_type.py 의 roundCode kbo_e).
//
// games 표의 game_type 과 맞대지 않는 이유: games 에 빠진 날(2026-09-01 처럼
// 문자중계만 있고 경기 결과가 안 만들어진 날)이 있으면 그날 공이 정규시즌인데도
// 빠집니다. 경기 ID 는 문자중계 행 자체에 있어 그런 영향을 받지 않습니다.
export const NON_REGULAR_PREFIXES = ['3333', '4444', '5555', '7777', '9999'];

/** `alias.gameID` 가 정규시즌 경기인 조건(앞에 AND 를 붙여 씁니다). */
export function regularSeasonSql(alias) {
  return NON_REGULAR_PREFIXES
    .map((p) => `${alias}.gameID NOT LIKE '${p}%'`)
    .join(' AND ');
}
