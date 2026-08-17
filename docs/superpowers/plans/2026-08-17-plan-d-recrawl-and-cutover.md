# 계획 D: 전 시즌 복원과 정기 실행 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 2015~2024 와 2026 을 다시 모아 넣고, 수집을 정기 실행으로 세우고, 무료 한도 안에서 계속 돌 수 있는 상태로 만들어 공개합니다.

**Architecture:** 수집은 GitHub Actions(러너에 브라우저와 파이썬이 있고 KBO 가 열립니다), 짧은 주기의 퓨처스 일정만 Worker Cron. 저장은 D1 이되 `play_by_play` 는 용량 때문에 손을 봐야 합니다. 큰 CSV 는 GitHub Releases 로 내보냅니다.

**Tech Stack:** GitHub Actions, Cloudflare Workers/D1/Pages, Python(수집), 빌드 도구 없음

## Global Constraints

- **예산 0원.** 유료 플랜, 도메인 구입, 카드 등록이 필요한 서비스는 쓰지 않습니다.
- 명령은 Windows PowerShell 기준입니다. 저장소 루트에서 실행합니다.
- 사용자 노출 한국어는 `습니다/합니다/입니다` 정중체를 씁니다.
- 화면 주소 `https://kbo-dashboard-a0g.pages.dev`, API `https://kbo-api.bstats-baseball.workers.dev`

---

## 먼저: 설계 문서의 전제 네 가지가 틀렸습니다

계획 D 를 시작하기 전에 이것부터 인정해야 합니다. 설계 문서
(`docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md`) 가
계획 D 로 미뤄 둔 항목들의 전제가 실측과 어긋났습니다.

| 설계 문서의 전제 | 실측 | 근거 |
|---|---|---|
| CSV 전량은 R2 사전 생성본으로 (§5) | **R2 는 무료 한도라도 결제 수단 등록을 요구합니다.** 활성화 직후 $5 청구 사례도 있습니다 | Cloudflare 커뮤니티 다수 보고(2026) |
| 저장 한계는 "약 3년 후" (§6) | **재크롤링하면 즉시 초과합니다.** 12시즌 약 1.57GB, DB당 한도 500MB | 아래 §용량 |
| D1 읽기 "인덱스 적용 시 소량, 충분" (§6) | **인덱스로는 `COUNT(*)` 가 줄지 않습니다.** 커버링 인덱스여도 전 행을 스캔해 과금합니다 | `EXPLAIN QUERY PLAN` 실측 |
| 저장소가 비공개 (§5) | **공개(PUBLIC)입니다** | `gh repo view` |

각각이 계획을 바꿉니다. 순서대로 봅니다.

### R2 대신 GitHub Releases

전량 CSV 를 둘 곳이 필요합니다. 셋을 비교했습니다.

| 곳 | 파일당 한도 | 대역폭 | 카드 |
|---|---|---|---|
| Cloudflare R2 | 넉넉 | 무료 | **필요** |
| Cloudflare Pages | 25 MiB | 무제한 | 불필요 |
| **GitHub Releases** | **2 GiB** | **과금 없음** | 불필요 |

`play_by_play` CSV 가 현재 35MB(2025 한 시즌)이므로 Pages 의 25MiB 를 넘습니다.
12시즌이면 420MB 입니다. **GitHub Releases 로 갑니다.** 저장소가 공개라
누구나 받을 수 있고, 릴리스당 자산 1,000개까지 됩니다.

### 저장소가 공개라 따라오는 것 둘

좋은 점 하나. **Actions 분이 무제한입니다.** 설계 문서는 월 2,000분을
아껴 쓰는 전제로 짜였는데 그럴 필요가 없습니다. 재크롤링을 시즌별 잡으로
넉넉히 나눠도 됩니다.

주의할 점 둘.

- **60일간 저장소 활동이 없으면 스케줄 워크플로가 자동으로 꺼집니다.**
  매일 도는 수집이 어느 날 조용히 멈춥니다. Task 6 에서 대응합니다.
- 비밀이 로그에 찍히면 전 세계가 봅니다. 이 저장소에는 과거 Gmail 앱
  비밀번호가 유출된 이력이 설계 문서 §8 에 적혀 있습니다. Task 8 에서
  한 번 훑습니다.

---

## 용량: `play_by_play` 하나가 전부입니다

표별로 실제 바이트를 쟀습니다.

