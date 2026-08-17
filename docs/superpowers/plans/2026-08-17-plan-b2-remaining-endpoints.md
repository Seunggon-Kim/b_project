# 계획 B2: 나머지 24개 엔드포인트 이식 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `api/main.py` 의 남은 엔드포인트 24개를 Cloudflare Workers 로 옮겨 API 이식을 끝냅니다.

**Architecture:** 계획 B 가 세운 뼈대(`src/index.js` 라우터, `src/lib/*` 유틸, 엔드포인트 하나에 파일 하나)를 그대로 씁니다. 검증도 같습니다. `wrangler deploy` 후 `migration/capture_worker.py` 로 응답을 떠 `golden_compare.py` 로 정답지와 대조합니다. 가벼운 것부터 옮겨 진도를 내고, 계산이 무거운 다섯 개는 CPU 를 실측한 뒤 방식을 정합니다.

**Tech Stack:** Cloudflare Workers (JavaScript, ES modules), Cloudflare D1, Cloudflare R2, Wrangler, Node 내장 `node:test`, Python 3.13

## Global Constraints

- 예산 0원. 유료 플랜 전환, 도메인 구입, VPS 임차는 금지합니다.
- Workers 무료 한도: 요청 100,000/일, **호출당 CPU 10ms**, 요청당 subrequest 50개, 응답 본문 메모리 128MB.
- D1 무료 한도: DB당 저장 500MB, 쓰기 100,000행/일, **읽기 5,000,000행/일**, **Worker 호출당 쿼리 50개**.
- R2 무료 한도: 저장 10GB, Class A 100만/월, Class B 1000만/월, **송신 무료**.
- **npm 의존성을 늘리지 않습니다.** 테스트는 Node 내장 `node --test` 입니다(인자 없이 부릅니다).
- 비밀은 git 에 두지 않습니다.
- 사용자 노출 한국어는 `습니다/합니다/입니다` 정중체를 씁니다.
- 명령은 Windows PowerShell 기준입니다. 저장소 루트에서 실행합니다.
- 배포 주소: `https://kbo-api.bstats-baseball.workers.dev`
- **이식 기준 원본은 `api/main.py` 입니다. 동작을 바꾸지 않습니다.** 버그로 보이는 것도 그대로 옮깁니다. 골든 정답지가 현재 동작으로 떠 있기 때문입니다.

---

## 계획 B 에서 이어받는 것

이미 만들어져 있어 그대로 씁니다. 다시 만들지 마십시오.

| 파일 | 내보내는 것 |
|---|---|
| `src/lib/router.js` | `createRouter`, `matchPath`, `queryInt`, `queryStr` |
| `src/lib/respond.js` | `json(data, status)`, `serverError(err)` |
| `src/lib/cache.js` | `ttlCache(초)` |
| `src/lib/html.js` | `stripTags`, `decodeEntities` |
| `src/lib/kst.js` | `kstToday`, `kstDateOf` |
| `src/routes/standings.js` | `KBO_TEAM_CODE`, `KBO_CODE_TO_TEAM` |
| `src/routes/leaders.js` | `ipToOuts`, `fmt3`, `teamCode`, `WOBA_CONST` |
| `migration/capture_worker.py` | 배포본 응답을 `golden/actual` 로 뜹니다. 미이식 404 는 건너뜁니다 |
| `migration/golden_compare.py` | 정답지 대조. 라이브 응답은 구조만 봅니다 |

계획 B 에서 얻은 교훈도 이어집니다.

- **`fmt3` 같은 포맷 헬퍼를 반드시 거치십시오.** `null` 을 `'-'` 로, `0` 은 `'0.000'` 으로 만듭니다. `!value` 로 거르면 `0` 이 `'-'` 가 되어 틀립니다.
- **Python 의 `round()` 는 은행가 반올림입니다.** `.5` 에서 짝수 쪽으로 갑니다. `Math.round` 를 그냥 쓰면 어긋납니다. `leaders.js` 의 `pyRound` 를 재사용하십시오.
- **SQL 이 준 순서를 JS 에서 다시 정렬하지 마십시오.** 동점자 순서가 달라집니다.
- **파이썬의 없는 키는 `None` 이지만 JS 의 `undefined` 는 `JSON.stringify` 에서 키째 사라집니다.** `?? null` 로 고정하십시오.

---

## 대상 24개와 분류

| 그룹 | 엔드포인트 | 원본 줄 수 |
|---|---|---|
| **1. 소형 조회** | `/teams` 8, `/players/search` 8, `/stats/seasons` 17, `/players/{id}` 22, `/stats/regulation` 24, `/dashboard/stats` 26, `/db/tables` 26 | 131 |
| **2. wRC+ 계열** | `/wrc/batter-search` 21, `/wrc/by-stadium` 27, `/wrc/top-changes` 32, `/wrc/leaderboard` 34, `/wrc/seasons` 40, `/wrc/batter/{id}` 43 | 197 |
| **3. 기록 조회** | `/players/{id}/arsenal` 35, `/stats/batters` 38, `/db/table/{name}` 45, `/games` 46, `/stats/pitchers` 49 | 213 |
| **4. 무거운 것** | `/players/{id}/usage` 86, `/logo/{code}` 99, `/db/table/{name}/csv` 109, `/stats/team_range` 129, `/wrc/distribution` 144 | 567 |

