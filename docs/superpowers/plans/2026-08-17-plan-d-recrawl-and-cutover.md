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

### 슬림화를 검토했고, 하지 않기로 했습니다

처음에는 컬럼을 줄이려 했습니다. `src/routes/*.js` 가 `play_by_play` 에서
쓰는 컬럼이 74개 중 22개뿐이기 때문입니다. 그런데 실제로 만들어 재 보니
**깎아도 필요한 DB 수가 줄지 않았습니다.**

네 가지를 실제로 재구축해 쟀습니다. 추정이 아닙니다.

| 구성 | 한 시즌 | 12시즌 | 필요 DB |
|---|---|---|---|
| **A. 현행 74컬럼** | 127.5MB | 1,530MB | **4개** |
| B. API 가 쓰는 22개만 | 47.8MB | 574MB | 2개 |
| C. API + 파생 계산분 33개 | 54.0MB | 649MB | 2개 |
| D. 사람이 읽는 값까지 42개 | 67.4MB | 808MB | 2개 |

B·C·D 가 전부 2개입니다. 22개까지 깎아도, 42개를 남겨도 같습니다.
그리고 A 는 4개인데 공용 DB 를 더해도 **5개로 한도 10개의 절반**입니다.

쓰기 계상도 달라지지 않습니다. D1 은 행 수 × (1 + 인덱스 수)로 세지
컬럼 수는 보지 않습니다. 적재 시간이 줄지도 않습니다.

**얻는 것이 없으므로 깎지 않습니다.** 아래는 깎았을 때 잃는 것입니다.
나중에 누가 다시 이 유혹에 빠지지 않도록 적어 둡니다.

**첫째, 데이터 탐색기가 읽을 수 없는 표가 됩니다.**

| 컬럼 | 실제 값 |
|---|---|
| `pitcher` / `batter` | 폰세, 안현민 → **ID 숫자만 남습니다** |
| `description` | "안현민 : 중견수 플라이 아웃" |
| `balls` / `strikes` / `outs` | 3 / 2 / 0 |
| `inning`, `score_home`, `score_away` | 1회, 0:0 |
| `on_1b` / `on_2b` / `on_3b` | 주자 이름 |
| `pos_1`~`pos_9` | 수비 라인업 |

남는 22개는 `px`, `pz`, `sz_top` 같은 좌표와 ID 입니다. 표를 열어도
무슨 일이 일어난 경기인지 알 수 없습니다. `column_descriptions.json` 에는
74개 전부에 설명이 붙어 있습니다.

**둘째, 파생 지표를 다시 계산할 수 없게 됩니다.** 이쪽이 더 큽니다.
`park_factors/build_re24_run_values.py:52` 가 요구하는 컬럼입니다.

```
pbp_id, game_date, away, home, inning, inning_topbot, outs,
score_home, score_away, pa_result, on_1b, on_2b, on_3b
```

이 중 9개가 22개 목록에 없습니다. RE24·파크팩터·wRC+ 재계산이 막힙니다.
Task 5 가 "전 시즌을 모은 뒤 RE24 를 제대로 만든다"인데 그것을 못 합니다.

**셋째, `pbp_id` 는 기본키라 애초에 뺄 수 없습니다.** 22개 목록에
없었는데 PRIMARY KEY 이고, Task 1 의 keyset 페이지네이션도 이것을 씁니다.

### 그래서: 74컬럼 그대로, 3시즌씩 4분할

```
kbo-stats          공용. play_by_play 를 뺀 17개 표 (2.7MB)
kbo-pbp-2015-2017  play_by_play 3시즌 (약 382MB)
kbo-pbp-2018-2020  play_by_play 3시즌 (약 382MB)
kbo-pbp-2021-2023  play_by_play 3시즌 (약 382MB)
kbo-pbp-2024-2026  play_by_play 3시즌 (약 382MB)
```

DB 5개, 한도 10개. 데이터 손실 없고, 파생 계산 문제 없고, 되돌릴 일도
없습니다.

`games` 표는 네 pbp DB 에도 복제합니다(시즌당 약 15KB). `teamrange.js:222`
가 `JOIN games` 를 하는데, 복제해 두면 그 SQL 을 그대로 둘 수 있습니다.

**화면은 이 구조를 모릅니다.** Worker 가 필요한 DB 에 묻고 합쳐서
내보냅니다. 2019년 선수의 구종 차트를 요청하면 `kbo-pbp-2018-2020` 만
봅니다.

