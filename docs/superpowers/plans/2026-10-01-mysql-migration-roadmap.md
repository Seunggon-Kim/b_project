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
| 보안 | `ENCRYPTED_ONLY`, 삭제 방지, 허용 네트워크 없음(2026-10-02 삭제). 접속은 Cloud SQL Auth Proxy 로만 합니다 |
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
| 0-1 | D1 유료 전환(월 5달러) | 하루 한도 문제 즉시 해소 | 하지 않음(2026-10-02 evan 결정: 무료 유지, 이전을 빨리 끝냄) |
| 0-2 | `kbo-pbp-2008-2011`·`kbo-pbp-2012-2014` 의 `meta_table_counts` 에 `play_by_play` 행 수(668,325 / 547,226) 기록 | `/dashboard/stats` 캐시 미스당 120만 행 읽기 제거 | 완료(2026-10-02) |
| 0-3 | `sync_players_from_roster.py` 가 `teams` 에 없는 팀(상무·울산)을 건너뛰게 수정, `roster.yml` 뒤 단계 조건을 `!cancelled() &&` 로 | 8/29 이후 33번 연속 실패 해소, 퓨처스 기록·캐시 비우기 정상화 | 완료(2026-10-02, 브랜치 fix/phase2a-collectors, 커밋 847f314: teams 에 없는 소속 건너뜀, roster 뒤 단계 !cancelled()) |
| 0-4 | 오류 응답에 `cache-control: no-store`(Worker 11개 라우트), 화면은 `error` 필드를 보고 "불러오지 못했습니다" 표시(화면 세션) | 한 번의 D1 실패가 10분~1시간 굳는 것 방지 | 승인 대기 |
| 0-5 | 이전이 끝날 때까지 주 1회 파크팩터 작업의 확인용 COUNT 를 끄거나 작업을 멈춤 | 주 1회 한도 초과 방지 | 완료(2026-10-02, 브랜치 fix/phase2a-collectors, 커밋 2847d84: 주간 일정을 커밋으로 끔. 2B 에서 MySQL 기준으로 다시 켬) |

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

### 1단계 결과

- 2026-10-02 에 실행을 마쳤습니다. 30개 표, play_by_play 3,983,367행, 외래키 고아 행 0 입니다.
- 대조는 모두 같습니다(표별 행 수, 경기별 12,491경기, 표본 200행, 경기 안 순서 0건 뒤바뀜).
- 스냅샷은 혼합본입니다(공용 표·2008-2014·2024-2026 은 새로, 2015-2023 은 8/29 사본). 상세는 1단계 계획서 `실제 실행 기록`.
- 남은 보강은 아래 2단계 앞 목록입니다.

### 2단계: 수집 스크립트를 MySQL 로 (상세 계획서 있음)

