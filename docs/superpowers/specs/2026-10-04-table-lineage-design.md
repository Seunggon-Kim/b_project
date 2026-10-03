# 테이블 계보(리니지) 설계

- 날짜: 2026-10-04
- 결정: evan (목적=방문자와 운영 둘 다, 범위=4단계, 관리=자동+손 파일 섞기, 위치=데이터 탐색 페이지 새 탭)
- 담당: 데이터(손 파일·생성 스크립트·결과 JSON·테스트) = DB 세션, 화면(탭) = 화면 세션

## 왜 만드나

1. 방문자에게 "이 숫자가 어디서 왔는지"를 보여 줍니다. 포트폴리오에서 수집부터 화면까지의 흐름을 한 장으로 설명합니다.
2. 운영자가 멈춘 표를 바로 찾습니다. 2026-10-03 에 `team_season_rank` 가 한 번 채운 뒤 어떤 작업도 갱신하지 않아 한 달 넘게 8월 말 값이었습니다. 표마다 "누가 언제 쓰는지"가 보였다면 바로 드러났을 것입니다.

## 화면에 보이는 것 (요약)

`https://bstats.pages.dev/pages/database-explorer` 의 새 탭 **테이블 계보** (`#lineage`).

    원천          수집 작업        표                    화면
    KBO 기록실 ─▶ daily 03:33 ─▶ games ──────────────▶ 팀 통계
    네이버 중계 ─▶ roster 16:07 ─▶ play_by_play ─┐      선수 분석
    ...            weekly 화 05:47   (계산 표) ◀──┘      ...
                   monthly 1일       wrc_plus_comparison

- 표 칸은 "받아 온 표"와 "계산 표"를 나누고, 계산 표로 가는 화살표(표 → 계산 표)를 그립니다.
- 무엇이든 누르면 이어진 앞뒤 경로만 진하게, 나머지는 흐리게 합니다.
- 오른쪽 상세 창: 표면 설명·행 수·쓰는 스크립트와 작업·마지막 실행과 상태·읽는 API 주소·화면. 작업이면 실행 시각과 부르는 스크립트.
- 표마다 상태 점: 초록(제때 성공), 빨강(마지막 실행 실패), 회색(오래됨). 손 작업으로만 채우는 표는 "손 작업" 표시만 합니다.
- 휴대폰: 4칸을 위아래로 쌓고 선 대신 목록으로 보여 줍니다.
- 사이트 규칙: 이모지 없음, 상태 점·숫자에 `data-tooltip`(정의·기준), 문장은 습니다체.

## 데이터: 세 조각

### 1. 손 파일 `database/lineage_writes.json` (사람이 관리)

자동으로 뽑기 어려운 "스크립트 → 표"와 원천만 적습니다. 수집 코드는 SQL 을 조립해 만드는 곳이 많아 기계로 뽑으면 틀리기 쉽습니다.

```json
{
  "sources": {
    "kbo_record":    { "name": "KBO 기록실", "url": "https://www.koreabaseball.com/Record/" },
    "naver_relay":   { "name": "네이버 문자중계", "url": "https://sports.naver.com/kbaseball/" }
  },
  "scripts": {
    "data_collection/team_ranks.py": {
      "sources": ["kbo_record"],
      "writes": ["team_season_rank"],
      "reads": [],
      "status_key": "team_ranks"
    },
    "park_factors/build_wrc_plus.py": {
      "sources": [],
      "writes": ["wrc_plus_comparison"],
      "reads": ["play_by_play", "games", "self_park_factor", "statiz_yearly_constants"],
      "status_key": "park_factors"
    }
  },
  "manual_tables": {
    "franchises": "손으로 만든 구단 계보표입니다(migration/build_franchises.py)."
  }
}
```