이어붙인 순서가 원본과 같은지도 확인했습니다. `pbp_id` 오름차순이
`game_date` 순서를 거스르는 지점이 **0개**입니다(실측). 시즌 순으로
이어붙이면 원본과 같은 순서가 나옵니다.

### 성장 여지

매년 약 127MB 씩 늘어 마지막 묶음이 **2027 시즌에 500MB 를 넘습니다.**
그때 DB 를 하나 더 만들면 됩니다. 지금 10개 중 5개만 씁니다.

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
늘리면 위험합니다. 3시즌씩 4분할인 이유가 그것입니다. 시즌당 하나씩
나누면 fan-out 이 12개가 되어 쿼리 한도를 압박합니다.

---

## 2026 시즌은 통째로 비어 있습니다

재크롤링 범위를 정할 때 이것부터 알아야 합니다. 실측한 현재 상태입니다.

| 표 | 2026 |
|---|---|
| `play_by_play` | **없음** |
| `games` | **없음** |
| 공식 타자·투수 기록 | **없음** |
| `statiz_park_factor` | 없음 (2015~2025 만) |
| `futures_games` | 407건, 단 **2026-04-01 ~ 06-29 에서 멈춤** |
| `wrc_plus_comparison` | **있음** (덤프 복원분) |
| `weighted_pf_by_batter_season` | **있음** (덤프 복원분) |

2026 시즌은 이미 약 515경기가 열렸습니다(10구단 × 103경기 ÷ 2, 2026-08-17
기준). 그것이 전부 없습니다.

홈 화면에 오늘 경기와 순위가 나오는 것은 네이버·KBO 실시간 API 에서 직접
받기 때문입니다. DB 를 거치지 않아 겉보기에는 멀쩡합니다.

### 함정: 파생표 재계산은 전 시즌을 모은 뒤에만 합니다

`wrc_plus_comparison` 과 `weighted_pf_by_batter_season` 에는 **2015~2026
전 시즌 값이 있습니다.** EC2 가 계산해 둔 것을 덤프에서 복원한 것입니다.
그런데 원천 `play_by_play` 에는 2025·2026 밖에 없습니다.

`park_factors/build_wrc_plus.py:73` 이 이렇게 시작합니다.

```sql
DELETE FROM wrc_plus_comparison;
DELETE FROM weighted_pf_by_batter_season;
```

**시즌별이 아니라 표 전체를 지웁니다.** 그리고 PBP 에 있는 시즌만 다시
넣습니다. 지금 돌리면 2015~2024 파생값이 통째로 사라지고, 그 열 시즌은
원천이 없어 되살릴 수도 없습니다.

`build_re24_run_values.py` 도 같습니다. `season=0` 은 "완결된 시즌을 모두
모은 기준선"이라 시즌이 빠지면 값 자체가 달라집니다.

**그러므로 재계산은 2015~2024 를 전부 모은 뒤 단 한 번 합니다.**
시즌을 하나씩 넣을 때마다 돌리면 안 됩니다.

그때까지 2026 파생값은 EC2 가 7월 중순까지 계산한 값으로 남습니다.
화면의 2026 wRC+ 가 최신이 아니라는 뜻이지만, 열 시즌을 잃는 것보다
낫습니다.

`build_wrc_plus.py:71` 이 `*_bak` 으로 한 단계 백업을 남기기는 합니다.
그것에 기대지 마십시오. 두 번 돌리면 백업도 덮입니다.

### 2026 포스트시즌 컷오프가 아직 없습니다

`data_collection/load_year_pbp.py:26` 과 `games_from_pbp.py:40` 의
`PLAYOFF_START` 표가 2025 에서 끝납니다. 2026 이 없습니다.

값이 없으면 코드가 전부 "정규시즌"으로 넣습니다(`games_from_pbp.py:86`).
2026-08-17 현재는 포스트시즌 전이라 결과가 맞습니다. **10월에 포스트시즌이
시작하면 그때부터 틀립니다.** 일정이 확정되면 두 파일에 같은 값을
넣으십시오. 한쪽만 고치면 두 표의 `game_type` 이 어긋납니다.

### 퓨처스가 6월 29일에 멈춘 이유는 따로 있습니다