상세 계획서는 `2026-10-02-mysql-phase2-overview.md` 에서 시작합니다(2A 수집기 버그,
2C 도구 보강, 2B 이중 적재). 아래 목록과 달라진 판단(백필은 끝나 meta 수정 대신 단계 삭제,
D1 의 깨진 포스트시즌 행은 고치지 않음, 키 대신 WIF, 보강 4건 중 2건 보류, `db_load.py`
대신 `mirror()`)은 개요 문서의 표에 이유와 함께 적었습니다. 아래는 1단계 때 쓴 원래 목록입니다.

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
- 다음 스냅샷·전환 전에 고칠 1단계 도구 보강(최종 검토 결과):
  1. 인덱스 이월: D1 의 `sqlite_master` 에서 인덱스 DDL(공용·샤드)을 읽어 스냅샷에 적용하는 단계를 코드로 만듭니다(`--all-tables` 일 때만). verify 가 schema_post 개체가 모두 있는지 확인합니다. 부분 UNIQUE 인덱스가 전체 UNIQUE 로 바뀌는 문제도 함께 처리합니다. **완료(2026-10-02, 2C):** 스냅샷이 D1 인덱스를 따라오고(`--indexes-only`), 부분 UNIQUE 는 옮기지 않으며, MySQL 에 공용 인덱스 13개와 `idx_pbp_game_date` 를 만들었습니다. verify `--objects-only` 로 확인합니다.
  2. `d1_to_sqlite --append` 보호: 행 수가 맞지 않으면 이번에 붙인 행을 지우고 멈춥니다. 받은 샤드 이름을 기록해 같은 샤드 재부착을 거부합니다. `--shards` 이름을 검증합니다. 쓰는 중인 샤드는 `--count-check d1` 로 확인합니다. 계획 Step 3 기대값을 샤드별 합계와 정확히 비교합니다. **보류(2026-10-02):** 2B 따라잡기는 공용 표 다시 넣기와 PBP 다시 받기라 이 기능을 쓰지 않습니다. 전체 재이전 때 합니다.
  3. 적재기: 시작할 때 같은 계정의 이전 연결을 정리합니다. `SET SESSION lock_wait_timeout=120` 을 둡니다. 가능하면 이 프로세스가 쓴 연결 번호만 끊습니다. KILL 범위 문구를 실제와 맞춥니다(같은 계정·같은 DB 의 다른 연결을 모두 끊습니다. 적재 중 verify 등 동시 실행 금지). **완료(2026-10-02, 2C):** 시작 때 정리, `lock_wait_timeout` 120초, `--post-only`. 이 프로세스의 연결만 끊는 방식 대신 같은 계정·같은 DB 의 다른 연결을 모두 끊고, 수집 계정으로는 시작하지 않게 했습니다.
  4. 스냅샷 지문: `--fresh` 때 스냅샷 이름·크기·표별 행 수·schema_types.json 해시를 MySQL 작은 표에 남기고 `--resume`·verify 가 확인합니다. 스냅샷의 옮길 표·열이 schema_types.json 에 없으면 load·verify 가 실패합니다. **보류(2026-10-02):** 2번과 같은 이유입니다.
- `shard_backfill` 이 meta_table_counts 를 갱신하지 않습니다(옛 샤드 meta 가 다시 낡을 수 있습니다).
- 수집기 버그: 포스트시즌 일부 경기(경기 코드 3333/5555/7777)의 play_by_play.game_date 에 경기 코드 일부(예: TOB00929)가 들어갑니다. 2026 포스트시즌 전에 고칩니다(1단계 리허설에서 발견, 2026-10-02).

### 2단계 결과

- 병합: 2A 수집기 버그(0691f23, 2026-10-02), 2C 인덱스·적재 도구(184662e, 10-02, MySQL 인덱스 14개), 2B 이중 적재(9789f3f, 10-03). 수집 계정 `bstats_loader`(SELECT·INSERT·UPDATE·DELETE)로 키 없는 WIF 인증, 매일 D1·MySQL 대조(`migration/mysql/reconcile.py`).
- 켬: 2026-10-03 저장소 변수 `MYSQL_MIRROR=on`. roster 손 실행으로 GCP 인증·MySQL 연결·이중 적재 확인, 공용 표 29개 다시 넣기, 9/29·10/1(한도 초과로 빠진 날) 따라잡기 뒤 대조 "모두 같습니다". weekly 는 MySQL 에서 내려받아 다시 켬(f2414fa, 첫 예약 실행 10/6).
- 대조: 10/3 모두 같음. 10/4 손 실행 daily 는 수집 전부 성공, 대조만 실패(그 실행이 막 지운 `game_team_stats` 를 세던 옛 코드로 돌았음) → 최신 코드로 다시 대조해 "모두 같습니다"(표 27개·값 대조·최근 3일 9경기). 10/4 새벽 정기 daily 는 D1 하루 한도 초과로 PBP 적재부터 실패(MySQL 이중 적재도 D1 다음이라 함께 빠짐) → 손 실행으로 따라잡음.
- 함께 고친 수집 문제: 팀 순위 정기 갱신(team_ranks, db40865), 실행 기록 키 3개(5a4768f), games 최종 점수에 끝내기 득점·숫자 비교(cbb3e64, 657경기 수정), 빠진 경기 채우기(569ef02·57c5172·58857eb), 빈 표 `game_team_stats` 정리(a1b5ad9).
- 7일 지켜보기는 줄였습니다(evan, 2026-10-04): 운영 API 가 이미 MySQL 을 읽고, D1 하루 한도가 수집·대조를 거듭 멈추게 해 5단계(수집이 D1 을 쓰지 않게)를 앞당깁니다.

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

