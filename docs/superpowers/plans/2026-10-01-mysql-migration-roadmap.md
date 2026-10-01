# D1 → Cloud SQL(MySQL) 이전 로드맵

> 이 문서는 전체 지도입니다. 단계마다 상세 계획서를 따로 둡니다.
> 지금 상세 계획서가 있는 단계는 1단계뿐입니다:
> `docs/superpowers/plans/2026-10-01-mysql-phase1-schema-and-load.md`
> 2단계부터는 1단계 결과(실제 스키마, 데이터 품질 보고)를 보고 씁니다.

## 왜 옮기나

2026-10-01 조사에서 다음이 확인됐습니다.

- D1 무료 요금제의 하루 읽기 한도(500만 행, 09:00 KST 초기화)를 9월에만
  4일 넘겼습니다. 9/29 에는 약 23시간 D1 이 막혀 그날 1군 등록·말소가
  영구히 빠졌습니다(KBO 는 그날 것만 공개).
- 주된 원인은 주 1회 파크팩터 작업의 전체 내려받기(약 400만 행 + 확인용
  COUNT 400만 행)와, 행 수 메타가 없는 샤드 두 개를 `/dashboard/stats` 가
  통째로 세는 것(호출당 약 120만 행)입니다.
- 이 사이트는 포트폴리오로도 쓰므로 실무에서 쓰는 DB 를 원합니다. 7개로
  나뉜 D1 을 한 DB 로 통합 관리하기를 원합니다.

## 목표 구조

```
수집(GitHub Actions) ──> Cloud SQL MySQL 8.4 `bstats` (한 DB) ──> API(Cloudflare Worker) ──> 화면(Pages)
                              │                                  (Hyperdrive + mysql2)
                              └──> BigQuery (Cloud SQL 연합 쿼리, 분석)
```

이미 만든 것(2026-10-01):

| 항목 | 값 |
|---|---|
| GCP 프로젝트 | `bstats-kbo` (개인 결제 계정, 원화) |
| gcloud 설정 | `bstats` (기본값 아님. 명령마다 `--configuration=bstats`) |
| 예산 알림 | 월 30,000원, 50·90·100% |
| 인스턴스 | `bstats-mysql`, asia-northeast3, MYSQL_8_4, db-f1-micro, SSD 10GB 자동 증가 |
| 보안 | `ENCRYPTED_ONLY`, 삭제 방지, 허용 네트워크 없음 |
| 백업 | 매일 17:00 UTC(02:00 KST), 7개 보관 |
| 점검 | 일요일 19:00 UTC(월 04:00 KST) |
| 데이터베이스 | `bstats` utf8mb4 / utf8mb4_0900_ai_ci |
| 관리자 비밀번호 | `~/.bstats/cloudsql_root_password.txt` (저장소 밖) |

## 원칙

- **전환 전까지 D1 이 정본입니다.** MySQL 은 사본입니다. 사이트와 수집은
  전환 날까지 D1 으로 돕니다.
- **API 응답 모양을 바꾸지 않습니다.** 필드 이름, 타입(문자열/숫자), 순서,
  소수 자릿수가 같아야 합니다. 화면은 이전을 몰라야 합니다.
- **비밀은 저장소에 두지 않습니다.** 비밀번호·키는 `~/.bstats/` 또는
  GitHub/Cloudflare 시크릿에만 둡니다.
- **회사 GCP·회사 계정(@delivered.co.kr)을 쓰지 않습니다.**
- **D1 읽기 예산을 지킵니다.** D1 을 통째로 읽는 일은 그날 사용량을 먼저
  보고 합니다(1단계 `migration/mysql/d1_usage.py`).
- 배포·push·D1 쓰기·요금이 드는 GCP 변경은 evan 확인 후에 합니다.

## 단계

### 0단계: 안정화 (D1 을 쓰는 동안 데이터 손실 막기)

이전은 몇 주 걸립니다. 그동안 D1 이 막히면 등록·말소가 또 빠집니다.
아래는 서로 독립이라 하나씩 승인받아 진행합니다.