EC2 는 2026-07-14 에 정지했는데 `futures_games` 는 06-29 에서 끊겼습니다.
2주가 빕니다. 서버 정지와 다른 원인이 있다는 뜻입니다. Task 6 에서
퓨처스 수집을 세울 때 원인을 먼저 확인하십시오. 같은 이유로 또 멈춥니다.

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

**컬럼 수는 쓰기 계상과 무관합니다.** D1 은 행 수 × (1 + 인덱스 수)로
셉니다. 74컬럼을 그대로 두어도 22컬럼으로 깎아도 같습니다. 슬림화가
적재 시간을 줄여 주지 않는 이유입니다.

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

## 실행 순서를 바꿨습니다 (2026-08-17)

계획은 Task 3(분할) → Task 5(재크롤링) 순서였는데, **Task 5 를 먼저
합니다.** 이유가 있습니다.

지금 D1 은 136MB 이고 한도는 500MB 입니다. 2026 한 시즌을 더 넣어도
약 264MB 로 아직 여유가 있습니다. **분할하지 않고도 들어갑니다.**

빈 DB 4개를 먼저 만들고 fan-out 코드를 짜면, 데이터가 2025 하나뿐이라
그 코드가 실제로 맞는지 검증할 길이 없습니다. 시즌이 여럿 들어온 뒤에
나누면 실제 데이터로 확인하면서 짤 수 있습니다.

그래서 이 순서로 갑니다.

| 순서 | 내용 | 상태 |
|---|---|---|
| Task 1 | 읽기량 감축 | **완료** |
| Task 2 | Workers Cache | **완료** |
| Task 5 | 재크롤링 (2026 부터) | 진행 중 |
| Task 3·4 | 500MB 에 닿을 때 분할 | 대기 |
| Task 6~8 | 정기 실행, CSV, 마무리 | 대기 |

**분할 시점**: 시즌을 넣다가 D1 이 400MB 를 넘으면 그때 Task 3 으로
갑니다. `npx wrangler d1 info kbo-stats` 로 적재할 때마다 확인하십시오.
500MB 를 넘기고 나서는 늦습니다.

## Task 1: 읽기량부터 줄입니다 — 완료

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

## Task 2: Workers Cache 를 켭니다 — 완료

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

## Task 3: `play_by_play` 를 네 개 DB 로 나눕니다

컬럼은 74개 그대로입니다. 슬림화는 하지 않습니다(§슬림화를 검토했고,
하지 않기로 했습니다 참조).

**Files:** `wrangler.toml`, `src/lib/shard.js`, `migration/shard_plan.py`

- [ ] **Step 1: D1 네 개를 만듭니다**

```powershell
npx wrangler d1 create kbo-pbp-2015-2017
npx wrangler d1 create kbo-pbp-2018-2020
npx wrangler d1 create kbo-pbp-2021-2023
npx wrangler d1 create kbo-pbp-2024-2026
```

만든 뒤 `npx wrangler d1 list` 로 계정 전체 개수를 세십시오. **한도가
10개입니다.** 공용 1 + pbp 4 = 5개여야 합니다.

- [ ] **Step 2: 바인딩 네 개를 추가합니다**

`wrangler.toml` 에 `[[d1_databases]]` 블록을 반복합니다. 바인딩 이름은
시즌 범위를 그대로 씁니다(`DB_2015_2017` 등). 코드에서 시즌으로 이름을
만들어 찾을 수 있어야 합니다.

- [ ] **Step 3: 라우팅과 fan-out 을 만듭니다**

```javascript
// 시즌 하나 -> 그 시즌이 든 D1 바인딩
export function shardOf(env, season) { /* ... */ }
// 시즌 목록 -> 관련 DB 에만 질의하고 결과를 이어붙입니다.
// 시즌 순으로 정렬해 이어야 원본 순서와 같아집니다.
export async function fanOut(env, seasons, fn) { /* ... */ }
```

**두 가지를 지키십시오.**

- Worker 호출당 D1 쿼리는 50개입니다. DB 4개로 늘었으니 `dashboard.js`
  처럼 DB 하나에 4쿼리를 던지는 코드는 **DB 당 1쿼리로 합쳐야** 합니다.
  합치면 4개, 안 합치면 16개입니다.
- 필요 없는 DB 에는 묻지 마십시오. 2019년 요청에 네 DB 를 다 두드리면
  쿼리도 읽기도 네 배입니다.

- [ ] **Step 4: `games` 를 네 pbp DB 에 복제합니다**