| 표 | 행 수 | 데이터+인덱스 | 비중 |
|---|---|---|---|
| **play_by_play** | 229,667 | **131.1MB** | **96.6%** |
| player_news | 2,875 | 1.26MB | 0.9% |
| 나머지 16개 표 전부 | | 약 1.4MB | |
| 합계 | | 133.8MB | |

`play_by_play` 를 뺀 전체가 2.7MB 입니다. 그러니 이 표만 어떻게 하면 됩니다.

### API 는 74개 컬럼 중 22개만 씁니다

`src/routes/*.js` 에서 `play_by_play` 를 읽는 쿼리 9곳을 전부 읽고 참조
컬럼을 모았습니다.

```
gameID pitcher_ID batter_ID game_date
pitch_type px pz speed pitch_result pfx_x pfx_z x0 z0 sz_top sz_bot
stands throws
inning_topbot pa_result outs_on_play runs_scored
stadium
```

22개입니다. 안 쓰는 52개에 무거운 것이 몰려 있습니다. `description`
(행당 17.8B), `pitchID`(12.3B), 수비수 이름·ID 18개, 원시 물리량 9개 등입니다.

22컬럼으로 실제로 재구축해 재 봤습니다. **추정이 아니라 실측입니다.**

| 구성 | 크기 |
|---|---|
| 현행 74컬럼 + 인덱스 3 | 131.1MB |
| **슬림 22컬럼 + 인덱스 3** | **46.5MB (65% 감소)** |
| 슬림 22컬럼, 타석 종결 행만(55,924행) | 11.9MB (91% 감소) |

### 다만 슬림화는 화면 기능을 깎습니다

`dbexplorer.js` 는 `SELECT *` 입니다. 컬럼을 지우면 **데이터 탐색기와
CSV 에서 그 52개가 사라집니다.** 그리고 `database/column_descriptions.json`
에는 74개 전부에 설명이 붙어 있습니다. `description`(경기 상황 서술),
`balls`, `batter`(타자 이름) 처럼 사람이 보고 싶어 할 값들입니다.

이 손실을 GitHub Releases 로 메웁니다. **탐색기에서는 22컬럼을 보되,
전량 CSV 는 원본 74컬럼으로 내려받게 합니다.** 원본을 버리지 않습니다.

### 안 비교

12시즌 기준입니다. 2015~2024 는 모두 10구단 720경기 체제라 시즌당 행 수가
2025 와 비슷하다고 봤습니다.

| 안 | 크기 | DB 수 | 가능 | 대가 |
|---|---|---|---|---|
| A. 현행 74컬럼 + 시즌 분리 | 131MB × 12 = 1.57GB | 7~12 | 가능하나 DB 10개 한도에 빠듯 | 코드 수정 범위가 가장 큼 |
| B. 슬림 + 단일 DB | **558MB** | 1 | **불가** (500MB 를 12% 초과) | 아깝게 안 됩니다 |
| **C. 슬림 + 2분할** | 각 약 280MB | 3 | **가능** | 크로스 시즌 쿼리 4곳 수정 |
| D. 슬림 + 옛 시즌은 타석 행만 | 약 247MB | 1 | 가능 | 옛 시즌 구종 화면이 빈 응답 |
| E. 최근 5시즌만 | 233MB | 1 | 가능 | **원본 사이트 기능 축소** |

**C 를 권합니다.** D 는 DB 하나로 끝나 매력적이지만 2015~2023 의
`/players/:id/arsenal`·`/usage`(투구 단위 구종 화면)가 빈 화면이 됩니다.
그건 이전이 아니라 축소입니다. E 도 같은 이유로 뺐습니다.

C 의 DB 구성입니다.

```
kbo-stats          공용. play_by_play 를 뺀 17개 표 (2.7MB)
kbo-pbp-2015-2020  슬림 play_by_play 6시즌 (약 280MB)
kbo-pbp-2021-2026  슬림 play_by_play 6시즌 (약 280MB)
```

`games` 표는 두 pbp DB 에도 복제합니다(시즌당 약 15KB). `teamrange.js:222`
가 `JOIN games` 를 하는데, 복제해 두면 그 SQL 을 그대로 둘 수 있습니다.

### 시즌을 가로지르는 쿼리 네 곳

DB 를 나누면 SQL 하나로 못 쓰는 곳입니다. 전수 확인했습니다.