그룹 4 가 이 계획의 위험입니다. 계획 B 에서 옮긴 것들은 외부 `fetch` 위주라 CPU 를
거의 쓰지 않았습니다. **여기서 처음으로 호출당 CPU 10ms 가 실제 제약이 됩니다.**

---

## 응답 계약

정답지(`migration/golden/expected/*.json`)에서 뽑은 것입니다. 추측하지 말고 이 표와
실제 파일을 보십시오. 타입이 하나라도 어긋나면 골든 비교가 잡아냅니다.

### JSON 이 아닌 응답 두 종류

`/logo/{code}` 와 `/db/table/{name}/csv` 는 JSON 이 아닙니다. 정답지에 이렇게 남습니다.

```
{"__content_type__": "str", "__length__": "int", "__sha256__": "str"}
```

`golden_capture.py` 가 본문을 파싱하지 못하면 **content-type, 바이트 길이, SHA-256**
으로 요약해 저장하기 때문입니다. 다시 말해 **바이트 단위로 같아야 통과합니다.**
CSV 의 줄바꿈(`\r\n` 인지 `\n` 인지), BOM 유무, 헤더 순서가 한 글자라도 다르면
해시가 어긋납니다. 이식 검증으로는 오히려 가장 엄격합니다.

### 주요 계약

| 엔드포인트 | 형태 |
|---|---|
| `/dashboard/stats` | `{players, batters, pitchers, games, plays: int, seasons: str, status: str}` |
| `/teams` | `{teams: [{team_id, team_name, team_name_en, city, founded_year, stadium}]}` |
| `/players/search` | `{players: [players 테이블 전체 컬럼 18개]}` |
| `/players/{id}/arsenal` | `{player_id: str, count: int, arsenal: [...]}` |
| `/players/{id}/usage` | `{player_id: str, usage: [...]}` |
| `/wrc/seasons` | **배열** `[{season, min_pa, n_batters: int, mean_wrc_home, mean_wrc_half, mean_wrc_weighted, mean_delta, std_delta: float}]` |
| `/wrc/leaderboard`·`by-stadium`·`top-changes` | **배열**. 데이터 없는 시즌이면 `[]` |
| `/wrc/distribution` | `{season, min_pa, n: int, histogram: {home,half,weighted: [{bin,count: int}]}, stats: {home,half,weighted: {n: int, mean,median,p10,p90: float}}}` |
| `/db/table/{name}` | `{table, category: str, columns: [str], schema: [{name,type,desc: str, notnull,pk: bool}], rows: [...], limit, offset: int, total: int}` |

`players_search_q` 의 `birthday` 가 **`int`** 입니다(`20010216`). 문자열이 아닙니다.
`/wrc/seasons` 는 객체가 아니라 **배열**을 돌려줍니다.

---

## File Structure

| 파일 | 책임 |
|---|---|
| `src/routes/teams.js` | `/teams` |
| `src/routes/players.js` | `/players/search`, `/players/{id}`, `/players/{id}/arsenal`, `/players/{id}/usage` |
| `src/routes/stats.js` | `/stats/seasons`, `/stats/regulation`, `/stats/batters`, `/stats/pitchers`, `/stats/team_range` |
| `src/routes/dashboard.js` | `/dashboard/stats` |
| `src/routes/games.js` | `/games` |
| `src/routes/dbexplorer.js` | `/db/tables`, `/db/table/{name}`, `/db/table/{name}/csv` |
| `src/routes/wrc.js` | wRC+ 계열 6개 |
| `src/routes/logo.js` | `/logo/{code}` |
| `src/lib/coldict.js` | `column_descriptions.json` 을 Worker 번들에 넣어 읽습니다 |
| `test/*.test.js` | 순수 함수 단위 테스트 |
| `migration/measure_cpu.py` | 그룹 4 의 CPU 실측 |
| `migration/export_csv_to_r2.py` | CSV 사전 생성과 R2 업로드 (Task 8 에서 필요할 때만) |

한 파일에 여러 엔드포인트를 묶은 곳이 있습니다. 같은 표를 읽고 헬퍼를 공유하는
것들입니다. `/wrc/*` 여섯 개가 `wrc_plus_comparison` 과 `_eff_min_pa` 를 같이 씁니다.

---

## Task 1: 소형 조회 7개

**Files:**
- Create: `src/routes/teams.js`, `src/routes/dashboard.js`, `src/routes/stats.js`, `src/routes/players.js`, `src/routes/dbexplorer.js`
- Create: `src/lib/coldict.js`
- Modify: `src/index.js`

**Interfaces:**
- Consumes: 계획 B 의 `json`, 라우터
- Produces:
  - `teams(request, env)`, `dashboardStats(request, env)`
  - `statsSeasons(request, env)`, `statsRegulation(request, env)`
  - `playersSearch(request, env)`, `playerDetail(request, env, ctx, params)`
  - `dbTables(request, env)`
  - `columnDict()` — `column_descriptions.json` 을 돌려줍니다

**원본**: `/teams` 109-117, `/players/search` 118-126, `/players/{id}` 127-149,
`/dashboard/stats` 82-108, `/stats/seasons` 337-354, `/stats/regulation` 355-379,
`/db/tables` 646-672 (헬퍼 `list_table_names` 622-630, `load_col_dict` 631-645).

일곱 개를 한 태스크로 묶은 이유는 각각 10~26줄이고 전부 D1 단순 조회라, 따로
나누면 검증 왕복만 늘기 때문입니다.

- [ ] **Step 1: 원본 일곱 개를 읽습니다**