`teamrange.js:222` 의 `JOIN games` 를 그대로 두기 위해서입니다. 시즌당
15KB 라 용량은 문제없습니다. **적재할 때 다섯 DB 의 games 가 어긋나지
않게 하십시오.** 공용 DB 의 games 가 정본이고 나머지는 사본입니다.

- [ ] **Step 5: 크로스 시즌 네 곳을 고칩니다**

이 문서 §시즌을 가로지르는 쿼리의 표를 따르십시오.

- [ ] **Step 6: 탐색기의 페이지 넘기기를 DB 경계에 걸쳐 계산합니다**

`play_by_play` 라는 단일 표가 이제 없습니다. 그래도 **화면은 그대로 둘 수
있습니다.** 각 DB 의 행 수를 알면(Task 1 의 메타 표) 요청한 offset 이
몇 번째 DB 의 몇 번째 행인지 계산됩니다. 경계를 걸치면 두 DB 에서 나눠
읽어 이어붙입니다.

순서도 맞습니다. `pbp_id` 오름차순이 `game_date` 순서를 거스르는 지점이
0개임을 확인했습니다. 시즌 순으로 이어붙이면 원본과 같습니다.

**행 수 표시도 합계로 바꾸십시오.** 지금은 한 DB 의 `COUNT(*)` 인데,
네 DB 의 합이어야 사용자가 보는 숫자가 맞습니다.

- [ ] **Step 7: 골든을 로컬에서 돌립니다**

이 작업의 목적은 저장 위치를 바꾸는 것이지 응답을 바꾸는 것이 아닙니다.
**102건 전부 일치해야 합니다.** 하나라도 달라지면 fan-out 이나 순서가
틀린 것입니다.

원격이 아니라 로컬 D1 에 돌리십시오.

---

## Task 4: 적재를 시즌에 맞는 DB 로 보냅니다

**Files:** `migration/export_to_d1.py`, `migration/load_to_d1.py`, `migration/shard_plan.py`

- [ ] **Step 1: 시즌 -> DB 배정을 한 곳에서 정합니다**

`shard_plan.py` 가 정본이고, Worker 의 `shard.js` 와 값이 같아야 합니다.
**두 곳에 따로 적으면 언젠가 어긋납니다.** 배정표를 JSON 으로 두고
양쪽이 읽는 편이 낫습니다.

- [ ] **Step 2: 내보내기를 시즌별로 자릅니다**

지금 `export_to_d1.py` 는 표 전체를 청크로 나눕니다. `play_by_play` 는
시즌으로 먼저 자른 뒤 청크로 나눠야 합니다.

- [ ] **Step 3: 적재 후 DB 별 행 수를 대조합니다**

각 DB 의 `play_by_play` 행 수 합계가 로컬 원본과 같아야 합니다.
**한 시즌이 두 DB 에 들어가거나 빠지는 것이 가장 흔한 실수입니다.**
시즌별 행 수를 따로 세어 비교하십시오.

- [ ] **Step 4: 메타 행 수 표를 갱신합니다**

Task 1 에서 만든 표에 DB 별·시즌별 행 수를 넣습니다. 탐색기 페이지
넘기기가 이 값을 씁니다.

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

**2015~2024 를 전부 채운 뒤에 하십시오.** `build_wrc_plus.py:73` 이
`DELETE FROM wrc_plus_comparison` 으로 표 전체를 지우고 PBP 에 있는
시즌만 다시 넣습니다. 일부만 채운 상태로 돌리면 나머지 시즌이 사라지고
원천이 없어 되살릴 수 없습니다.

이때 **계획 C 에서 못 넣은 `re24_matrix_by_season` 이 비로소 제대로
만들어집니다.** `season=0` 이 열한 시즌을 모은 값이 되어야 맞습니다.
2025 하나만으로 만들면 안 되는 이유가 그것이었습니다.

만든 뒤 `season=0` 의 `n_obs` 가 단일 시즌 값보다 훨씬 큰지 확인하십시오.
같다면 여전히 한 시즌만 들어간 것입니다.

- [ ] **Step 6: 요인 통계 화면이 살아났는지 봅니다**

`py migration/check_pages_browser.py` 가 일곱 페이지 전부 정상이어야 합니다.

---

## 2026 적재에서 드러난 것 둘 (2026-08-17)

2026 PBP 를 넣고 확인하다 발견했습니다. 둘 다 계획에 없던 항목입니다.

### 1. 수집 뒤 캐시를 비워야 합니다