| 위치 | 무엇을 하는가 | 판정 |
|---|---|---|
| `src/routes/wrc.js:86-89` | 시즌별 경기 수 CTE | GROUP BY 축이 시즌이라 DB별 질의 후 이어붙이면 같습니다 |
| `src/routes/wrc.js:235-241` | 타자의 구장별 분포 | 그룹이 시즌 안에 갇혀 있어 이어붙이면 같습니다 |
| `src/routes/dashboard.js:26-38` | 전체 경기·플레이 수, 시즌 범위 | 합·min·max 를 JS 에서. **DB당 1쿼리로 합쳐야 합니다** |
| `src/routes/teamrange.js:219-235` | 기간별 팀 집계 | 이미 JS 누적이라 여러 DB 결과를 이어 돌리면 됩니다 |

`dbexplorer.js` 는 다릅니다. `play_by_play` 라는 단일 표를 LIMIT/OFFSET 으로
넘기는데, 나누면 그 표가 없습니다. Task 4 에서 따로 다룹니다.

**주의**: Worker 호출당 D1 쿼리는 50개입니다. `dashboard.js` 를 지금 형태
그대로 DB 2개에 fan-out 하면 4쿼리 × 2 = 8개로 여유가 있지만, DB 를 더
늘리면 위험합니다. 그래서 C(2분할)이지 시즌당 1개가 아닙니다.

---

## 읽기: 지금 한도의 11배를 읽고 있습니다

`wrangler d1 info kbo-stats` 실측입니다.

```
rows_read_24h     55,345,518      한도 5,000,000
rows_written_24h     954,775      한도   100,000
```

### 55M 의 정체는 사용자가 아니라 우리 검증 스크립트입니다

`migration/golden_matrix.py` 가 wRC 시즌 13개마다 무거운 엔드포인트를
5회씩 부릅니다. `effMinPa` 만 69회 × 229,667행 = 15.85M 이고, 매트릭스
1런이 약 19M 입니다. 55.3M ÷ 19M ≈ 2.9런. 오늘 `capture_worker.py` 를
원격에 두세 번 돌린 것과 맞습니다.

**그러니 "사용자가 몰려서"가 아닙니다.** 다만 이것이 면죄부는 아닙니다.
12시즌이 되면 실사용만으로 넘습니다.

### 지금도 한도가 강제되지 않지만 기대면 안 됩니다

55M 을 읽고도 응답이 돌아옵니다. 적재 때 쓰기 954,775(한도 9.5배)도
막히지 않았습니다. 그러나 공식 문서는 초과 시 **"D1 에 쿼리를 실행할 수
없고 API 가 오류를 반환한다"** 고 명시합니다. 스로틀이 아니라 거부입니다.
걸리면 사이트가 통째로 죽습니다.

### 엔드포인트별 1회 읽기 (실측 기반)

| 엔드포인트 | 1회당 | 원인 |
|---|---|---|
| `/dashboard/stats` | **약 919,900** | pbp 풀스캔 4회 |
| `/db/tables` | 약 240,900 | 18개 표 `COUNT(*)` |
| `/wrc/*` 6개 | 각 약 232,000 | 전부 `effMinPa` 경유 |
| `/wrc/seasons` | 약 258,000 | gp CTE 풀스캔 |
| `/stats/team_range` | 기간 비례, 시즌 전체 약 457,000~915,000 | pbp 를 2회 읽음 |

화면 한 번 여는 값입니다.

| 페이지 | 1회 열람 | 하루 몇 번이면 한도 초과 |
|---|---|---|
| 아티클 | 약 1,690,000 | **3번** |
| 데이터 탐색 | 약 1,160,000 | 4.3번 |
| 팀 통계 | 약 927,000 | 5.4번 |

12시즌이 되면 `/dashboard/stats` **한 번 호출이 약 11M** 입니다. 하루
한도의 2.2배입니다. 고치지 않으면 운영이 성립하지 않습니다.

### 고칠 것 — 효과 큰 순서

**1. `play_by_play` 풀스캔을 `games` 로 대체 (효과 최대)**

`effMinPa`(`wrc.js:33-37`)가 시즌 경기 수를 pbp 풀스캔으로 셉니다.
`games` 표(719행, `idx_games_season` 커버링)로 바꾸면 **229,667 → 719**
입니다. wRC 엔드포인트 6개가 전부 이걸 지나므로 한 번에 해결됩니다.
`wrc.js:86-89` 와 `dashboard.js:26-38` 도 같습니다.

아티클 페이지 1.69M → 약 30,000 (98% 감소).

**2. 행 수 메타 표**

`COUNT(*)` 는 인덱스로 못 줄입니다. `EXPLAIN QUERY PLAN` 실측에서
커버링 인덱스를 타고도 229,667행을 전부 스캔합니다. 그러니 세지 말고
적재할 때 기록해 둡니다. `/db/tables` 240,846 → **18**.