| # | 할 일 | 효과 | 상태 |
|---|---|---|---|
| 0-1 | D1 유료 전환(월 5달러) | 하루 한도 문제 즉시 해소 | evan 결정 대기 |
| 0-2 | `kbo-pbp-2008-2011`·`kbo-pbp-2012-2014` 의 `meta_table_counts` 에 `play_by_play` 행 수(668,325 / 547,226) 기록 | `/dashboard/stats` 캐시 미스당 120만 행 읽기 제거 | 승인 대기(D1 쓰기 2행) |
| 0-3 | `sync_players_from_roster.py` 가 `teams` 에 없는 팀(상무·울산)을 건너뛰게 수정, `roster.yml` 뒤 단계 조건을 `!cancelled() &&` 로 | 8/29 이후 33번 연속 실패 해소, 퓨처스 기록·캐시 비우기 정상화 | 승인 대기 |
| 0-4 | 오류 응답에 `cache-control: no-store`(Worker 11개 라우트), 화면은 `error` 필드를 보고 "불러오지 못했습니다" 표시(화면 세션) | 한 번의 D1 실패가 10분~1시간 굳는 것 방지 | 승인 대기 |
| 0-5 | 이전이 끝날 때까지 주 1회 파크팩터 작업의 확인용 COUNT 를 끄거나 작업을 멈춤 | 주 1회 한도 초과 방지 | 승인 대기 |

### 1단계: 스키마 설계와 데이터 이전 (상세 계획서 있음)

D1 을 로컬 SQLite 스냅샷으로 한 번 내려받고, 그 스냅샷에서 MySQL 로
옮긴 뒤, 두 쪽을 행 수와 열별 합계로 대조합니다. D1 읽기는 내려받기
한 번뿐입니다. 결과물은 검증된 MySQL 사본과 데이터 품질 보고서입니다.

이 단계에서 정하는 스키마 규칙:

- 7개 D1 을 한 DB 로 합칩니다. `play_by_play` 는 한 표가 됩니다.
- `play_by_play.pbp_id` 는 새로 매깁니다(`BIGINT UNSIGNED AUTO_INCREMENT`).
  샤드마다 번호를 따로 붙여 겹칠 수 있기 때문입니다. 시즌 순 → 샤드 안
  원래 번호 순으로 넣어 경기 안의 순서(RE24 계산이 `ORDER BY pbp_id`
  에 기댐)를 지킵니다.
- 선수 ID 열(`player_id`, `batter_ID`, `pitcher_ID`, `on_1b_id`…, `pos_1_id`…)
  은 값이 모두 정수면 `INT UNSIGNED` 로 통일합니다. `'78513.0'` 같은
  float 표기는 정수로 고칩니다.
- 숫자 열(INTEGER/REAL 선언)의 빈 문자열 `''`·`'-'` 은 `NULL` 로 바꿉니다.
- 선언은 TEXT 이지만 값이 모두 `YYYY-MM-DD` 면 `DATE`,
  `YYYY-MM-DD HH:MM:SS` 면 `DATETIME` 으로 둡니다. `game_date`(YYYYMMDD
  정수)는 `INT` 그대로 둡니다.
- 그 밖의 TEXT 는 실제 최대 길이의 두 배 이상인 `VARCHAR` 단계로 둡니다.
  `back_number` 처럼 `'00'` 과 `'0'` 이 다른 열은 글자로 남습니다.
- `_bak` 표, `sqlite_*`·`_cf_*`·`d1_migrations` 는 옮기지 않습니다.

### 2단계: 수집 스크립트를 MySQL 로 (상세 계획서는 1단계 뒤)

- `data_collection/d1_load.py` 에 모인 적재 함수(`run_d1`, `run_d1_file`,
  `query`, `build_upserts`, `build_inserts`, `refresh_count`)를 같은
  이름의 MySQL 판 `data_collection/db_load.py` 로 만들고, 스크립트는
  import 한 줄만 바꿉니다.
- 바꿔야 할 SQLite 문법(1단계 조사 결과): `ON CONFLICT … DO UPDATE` 4곳,
  `INSERT OR REPLACE` 2곳, `INSERT OR IGNORE` 1곳, `datetime('now')` 6곳,
  `PRAGMA table_info` 1곳, 큰따옴표 식별자 여러 곳, 별칭 없는 파생 표 2곳
  (`heal_player_photos.py`), MySQL 예약어 `rank` 열(`team_ranks.py`),
  TEXT 를 PK 에 쓰는 DDL 3곳.
- 값을 전부 따옴표 문자열로 넣는 `sql_literal` 은 MySQL 엄격 모드에서
  깨집니다. 파라미터 바인딩(`cursor.executemany`)으로 바꿉니다.
- 이중 적재 기간: 한동안 D1 과 MySQL 에 같이 씁니다. 매일 행 수를 대조합니다.
- GitHub Actions 접속: Cloud SQL Auth Proxy + 수집 전용 서비스 계정 키
  (GitHub 시크릿). 러너 IP 가 매번 바뀌어 IP 허용 방식은 쓰지 않습니다.