- `writes`·`reads` 는 표 이름입니다. `reads` 가 있는 스크립트가 쓴 표는 **계산 표**입니다.
- `status_key` 는 `/jobs/status` 의 키(`meta_job_runs.job`)입니다. 지금 키: `pbp, games, futures, official_stats, roster, roster_pm, add_new_players, team_ranks, park_factors, player_info, reconcile`. 실행 기록을 남기지 않는 스크립트는 생략하고, 화면은 그 작업 단계의 기록 키를 씁니다(아래 `jobs[].status_key`).
- `manual_tables`: 어떤 작업도 쓰지 않고 손으로 채운 표와 이유입니다. 여기에도 없고 어떤 스크립트도 쓰지 않는 표는 테스트가 실패합니다(= 고아 표를 숨기지 못함).
- `reconcile.py`·`record_job_run.py`·`mysql_to_sqlite.py` 처럼 표를 만들지 않는 거들기 스크립트는 `"writes": []` 로 적습니다.

### 2. 생성 스크립트 `scripts/build_lineage.py` (자동)

아래를 모아 손 파일과 합쳐 결과 파일을 씁니다. 같은 입력이면 같은 출력(시각·순서 고정, 키 정렬)이어야 합니다.

| 조각 | 어디서 뽑나 | 방법 |
|---|---|---|
| 작업 → 스크립트, 실행 시각 | `.github/workflows/{daily,roster,weekly,monthly}.yml` | `python <경로>.py`·`python -m <모듈>` 호출과 `cron:` 을 읽습니다. 단계 이름도 함께 가져옵니다. cron(UTC)을 한국 시각 문구로 바꿉니다(예: `33 18 * * *` → "매일 03:33"). |
| API 주소 → 표 | `src/index.js` 의 `router.add('GET', 경로, 함수)`, `src/routes/*.js` | 함수별로 SQL 글자의 `FROM`·`JOIN` 뒤 표 이름을 뽑아 실제 표 목록(`migration/mysql/schema.sql`)에 있는 것만 남깁니다. 같은 파일의 도우미 함수가 쓰는 SQL 은 그 파일의 라우트 모두에 붙입니다(과대 추정 허용, 누락보다 낫습니다). |
| 화면 → API 주소 | `dashboard_js/**/*.html`, `dashboard_js/js/*.js` | `${API_BASE_URL}/…` 글자를 뽑고, `api.js` 의 메서드(`API.getX`)가 부르는 주소를 그 메서드를 부르는 화면에 붙입니다. 경로의 변수 부분은 `src/index.js` 패턴(`/players/:id`)에 맞춰 정규화합니다. |
| 표 설명·분류 | `database/column_descriptions.json` | `category`, `table_desc` (갱신 주기는 손으로 적은 `update_freq` 대신 `jobs[].schedule_kst` 를 씁니다) |

외부 사이트를 그대로 넘기는 API(`/standings`, `/schedule*`, `/futures*`)는 표가 없으므로 원천에 "KBO 실시간"으로 잇습니다.

### 3. 결과 파일 `dashboard_js/data/table_lineage.json` (생성물, 커밋)

화면은 이 파일 하나와 기존 API 두 개(`/db/tables` 행 수, `/jobs/status` 실행 기록)만 읽습니다. 새 Worker API 는 만들지 않습니다.

```json
{
  "version": 1,
  "sources": [{ "id": "kbo_record", "name": "KBO 기록실", "url": "…" }],
  "jobs": [{
    "id": "daily", "workflow": "daily.yml", "cron_utc": "33 18 * * *",
    "schedule_kst": "매일 03:33", "stale_hours": 36,
    "steps": [{ "name": "올 시즌 팀 순위 적재", "script": "data_collection/team_ranks.py", "status_key": "team_ranks" }]
  }],
  "scripts": [{
    "path": "data_collection/team_ranks.py", "jobs": ["daily"], "sources": ["kbo_record"],
    "writes": ["team_season_rank"], "reads": [], "status_key": "team_ranks"
  }],
  "tables": [{
    "name": "team_season_rank", "kind": "collected",
    "category": "…", "desc": "…",
    "written_by": ["data_collection/team_ranks.py"], "derived_from": [],
    "routes": ["/teams/:id"], "pages": ["pages/team-record.html"], "manual_note": null
  }],
  "routes": [{ "path": "/teams/:id", "tables": ["team_season_rank", "…"], "pages": ["pages/team-record.html"] }],
  "pages": [{ "path": "pages/team-record.html", "title": "팀 기록실", "routes": ["/teams/:id"] }],
  "edges": [
    { "from": "source:kbo_record", "to": "job:daily" },
    { "from": "job:daily", "to": "table:team_season_rank" },
    { "from": "table:play_by_play", "to": "table:wrc_plus_comparison" },
    { "from": "table:team_season_rank", "to": "page:pages/team-record.html" }
  ]
}
```