**3. Workers Cache 켜기**

2026-07-06 에 나온 기능입니다. **전 플랜 무료이고 workers.dev 에서
동작하며, 캐시 히트면 Worker 가 아예 실행되지 않아 D1 읽기가 0 입니다.**
`wrangler.toml` 에 `[cache] enabled = true` 를 넣고 응답에
`Cache-Control` 을 붙이면 됩니다. 데이터가 하루 한 번 바뀌므로
`max-age=3600, stale-while-revalidate=86400` 이 적당합니다.

**4. keyset 페이지네이션**

`LIMIT n OFFSET k` 는 건너뛴 k행도 스캔해 과금합니다. `pbp_id` 가
rowid 이므로 `WHERE pbp_id > ? ORDER BY pbp_id LIMIT ?` 로 바꿉니다.

**5. `team_range` 사전 집계**

12시즌에서 전 기간 조회가 약 11M 로 유일하게 남는 폭탄입니다. 경기 ×
공수 × `pa_result` 롤업 표를 적재 시 만들면 약 21,000행으로 끝납니다.

**6. 인덱스 2개**: `wrc_plus_comparison(season)`,
`weighted_pf_by_batter_season(batter_ID, season)`. 지금은 쿼리마다
자동 인덱스를 빌드합니다.

**7. 운영 수칙**: 골든 매트릭스를 원격에 돌리지 않습니다. 55M 의 직접
원인입니다. 로컬 D1(`--local`)로 돌립니다.

---

## 쓰기: 재적재 분량

| | 값 |
|---|---|
| 한 시즌 pbp | 229,667행 × (1 + 인덱스 3) = **918,668 쓰기** |
| 12시즌 | **약 11,024,016 쓰기** |
| 한도대로면 | 110일 |
| 실측 전례 | 2025 한 시즌이 하루에 끝남 (한도 미강제) |

슬림화하면 인덱스는 그대로라 쓰기 계상은 같습니다. 줄지 않습니다.
`migration/load_to_d1.py` 의 예산 관리와 `.progress` 이어하기를 그대로 씁니다.

---

## 수집: 무엇을 어디서 돌릴지

실측된 사실입니다.

- Actions 러너에서 KBO 접속·Selenium 완주 확인
- Cloudflare 엣지에서 네이버·KBO 열림, **구글은 막힘**
- 한 시즌 PBP 수집 **21~35분** (`crawler/log.txt` 실측)
- Actions 잡당 6시간 제한

| 작업 | 어디서 | 근거 |
|---|---|---|
| 공식 통계(Selenium 체인) | Actions | Worker 에 브라우저가 없습니다 |
| PBP + games | Actions | 경기당 11~15요청이라 Worker 의 서브리퀘스트 50개를 넘습니다 |
| player_detector, cleanup, registry_sync | Actions | 파이썬 로직과 다수 요청 |
| park_factors 재계산 | Actions | 무거운 pandas. CPU 10ms 로는 불가 |
| **퓨처스 일정 (30분 간격)** | **Worker Cron** | 요청 1~3개로 가볍고, Actions cron 은 지연이 잦아 30분 주기에 안 맞습니다. 단 파이썬을 JS 로 다시 써야 합니다 |
| 선수 뉴스 | Actions | 구글이 엣지에서 막힙니다 |
| auto_deploy | **삭제** | Pages 가 push 로 자동 배포합니다 |

Worker Cron 한도는 계정당 5개, 최소 1분 간격입니다. Cron 핸들러도 CPU 는
10ms 로 같지만 벽시계로는 15분까지 허용되므로 D1 대기는 문제없습니다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `migration/slim_pbp.py` | **신규.** 74컬럼 → 22컬럼 슬림 스키마 생성·이관 |
| `migration/shard_plan.py` | **신규.** 시즌 묶음별 DB 배정과 검증 |
| `src/lib/shard.js` | **신규.** 시즌 → D1 바인딩 라우팅, fan-out 병합 |
| `src/lib/counts.js` | **신규.** 행 수 메타 표 조회 |
| `src/routes/*.js` | 수정. 풀스캔 제거, 샤드 라우팅, Cache-Control |
| `wrangler.toml` | 수정. D1 바인딩 3개, `[cache]`, `[triggers]` |
| `src/index.js` | 수정. `scheduled` 핸들러(퓨처스) |
| `.github/workflows/daily.yml` | 수정. 정기 실행 전체 |
| `.github/workflows/backfill.yml` | **신규.** 시즌 지정 재크롤링 |
| `.github/workflows/monthly.yml` | **신규.** 선수 프로필 월 1회 |
| `.github/workflows/release-csv.yml` | **신규.** 전량 CSV 를 Releases 로 |
| `dashboard_js/pages/database-explorer.html` | 수정. Cron 표를 실제 스케줄로 |