```powershell
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[81:149]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[336:379]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[621:672]))"
```

- [ ] **Step 2: 컬럼 사전을 Worker 에서 읽을 방법을 만듭니다**

`/db/tables` 와 `/db/table/{name}` 이 `database/column_descriptions.json` 을 씁니다.
Worker 에는 파일 시스템이 없습니다. 두 가지 방법이 있는데 **첫 번째를 씁니다.**

| 방법 | 평가 |
|---|---|
| **번들에 넣기** | `import dict from '../../database/column_descriptions.json'` 로 정적 import. wrangler 가 번들에 포함합니다. 파일이 바뀌면 재배포가 필요하지만, 이 사전은 수동 관리 문서라 거의 안 바뀝니다 |
| D1 표로 옮기기 | 조회마다 쿼리가 늘고, 사전이 git 에 있는 편이 관리하기 낫습니다 |

`src/lib/coldict.js` 를 만듭니다.

```javascript
// 컬럼 설명 사전입니다. Worker 에는 파일 시스템이 없어 번들에 넣습니다.
// wrangler 가 JSON import 를 정적으로 묶어 줍니다.
//
// 원본 api/main.py:631-645 의 load_col_dict 는 파일을 읽어 캐시합니다.
// 여기서는 import 자체가 캐시 역할을 합니다.
import raw from '../../database/column_descriptions.json';

export function columnDict() {
  return raw;
}

/** 표 하나의 컬럼 설명을 돌려줍니다. 없으면 빈 객체입니다. */
export function tableColumns(table) {
  const t = (raw.tables || {})[table];
  return (t && t.columns) || {};
}

/** 표의 분류명입니다. 원본이 category 필드로 내보냅니다. */
export function tableCategory(table) {
  const t = (raw.tables || {})[table];
  return (t && t.category) || '';
}
```

먼저 wrangler 가 JSON import 를 처리하는지 확인하십시오. 안 되면
`compatibility_flags` 나 `rules` 설정이 필요할 수 있습니다.

```powershell
npx wrangler deploy --dry-run --outdir=.wrangler/tmp
```

- [ ] **Step 3: 일곱 개를 작성합니다**

각 파일에 원본 SQL 을 그대로 옮깁니다. 주의할 점입니다.

- `/players/{id}` 는 `robust_player_lookup`(45-55)을 씁니다. 문자열로 먼저, 숫자면
  정수로 한 번 더 찾습니다. `players.player_id` 에 문자열과 정수가 섞여 있어 생긴
  처리입니다. `src/routes/news.js` 에 같은 코드가 있으니 참고하십시오.
- `/db/tables` 는 `sqlite_master` 를 읽습니다. D1 에서도 됩니다. 다만 D1 이
  내부 표(`_cf_KV`)를 하나 더 갖고 있어 개수가 다를 수 있습니다. 정답지와 비교해
  원본이 무엇을 거르는지(`list_table_names` 622-630) 확인하고 맞추십시오.
- `/dashboard/stats` 의 `seasons` 는 **문자열**입니다(`"2025"` 또는 `"2015-2026"`).
  정수가 아닙니다.

- [ ] **Step 4: 라우트를 등록합니다**

`src/index.js` 에 더합니다. 등록 순서는 상관없습니다. 라우터가 세그먼트 개수를
먼저 보므로 `/players/search` 와 `/players/:id` 가 충돌하지 않습니다. 다만 둘 다
2세그먼트라 **`/players/search` 를 먼저 등록해야** `search` 가 `:id` 로 잡히지
않습니다.

```javascript
router.add('GET', '/teams', teams);
router.add('GET', '/dashboard/stats', dashboardStats);
router.add('GET', '/stats/seasons', statsSeasons);
router.add('GET', '/stats/regulation', statsRegulation);
router.add('GET', '/db/tables', dbTables);
router.add('GET', '/players/search', playersSearch);  // :id 보다 먼저
router.add('GET', '/players/:id', playerDetail);
```

- [ ] **Step 5: 라우트 우선순위 테스트를 추가합니다**

`test/router.test.js` 에 더합니다.

```javascript
test('먼저 등록한 고정 경로가 자리표시자를 이깁니다', async () => {
  const r = createRouter();
  r.add('GET', '/players/search', () => new Response('search'));
  r.add('GET', '/players/:id', () => new Response('detail'));
  const res = await r.handle(
    new Request('https://x/players/search'), {}, {});
  assert.equal(await res.text(), 'search');
});

test('자리표시자는 다른 값을 받습니다', async () => {
  const r = createRouter();
  r.add('GET', '/players/search', () => new Response('search'));
  r.add('GET', '/players/:id', () => new Response('detail'));
  const res = await r.handle(
    new Request('https://x/players/50030'), {}, {});
  assert.equal(await res.text(), 'detail');
});
```

`createRouter` 를 import 목록에 추가해야 합니다.

- [ ] **Step 6: 검증합니다**