Task 2 에서 Workers Cache 를 켰습니다. 읽기를 0 으로 만드는 대신,
**데이터를 갱신해도 최대 한 시간 동안 옛 값이 나갑니다.**

2026 을 적재한 직후 실측입니다.

| | 경기 | 플레이 | 시즌 |
|---|---|---|---|
| 캐시된 응답 (사용자가 본 것) | 719 | 229,667 | 2025 |
| 실제 데이터 | 1,262 | 405,416 | 2025~2026 |

한 시간 뒤 저절로 맞춰지지만, 매일 새벽 수집이 끝난 뒤 한 시간 동안
어제 숫자가 보이는 것은 좋지 않습니다. **적재 단계 끝에 캐시 비우기를
넣으십시오.** Cloudflare 의 cache purge 를 Actions 에서 부르면 됩니다.

넣지 않으려면 최소한 그 지연을 화면에 적어야 합니다. 사용자가 "왜 오늘
경기가 없지"라고 생각하게 두면 안 됩니다.

### 2. PBP 만으로는 시즌 셀렉터가 안 채워집니다

`/stats/seasons`(`src/routes/stats.js:6-17`)는 `play_by_play` 가 아니라
**공식 기록 표**를 봅니다.

```sql
SELECT season FROM kbo_official_batter_stats
UNION
SELECT season FROM kbo_official_pitcher_stats
```

2026 PBP 를 175,749행 넣었는데도 시즌 목록이 `[2025]` 인 이유입니다.
공식 기록에 2026 이 없습니다.

그러므로 시즌 하나를 되살리려면 **두 가지를 다 모아야 합니다.**

| 대상 | 수집기 | 필요한 것 |
|---|---|---|
| play-by-play | `crawler/pbp.py` | HTTP 만. 시즌당 20~25분 |
| 공식 타자·투수 기록 | `selenium_batter_scraper.py`, `selenium_pitcher_scraper.py` | **Selenium**. 시즌당 15~20분 |

PBP 백필과 공식 기록 백필을 짝으로 돌리십시오. 한쪽만 하면 화면이
반쪽만 살아납니다.

## 정기 실행의 진짜 문제: 러너에 DB 가 없습니다

계획을 세울 때 "Actions 에서 돌린다"고만 적고 **DB 를 어디에 두는지**
정하지 않았습니다. 이것부터 풀어야 Task 6 을 만들 수 있습니다.

EC2 에서는 모든 스크립트가 로컬 SQLite 를 직접 읽고 썼습니다. 셋은
경로가 아예 박혀 있습니다.

| 스크립트 | 경로 |
|---|---|
| `data_collection/daily_kbo_pbp.sh:24` | `/home/ubuntu/b_project/database/kbo_stats.db` |
| `data_collection/daily_player_detector.py:21` | 〃 |
| `data_collection/daily_cleanup_orphan_stats.py:15` | 〃 |

Actions 러너에는 그 경로도 없고 파일도 없습니다. DB 는 226MB(12시즌이면
약 1.3GB)라 git 에 둘 수 없습니다.

### 작업을 두 부류로 나누면 대부분이 풀립니다

각 작업이 실제로 얼마나 넓은 데이터를 보는지 확인했습니다.

| 작업 | 보는 범위 | 로컬 DB |
|---|---|---|
| PBP 일일 수집 | 어제 5경기 | 불필요 |
| 공식 타자·투수 기록 | 시즌 누적 398+281행 | 불필요 |
| 선수 뉴스 | 선수 목록 585행 | 불필요 (이미 D1 직접) |
| `daily_player_detector` | 어제 PBP | 불필요 |
| `daily_cleanup_orphan_stats` | 공식 기록 2024 이후 | 불필요 |
| `player_registry_sync` | players 585행 | 불필요 |
| 퓨처스 일정 | 없음 | 불필요 |
| **`park_factors/*`** | **전 시즌 PBP 240만 행** | **필요** |

**전체 DB 가 필요한 것은 park_factors 하나뿐입니다.** 나머지는 D1 에
직접 질의하고 직접 쓰면 됩니다. 지금 뉴스 수집이 이미 그렇게 돕니다
(`collect_player_news.py --source d1`).

### 그래서 이렇게 나눕니다

**일일(daily.yml)** — 로컬 DB 없이 D1 직접