3단계 확인 목록(최종 검토 결과):

- player_id 등 TEXT 가 INT UNSIGNED 로 바뀌어 JSON 타입이 문자열에서 숫자로 바뀝니다. 응답 모양 원칙과 충돌하므로 CAST 로 유지합니다.
- `''` 를 NULL 로 정리해 AVG/SUM 의미가 바뀔 수 있습니다(speed 12,103행, pitch_number 11,283행).
- 포스트시즌 26,450행이 날짜 범위 안으로 들어옵니다. 시즌 집계 포함 여부를 정해야 합니다.
- 정렬 규칙이 utf8mb4_0900_ai_ci 라 SQLite BINARY 와 다릅니다(ID·코드 열은 utf8mb4_bin 검토).
- 외래키가 생긴 표에 `INSERT OR REPLACE` 를 `REPLACE` 로 옮기면 실패하므로 `ON DUPLICATE KEY UPDATE` 를 씁니다.
- 자유 글자 열 VARCHAR 가 관측 최대의 2배라 빠듯합니다(수집기 이전 때 넓히기 검토).

### 3단계 결과

상세 계획서는 `2026-10-03-mysql-phase3-api.md` 입니다. 위 원래 목록과 달리 샤드 계층은 걷어내지 않고 `DB_BACKEND` 스위치로 D1 경로를 남겼습니다(되돌리기용, 5단계에서 걷어냄).

- **전환: 2026-10-04 01시경(KST), 계획보다 앞당김.** 10/3(UTC) D1 하루 읽기가 646만 행(한도 500만)이 되어 운영 API 가 UTC 자정까지 500 을 냈습니다. 그중 약 276만 행은 빠진 경기 채우기 스크립트가 샤드 행 수를 COUNT(*) 로 네 번 센 것입니다. evan 결정으로 MySQL 스테이징을 점검(대조 목록 102개 중 100개 정상, 나머지 2개는 목록 오류·잘못된 주소)한 뒤 운영을 MySQL 로 바꿨습니다. 운영 배포는 evan 이 직접 실행했습니다(버전 02a2fc15 → 전환 뒤 보정 75e488d6 → 설명 사전 2ce5251c).
- 구성: Hyperdrive `bstats-mysql`(VERIFY_CA, Cloud SQL 서버 CA 업로드), Cloud SQL 허용 네트워크 = Cloudflare 공개 IPv4 15개 대역, 읽기 전용 계정 `bstats_api`(SELECT 만, SSL 필수). `wrangler.toml` 의 `DB_BACKEND` 기본값은 `"mysql"`. 되돌리기는 `"d1"` 로 다시 배포하거나 `wrangler rollback`.
- 하루 질의: 전환 전 7일 D1 질의 최대 269건/일 → Hyperdrive 무료 10만/일과 거리가 멉니다.
- 대조(2026-10-04, `docs/mysql-migration/api-compare-phase3.md`): 스테이징-D1 ↔ 운영(MySQL) 101개 주소. 엄격 44개 차이 → 순서 무시 23개 → 모두 동률 순서·동률 경계·기록 시각(이중 적재 몇 초)·1단계 데이터 수정·표 타입 표시·D1 옛 사본으로 설명됩니다. **계산 차이 0.** 동률 순서는 ORDER BY 끝에 고유 열을 더해 고정했습니다.
- 확인 목록 결과: (1) TEXT→INT 로 바뀐 ID 는 어댑터가 글자로 되돌립니다. Hyperdrive 가 mysql2 열 정보(`orgTable`)를 주지 않아 열 이름 규칙으로 물러서므로, D1 에서 INTEGER 였던 곳(`/roster`, `/roster/moves`, `/wrc/leaderboard`, `/wrc/top-changes`, 데이터 탐색)은 `src/lib/ids.js` 로 숫자로 되돌립니다. (2) `''`→NULL 과 (3) 포스트시즌 날짜 수정은 받아들인 차이입니다. (4) 정렬 규칙(ai_ci) 때문에 생긴 차이는 대조에서 보이지 않았습니다. 숫자 아닌 선수 ID 는 MySQL 이 느슨하게 맞추므로 질의 전에 404 로 막았습니다.
- 함께 고친 것: DB 연결 실패는 503·no-store(0 이 한 시간 캐시되지 않게), 음수 LIMIT 은 "제한 없음"으로, CSV 만 본문 끝까지 연결 유지.
- 남은 것(5단계): D1 쓰기 중지, 샤드 코드·바인딩 걷어내기, 스테이징 Worker 두 개(`kbo-api-stg-d1`, `kbo-api-stg-my`) 삭제, D1 2주 보관 뒤 삭제.