```powershell
node --test
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

기대: 일치 건수가 이 일곱 개만큼 늘고 불일치가 없습니다. 뉴스 3건은 출처를 바꿨으니
불일치로 남습니다(설계 문서 §7 위험 2 결정 항목).

- [ ] **Step 7: 커밋합니다**

```powershell
git add src/ test/
git commit -m "feat(workers): 소형 조회 엔드포인트 7개 이식"
```

---

## Task 2: wRC+ 계열 6개

**Files:**
- Create: `src/routes/wrc.js`
- Create: `test/wrc_helpers.test.js`
- Modify: `src/index.js`

**Interfaces:**
- Consumes: Task 1 의 패턴, 계획 B 의 `fmt3`
- Produces:
  - `effMinPa(db, season, requested) -> Promise<number>` — 원본 `_eff_min_pa`
  - `wrcSeasons`, `wrcByStadium`, `wrcLeaderboard`, `wrcTopChanges`, `wrcBatter`, `wrcBatterSearch`

**원본**: `_eff_min_pa` 818-827, `/wrc/seasons` 829-869, `/wrc/by-stadium` 870-897,
`/wrc/leaderboard` 898-932, `/wrc/top-changes` 933-965, `/wrc/batter/{id}` 966-1009,
`/wrc/batter-search` 1010-1031.

여섯 개가 `wrc_plus_comparison` 과 `_eff_min_pa` 를 공유해 한 파일에 둡니다.

- [ ] **Step 1: `_eff_min_pa` 의 동작을 확인합니다**

```powershell
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[817:830]))"
```

진행 중 시즌은 규정타석(3.1 × 팀 경기수)으로 임계값을 낮추고, 완료 시즌은 요청값을
그대로 씁니다. **`play_by_play` 에서 경기 수를 셉니다.** D1 의 `play_by_play` 는
아직 적재 중이라(계획 A Task 8) 값이 다를 수 있습니다. 적재가 끝난 뒤 검증하거나,
그 사실을 알고 차이를 해석하십시오.

`round(3.1 * ...)` 가 나옵니다. **`leaders.js` 의 `pyRound` 를 쓰십시오.**
그 함수를 export 하도록 고치고 여기서 import 합니다.

- [ ] **Step 2: 헬퍼 테스트를 작성합니다**

`test/wrc_helpers.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { qualPaOf } from '../src/routes/wrc.js';

test('경기 수에서 규정타석을 냅니다', () => {
  // 원본: int(round(3.1 * round(2.0 * g / 10.0)))
  assert.equal(qualPaOf(720), 446);
});

test('경기가 없으면 0 입니다', () => {
  assert.equal(qualPaOf(0), 0);
});

test('은행가 반올림을 씁니다', () => {
  // 3.1 * 75 = 232.5. Python round 는 232, Math.round 는 233 입니다.
  assert.equal(qualPaOf(375), 232);
});
```

`qualPaOf(g)` 는 `_eff_min_pa` 안의 계산만 떼어 낸 순수 함수입니다. DB 접근이
섞이면 테스트할 수 없어 분리합니다.

- [ ] **Step 3: 여섯 개를 작성합니다**

주의할 점입니다.

- `/wrc/seasons` 는 **배열**을 돌려줍니다. 객체가 아닙니다.
- `/wrc/leaderboard` 의 `sort` 지원값은 `home`·`half`·`weighted`·`wOBA` 넷이고,
  그 밖의 값은 `half` 로 떨어집니다(원본 900-901).
- `/wrc/top-changes` 의 `direction` 은 `up`·`down` 입니다.
- 데이터 없는 시즌(1990)이면 빈 배열이어야 합니다. `null` 이나 키 누락이 아닙니다.
- `/wrc/seasons` 의 `std_delta` 계산이 원본 856-862 에 있습니다. 표본 표준편차인지
  모표준편차인지 확인해 그대로 옮기십시오. 분모가 `n` 인지 `n-1` 인지가 값을 바꿉니다.

- [ ] **Step 4: 검증합니다**

```powershell
node --test
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

정답지에 wRC+ 계열이 여러 시즌(2015·2021·2026·1990)과 정렬 네 가지로 들어 있습니다.
**전부 값까지 일치해야 합니다.** 외부 호출이 없는 DB 계산이라 라이브 예외가 없습니다.

- [ ] **Step 5: 커밋합니다**

```powershell
git add src/routes/wrc.js src/index.js test/wrc_helpers.test.js
git commit -m "feat(workers): wRC+ 계열 엔드포인트 6개 이식"
```

---

## Task 3: 기록 조회 5개

**Files:**
- Modify: `src/routes/players.js`, `src/routes/stats.js`, `src/routes/dbexplorer.js`
- Create: `src/routes/games.js`
- Modify: `src/index.js`

**Interfaces:**
- Produces: `playerArsenal`, `statsBatters`, `statsPitchers`, `dbTable`, `games`

**원본**: `/players/{id}/arsenal` 214-249, `/stats/batters` 380-418,
`/stats/pitchers` 419-447, `/db/table/{name}` 673-718, `/games` 599-621.

- [ ] **Step 1: 원본을 읽습니다**

```powershell
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[213:249]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[379:447]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[598:621]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[672:718]))"
```

- [ ] **Step 2: `/players/{id}/arsenal` 의 읽기량을 확인합니다**

이 엔드포인트가 `play_by_play` 를 투수 하나로 걸러 읽습니다. 정답지에서 `count` 가
2,209 였습니다. **D1 읽기 한도는 하루 500만 행**이라 이 정도는 문제없지만, 인덱스가
없으면 전체 스캔이 됩니다. `idx_pbp_pitcher` 가 있으니 그것을 타는지 확인하십시오.

```powershell
npx wrangler d1 execute kbo-stats --remote --command "EXPLAIN QUERY PLAN SELECT pitch_type FROM play_by_play WHERE pitcher_ID='50030'" --yes
```