```
어제 PBP 수집 -> INSERT SQL -> D1
공식 기록 수집 -> UPSERT SQL -> D1
선수 뉴스 -> D1            (이미 구현됨)
player_detector -> D1 질의
cleanup -> D1 질의
registry_sync -> D1 질의
행 수 메타 갱신
캐시 비우기                 (아래 참조)
실행 시각 기록
```

**주간(weekly.yml)** — park_factors 전용

전 시즌 PBP 가 필요하므로 D1 에서 내려받아 임시 SQLite 를 만든 뒤
계산하고, **파생표만** 다시 올립니다. 파생표는 다 합쳐 2.7MB 라 가볍습니다.

읽기 비용이 한 번에 약 240만 행입니다. 하루 한도 500만의 절반이라
매일은 무리고 주 1회가 적당합니다. 파크팩터와 wRC+ 가 하루 사이에
크게 변하지 않으므로 손해가 적습니다.

Actions 캐시(10GB, 7일 미사용 시 삭제)에 SQLite 를 얹는 방법도 있습니다.
빠르지만 상태를 들고 다녀야 하고, 캐시가 날아가면 조용히 옛 데이터로
계산합니다. **틀린 값을 조용히 내는 쪽이 느린 것보다 나쁩니다.**
D1 에서 매번 받는 편이 확실합니다.

**월간(monthly.yml)** — `player_info_scraper.py`. Selenium, 585명 × 2초.

### 캐시 비우기가 일일 흐름의 마지막입니다

Task 2 에서 캐시를 켰으므로 적재 뒤 비우지 않으면 최대 한 시간 동안
어제 숫자가 보입니다. 실측으로 확인한 문제입니다(§2026 적재에서 드러난 것).
일일 워크플로 끝에 넣으십시오.

### 남은 것: 경로가 박힌 스크립트 셋

`/home/ubuntu/...` 를 환경변수로 바꿔야 합니다. `park_factors` 는 이미
`KBO_DB` 환경변수를 봅니다(`build_re24_run_values.py:28`). 같은 방식으로
맞추면 됩니다.

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

D1 에 74컬럼이 그대로 있으므로 D1 에서 뽑아도 되고, 수집 단계의 로컬
SQLite 에서 뽑아도 됩니다. **D1 에서 뽑으면 읽기 한도를 크게 씁니다**
(전량 스캔 약 276만 행). 로컬에서 뽑는 편이 낫습니다.

`play_by_play` 는 시즌별 파일로 나눠 올리십시오. 한 파일 420MB 보다
시즌별 35MB 가 받는 쪽에도 편합니다.

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
| D1 저장 | pbp DB 네 개가 각각 500MB 아래인지, 계정 총합이 5GB 아래인지 |
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
- [ ] `play_by_play` 컬럼이 74개 그대로입니다 (탐색기에서 확인)
- [ ] 일곱 페이지가 전부 정상입니다 (요인 통계 포함)
- [ ] 하루 실사용 `rows_read` 가 5,000,000 아래입니다
- [ ] pbp DB 네 개가 각각 500MB 아래입니다
- [ ] 수집이 스케줄대로 며칠 연속 돕니다
- [ ] 전량 CSV 를 Releases 에서 받을 수 있습니다
- [ ] 화면의 Cron 표가 실제 스케줄과 같습니다
- [ ] 공개 저장소에 비밀이 없습니다

## 계획 D 에서 하지 않는 것

- **커스텀 도메인**: `bstats.duckdns.org` 는 DuckDNS 가 CNAME 을 지원하지
  않아 Pages 에 붙일 수 없습니다(설계 문서 §2 결정). 도메인 구입은 예산
  조건에 어긋납니다. `pages.dev` 주소를 씁니다.
- **디자인 개선**: 이전이 목적입니다.
- **R2**: 결제 수단 등록을 요구해 쓰지 않습니다. GitHub Releases 로 갈음합니다.
- **컬럼 슬림화**: 검토했고 하지 않습니다. 깎아도 필요한 DB 수가 줄지
  않는데(실측) 탐색기와 파생 계산만 잃습니다.

## 열려 있는 판단

실행 전에 정해야 합니다. 제가 정할 수 없는 것들입니다.

1. **요인 통계 화면을 지금 고칠지.** 계획 C 에서 남겨 둔 판단입니다.
   RE24 가 404 면 파크 팩터 탭까지 죽는 구조인데, Task 5 에서 RE24 가
   채워지면 증상은 사라집니다. 다만 결함 자체는 남습니다.