- `kind`: `collected`(작업이 원천에서 받아 씀) · `derived`(쓰는 스크립트에 `reads` 가 있음) · `manual`(손으로 채움) · `meta`(`meta_*` 표, 그림에서는 숨김).
- `stale_hours`: daily·roster 36, weekly 8×24, monthly 35×24.
- `edges` 는 그림의 4칸 선만 담습니다(원천→작업, 작업→표, 표→계산 표, 표→화면). 스크립트·API 는 상세 창 정보입니다.
- 정렬: 모든 배열은 이름 순, 객체 키는 사전 순. 시각·커밋 해시를 넣지 않습니다(재생성 비교 테스트를 위해).

## 상태 점 규칙 (화면 세션 구현)

표의 상태는 그 표를 쓰는 스크립트들의 `status_key` 기록(`/jobs/status` 의 `details[key]`) 중 가장 나쁜 것입니다.

| 점 | 조건 | 툴팁 문구(예) |
|---|---|---|
| 초록 | 모든 기록이 `ok`/`skip` 이고 `last_run_at` 이 `stale_hours` 안 | "마지막 갱신 10/04 07:41 (daily, 성공)" |
| 빨강 | 기록 하나라도 `fail` | "마지막 실행 실패 10/04 07:41 (daily)" |
| 회색 | 기록이 없거나 `stale_hours` 를 넘김 | "36시간 넘게 갱신이 없습니다" |
| 없음 | `kind` 가 `manual` | "손 작업으로 채운 표입니다: <manual_note>" |

`/jobs/status`·`/db/tables` 를 못 읽으면 점과 행 수를 감추고 "운영 정보를 불러오지 못했습니다" 한 줄만 보입니다. 그림 자체는 정적 JSON 이라 그대로 보입니다.

## 테스트 (DB 세션, `tests/test_lineage.py`)

1. 워크플로 4개가 부르는 스크립트가 모두 손 파일 `scripts` 에 있습니다(거들기 포함). 없으면 실패 — 새 단계를 더하고 계보를 잊는 것을 막습니다.
2. 손 파일의 `writes`·`reads`·`manual_tables` 표 이름이 모두 `migration/mysql/schema.sql` 에 있습니다.
3. `schema.sql` 의 모든 표(`meta_*` 제외)가 어떤 스크립트의 `writes` 나 `manual_tables` 에 있습니다(고아 표 금지).
4. `status_key` 가 워크플로의 `record_job_run.py --job <키>` 목록에 있습니다.
5. `build_lineage.py` 를 다시 돌린 결과가 커밋된 `dashboard_js/data/table_lineage.json` 과 같습니다(생성 잊음 방지).
6. 생성기 단위 시험: cron→한국 시각 문구, `FROM`/`JOIN` 표 이름 뽑기(백틱·별칭·하위 질의), `${API_BASE_URL}` 경로 정규화.

## 하지 않는 것

- 열(컬럼) 단위 계보. 표 단위까지만 그립니다.
- 새 Worker API·DB 표. 정적 JSON 과 기존 API 두 개로 충분합니다.
- 그림 라이브러리 강제. 화면 세션이 정합니다(4칸 고정 배치라 SVG 선만으로도 됩니다). 외부 스크립트는 사이트 규칙상 cdnjs 등 허용된 곳만.
- 실시간 표 행 수 계산. `/db/tables` 의 메타 값을 그대로 씁니다.

## 진행 순서

1. DB 세션: 손 파일 + 생성 스크립트 + 결과 JSON + 테스트 → PR 없이 evan 허락 뒤 main push (데이터 파일과 스크립트만, 화면 변화 없음).
2. 화면 세션: 결과 JSON 모양(위 3절)을 받아 탭 구현 → 미리보기 PNG → evan 허락 뒤 Pages 배포.
3. 이후 작업·표를 바꾸는 사람은 손 파일을 고치고 `py scripts/build_lineage.py` 를 돌립니다. 잊으면 테스트 1·3·5 가 잡습니다.