---

## Task 1: 읽기량부터 줄입니다

재크롤링 전에 합니다. 지금 스키마로도 효과가 있고, 12시즌을 넣은 뒤에
고치려면 그 사이에 한도에 걸립니다.

**Files:** `src/routes/wrc.js`, `src/routes/dashboard.js`, `src/lib/counts.js`,
`migration/export_to_d1.py`, `wrangler.toml`

- [ ] **Step 1: `effMinPa` 를 games 기반으로 바꿉니다**

`src/routes/wrc.js:33-37` 의 `COUNT(DISTINCT gameID) FROM play_by_play` 를
`SELECT COUNT(*) FROM games WHERE season = ?` 로 바꿉니다.

**두 값이 같은지 먼저 확인하십시오.** `games` 에 pbp 가 없는 경기가 있으면
값이 달라지고, 그러면 `/wrc/*` 여섯 개의 응답이 전부 바뀝니다.

```powershell
py -c "import sqlite3; c=sqlite3.connect('database/kbo_stats.db'); print(c.execute(\"SELECT COUNT(DISTINCT gameID) FROM play_by_play WHERE substr(gameID,1,4)='2025'\").fetchone(), c.execute(\"SELECT COUNT(*) FROM games WHERE season=2025\").fetchone())"
```

다르면 이 치환을 하지 말고 원인을 먼저 밝히십시오.

- [ ] **Step 2: `wrc.js:86-89` 와 `dashboard.js:26-38` 도 같은 방식으로**

- [ ] **Step 3: 행 수 메타 표를 만듭니다**

`meta_table_counts(name TEXT PRIMARY KEY, n INTEGER, updated_at TEXT)`.
적재 스크립트가 갱신하고, `dbexplorer.js:37`·`:95-96`·`:183-185` 가 읽습니다.

**메타가 실제 행 수와 어긋나면 화면이 거짓말을 합니다.** 적재 후 대조하는
검증을 같이 넣으십시오.

- [ ] **Step 4: 인덱스 2개를 추가합니다**

- [ ] **Step 5: 골든 비교로 응답이 안 변했는지 확인합니다**

읽기를 줄이는 것이 목적이지 응답을 바꾸는 것이 아닙니다.
**이번에는 로컬 D1 에 돌리십시오.** 원격에 돌리면 그 자체로 19M 을 씁니다.

- [ ] **Step 6: 줄었는지 실측합니다**

`wrangler d1 info` 의 `rows_read_24h` 를 조치 전후로 비교하십시오.
숫자가 안 줄면 고친 것이 아닙니다.

---

## Task 2: Workers Cache 를 켭니다

**Files:** `wrangler.toml`, `src/lib/respond.js`

- [ ] **Step 1: `[cache] enabled = true` 를 넣고 배포합니다**

- [ ] **Step 2: 응답에 `Cache-Control` 을 붙입니다**

엔드포인트 성격별로 다르게 둡니다.

| 성격 | 값 |
|---|---|
| 하루 한 번 바뀜 (wrc, stats, db) | `public, max-age=3600, stale-while-revalidate=86400` |
| 실시간 (schedule, standings) | `public, max-age=30` |
| 안 바뀜 (logo) | `public, max-age=604800` |

- [ ] **Step 3: 캐시가 실제로 도는지 확인합니다**

같은 URL 을 두 번 부르고 응답 헤더의 `cf-cache-status` 를 보십시오.
두 번째가 `HIT` 여야 합니다. `MISS` 만 나오면 켜진 것이 아닙니다.

- [ ] **Step 4: 캐시가 라이브 데이터를 굳히지 않는지 봅니다**

`/schedule` 이 30초 캐시로 오늘 경기를 제때 갱신하는지 확인하십시오.

---

## Task 3: `play_by_play` 를 슬림화합니다

**Files:** `migration/slim_pbp.py`, `migration/export_schema.py`

- [ ] **Step 1: 참조 컬럼 목록을 코드에서 다시 뽑습니다**

이 문서의 22개 목록을 그대로 믿지 마십시오. Task 1 에서 쿼리를 고쳤으니
달라졌을 수 있습니다. `src/routes/*.js` 를 다시 훑어 목록을 만드십시오.

- [ ] **Step 2: 슬림 스키마로 로컬에 재구축합니다**