### 4단계: 빅쿼리 연결 (상세 계획서는 3단계 뒤)

- BigQuery Connection API 로 Cloud SQL 연결을 만들고, 데이터셋은 같은
  지역(asia-northeast3)에 둡니다. `EXTERNAL_QUERY` 로 MySQL 표를 바로 봅니다.
- 파크팩터·wRC+·RE24 계산을 빅쿼리 SQL 로 옮기는 것은 여기서 검토합니다.

### 5단계: 전환과 정리

- 전환일: D1 쓰기 중지 → 마지막 변경분 동기화 → 대조 → Worker 를 MySQL
  판으로 배포 → 하루 지켜보기.
- D1 은 2주 동안 읽기 전용으로 두고, 이상 없으면 지웁니다. D1 유료였다면
  해지합니다.

## 보안 정리

- 1단계 뒤 /32 허용 네트워크를 삭제했습니다(2026-10-02, 프록시 경유 접속 확인).
- 5단계 뒤 migrator 비밀번호를 교체하고 서비스 계정 키를 삭제합니다.
- migrator 계정은 앱에 쓰지 않습니다.
- 5단계 뒤 WIF 공급자 조건(저장소 ID·main)과 bstats-loader 권한(Cloud SQL 클라이언트만)을 다시 확인합니다.

## 접속 설계

| 누가 | 방법 | 계정 | 단계 |
|---|---|---|---|
| 이전 작업(evan PC) | Cloud SQL Auth Proxy(서비스 계정 `bstats-migrator`). 직접 TLS 경로(공인 IP `/32` 허용 + 서버 CA 검증)는 보조 | `bstats_migrator` (bstats.* 전체) | 1 |
| 수집(GitHub Actions) | Cloud SQL Auth Proxy + Workload Identity Federation(키 없음, 이 저장소 main 에서만) | `bstats_loader` (bstats.* SELECT·INSERT·UPDATE·DELETE) | 2 |
| API(Cloudflare Worker) | Hyperdrive | `bstats_api` (bstats.* 읽기 전용) | 3 |
| 분석(BigQuery) | Cloud SQL 연결 | `bstats_bq` (읽기 전용) | 4 |

## 비용

- Cloud SQL: 월 약 1.5만~2만 원(db-f1-micro, SSD 10GB, 백업). 이미 과금 중입니다.
- BigQuery: 무료 범위(저장 10GiB, 조회 월 1TiB) 안으로 예상합니다.
- D1 은 무료로 유지합니다(0-1 하지 않음). 대신 이전을 빨리 끝내 D1 을 쓰지 않게 합니다.

## 결정 대기

1. 0단계 나머지(0-3·0-4·0-5) 승인. D1 무료 유지 중 남은 큰 위험은 주 1회 파크팩터 작업(한 번에 약 800만 행)이라 전환 전까지 끄는 0-5 를 우선합니다.
2. 결정됨: 혼합 스냅샷으로 2026-10-02 에 실행했습니다.
3. 결정됨: 1단계 브랜치를 2026-10-02 main 에 병합했습니다.