- 수집기 버그: 포스트시즌 일부 경기(경기 코드 3333/5555/7777)의 play_by_play.game_date 에 경기 코드 일부(예: TOB00929)가 들어갑니다. 2026 포스트시즌 전에 고칩니다(1단계 리허설에서 발견, 2026-10-02).

### 3단계: API 를 MySQL 로 (상세 계획서는 2단계 뒤)

- Cloudflare Hyperdrive(MySQL 정식 지원, 2026-08) + `mysql2`.
  `compatibility_flags = ["nodejs_compat"]` 가 필요합니다.
- 연결 옵션: `dateStrings: true`(DATE/DATETIME 을 문자열로),
  `decimalNumbers: true`(SUM/AVG 의 DECIMAL 을 숫자로), `supportBigNumbers`.
- 바꿔야 할 SQL(조사 결과, `src/`):
  - 별칭 없는 파생 표 5곳(players.js 3, stats.js 1, futuresplayer.js 1)
  - `CAST(… AS TEXT)` 6곳 → `CAST(… AS CHAR)`, `AS INT/INTEGER` 2곳 → `AS SIGNED`
  - `CAST(… AS REAL)` 3곳: SQLite 의 앞부분 숫자 해석('98 1/3' → 98)에 기댐 → 명시적 파싱
  - 스칼라 `MIN(?, x)` 1곳 → `LEAST`, `date('now','+9 hours',?)` 1곳, 정수 나눗셈 1곳 → `DIV`
  - `sqlite_master`·`PRAGMA table_info` 7곳 → `information_schema`
  - 큰따옴표 식별자 8곳 → 백틱
  - `LIMIT ?` 10곳: mysql2 `execute()` 의 숫자 바인딩 문제 확인
  - `ROUND` 36곳, `SUM`·`AVG` 22곳: DOUBLE/DECIMAL 반올림 차이를 저장된 정답과 바이트 단위로 대조
- 샤드 계층(`shard.js`, `pbpvirtual.js` 의 분할, `fanOut`)은 한 DB 라 걷어냅니다.
- 소스 문자열을 검사하는 테스트 6개(sqlbind, kbbpct, seasonteam, playerteam,
  schedulelink, teamseason)를 함께 고칩니다.
- Hyperdrive 의 접속 경로(공인 IP 허용 목록 또는 Cloudflare Tunnel)는
  이 단계에서 정합니다.

### 4단계: 빅쿼리 연결 (상세 계획서는 3단계 뒤)

- BigQuery Connection API 로 Cloud SQL 연결을 만들고, 데이터셋은 같은
  지역(asia-northeast3)에 둡니다. `EXTERNAL_QUERY` 로 MySQL 표를 바로 봅니다.
- 파크팩터·wRC+·RE24 계산을 빅쿼리 SQL 로 옮기는 것은 여기서 검토합니다.

### 5단계: 전환과 정리

- 전환일: D1 쓰기 중지 → 마지막 변경분 동기화 → 대조 → Worker 를 MySQL
  판으로 배포 → 하루 지켜보기.
- D1 은 2주 동안 읽기 전용으로 두고, 이상 없으면 지웁니다. D1 유료였다면
  해지합니다.

## 접속 설계

| 누가 | 방법 | 계정 | 단계 |
|---|---|---|---|
| 이전 작업(evan PC) | 공인 IP `/32` 허용 + TLS + 서버 CA 검증 | `bstats_migrator` (bstats.* 전체) | 1 |
| 수집(GitHub Actions) | Cloud SQL Auth Proxy + 서비스 계정 키 | `bstats_loader` (bstats.* 읽기·쓰기) | 2 |
| API(Cloudflare Worker) | Hyperdrive | `bstats_api` (bstats.* 읽기 전용) | 3 |
| 분석(BigQuery) | Cloud SQL 연결 | `bstats_bq` (읽기 전용) | 4 |

## 비용

- Cloud SQL: 월 약 1.5만~2만 원(db-f1-micro, SSD 10GB, 백업). 이미 과금 중입니다.
- BigQuery: 무료 범위(저장 10GiB, 조회 월 1TiB) 안으로 예상합니다.
- D1 유료를 고르면 이전 기간 동안 월 5달러가 더해집니다.

## 결정 대기

1. 0단계 항목별 승인(특히 0-1 D1 유료, 0-2 메타 2행 쓰기).
2. 1단계 스냅샷을 하루에 받을지(유료) 이틀에 나눠 받을지(무료).