기대: 출력에 `USING INDEX idx_pbp_pitcher` 가 보입니다. `SCAN play_by_play` 만
나오면 인덱스를 타지 않는 것이라 원인을 찾아야 합니다.

- [ ] **Step 3: 다섯 개를 작성합니다**

주의할 점입니다.

- `/stats/batters` 와 `/stats/pitchers` 는 `team_ids` 파라미터가 쉼표 목록입니다
  (`"LG,KT"`). 원본이 어떻게 쪼개고 바인딩하는지 보고 그대로 옮기십시오.
  **문자열을 SQL 에 직접 끼워 넣지 마십시오.** 바인딩 자리표시자를 개수만큼 만듭니다.
- `/db/table/{name}` 은 표 이름을 경로에서 받습니다. **`sqlite_master` 로 존재를
  확인한 뒤에만** 조회하십시오. 원본이 그렇게 합니다(없으면 `{"detail": "Table not
  found"}`). 이름을 그대로 SQL 에 넣는 자리라 확인이 곧 방어입니다.
- `/games` 는 `sqlite_master` 도 읽습니다. 원본 599-621 에서 무엇을 확인하는지
  보십시오.

- [ ] **Step 4: 검증하고 커밋합니다**

```powershell
node --test
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
git add src/ && git commit -m "feat(workers): 기록 조회 엔드포인트 5개 이식"
```

---

## Task 4: 무거운 다섯 개의 CPU 실측

**Files:**
- Create: `migration/measure_cpu.py`

**Interfaces:**
- Produces: 그룹 4 각각의 CPU 시간과 D1 읽기 행 수. 이 수치가 Task 5~8 의 방식을 정합니다.

**측정 없이 구현하지 마십시오.** 10ms 를 넘는지 모르는 채로 옮기면, 다 만든 뒤에
`Worker exceeded CPU time limit` 를 보고 처음부터 다시 설계하게 됩니다.

- [ ] **Step 1: 측정용 임시 엔드포인트를 만듭니다**

`src/index.js` 에 넣습니다. Task 8 에서 제거합니다.

```javascript
// CPU 실측용 임시 엔드포인트입니다. Task 8 에서 제거합니다.
//
// Workers 는 호출당 CPU 10ms 입니다. fetch 대기는 세지 않지만 D1 결과를
// JS 에서 도는 시간은 셉니다. 무거운 엔드포인트가 이 한도를 넘는지 재 봅니다.
router.add('GET', '/probe/cpu', async (request, env) => {
  const url = new URL(request.url);
  const which = url.searchParams.get('q') || '';
  const t0 = Date.now();
  let rows = 0;
  let note = '';

  if (which === 'pbp_scan') {
    // /stats/team_range 가 하는 것과 비슷한 대량 스캔입니다.
    const r = await env.DB.prepare(
      'SELECT pa_result, inning_topbot, score_home, score_away '
      + 'FROM play_by_play WHERE game_date BETWEEN ? AND ?',
    ).bind(20250401, 20250430).all();
    rows = r.results.length;
    // 실제 집계와 비슷한 일을 시켜 봅니다.
    let n = 0;
    for (const x of r.results) if (x.pa_result) n += 1;
    note = 'counted ' + n;
  } else if (which === 'pitcher') {
    const r = await env.DB.prepare(
      'SELECT pitch_type, px, pz, speed FROM play_by_play WHERE pitcher_ID = ?',
    ).bind('50030').all();
    rows = r.results.length;
  } else if (which === 'wrc_all') {
    const r = await env.DB.prepare(
      'SELECT wRC_home, wRC_half, wRC_weighted FROM wrc_plus_comparison '
      + 'WHERE season = ? AND PA >= ?',
    ).bind(2025, 100).all();
    rows = r.results.length;
    const vals = r.results.map((x) => x.wRC_half).sort((a, b) => a - b);
    note = 'median ' + (vals[Math.floor(vals.length / 2)] ?? 'none');
  } else if (which === 'logo') {
    const r = await env.DB.prepare(
      'SELECT * FROM team_logos LIMIT 1').first();
    rows = r ? 1 : 0;
    note = 'keys ' + (r ? Object.keys(r).join(',') : 'none');
  } else {
    return json({ error: 'q 를 pbp_scan|pitcher|wrc_all|logo 중에서 주십시오' }, 400);
  }

  return json({ q: which, rows, wall_ms: Date.now() - t0, note });
});
```

**주의**: `Date.now()` 는 Workers 에서 I/O 사이에만 갱신됩니다. 순수 계산 구간의
경과는 0 으로 보일 수 있습니다. 그래서 이 수치는 참고이고, **진짜 판정은 실제 CPU
한도 초과 오류가 나는지로 합니다.** 아래 Step 3 을 보십시오.

- [ ] **Step 2: 측정 스크립트를 작성합니다**

`migration/measure_cpu.py` 를 만듭니다.