- [ ] **Step 3: 22컬럼만으로 골든이 통과하는지 확인합니다**

**`/db/table/play_by_play` 와 CSV 는 반드시 달라집니다.** 컬럼이 사라지니
당연합니다. 그 두 개를 뺀 나머지가 전부 일치해야 합니다. 다른 것이
바뀌었다면 필요한 컬럼을 빠뜨린 것입니다.

- [ ] **Step 4: 컬럼 사전을 정리합니다**

`database/column_descriptions.json` 의 `play_by_play` 74개 중 52개가
이제 없는 컬럼입니다. 남은 22개만 남기되, **삭제하지 말고 별도 절로
옮겨 두십시오.** 원본 CSV(Task 7)를 받은 사람에게는 그 설명이 필요합니다.

---

## Task 4: DB 를 세 개로 나눕니다

**Files:** `wrangler.toml`, `src/lib/shard.js`, `src/routes/*.js`, `migration/shard_plan.py`

- [ ] **Step 1: D1 두 개를 만듭니다**

```powershell
npx wrangler d1 create kbo-pbp-2015-2020
npx wrangler d1 create kbo-pbp-2021-2026
```

- [ ] **Step 2: 바인딩을 추가합니다**

- [ ] **Step 3: 라우팅 함수를 만듭니다**

```javascript
// 시즌 하나를 받아 그 시즌이 든 D1 바인딩을 돌려줍니다.
export function shardOf(env, season) { /* ... */ }
// 여러 시즌에 걸친 질의를 각 DB 에 돌리고 결과를 이어붙입니다.
export async function fanOut(env, seasons, fn) { /* ... */ }
```

**Worker 호출당 D1 쿼리 50개 한도를 넘지 않게 하십시오.** DB 2개면
여유가 있지만, `dashboard.js` 처럼 DB 하나에 4쿼리를 던지는 코드는
DB 당 1쿼리로 합쳐야 합니다.

- [ ] **Step 4: `games` 를 두 pbp DB 에 복제합니다**

`teamrange.js:222` 의 `JOIN games` 를 유지하기 위해서입니다. 시즌당 15KB 라
용량은 문제없습니다. **적재할 때 세 DB 의 games 가 어긋나지 않게 하십시오.**

- [ ] **Step 5: 크로스 시즌 네 곳을 고칩니다**

이 문서 §시즌을 가로지르는 쿼리의 표를 따르십시오.

- [ ] **Step 6: 데이터 탐색기를 정합니다**

`play_by_play` 라는 단일 표가 이제 없습니다. 선택지입니다.

| 안 | 내용 |
|---|---|
| 시즌 선택 추가 | 탐색기에 시즌 셀렉터를 두고 그 시즌 DB 만 봅니다. 화면이 바뀝니다 |
| 가상 통합 | 두 DB 를 순서대로 이어 페이지네이션합니다. offset 계산이 복잡합니다 |
| 최근 묶음만 | 탐색기에서는 2021~2026 만 보이고, 전체는 Releases CSV 로 |

**어느 것도 원본과 같지 않습니다.** 무엇을 고르든 화면에 그 사실을 적으십시오.

- [ ] **Step 7: 골든을 로컬에서 돌립니다**

---

## Task 5: 2015~2024 와 2026 을 다시 모읍니다

**Files:** `.github/workflows/backfill.yml`

- [ ] **Step 1: 백필 워크플로를 만듭니다**

`workflow_dispatch` 로 연도를 입력받아 그 시즌만 돕니다.
`crawler/pbp.py -f YYYYMMDD -t YYYYMMDD` 가 날짜 범위를 받습니다.
`data_collection/backfill_2015_2024.sh` 에 시즌 루프가 이미 있으니
참고하십시오.

**시즌 하나당 잡 하나로 나누십시오.** 한 시즌이 21~35분이라 6시간 제한에
여유가 있지만, 11시즌을 한 잡에 넣으면 4~6.5시간으로 아슬아슬합니다.
중간에 죽으면 처음부터 다시 합니다.

- [ ] **Step 2: 한 시즌으로 먼저 시험합니다**

2024 하나만 돌려 끝까지 가는지 보십시오. 열한 번 돌리기 전에 합니다.

- [ ] **Step 3: 수집 결과를 검증합니다**

경기 수가 시즌 기대치(720 안팎)와 맞는지, 행 수가 2025(229,667)와
비슷한 규모인지 보십시오. **크게 적으면 조용히 실패한 것입니다.**

- [ ] **Step 4: D1 에 적재합니다**

