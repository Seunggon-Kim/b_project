# 3단계 API 대조: D1 ↔ MySQL (2026-10-04)

운영 API(`kbo-api`)는 2026-10-04 01시경(KST)에 MySQL(Hyperdrive)로 앞당겨 전환했습니다(로드맵 "3단계 결과"). 전환 뒤 D1 하루 한도가 풀린 10시 이후, 같은 코드를 D1 으로 읽는 스테이징(`kbo-api-stg-d1`)과 운영(MySQL)의 응답을 견줬습니다.

## 방법

- 도구: `scripts/api_compare.mjs`(본문 전체 비교, JSON 아니면 sha256, 기대 상태 코드, `--unordered` 는 배열을 다중집합으로 비교).
- 주소: `scripts/api_compare_urls.txt` 102개 중 101개. `/db/table/play_by_play?offset=2000000` 하나는 D1 읽기량(약 70만 행) 때문에 뺐습니다.
- A = `https://kbo-api-stg-d1.bstats-baseball.workers.dev`(D1), B = `https://kbo-api.bstats-baseball.workers.dev`(운영, MySQL).
- 원본 보고서: [엄격 비교](api-compare-phase3-strict.md)(배열 순서까지), [순서 무시](api-compare-phase3-unordered.md)(엄격에서 다른 43개만, 문자중계 CSV 제외).

## 결과

| 단계 | 견준 주소 | 다른 주소 |
|---|---|---|
| 엄격 | 101 | 44 |
| 순서 무시(다른 43개만) | 43 | 23 |

**계산이 다른 곳은 없습니다.** 남은 차이는 모두 아래로 설명됩니다.

| 분류 | 주소(예) | 설명 | 판단 |
|---|---|---|---|
| 동률의 순서 | `/leaders`, `/stats/*`, `/games`, `/roster/moves`, `/wrc/leaderboard`, `/wrc/batter-search`, `/wrc/batter/:id` 구장 분포 | 정렬 값이 같은 행의 순서가 엔진마다 다릅니다(순서 무시에서 사라진 20개). | 동률 순서를 고정함(아래) |
| 동률 경계 | `/stats/pitchers?season=2019&limit=50` 50위(평균자책 3.62: 장필준 ↔ 쿠에바스), `/stats/batters?season=2025&limit=50` 50위(타율 .275: 황재균 ↔ 윤도현), `/leaders?season=2015` 탈삼진 5위(164: 윤성환 ↔ 해커), `/players/search?q=김`(정렬 없는 LIMIT 50), `/games?limit=30` 같은 날 경기, `/db/table/*` 행(D1 rowid 순 ↔ InnoDB 기본키 순) | LIMIT 로 자를 때 같은 값의 누가 들어오는지가 다릅니다. | 동률 순서를 고정함(아래) |
| 기록 시각 | `/stats/*?season=2026`, `/players/53375` 의 `updated_at`(01:24:49 ↔ 01:24:53) | 이중 적재가 D1 다음 MySQL 에 쓰는 몇 초 차이입니다. | 받아들임 |
| 1단계 데이터 수정 | `/players/77829/usage?season=2010`(투구 2768 ↔ 2891), `/wrc/batter/74163` 구장 분포, `/db/table/play_by_play`(`74163.0` ↔ `74163`, `pbp_id`) | `.0` 꼴 ID 통일, 2008~2015 포스트시즌 날짜 수정, `pbp_id` 새로 매김 | 받아들임(MySQL 쪽이 맞음) |
| 표 정보 표시 | `/db/table/*` 의 `schema[].type`·`notnull` | MySQL 타입을 SQLite 식으로 바꿔 보여 줍니다. 기본키 열은 늘 NOT NULL 입니다. | 받아들임 |
| D1 옛 사본 | `/stats/team_range?start=20190501&end=20190531` | D1 은 문자중계 샤드마다 따로 둔 `games`·`teams` 사본 때문에 경기 0개짜리 "SSG" 줄이 하나 더 나옵니다. MySQL 은 한 표라 SK 10팀입니다. | MySQL 쪽이 맞음 |

## 뒤따른 일

- 동률 순서 고정: 목록 질의의 ORDER BY 끝에 고유 열(선수 ID·경기 ID 등)을 더해 같은 요청이 늘 같은 순서를 돌려주게 했습니다(브랜치 `fix/stable-tie-order`).
- 스테이징 Worker 두 개(`kbo-api-stg-d1`, `kbo-api-stg-my`)는 5단계(D1 정리) 때 지웁니다.