```python
# -*- coding: utf-8 -*-
"""무거운 엔드포인트의 부하를 재 봅니다.

Workers 는 호출당 CPU 10ms 입니다. 넘으면 요청이 죽습니다. 어떤 방식으로
옮길지 정하기 전에 이 한도에 걸리는지 확인합니다.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

BASE = "https://kbo-api.bstats-baseball.workers.dev"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

CASES = ["pbp_scan", "pitcher", "wrc_all", "logo"]


def call(base, q):
    url = "%s/probe/cpu?q=%s" % (base.rstrip("/"), q)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")[:200]
    except Exception as exc:
        return 0, "%s: %s" % (type(exc).__name__, exc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=BASE)
    args = ap.parse_args()

    print("%-10s %-6s %10s %9s  %s" % ("항목", "상태", "행", "경과", "비고"))
    print("-" * 70)
    over = []
    for q in CASES:
        status, body = call(args.base_url, q)
        if status != 200:
            over.append(q)
            print("%-10s %-6s %10s %9s  %s" % (q, status, "-", "-", body))
            continue
        print("%-10s %-6s %10s %7sms  %s" % (
            q, status, format(body.get("rows", 0), ","),
            body.get("wall_ms"), body.get("note", "")[:30]))

    print()
    if over:
        print("한도 초과로 보이는 항목: %s" % ", ".join(over))
        print("이 항목들은 사전 계산이나 R2 우회가 필요합니다.")
        return 1
    print("네 가지 모두 Worker 안에서 처리됩니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: 실측합니다**

```powershell
npx wrangler deploy
py migration/measure_cpu.py
```

**판정 기준**은 `wall_ms` 숫자가 아니라 **요청이 성공하는지**입니다. CPU 한도를
넘으면 Cloudflare 가 요청을 끊어 HTTP 오류나 빈 응답이 옵니다. 200 이 오면 그
작업량은 Worker 안에서 처리된다는 뜻입니다.

`wrangler tail` 로 실제 CPU 를 볼 수도 있습니다.

```powershell
npx wrangler tail --format=json
```

다른 창에서 요청을 보내면 로그에 `cpuTime` 이 찍힙니다.

- [ ] **Step 4: 결과를 표로 정리해 계획에 적습니다**

이 파일의 아래 "실측 결과" 절을 채우십시오. Task 5~8 이 이 표를 보고 갈립니다.

| 항목 | 행 수 | 결과 | 판정 |
|---|---|---|---|
| `pbp_scan` | | | |
| `pitcher` | | | |
| `wrc_all` | | | |
| `logo` | | | |

- [ ] **Step 5: 커밋합니다**

```powershell
git add migration/measure_cpu.py src/index.js docs/superpowers/plans/2026-08-17-plan-b2-remaining-endpoints.md
git commit -m "feat(migration): 무거운 엔드포인트 CPU 실측 도구와 결과"
```

---

## Task 5: /logo/{code}

**Files:**
- Create: `src/routes/logo.js`
- Modify: `src/index.js`

**원본**: 1374-1394 (99줄 분량에 헬퍼 포함).

- [ ] **Step 1: 로고가 어디에 어떤 형태로 있는지 확인합니다**

```powershell
py -c "import sqlite3;c=sqlite3.connect('file:database/kbo_stats.db?mode=ro',uri=True);print([r[1] for r in c.execute('PRAGMA table_info(team_logos)')]);r=c.execute('SELECT * FROM team_logos LIMIT 1').fetchone();print([type(x).__name__ for x in r])"
```

`team_logos` 는 13행이고 행 하나가 최대 87KB 였습니다(계획 A 실측). 이미지가 그대로
들어 있다는 뜻입니다. 컬럼 타입이 BLOB 인지 TEXT(base64)인지 확인하십시오.

- [ ] **Step 2: D1 이 BLOB 을 어떻게 돌려주는지 확인합니다**

```powershell
npx wrangler d1 execute kbo-stats --remote --command "SELECT typeof(logo) FROM team_logos LIMIT 1" --yes
```

컬럼 이름은 Step 1 에서 확인한 것으로 바꾸십시오. D1 의 JS 바인딩은 BLOB 을
`ArrayBuffer` 로 줍니다. 그것을 `new Response(buffer, {headers})` 로 그대로
내보내면 됩니다.

- [ ] **Step 3: 작성합니다**

원본이 어떤 content-type 을 내보내는지, 없는 코드일 때 무엇을 돌려주는지
(`/logo/ZZ` 정답지 참조) 확인해 맞추십시오.

**정답지가 SHA-256 으로 대조합니다. 바이트가 하나라도 다르면 불일치입니다.**

- [ ] **Step 4: 검증하고 커밋합니다**

```powershell
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

`logo_LG.json` 의 `__sha256__` 가 같아야 합니다.

---

## Task 6: /players/{id}/usage 와 /stats/team_range

**Files:**
- Modify: `src/routes/players.js`, `src/routes/stats.js`

**원본**: `/players/{id}/usage` 250-336, `/stats/team_range` 469-598
(상수 `_TR_*` 448-461, `_tr_norm_date` 464-467).

둘 다 `play_by_play` 를 대량으로 읽어 집계합니다. **Task 4 의 실측 결과에 따라
방식이 갈립니다.**

| Task 4 결과 | 방식 |
|---|---|
| `pbp_scan` 이 200 | Worker 안에서 그대로 집계합니다. 원본을 옮기면 끝입니다 |
| `pbp_scan` 이 실패 | **SQL 로 집계를 밀어 넣습니다.** JS 루프 대신 `GROUP BY` 로 D1 이 계산하게 하면 Worker CPU 를 거의 쓰지 않습니다 |

두 번째 경우가 되면 원본의 파이썬 루프를 SQL 로 다시 표현해야 합니다. **결과가
같은지 확인하는 방법은 골든 비교입니다.** 값이 어긋나면 SQL 이 원본 로직과 다른
것이니, 원본 루프를 한 줄씩 짚어 가며 맞추십시오.

