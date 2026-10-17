# 데이터 관리 페이지와 비공개 비용 보고서 설계

작성 2026-10-18. evan 과 브레인스토밍으로 정했습니다. 미리보기는 evan PC 바탕화면
`bstats_미리보기/data_ops/`(공개 페이지)와 `bstats_미리보기/cost_report/`(비용 보고서)에
있습니다. 미리보기 숫자 가운데 용량·빅쿼리 값·비용·Cloudflare 값은 예시입니다.

## 1. 목적

bstats 의 데이터가 어디에 얼마나 있고, 언제 들어왔고, 어디서 오는지를 한곳에서
봅니다. 돈과 무료 한도는 evan 만 따로 봅니다.

## 2. 정한 것(evan, 2026-10-18)

| 질문 | 결정 |
|---|---|
| 비용·인프라 정보를 공개 사이트에 보이나 | 비용만 비공개. 저장소·수집 상태·출처·중단 이력은 공개. 인프라 식별자(프로젝트 ID, 데이터셋 이름, 인스턴스 이름, IP 대역, Hyperdrive ID, 오류 원문)는 공개 화면·응답에 넣지 않음 |
| GCP 결제 빅쿼리 내보내기 | 켬(표준 사용 비용). evan 이 결제 콘솔에서 직접 켬 |
| Cloudflare 무료 한도 대비 사용량 | 비공개 보고서에만. 토큰은 evan PC(`~/.bstats/`)에만 |
| 위치 | 새 페이지 `pages/data-ops.html`, 위쪽 메뉴 '데이터 탐색' 오른쪽에 '데이터 관리' |
| 빅쿼리 현황을 공개 페이지로 가져오는 방법 | 주간 복사가 MySQL 새 표 `meta_bq_tables` 에 스냅샷을 남기고 Worker 는 MySQL 만 읽음(Worker 에 GCP 키 없음) |
| 비용 보고서 화면 | 미리보기 3차안대로. KBO Dia Gothic, 모든 항목 툴팁, 일별은 변동비만, Cloudflare 는 게이지+실제 값 축, CPU 는 '끊긴 요청' 차트 상자 |
| 공개 페이지 화면 | 미리보기대로. 요약 타일 4 · 저장소 표(용량 큰 10개, 나머지 접기) · 수집 작업 카드 · 출처 · 중단 이력 |

## 3. 전체 구조

```
공개(bstats.pages.dev)                              비공개(evan PC)
pages/data-ops.html                                 scripts/ops/cost_report.py
  ├ GET /ops/storage  ─ Worker ─ Hyperdrive ─ MySQL     ├ 빅쿼리 결제 내보내기 표(개인 gcloud 토큰)
  ├ GET /jobs/status  (기존)                            └ Cloudflare GraphQL(읽기 전용 토큰)
  ├ data/table_lineage.json (기존, 읽기만)            → 바탕화면/bstats_비용보고/<날짜>/report.html·png
  └ data/source_history.json (새 손 파일)

weekly.yml: 빅쿼리 복사 → 결과 JSON → record_bq_snapshot.py → MySQL meta_bq_tables
```

## 4. 공개 페이지: 데이터

### 4-1. 새 표 `meta_bq_tables`