`migration/export_to_d1.py` + `load_to_d1.py` 경로를 씁니다. 시즌에 맞는
DB 로 보내야 합니다.

쓰기 한도가 강제되면 시즌당 9.2일입니다. 강제되지 않으면 하루입니다.
**어느 쪽인지 첫 시즌에서 드러납니다.** `.progress` 이어하기가 있으니
막혀도 잃지 않습니다.

- [ ] **Step 5: 파생 표를 다시 만듭니다**

전 시즌이 들어온 뒤에 합니다. `park_factors/run_pipeline.sh` 가
`compute_self_park_factors.py` → `build_wrc_plus.py` →
`build_re24_run_values.py` 를 순서대로 돕니다.

이때 **계획 C 에서 못 넣은 `re24_matrix_by_season` 이 비로소 제대로
만들어집니다.** `season=0` 이 열한 시즌을 모은 값이 되어야 맞습니다.
2025 하나만으로 만들면 안 되는 이유가 그것이었습니다.

만든 뒤 `season=0` 의 `n_obs` 가 단일 시즌 값보다 훨씬 큰지 확인하십시오.
같다면 여전히 한 시즌만 들어간 것입니다.

- [ ] **Step 6: 요인 통계 화면이 살아났는지 봅니다**

`py migration/check_pages_browser.py` 가 일곱 페이지 전부 정상이어야 합니다.

---

## Task 6: 정기 실행을 세웁니다

**Files:** `.github/workflows/daily.yml`, `monthly.yml`, `wrangler.toml`, `src/index.js`

- [ ] **Step 1: daily.yml 에 스케줄과 빠진 단계를 넣습니다**

지금 daily.yml 에는 `schedule:` 이 없고, 타자 수집만 있으며, 통계·PBP 의
D1 적재 경로가 없습니다(뉴스만 적재합니다).

**cron 은 정각을 피하십시오.** GitHub 문서가 "높은 부하 시간대에 지연될
수 있고 매 시각 정각이 그렇다"고 명시합니다. `17`, `43` 같은 분을 쓰십시오.

- [ ] **Step 2: 60일 자동 비활성화에 대비합니다**

공개 저장소는 60일간 활동이 없으면 스케줄 워크플로가 꺼집니다.
매일 도는 워크플로가 있으면 실행 자체가 활동으로 잡히는지 **확인하십시오.**
확실하지 않으면 워크플로가 실패했을 때 알림을 받는 장치를 두십시오.

- [ ] **Step 3: monthly.yml 을 만듭니다**

`player_info_scraper.py`. 585명 × sleep 2초라 40~90분 추정입니다.

- [ ] **Step 4: 퓨처스를 Worker Cron 으로 옮깁니다**

`futures_schedule.py` 를 JS 로 다시 써서 `scheduled` 핸들러에 넣습니다.
30분 간격입니다.

**이식이 어렵거나 오래 걸리면 Actions 2시간 간격으로 두십시오.**
저장소가 공개라 분 부담이 없습니다. 30분 정시성은 있으면 좋은 것이지
없으면 안 되는 것이 아닙니다.

- [ ] **Step 5: 실행 시각을 D1 에 기록합니다**

EC2 의 `cron_status.json` 을 대체합니다. 화면의 "마지막 업데이트 시간"이
이것을 읽습니다.

- [ ] **Step 6: 하루 돌려 보고 결과를 봅니다**

---

## Task 7: 전량 CSV 를 GitHub Releases 로

**Files:** `.github/workflows/release-csv.yml`, `src/routes/dbexplorer.js`

- [ ] **Step 1: CSV 생성·업로드 워크플로를 만듭니다**

**원본 74컬럼으로 만드십시오.** D1 은 슬림 22컬럼이지만, 내려받는 쪽은
원본이 필요합니다. 수집 단계의 로컬 SQLite 에서 뽑습니다.

gzip 압축합니다. 릴리스 태그는 `data-YYYYMMDD` 같은 고정 규칙으로 두고,
**최신 릴리스를 가리키는 안정된 주소**가 있어야 Worker 가 리다이렉트할 수
있습니다(`/releases/latest/download/<파일명>`).

- [ ] **Step 2: Worker 가 큰 표 요청을 리다이렉트하게 합니다**

지금은 20,000행을 넘으면 413 을 냅니다. 그 자리에서 Releases 로 302 를
보냅니다. 작은 표는 지금처럼 즉석 생성합니다.

- [ ] **Step 3: 동작 차이를 화면에 적습니다**