- [ ] **Step 1: 원본을 읽습니다**

```powershell
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[249:336]))"
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[447:598]))"
```

`_TR_*` 상수들은 `pa_result` 문자열을 분류하는 집합입니다(`안타`·`2루타`·`볼넷` 등).
JS 로는 `Set` 이나 객체로 옮깁니다. **한글 문자열을 한 글자도 바꾸지 마십시오.**
`몸에 맞는 볼` 과 `몸에 맞는 공` 처럼 표기가 둘인 것들이 있습니다.

- [ ] **Step 2: 분류 집합 테스트를 작성합니다**

`test/team_range_words.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { TR_HIT, TR_WALK, TR_AB } from '../src/routes/stats.js';

test('안타 계열이 셋입니다', () => {
  // 원본 _TR_H1 = {'안타', '내야안타', '번트 안타'}
  assert.ok(TR_HIT.has('안타'));
  assert.ok(TR_HIT.has('내야안타'));
  assert.ok(TR_HIT.has('번트 안타'));
});

test('볼넷 표기 다섯 가지를 모두 담습니다', () => {
  for (const w of ['볼넷', '자동 고의4구', '고의4구', '고의 4구', '자동 고의 4구']) {
    assert.ok(TR_WALK.has(w), w);
  }
});

test('타수에 볼넷은 들어가지 않습니다', () => {
  assert.ok(!TR_AB.has('볼넷'));
});

test('타수에 삼진과 낫아웃 출루가 들어갑니다', () => {
  assert.ok(TR_AB.has('삼진'));
  assert.ok(TR_AB.has('낫아웃 출루'));
});
```

- [ ] **Step 3: 작성하고 검증합니다**

```powershell
node --test
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

**주의**: D1 의 `play_by_play` 적재가 끝나지 않았으면 값이 정답지와 다릅니다.
`py migration/verify_d1.py` 로 행 수를 먼저 확인하십시오. 229,667행이 아니면
이 태스크의 값 검증은 적재 완료 후로 미룹니다.

---

## Task 7: /wrc/distribution

**Files:**
- Modify: `src/routes/wrc.js`

**원본**: 1032-1086.

히스토그램과 분위수(p10·중앙값·p90)를 계산합니다. 정답지 계약입니다.

```
{season, min_pa, n: int,
 histogram: {home, half, weighted: [{bin: int, count: int}]},
 stats: {home, half, weighted: {n: int, mean, median, p10, p90: float}}}
```

- [ ] **Step 1: 분위수 계산 방식을 확인합니다**

```powershell
py -c "import io;s=io.open('api/main.py',encoding='utf-8').readlines();print(''.join(s[1031:1086]))"
```

파이썬이 `statistics.median` 을 쓰는지 직접 계산하는지, 분위수를 어떻게 뽑는지
(보간하는지 가장 가까운 값을 쓰는지) 보십시오. **이 차이가 소수점 값을 바꿉니다.**

- [ ] **Step 2: 계산 함수를 순수 함수로 분리하고 테스트합니다**

`test/wrc_stats.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { median, percentile, histogram } from '../src/routes/wrc.js';

test('홀수 개의 중앙값은 가운데 값입니다', () => {
  assert.equal(median([1, 2, 3]), 2);
});

test('짝수 개의 중앙값은 두 값의 평균입니다', () => {
  // Python statistics.median 이 그렇게 합니다.
  assert.equal(median([1, 2, 3, 4]), 2.5);
});

test('빈 배열의 중앙값은 null 입니다', () => {
  assert.equal(median([]), null);
});

test('분위수가 원본과 같은 방식입니다', () => {
  // Step 1 에서 확인한 방식에 맞춰 기대값을 적으십시오.
  // 보간이면 p10([1..10]) 은 1.9, 최근접이면 2 입니다.
  assert.equal(percentile([1,2,3,4,5,6,7,8,9,10], 10), /* Step 1 결과 */ 1.9);
});

test('히스토그램 구간이 원본과 같습니다', () => {
  const h = histogram([95, 100, 105], 10);
  assert.ok(Array.isArray(h));
  assert.ok(h.every((b) => typeof b.bin === 'number'
                        && typeof b.count === 'number'));
});
```

- [ ] **Step 3: 작성하고 검증합니다**

세 시즌(2015·2021·2026)의 정답지가 있습니다. 값까지 일치해야 합니다.

---

## Task 8: /db/table/{name}/csv 와 정리

**Files:**
- Modify: `src/routes/dbexplorer.js`
- Create: `migration/export_csv_to_r2.py` (R2 방식을 택할 때만)
- Modify: `src/index.js`, 설계 문서

**원본**: 719-770.

`limit=0` 이면 표 전체를 CSV 로 내보냅니다. `play_by_play` 는 229,667행이라
Worker 메모리와 CPU 둘 다 위험합니다.

- [ ] **Step 1: 실제로 되는지 재 봅니다**

작은 표부터 큰 표까지 올려 가며 어디서 깨지는지 봅니다.

```powershell
py -c "
import urllib.request
UA = {'User-Agent':'Mozilla/5.0 Chrome/125.0'}
base = 'https://kbo-api.bstats-baseball.workers.dev'
for t in ['teams','stadium_dim','games','wrc_plus_comparison','play_by_play']:
    url = base + '/db/table/%s/csv?limit=0' % t
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120)
        b = r.read()
        print('%-24s HTTP %s  %.1fKB' % (t, r.status, len(b)/1024))
    except Exception as e:
        print('%-24s 실패 %s' % (t, str(e)[:70]))