```sql
CREATE TABLE `meta_bq_tables` (
  `name` VARCHAR(64) NOT NULL,
  `bq_rows` BIGINT,
  `bq_bytes` BIGINT,
  `last_ok_at` DATETIME,
  `last_try_at` DATETIME NOT NULL,
  `status` VARCHAR(8) NOT NULL,
  `error` VARCHAR(300),
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

- 시각은 KST 입니다. `status` 는 `ok` 또는 `fail` 입니다.
- `bq_rows`·`bq_bytes`·`last_ok_at` 은 마지막으로 **성공한** 복사의 값입니다. 실패하면
  이 셋은 그대로 두고 `status`·`last_try_at`·`error` 만 바꿉니다(빅쿼리에는 그 전 사본이
  남아 있기 때문입니다).
- MySQL 에 없는 표의 줄은 지웁니다.
- `meta_` 로 시작하므로 `/db/tables`·데이터 탐색에는 나오지 않습니다(`lib/schema.js`).
- **만들기는 evan 이 직접 실행합니다**(수집 계정 `bstats_loader` 에는 CREATE 권한이 없음).
  `migration/mysql/schema.sql` 에도 같은 정의를 넣습니다.

### 4-2. 주간 복사 쪽 바뀌는 것

- `migration/mysql/sqlite_to_bigquery.py`
  - `--result-json PATH` 를 더합니다. 표마다 `{name, source, rows, bytes, error}` 를 씁니다.
  - `load_table` 이 빅쿼리 표의 `num_rows` 와 함께 `num_bytes` 도 돌려줍니다.
  - `meta_bq_tables` 는 복사하지 않습니다(지난주 스냅샷이 다시 복사되는 것을 막음).
  - MySQL 은 지금처럼 읽기만 합니다.
- 새 `migration/mysql/record_bq_snapshot.py`
  - 결과 JSON 을 읽어 수집 계정으로 `meta_bq_tables` 에 씁니다. 한 트랜잭션입니다.
  - `record_job_run.py` 와 같은 접속 방식(`BSTATS_MYSQL_SETTINGS`)을 씁니다.
  - 결과 JSON 이 없거나 깨졌으면 아무것도 바꾸지 않고 0 이 아닌 값으로 끝납니다.
- `.github/workflows/weekly.yml`
  - '빅쿼리 복사' 단계에 `--result-json` 을 붙입니다.
  - 그 뒤에 '빅쿼리 현황 기록' 단계를 둡니다(`if: always()` 이고 결과 파일이 있을 때만).
  - 이 단계가 실패해도 주간 작업 판정은 바꾸지 않습니다. 기록 실패는 요약에 적습니다.

### 4-3. Worker 새 주소 `GET /ops/storage`

`src/routes/ops.js`, `src/index.js` 에 등록, `src/lib/cachepolicy.js` 에 `['/ops/storage', 3600]`.

```json
{
  "generated_at": "2026-10-18 21:40",
  "mysql": {
    "tables": [{ "name": "play_by_play", "category": "수집 데이터", "rows": 3991757,
                 "rows_updated_at": "2026-10-17 23:59",
                 "data_bytes": 0, "index_bytes": 0 }],
    "total_rows": 0, "total_bytes": 0
  },
  "bigquery": {
    "last_copy_at": "2026-10-13 11:27", "ok": 31, "fail": 0,
    "tables": [{ "name": "play_by_play", "rows": 0, "bytes": 0,
                 "last_ok_at": "…", "last_try_at": "…", "status": "ok" }]
  }
}
```

- 질의 세 개입니다.
  1. `information_schema.tables` 의 `data_length`·`index_length`(`meta_` 와 뷰는 뺌).
  2. `meta_table_counts`(기존 `countsOf`).
  3. `meta_bq_tables`.
- 분류(`category`)는 기존 `columnDict()` 에서 읽습니다.
- `error` 칸은 응답에 넣지 않습니다.
- `last_copy_at` = `last_try_at` 의 가장 늦은 값입니다.
- MySQL 질의 1·2 가 실패하면 기존 규칙대로 503 + `no-store` 입니다.
- 질의 3 만 실패하면(표가 아직 없을 때 포함) `"bigquery": null` 로 200 을 돌려줍니다.
- 용량은 MySQL 추정치이고 하루 단위로 갱신됩니다(`information_schema_stats_expiry` 기본값).
  화면 툴팁에 그렇게 적습니다.

### 4-4. 정적 파일

- `dashboard_js/data/table_lineage.json`: 읽기만 합니다. `sources`, `scripts[].sources`,
  `scripts[].stopped`, `jobs` 를 씁니다.
- 새 `dashboard_js/data/source_history.json`: 손으로 적는 이력입니다.

```json
{ "events": [
  { "date": "2026-10-17", "kind": "중단", "sources": ["kbo_record", "kbo_futures"],
    "what": "KBO 공식 사이트 수집 전부", "detail": "…", "reason": "KBO 이용약관 제14조" }
] }
```

- `kind` 는 `중단`·`대체`·`재개`·`알림` 넷입니다.
- 첫 항목들은 2026-09-15 약관 공고, 10-14 시행, 수집 중단(`f91bfc4` 등), `/standings`
  네이버 대체, 퓨처스·등록 명단 화면 내림입니다. 날짜는 만들 때 커밋 기록으로 다시 맞춥니다.

## 5. 공개 페이지: 화면

파일: `dashboard_js/pages/data-ops.html`, `dashboard_js/js/dataops/model.js`(DOM 없는 계산),
`dashboard_js/js/dataops/view.js`, `dashboard_js/css/dataops.css`. API 주소는 `config.js` 의
값을 씁니다(`api.js` 는 쓰지 않음). 수집 상태 계산은 `js/lineage/model.js` 를 불러
`window.Lineage.model` 의 기존 함수를 씁니다(그 파일은 고치지 않습니다).

위에서 아래로:

1. **요약 타일 4개.** MySQL 전체(행 수·표 수·용량), 빅쿼리 사본(행 수가 같은 표 수 / 전체,
   마지막 복사), 수집 작업(정상 단계 수 / 예약 중인 단계 수, 확인 필요·예약 멈춤 수),
   출처(사용 중 수, 수집 중단 수).
2. **저장소 현황 표.** 칸: 표 · 분류 · MySQL 행 수 · MySQL 용량(막대) · 빅쿼리 행 수 ·
   빅쿼리 용량 · 비교. MySQL 용량이 큰 순서로 10개만 먼저 보이고 '나머지 N개 표 보기'로
   펼칩니다. 합계 줄은 전체 기준입니다.
   비교 칸은 네 가지뿐입니다: `같음`, `차이 +N행`(MySQL − 빅쿼리), `복사 실패`, `빅쿼리에 없음`.
   해석(예: '복사 뒤 늘어남')은 붙이지 않습니다.
3. **수집 작업 상태.** 계보 파일 `jobs` 4개를 카드로, 카드 안에 `status_key` 가 있는 단계마다
   상태 점(정상·오래됨·실패·기록 없음)과 마지막 실행 시각을 둡니다. `stopped` 작업은 회색
   카드에 '예약 멈춤'. 아래에 데이터 탐색 링크.
4. **출처**(왼쪽). 계보 파일 `sources` 마다 카드. 상태 규칙: 그 출처를 쓰는 스크립트가
   하나 이상 있고 모두 `stopped` 면 '수집 중단', 아니면 '사용 중'. 바깥 사이트 주소는 링크로
   걸지 않고 'KBO 공식 사이트'·'네이버 스포츠' 같은 이름만 씁니다.
5. **수집 중단 이력**(오른쪽). `source_history.json` 을 최근 것부터. 날짜 · 종류 칩 · 무엇 ·
   설명 · 이유.

모든 칸 제목·타일·표 줄·단계·출처에 툴팁이 있습니다(정의·계산식·기준). 툴팁 모양은
bstats 공용(첫 줄 굵게, 둘째 보통, 셋째부터 흐림)이고 키보드 초점으로도 열립니다.
색은 `style.css` 토큰만 써서 어두운 테마에서도 맞습니다. 좁은 화면(900px 이하)은 타일·카드
2열, 출처·이력 1열입니다.

각 부분은 따로 실패합니다. `/ops/storage` 가 실패하면 저장소 표와 앞 타일 2개만 '불러오지
못했습니다'로 바뀌고, 나머지는 그대로 그립니다. `bigquery: null` 이면 빅쿼리 칸을 '정보 없음'
으로 둡니다.

## 6. 비공개 비용 보고서

### 6-1. 실행과 입력

- `py scripts/ops/cost_report.py --month 2026-10 [--budget 30000]` 를 evan PC 에서 손으로 실행합니다.
  예약 실행은 없습니다.
- 출력: `바탕화면/bstats_비용보고/<YYYY-MM-DD>/report.html`, `report.png`(헤드리스 Edge,
  `Start-Process` 와 호출마다 다른 `--user-data-dir`), 글꼴 폴더 사본.
- 코드에는 비밀값·결제 계정 ID 를 넣지 않습니다. 읽는 파일:
  - `~/.bstats/billing_export_table.txt`: 결제 내보내기 표 전체 이름.
  - `~/.bstats/cf_account_id.txt`, `~/.bstats/cf_analytics_token.txt`.
- 빅쿼리 인증: `gcloud --configuration=bstats auth print-access-token` 으로 받은 토큰.
  `gcloud auth application-default login` 은 쓰지 않습니다(회사 ADC 를 덮음).

### 6-2. 구성(미리보기 3차안)

1. 이번 달 요약 타일 3개: 누적 순액(비용 + 크레딧), 월말 단순 추정(누적 ÷ 지난 날 수 ×
   그 달 일수, 추정 기간·한계를 툴팁에), 예산 대비(누적 ÷ 예산, 월말 추정 기준도).
2. GCP 서비스별 월 표(Cloud SQL·BigQuery·Monitoring·기타·합계)와 Cloud SQL SKU 세부 표
   (금액·비중·고정/변동 표시).
3. GCP 일별 변동비(최근 30일). 고정비(인스턴스 시간 + 저장소)는 막대 위 한 줄로 따로 적고,
   막대는 변동비(백업·PITR 로그, 네트워크, BigQuery, 기타)만 쌓습니다. 점선 = 지난 29일
   변동비 중앙값. 오늘 칸은 흐리게(집계 중).
4. Cloudflare 무료 한도 대비(최근 30일, UTC 하루) 세 상자: Workers 요청 수, Hyperdrive 질의 수,
   CPU 한도 초과로 끊긴 요청. 앞의 둘은 '최고 N% / 한도' 게이지 + 실제 값 축 차트. 가장 많은
   날이 한도의 50% 를 넘으면 축을 한도까지 늘리고 빨간 한도 선을 그립니다. 끊긴 요청 상자
   머리에 30일 합·비율·CPU 중앙값·P99(한도의 몇 배).
5. 기준과 주의.

글꼴 KBO Dia Gothic(저장소의 woff), 모든 항목 툴팁, 차트는 Python 이 인라인 SVG 로 그립니다
(외부 CDN 없음).

### 6-3. 데이터 규칙

- 순액 = `cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)`.
- 월은 `invoice.month`, 일은 `usage_start_time` 을 KST 로 바꾼 날짜입니다.
- 고정비 SKU 는 코드에 이름 목록으로 둡니다(인스턴스 시간·저장소). 목록에 없는 Cloud SQL
  SKU 는 변동비로 넣고 '기준과 주의'에 이름을 적어 evan 이 확인하게 합니다. 짐작해서
  나누지 않습니다.
- 빅쿼리 질의는 먼저 시험 실행으로 읽을 바이트를 보고 50MB 를 넘으면 멈춥니다.
- Cloudflare 는 GraphQL 분석 API 입니다. 데이터셋·칸 이름(Workers 호출, Hyperdrive 질의,
  CPU 분위수, 한도 초과 상태)과 Hyperdrive 무료 한도 값은 **구현 첫 단계에서 실제 스키마와
  Cloudflare 문서로 확인**하고 확인한 날짜를 코드 상수 옆에 적습니다.
- 부분마다 따로 실패합니다. 토큰이 없으면 Cloudflare 칸만 '토큰 없음', 결제 표가 비면 GCP
  칸만 '내보내기 데이터 없음'.

## 7. evan 이 직접 할 일

1. GCP 결제 콘솔 → 결제 내보내기 → BigQuery 내보내기 → **표준 사용 비용** 사용 설정.
   프로젝트 `bstats-kbo`, 새 데이터셋 `billing_export`(서울). 표 이름이 생기면
   `~/.bstats/billing_export_table.txt` 에 적습니다.
2. Cloudflare 에서 **Account Analytics: Read** 만 가진 토큰을 만들어
   `~/.bstats/cf_analytics_token.txt` 에, 계정 ID 를 `~/.bstats/cf_account_id.txt` 에 둡니다.
3. MySQL 에 `meta_bq_tables` 만들기(4-1 의 DDL, root 로).
4. push·Worker 배포·Pages 배포 허락(건마다).

## 8. 다른 세션과 겹치는 곳, 순서

- KBO 이용약관 대응 세션이 `database-explorer.html`·`scripts/build_lineage.py`·
  `dashboard_js/data/table_lineage.json` 을 다룹니다. 그 세션이 끝났다고 evan 이 확인하기 전에는
  이 셋을 고치지 않습니다.
- 계보 시험(`tests/test_lineage.py`)은 워크플로 단계, `pages/*.html` 목록, 등록된 GET 주소,
  `schema.sql` 의 표를 계보 결과 파일과 맞춰 봅니다(`test_결과_파일이_지금_코드로_만든_것과_같습니다`,
  `test_등록된_GET_주소는_어느_화면이든_씁니다` 등). 그래서 아래는 **계보 파일 다시 만들기와
  한 묶음**이고, 확인 뒤에만 main 에 넣습니다.
  - `weekly.yml` 의 새 단계, `schema.sql` 의 `meta_bq_tables`, `/ops/storage` 등록,
    `pages/data-ops.html`·`js/dataops/*`, `source_history.json`.
  - 모든 페이지(`index.html` + `pages/*.html`) 머리 메뉴에 '데이터 관리' 링크.
  - 계보 손 파일 반영 → `py scripts/build_lineage.py` → pytest·npm test 전부.
- 확인 전에도 할 수 있는 것(계보 결과를 바꾸지 않음):
  - 비공개 비용 보고서(6 전체). 워크플로가 부르지 않는 손 실행 스크립트입니다.
  - `sqlite_to_bigquery.py` 의 `--result-json`(기존 스크립트에 선택 인자만 더함)과
    `record_bq_snapshot.py`(아직 워크플로가 부르지 않음). 둘 다 시험 포함.
  - 위 묶음은 별도 브랜치에서 미리 만들어 두되, 계보 반영과 main 병합은 확인 뒤에 합니다.
  - 구현 첫 단계에서 위 판단(무엇이 계보 결과를 바꾸는지)을 `build_lineage.py` 를 돌려 다시
    확인합니다.
- 같은 main 을 여러 세션이 씁니다. push 직전 `git log origin/main..` 을 다시 보고 허락받은
  sha 만 올립니다. Pages 배포는 작업 폴더를 통째로 올리므로 배포 전 `git status --short dashboard_js`
  를 보고 남의 변경이 있으면 알립니다.
- koreabaseball.com·KBO 이미지 서버는 어떤 코드·시험·손 실행에서도 부르지 않습니다.

## 9. 시험

- Node(`test/`): `ops.test.js` — 응답 모양, `error` 칸이 응답에 없음, `meta_bq_tables` 질의
  실패 시 `bigquery: null`, MySQL 실패 시 503, `meta_` 표 제외, 캐시 정책 한 줄.
- Node: `dataops_model.test.js` — 비교 칸 네 가지, 출처 상태 규칙(스크립트 없음 / 일부 멈춤 /
  모두 멈춤), 이력 정렬, 10개 접기 경계.
- pytest: `record_bq_snapshot` — 성공은 덮어씀, 실패는 성공 값 유지, MySQL 에 없는 표 삭제,
  결과 파일 없음·깨짐이면 아무것도 안 씀. `sqlite_to_bigquery` — `--result-json` 내용,
  `meta_bq_tables` 제외.
- pytest: `cost_report` — 순액 계산, 고정/변동 분류와 목록 밖 SKU 표시, 월말 추정, 50% 한도선
  규칙, 시험 실행 50MB 초과 시 멈춤(빅쿼리·Cloudflare 는 가짜 응답으로).
- 화면은 127.0.0.2 로컬 미리보기 캡처를 바탕화면 `bstats_미리보기/data_ops/` 에 둡니다.

## 10. 하지 않는 것

- 비용·금액을 공개 페이지에 넣지 않습니다.
- Worker 에 GCP·Cloudflare 자격 증명을 넣지 않습니다.
- Cloud SQL 디스크 사용률(Monitoring API)은 넣지 않습니다(디스크 80% 경보가 이미 있음).
- 행 수 차이에 원인 해석을 붙이지 않습니다.
- 주소별 Worker CPU 는 Cloudflare API 가 준다는 것을 확인하기 전에는 넣지 않습니다.
- 비용 보고서 예약 실행은 두지 않습니다.