Releases 파일은 마지막 생성 시점 기준입니다. 하루 한 번 갱신이라
실질 차이는 없지만, **그 사실을 화면에 적어야** 사용자가 왜 오늘 경기가
없는지 압니다.

- [ ] **Step 4: 실제로 받아 봅니다**

전량을 내려받아 행 수와 컬럼 수를 로컬 DB 와 대조하십시오.

---

## Task 8: 공개 전 점검과 마무리

- [ ] **Step 1: 데이터 탐색기의 Cron 표를 실제 스케줄로 고칩니다**

`database-explorer.html:529-605` 가 죽은 EC2 crontab 을 보여줍니다.
아홉 개 작업 중 `auto_deploy_poll.sh` 는 저장소에 아예 없고(EC2 로컬에만
있던 파일로 보입니다), Pages 자동 배포로 대체되어 이제 불필요합니다.

Task 6 에서 세운 실제 스케줄로 바꾸십시오. **없는 것을 있다고 적지
마십시오.**

- [ ] **Step 2: 공개 저장소에 비밀이 없는지 훑습니다**

저장소가 PUBLIC 입니다. 과거 Gmail 앱 비밀번호 유출 이력이 있습니다.

```powershell
py -m detect_secrets scan --all-files
```

**대부분 오탐입니다**(골든 파일의 SHA-256 해시가 고엔트로피 문자열로
잡힙니다). 오탐을 걸러 내고 진짜만 보십시오. 커밋 이력에 남은 것도
확인하십시오. 지금 지워도 이력에 있으면 노출된 것입니다.

- [ ] **Step 3: 무료 한도 실측표를 갱신합니다**

설계 문서 §6 의 예상치가 두 항목에서 틀렸습니다. 12시즌 적재 후 실제
값으로 바꾸십시오.

| 자원 | 확인할 것 |
|---|---|
| D1 저장 | 세 DB 각각이 500MB 아래인지 |
| D1 읽기 | 하루 실사용이 5,000,000 아래인지 |
| D1 쓰기 | 일일 수집분이 100,000 아래인지 |
| Worker Cron | 등록 개수가 5개 아래인지 |

- [ ] **Step 4: 며칠 지켜봅니다**

정기 실행이 실제로 매일 도는지, 데이터가 갱신되는지 봅니다.
**하루 성공했다고 정기 실행이 된 것이 아닙니다.**

- [ ] **Step 5: 설계 문서 §11 M6·M7 을 채우고 커밋합니다**

---

## 완료 기준

- [ ] 2015~2026 이 전부 들어 있고 시즌 셀렉터에 다 나옵니다
- [ ] 일곱 페이지가 전부 정상입니다 (요인 통계 포함)
- [ ] 하루 실사용 `rows_read` 가 5,000,000 아래입니다
- [ ] 세 DB 각각 500MB 아래입니다
- [ ] 수집이 스케줄대로 며칠 연속 돕니다
- [ ] 전량 CSV 를 Releases 에서 받을 수 있습니다
- [ ] 화면의 Cron 표가 실제 스케줄과 같습니다
- [ ] 공개 저장소에 비밀이 없습니다

## 계획 D 에서 하지 않는 것

- **커스텀 도메인**: `bstats.duckdns.org` 는 DuckDNS 가 CNAME 을 지원하지
  않아 Pages 에 붙일 수 없습니다(설계 문서 §2 결정). 도메인 구입은 예산
  조건에 어긋납니다. `pages.dev` 주소를 씁니다.
- **디자인 개선**: 이전이 목적입니다.
- **R2**: 결제 수단 등록을 요구해 씁니다. GitHub Releases 로 갈음합니다.

## 열려 있는 판단

실행 전에 정해야 합니다. 제가 정할 수 없는 것들입니다.

1. **슬림화를 받아들이는지.** 데이터 탐색기에서 52개 컬럼이 사라집니다.
   전량 CSV 로는 계속 받을 수 있지만 화면에서는 안 보입니다.
   받아들이지 않으면 안 A(현행 74컬럼 + 시즌 분리)로 가야 하고, DB 가
   7개 이상 필요하며 코드 수정이 커집니다.
2. **데이터 탐색기를 어떻게 할지** (Task 4 Step 6 의 세 안).
3. **요인 통계 화면을 지금 고칠지.** 계획 C 에서 남겨 둔 판단입니다.
   RE24 가 404 면 파크 팩터 탭까지 죽는 구조인데, Task 5 에서 RE24 가
   채워지면 증상은 사라집니다. 다만 결함 자체는 남습니다.