"
```

- [ ] **Step 2: 결과에 따라 방식을 정합니다**

| 결과 | 방식 |
|---|---|
| `play_by_play` 까지 성공 | 그대로 둡니다. R2 가 필요 없습니다 |
| 큰 표에서 실패 | **Actions 가 미리 만들어 R2 에 올리고 Worker 가 302 로 넘깁니다** |

두 번째가 되면 설계 문서 §4 의 R2 항목대로 진행합니다. Actions 가 `.csv.gz` 를
만들어 R2 에 올리고, Worker 는 `/db/table/{name}/csv` 요청을 R2 공개 URL 로
리다이렉트합니다. **정답지는 `limit=5` 로만 떠 있어** 작은 응답은 Worker 가 직접
만들고 큰 것만 넘기는 혼합도 가능합니다.

- [ ] **Step 3: CPU 측정 엔드포인트를 제거합니다**

Task 4 에서 넣은 `/probe/cpu` 를 `src/index.js` 에서 지웁니다. `measure_cpu.py`
는 남깁니다.

- [ ] **Step 4: 전체 검증**

```powershell
node --test
py -m pytest tests/ -q
npx wrangler deploy
py migration/capture_worker.py
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

- [ ] **Step 5: 설계 문서 마일스톤을 갱신하고 커밋합니다**

§11 의 M4 행에 결과를 적습니다.

---

## 완료 기준

- [ ] `node --test` 가 전부 통과합니다
- [ ] `py -m pytest tests/ -q` 가 전부 통과합니다
- [ ] 엔드포인트 29개가 모두 배포본에서 200 을 돌려줍니다(`/logo/ZZ` 처럼 의도된 오류 제외)
- [ ] 골든 비교 불일치가 **뉴스 3건뿐**입니다. 그 셋은 출처를 바꾼 것이라 예외입니다
- [ ] `/probe/cpu` 가 코드에서 제거되었습니다
- [ ] 설계 문서 §11 M4 에 결과가 기록되어 있습니다

## 계획 B2 에서 하지 않는 것

- **프론트엔드**: 계획 C 입니다. API 주소만 바꾸면 되는 작업이라 이식이 끝난 뒤가 맞습니다.
- **Cron Trigger 등록, 워크플로 정기화**: 계획 D 입니다.
- **재크롤링**: 계획 D 입니다. 이 계획은 지금 D1 에 있는 데이터로 검증합니다.
- **D1 적재 완료 대기**: 적재(계획 A Task 8)는 병행됩니다. `play_by_play` 를 읽는
  엔드포인트(Task 6, 그리고 `_eff_min_pa` 를 쓰는 wRC+ 일부)는 적재가 끝나야 값이
  맞습니다. 그 사실을 알고 진행하되, 코드 이식 자체는 먼저 끝낼 수 있습니다.

## 실측 결과 (2026-08-17)

배포본 `/probe/cpu` 로 쟀습니다. **판정은 wall_ms 숫자가 아니라 요청이
200 으로 끝나는지**입니다. CPU 한도를 넘으면 Cloudflare 가 요청을 끊습니다.

| 항목 | 읽은 행 | 경과 | 결과 |
|---|---|---|---|
| `logo` (team_logos 1행) | 1 | 753ms | **통과** |
| `wrc_all` (분위수 계산) | 155 | 144ms | **통과** |
| `usage` (투수 단위 집계) | 80 | 138ms | **통과** |
| `pbp_scan` (한 달 스캔) | 5,667 | 357ms | **통과** |
| `pbp_all` (전량 읽기) | 18,000 | 1,329ms | **통과** |

`team_logos` 컬럼은 `code, name, league, mime, source` 입니다. `mime` 이
따로 있으니 그 값을 content-type 으로 쓰면 됩니다.

### 이 수치를 그대로 믿으면 안 됩니다

**지금 D1 의 `play_by_play` 는 18,000행입니다. 적재가 끝나면 229,667행,
12.8배가 됩니다.** 위 측정은 8% 짜리 데이터에서 나온 것입니다.

| 대상 | 지금 | 적재 완료 후 | 위험 |
|---|---|---|---|
| `pbp_all` = CSV 전체 | 18,000행 | 229,667행 | 74컬럼이면 JSON 이 300MB 급. **Workers 메모리 128MB 초과 가능** |
| `pbp_scan` = `/stats/team_range` | 5,667행 (한 달) | 시즌 전체 요청이면 229,667행 | 정답지에 `start=20250301&end=20251031` 요청이 있습니다 |
| `usage` | 80행 | 투수당 수천 행 | 규모가 제한적이라 여유 |

**따라서 적재 완료 후 재측정이 필수입니다.** 특히 CSV 전체와 team_range 는
그때 다시 재고 R2 우회 여부를 정합니다(Task 8).

지금 시점의 결론은 이렇습니다.

- Task 5 (`/logo`) — 지금 진행합니다. 데이터가 늘지 않습니다
- Task 6 (`/usage`, `/team_range`) — 코드는 지금 옮기되, 값 검증과 부하
  판정은 적재 완료 후
- Task 7 (`/wrc/distribution`) — 지금 진행합니다. `wrc_plus_comparison` 은
  이미 전량 적재돼 있어 데이터가 늘지 않습니다
- Task 8 (CSV) — **적재 완료 후에 판정합니다**
