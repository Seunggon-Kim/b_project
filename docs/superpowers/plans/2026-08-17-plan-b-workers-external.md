# 계획 B: Workers 기반 구축과 외부 연동 이식 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cloudflare Workers 위에 API 뼈대를 세우고, 외부 사이트에 의존하는 엔드포인트 5개를 먼저 이식해 위험 2(Cloudflare 엣지가 외부 사이트에서 차단당하는가)를 판정합니다.

**Architecture:** `src/index.js` 가 경로를 라우팅하고, 엔드포인트 하나가 파일 하나입니다. D1 은 `env.DB` 바인딩으로 접근합니다. 검증은 계획 A 에서 만든 골든 비교를 그대로 씁니다. `wrangler dev --remote` 로 Worker 를 띄우고 `golden_capture.py` 로 응답을 떠서 정답지와 대조합니다.

**Tech Stack:** Cloudflare Workers (JavaScript, ES modules), Cloudflare D1, Wrangler, Node 내장 `node:test`, Python 3.13 (골든 비교 도구)

## Global Constraints

- 예산 0원. 유료 플랜 전환, 도메인 구입, VPS 임차는 금지합니다.
- Workers 무료 한도: 요청 100,000/일, **호출당 CPU 10ms**, 요청당 subrequest 50개, Cron Trigger 계정당 5개.
- D1 무료 한도: DB당 저장 500MB, 쓰기 100,000행/일, 읽기 5,000,000행/일, **Worker 호출당 쿼리 50개**.
- **비밀은 git 에 두지 않습니다.** Cloudflare API 토큰은 GitHub Secrets, 런타임 비밀은 Workers 시크릿에 둡니다.
- **npm 의존성을 늘리지 않습니다.** 테스트는 Node 내장 `node:test` 를 씁니다. 번들이 커지면 Workers 시작 시간이 늘고, 의존성마다 공급망 위험이 붙습니다.
- 사용자 노출 한국어는 `습니다/합니다/입니다` 정중체를 씁니다.
- 작업 디렉터리는 저장소 루트입니다. 명령은 Windows PowerShell 기준으로 적습니다.
- D1 데이터베이스 이름: `kbo-stats`, 바인딩 이름: `DB`
- 이식 기준 원본은 `api/main.py` 입니다. **동작을 바꾸지 않습니다.** 버그로 보이는 것도 그대로 옮깁니다. 골든 정답지가 현재 동작으로 떠 있기 때문입니다.

---

## 이 계획의 범위

**넣는 것 — 엔드포인트 5개**

| 경로 | 외부 의존 | 원본 위치 |
|---|---|---|
| `/standings` | KBO `koreabaseball.com` (HTML) | `api/main.py:1474-1520` |
| `/schedule` | 네이버 `api-gw.sports.naver.com` (JSON) | `api/main.py:1177-1227` |
| `/schedule/futures` | KBO `koreabaseball.com` (POST JSON) | `api/main.py:1276-1373` |
| `/players/{id}/news` | 구글 `news.google.com` (RSS XML) | `api/main.py:150-212` |
| `/leaders` | **없음.** 순수 DB 계산 | `api/main.py:1594-1742` |

**빼는 것**

나머지 24개 엔드포인트는 **계획 B2** 에서 이식합니다. 이 계획을 먼저 끝내는 이유는 위험 2 가 여기서만 판명되기 때문입니다. 설계 문서 §7 위험 2 는 "이 설계에서 기능 손실이 발생할 수 있는 유일한 지점" 입니다. 24개를 다 옮기고 나서 알게 되면 늦습니다.

`/leaders` 는 외부 의존이 없는데도 넣었습니다. 계산이 가장 복잡한 엔드포인트라(wOBA → wRAA → wRC+, 파크팩터 자체 계산) **위험 4(이식 과정의 계산 오차)** 를 여기서 미리 드러내려는 것입니다. 나머지 23개를 옮기기 전에 숫자가 맞는지 확인해 두는 편이 낫습니다.

**[정정] 설계 문서의 "네이버 연동 5개" 는 부정확합니다.**

설계 문서 §11 M3 은 이 다섯을 "네이버 연동" 으로 묶었으나, 실제 외부 대상은 세 곳이고 `/leaders` 는 외부를 부르지 않습니다. 따라서 위험 2 는 네이버 하나가 아니라 **도메인 세 곳을 각각** 판정해야 합니다. 이 계획의 Task 2 가 그 일을 합니다.

---

## 응답 계약

이식본이 맞춰야 할 응답 형태입니다. **추측하지 말고 이 표를 따르십시오.** 정답지
(`migration/golden/expected/*.json`)에서 뽑은 것이라 실제 동작과 일치합니다.
타입이 하나라도 어긋나면 골든 비교가 잡아냅니다.

### `/standings`

```
{count: int, source: str, teams: [
  {rank: int, team: str, code: str, games: str, wins: str, losses: str,
   draws: str, pct: str, gb: str, last10: str, streak: str}
]}
```

`rank` 만 정수이고 나머지 수치는 **문자열**입니다. 원본이 `int(cells[0])` 만 하고
나머지는 파싱한 문자열 그대로 넣기 때문입니다.

### `/schedule`

```
{date: str, count: int, games: [...], error?: str}
```

`error` 는 실패했을 때만 붙습니다. **`games` 안쪽 구조는 아래 주의 사항을 보십시오.**

### `/schedule/futures`

```
{date: str, count: int, source: str, games: [
  {gameId: str, seriesId: int, series: str, stadium: str, time: str,
   status: str, statusInfo: str, currentInning: str,
   currentPitcher: str, currentBatter: str,
   home: {code: str, name: str, division: str, score: int|null},
   away: {code: str, name: str, division: str, score: int|null},
   decisions: {win: str, lose: str, save: str},
   final: bool, live: bool, cancel: bool, showScore: bool, winner: str}
]}
```

`score` 는 경기 전이면 `null` 입니다. `0` 이 아닙니다. 원본 `_futures_int` 가
변환 실패 시 `None` 을 돌려주기 때문입니다. 여기를 `0` 으로 만들면 "0:0 으로 지고
있는 경기" 처럼 보입니다.

### `/players/:id/news`

```
{player_name: str, news: [
  {title: str, link: str, press: str, desc: str, thumb: null}
], error?: str}
```

`desc` 는 항상 빈 문자열, `thumb` 은 항상 `null` 입니다. 원본이 고정값으로
채웁니다. 빼면 안 됩니다.

### `/leaders`

```
{season: int, qual_pa: int, qual_ip: int, wrc_pf_season: int,
 batter: {avg: [], obp: [], slg: [], ops: [], woba: [], wrc: []},
 pitcher: {ip: [], k: [], era: [], kpct: [], bbpct: [], kbb: []}}
```

각 배열의 원소는 모두 같은 모양입니다.

```
{player_id: str, name: str, team: str, code: str, value: str}
```

**`value` 는 문자열입니다.** 숫자가 아닙니다. 원본이 `"%.3f" % val` 로 만들고,
값이 없으면 `"-"` 를 넣습니다. 여기를 숫자로 내보내면 골든 비교가 전부 실패합니다.

데이터가 없는 시즌(`?season=1990`)이면 12개 배열이 **모두 빈 배열**이고 상위
네 개 정수 필드는 그대로 있습니다. 키를 빼거나 `null` 로 두면 안 됩니다.

---

## 선행 조건: 정답지 수정

**이 계획을 시작하기 전에 `/schedule` 정답지를 다시 떠야 합니다.**

계획 A 의 `migration/golden_matrix.py` 가 `/schedule` 에 `date=20250401` 을
보냈습니다. 그런데 이 엔드포인트는 `YYYY-MM-DD` 를 기대하고, 그 값을 그대로
네이버에 넘깁니다(`api/main.py:1190-1193`). 네이버가 400 을 돌려주어 정답지의
`games` 가 빈 배열로 굳었습니다.

정답지가 비어 있으면 이식본도 비어 있을 때 "일치" 로 통과합니다. 검증이 되지
않습니다. `_kbo_normalize_game` 이 만드는 필드 20여 개가 전혀 대조되지 않은 채
넘어갑니다.

Task 0 에서 이것부터 고칩니다.

---

## Task 0: /schedule 정답지 교정

**Files:**
- Modify: `migration/golden_matrix.py`
- Modify: `tests/test_golden_matrix.py`
- Regenerate: `migration/golden/expected/schedule*.json`

- [ ] **Step 1: 날짜 형식을 요구하는 테스트를 추가합니다**

`tests/test_golden_matrix.py` 에 더합니다.

```python
def test_schedule_uses_hyphenated_date():
    """/schedule 은 YYYY-MM-DD 를 기대합니다.

    api/main.py:1190-1193 이 date 를 그대로 네이버에 넘기므로, YYYYMMDD 로
    보내면 400 이 돌아와 정답지가 빈 배열로 굳습니다.
    """
    matrix = build_matrix(_conn())
    dates = [i["params"]["date"] for i in matrix
             if i["path"] == "/schedule" and "date" in i["params"]]
    assert dates, "날짜를 지정한 /schedule 요청이 있어야 합니다"
    for d in dates:
        assert len(d) == 10 and d.count("-") == 2, d


def test_futures_uses_hyphenated_date():
    """/schedule/futures 도 같은 형식을 받습니다."""
    matrix = build_matrix(_conn())
    dates = [i["params"]["date"] for i in matrix
             if i["path"] == "/schedule/futures" and "date" in i["params"]]
    assert dates
    for d in dates:
        assert len(d) == 10 and d.count("-") == 2, d
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_matrix.py -k date -v
```

기대: 두 개 모두 실패합니다.

- [ ] **Step 3: 매트릭스를 고칩니다**

`migration/golden_matrix.py` 의 마지막 부분을 바꿉니다.

```python
    # 날짜 지정 일정.
    # /schedule 은 date 를 그대로 네이버에 넘기므로 YYYY-MM-DD 여야 합니다.
    # YYYYMMDD 로 보내면 400 이 돌아와 games 가 빈 배열이 되고, 정답지로서
    # 값을 잃습니다.
    game_day = "%d-04-01" % season
    _add(matrix, "/schedule", {"date": game_day})
    _add(matrix, "/schedule/futures", {"date": game_day})
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
py -m pytest tests/test_golden_matrix.py -v
```

기대: 13개 모두 pass

- [ ] **Step 5: 로컬 API 를 띄우고 정답지를 다시 뜹니다**

```powershell
py -m uvicorn api.main:app --host 127.0.0.1 --port 8199
```

다른 창에서:

```powershell
py migration/golden_capture.py --base-url http://127.0.0.1:8199 --out migration/golden/expected
```

- [ ] **Step 6: games 가 실제로 채워졌는지 확인합니다**

```powershell
py -c "
import json, pathlib
for f in sorted(pathlib.Path('migration/golden/expected').glob('schedule*.json')):
    d = json.loads(f.read_text(encoding='utf-8'))
    b = d.get('body', {})
    print('%-42s count=%s error=%s' % (f.name, b.get('count'), b.get('error', '')[:60]))
"
```

기대: 날짜를 지정한 `/schedule` 의 `count` 가 0 보다 크고 `error` 가 없습니다.

**여전히 비어 있다면**: 그 날짜에 경기가 없었을 수 있습니다. 2025 시즌 정규시즌
경기가 있던 날로 바꾸십시오. 로컬 DB 에서 고를 수 있습니다.

```powershell
py -c "import sqlite3;c=sqlite3.connect('database/kbo_stats.db');print(c.execute('SELECT game_date, COUNT(*) FROM games GROUP BY game_date ORDER BY COUNT(*) DESC LIMIT 3').fetchall())"
```

네이버 API 가 과거 시즌을 안 주는 경우에는 오늘 날짜로 뜨십시오. 그 경우
`/schedule` 은 라이브 응답이라 구조 비교만 받게 되며, 그것이 정상입니다.

- [ ] **Step 7: 백업을 갱신하고 커밋합니다**

```powershell
Compress-Archive -Path migration\golden\expected\* -DestinationPath migration\golden\expected_backup.zip -Force
git add migration/golden_matrix.py tests/test_golden_matrix.py
git commit -m "fix(golden): /schedule 정답지가 잘못된 날짜 형식으로 비어 있던 문제"
```

---

## File Structure

| 파일 | 책임 |
|---|---|
| `package.json` | 수정. `wrangler` 의존성과 `dev`/`test`/`deploy` 스크립트 |
| `wrangler.toml` | 수정. `main = "src/index.js"` 추가 |
| `src/index.js` | 진입점. 요청을 라우터에 넘기고 예외를 잡습니다 |
| `src/lib/router.js` | 경로 패턴 매칭. `/players/:id/news` 같은 자리표시자를 처리합니다 |
| `src/lib/respond.js` | JSON 응답 생성. FastAPI 와 같은 헤더·본문 형태를 냅니다 |
| `src/lib/cache.js` | TTL 메모리 캐시. 원본의 `_SCHEDULE_CACHE` 등을 대신합니다 |
| `src/lib/html.js` | HTML 엔티티 디코드와 태그 제거. `/standings` 파싱용 |
| `src/lib/kst.js` | KST 오늘 날짜 계산. 원본이 UTC+9 로 하는 것을 그대로 옮깁니다 |
| `src/routes/standings.js` | `/standings` |
| `src/routes/schedule.js` | `/schedule` |
| `src/routes/futures.js` | `/schedule/futures` |
| `src/routes/news.js` | `/players/:id/news` |
| `src/routes/leaders.js` | `/leaders` |
| `test/router.test.js` | 라우터 단위 테스트 |
| `test/html.test.js` | HTML 유틸 단위 테스트 |
| `test/kst.test.js` | KST 날짜 단위 테스트 |
| `test/standings_parse.test.js` | 순위표 파싱 단위 테스트 |
| `test/leaders_calc.test.js` | wOBA·wRC+ 계산 단위 테스트 |
| `migration/probe_external.py` | Worker 를 통해 외부 도메인 도달을 판정 |

엔드포인트 하나에 파일 하나입니다. 계획 B2 에서 24개가 더 붙어도 파일마다 책임이 하나로 유지됩니다.

---

## Task 1: Workers 뼈대와 라우터

**Files:**
- Modify: `wrangler.toml`
- Modify: `package.json`
- Create: `src/index.js`
- Create: `src/lib/router.js`
- Create: `src/lib/respond.js`
- Create: `test/router.test.js`

**Interfaces:**
- Consumes: 계획 A 의 `wrangler.toml` D1 바인딩(`DB`, database_id `505c67f5-45ff-42ee-bce9-2f5f00cf90e7`)
- Produces:
  - `createRouter() -> {add(method, pattern, handler), handle(request, env, ctx)}` — `add` 의 `pattern` 은 `/players/:id/news` 형태입니다. 매칭되면 핸들러를 `(request, env, ctx, params)` 로 부릅니다.
  - `matchPath(pattern, pathname) -> object | null` — 매칭 결과 파라미터 객체, 안 맞으면 `null`
  - `json(data, status = 200) -> Response` — `application/json; charset=utf-8` 로 직렬화
  - `queryInt(url, name, fallback) -> number`, `queryStr(url, name, fallback) -> string` — 쿼리 파라미터 파서

- [ ] **Step 1: 실패하는 테스트를 작성합니다**

`test/router.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { matchPath, queryInt, queryStr } from '../src/lib/router.js';

test('고정 경로가 매칭됩니다', () => {
  assert.deepEqual(matchPath('/standings', '/standings'), {});
});

test('경로가 다르면 null 입니다', () => {
  assert.equal(matchPath('/standings', '/schedule'), null);
});

test('자리표시자를 값으로 뽑습니다', () => {
  assert.deepEqual(
    matchPath('/players/:id/news', '/players/50030/news'),
    { id: '50030' },
  );
});

test('자리표시자 개수가 다르면 매칭되지 않습니다', () => {
  assert.equal(matchPath('/players/:id/news', '/players/50030'), null);
});

test('경로 값의 퍼센트 인코딩을 풉니다', () => {
  assert.deepEqual(matchPath('/logo/:code', '/logo/%EB%91%90%EC%82%B0'),
                   { code: '두산' });
});

test('더 긴 경로가 자리표시자에 통째로 들어가지 않습니다', () => {
  // '/db/table/:name' 이 '/db/table/x/csv' 를 먹으면 CSV 라우트가 죽습니다.
  assert.equal(matchPath('/db/table/:name', '/db/table/players/csv'), null);
});

test('queryInt 는 없으면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y');
  assert.equal(queryInt(url, 'season', 2025), 2025);
});

test('queryInt 는 숫자가 아니면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y?season=abc');
  assert.equal(queryInt(url, 'season', 2025), 2025);
});

test('queryInt 는 값을 정수로 바꿉니다', () => {
  const url = new URL('https://x/y?season=2019');
  assert.equal(queryInt(url, 'season', 2025), 2019);
});

test('queryStr 은 빈 문자열을 그대로 돌려줍니다', () => {
  // 원본의 /wrc/batter-search 는 q="" 를 기본값으로 씁니다. 빈 값과 없는 값이 다릅니다.
  const url = new URL('https://x/y?q=');
  assert.equal(queryStr(url, 'q', 'FALLBACK'), '');
});

test('queryStr 은 없으면 기본값을 돌려줍니다', () => {
  const url = new URL('https://x/y');
  assert.equal(queryStr(url, 'q', 'FALLBACK'), 'FALLBACK');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/router.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 3: 라우터를 작성합니다**

`src/lib/router.js` 를 만듭니다.

```javascript
// 경로 매칭과 쿼리 파라미터 파서.
//
// 외부 라우팅 라이브러리를 쓰지 않습니다. 필요한 패턴이 `/a/b` 와 `/a/:id/b`
// 두 가지뿐이라, 의존성을 하나 늘릴 이유가 없습니다.

/**
 * 패턴과 경로를 맞춰 보고 파라미터 객체를 돌려줍니다. 안 맞으면 null 입니다.
 * 세그먼트 개수가 같아야 매칭됩니다. 그래야 `/db/table/:name` 이
 * `/db/table/players/csv` 를 잘못 먹지 않습니다.
 */
export function matchPath(pattern, pathname) {
  const p = pattern.split('/');
  const s = pathname.split('/');
  if (p.length !== s.length) return null;

  const params = {};
  for (let i = 0; i < p.length; i += 1) {
    if (p[i].startsWith(':')) {
      if (s[i] === '') return null;
      try {
        params[p[i].slice(1)] = decodeURIComponent(s[i]);
      } catch {
        params[p[i].slice(1)] = s[i];
      }
    } else if (p[i] !== s[i]) {
      return null;
    }
  }
  return params;
}

export function queryInt(url, name, fallback) {
  const raw = url.searchParams.get(name);
  if (raw === null || raw === '') return fallback;
  const n = Number.parseInt(raw, 10);
  return Number.isNaN(n) ? fallback : n;
}

export function queryStr(url, name, fallback) {
  const raw = url.searchParams.get(name);
  return raw === null ? fallback : raw;
}

export function createRouter() {
  const routes = [];
  return {
    add(method, pattern, handler) {
      routes.push({ method, pattern, handler });
      return this;
    },
    async handle(request, env, ctx) {
      const url = new URL(request.url);
      // 끝의 슬래시를 떼어 `/teams/` 와 `/teams` 를 같게 봅니다.
      const pathname = url.pathname.length > 1
        ? url.pathname.replace(/\/+$/, '')
        : url.pathname;

      let pathMatched = false;
      for (const r of routes) {
        const params = matchPath(r.pattern, pathname);
        if (params === null) continue;
        pathMatched = true;
        if (r.method !== request.method) continue;
        return r.handler(request, env, ctx, params);
      }
      // 경로는 있는데 메서드가 다르면 405, 경로 자체가 없으면 404.
      // FastAPI 가 그렇게 동작하므로 맞춥니다.
      return unmatched(pathMatched);
    },
  };
}

function unmatched(pathMatched) {
  const detail = pathMatched ? 'Method Not Allowed' : 'Not Found';
  return new Response(JSON.stringify({ detail }), {
    status: pathMatched ? 405 : 404,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      'access-control-allow-origin': '*',
    },
  });
}
```

- [ ] **Step 4: 응답 헬퍼를 작성합니다**

`src/lib/respond.js` 를 만듭니다.

```javascript
// FastAPI 와 같은 형태의 JSON 응답을 만듭니다.
//
// 골든 비교가 본문을 바이트가 아니라 파싱된 값으로 대조하므로 키 순서는
// 상관없습니다. 다만 content-type 이 다르면 requests 가 .json() 을 실패해
// 비교 자체가 어긋나므로 charset 까지 맞춥니다.

export function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'content-type': 'application/json; charset=utf-8',
      // 원본 api/main.py 의 CORSMiddleware(allow_origins=["*"]) 와 같게 둡니다.
      'access-control-allow-origin': '*',
    },
  });
}

/**
 * 원본은 최상위 예외 핸들러가 500 과 함께 detail 을 돌려줍니다.
 * 다만 외부 연동 엔드포인트들은 자체 try/except 로 200 + error 필드를
 * 내보냅니다. 그 차이를 그대로 유지해야 골든 비교가 통과합니다.
 */
export function serverError(err) {
  return json({ detail: String(err && err.message ? err.message : err) }, 500);
}
```

- [ ] **Step 5: 진입점을 작성합니다**

`src/index.js` 를 만듭니다.

```javascript
import { createRouter } from './lib/router.js';
import { json, serverError } from './lib/respond.js';

const router = createRouter();

// 원본 api/main.py:78-80 의 루트 응답입니다. 문구를 바꾸지 마십시오.
router.add('GET', '/', () => json({
  message: 'KBO Baseball Analytics API Active',
  version: '1.0.7',
}));

export default {
  async fetch(request, env, ctx) {
    try {
      const res = await router.handle(request, env, ctx);
      return res;
    } catch (err) {
      return serverError(err);
    }
  },
};
```

- [ ] **Step 6: 루트 응답이 정답지와 같은지 확인합니다**

```powershell
Get-Content migration\golden\expected\root.json -Raw
```

기대: `{"status": 200, "body": {"message": "KBO Baseball Analytics API Active", "version": "1.0.7"}}`
다르면 정답지를 따르십시오. 정답지가 실제 동작이고 이 계획의 코드는 옮겨 적은 것입니다.

- [ ] **Step 7: wrangler.toml 에 진입점을 추가합니다**

```toml
name = "kbo-api"
main = "src/index.js"
compatibility_date = "2026-08-17"

[[d1_databases]]
binding = "DB"
database_name = "kbo-stats"
database_id = "505c67f5-45ff-42ee-bce9-2f5f00cf90e7"
```

- [ ] **Step 8: package.json 에 스크립트를 추가합니다**

기존 내용을 지우지 말고 `scripts` 만 더합니다.

```json
{
  "scripts": {
    "dev": "wrangler dev --remote --port 8787",
    "test": "node --test test/",
    "deploy": "wrangler deploy"
  }
}
```

- [ ] **Step 9: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/router.test.js
```

기대: 11개 모두 pass

- [ ] **Step 10: Worker 를 띄워 왕복을 확인합니다**

```powershell
npx wrangler dev --remote --port 8787
```

다른 창에서:

```powershell
curl.exe http://127.0.0.1:8787/
curl.exe -i http://127.0.0.1:8787/없는경로
```

기대: 첫 번째는 루트 JSON, 두 번째는 404 와 `{"detail":"Not Found"}`.

`--remote` 를 쓰는 이유는 D1 원격 데이터를 보기 위해서입니다. `--local` 은 빈 로컬 D1 을 만들어 응답이 전부 0건이 됩니다.

- [ ] **Step 11: 커밋합니다**

```powershell
git add wrangler.toml package.json src/ test/
git commit -m "feat(workers): 라우터와 응답 헬퍼로 Worker 뼈대 구축"
```

---

## Task 2: 외부 도달 판정 (위험 2)

**Files:**
- Modify: `src/index.js`
- Create: `migration/probe_external.py`

**Interfaces:**
- Consumes: Task 1 의 라우터
- Produces: 위험 2 의 판정 결과. `/probe/external` 이 도메인별 도달 여부를 JSON 으로 돌려줍니다.

설계 문서 §7 위험 2 를 판정합니다. **이 계획에서 가장 먼저 답을 얻어야 하는 항목입니다.** 여기서 막히면 뒤 태스크의 이식 방식이 달라집니다.

판정 대상은 세 도메인입니다. 설계 문서는 "네이버" 하나로 적었지만 실제로는 셋입니다.

| 도메인 | 쓰는 곳 | 형식 |
|---|---|---|
| `api-gw.sports.naver.com` | `/schedule` | JSON GET |
| `www.koreabaseball.com` | `/schedule/futures`, `/standings` | HTML GET, JSON POST |
| `news.google.com` | `/players/:id/news` | RSS XML GET |

- [ ] **Step 1: 판정 엔드포인트를 추가합니다**

`src/index.js` 에 라우트를 하나 더합니다. 판정이 끝나면 Task 8 에서 제거합니다.

```javascript
// 위험 2 판정용 임시 엔드포인트입니다. Task 8 에서 제거합니다.
router.add('GET', '/probe/external', async () => {
  const targets = [
    {
      name: 'naver',
      url: 'https://api-gw.sports.naver.com/schedule/calendar'
         + '?upperCategoryId=kbaseball&categoryIds=kbo&date=2026-08-17',
      method: 'GET',
    },
    {
      name: 'kbo_html',
      url: 'https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx',
      method: 'GET',
    },
    {
      name: 'kbo_json',
      url: 'https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList',
      method: 'POST',
      body: 'leId=2&srId=0,9,10&date=20260817',
      headers: {
        'content-type': 'application/x-www-form-urlencoded',
        'referer': 'https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx',
        'x-requested-with': 'XMLHttpRequest',
      },
    },
    {
      name: 'google_news',
      url: 'https://news.google.com/rss/search'
         + '?q=%EC%95%BC%EA%B5%AC&hl=ko&gl=KR&ceid=KR:ko',
      method: 'GET',
    },
  ];

  const results = [];
  for (const t of targets) {
    const started = Date.now();
    try {
      const res = await fetch(t.url, {
        method: t.method,
        body: t.body,
        headers: { 'user-agent': 'Mozilla/5.0', ...(t.headers || {}) },
      });
      const text = await res.text();
      results.push({
        name: t.name,
        status: res.status,
        length: text.length,
        ms: Date.now() - started,
        head: text.slice(0, 160).replace(/\s+/g, ' '),
      });
    } catch (err) {
      results.push({
        name: t.name,
        status: 0,
        error: String(err && err.message ? err.message : err),
        ms: Date.now() - started,
      });
    }
  }
  return json({ results });
});
```

- [ ] **Step 2: 로컬 dev 로 먼저 확인합니다**

```powershell
npx wrangler dev --remote --port 8787
```

다른 창에서:

```powershell
curl.exe http://127.0.0.1:8787/probe/external
```

`--remote` 이므로 요청이 실제 Cloudflare 엣지에서 나갑니다. 로컬 PC 의 한국 IP 가 아닙니다. 이게 판정의 핵심입니다.

- [ ] **Step 3: 배포해서 다시 확인합니다**

dev 와 배포본이 다른 엣지를 탈 수 있으므로 둘 다 봅니다.

```powershell
npx wrangler deploy
```

출력에 나온 `https://kbo-api.<계정>.workers.dev` 주소로 요청합니다.

```powershell
curl.exe https://kbo-api.<계정>.workers.dev/probe/external
```

- [ ] **Step 4: 판정 스크립트를 작성합니다**

`migration/probe_external.py` 를 만듭니다. 눈으로 보는 대신 판정을 코드로 굳혀 둡니다. 나중에 다시 확인할 때 같은 기준을 씁니다.

```python
# -*- coding: utf-8 -*-
"""배포된 Worker 를 통해 외부 도메인 도달 여부를 판정합니다.

설계 문서 §7 위험 2 를 가르는 프로브입니다. 로컬 PC 에서 직접 부르면
한국 IP 라 늘 성공하므로, 반드시 Worker 를 거쳐 확인해야 합니다.
"""
import argparse
import json
import sys
import urllib.request

# 도메인별 최소 기대치입니다. 차단 페이지가 200 으로 오는 경우를 거릅니다.
EXPECT = {
    "naver": {"min_length": 200, "must_contain": "result"},
    "kbo_html": {"min_length": 20000, "must_contain": "__VIEWSTATE"},
    "kbo_json": {"min_length": 20, "must_contain": "game"},
    "google_news": {"min_length": 500, "must_contain": "<rss"},
}


def judge(row):
    """(통과 여부, 사유) 를 돌려줍니다."""
    rule = EXPECT.get(row["name"])
    if rule is None:
        return False, "판정 기준이 없습니다"
    if row.get("status") != 200:
        return False, "HTTP %s %s" % (row.get("status"), row.get("error", ""))
    if row.get("length", 0) < rule["min_length"]:
        return False, "본문이 %d자로 너무 짧습니다" % row.get("length", 0)
    if rule["must_contain"] not in row.get("head", ""):
        # head 는 앞 160자뿐이라 없을 수 있습니다. 길이가 충분하면 통과로 봅니다.
        if row.get("length", 0) >= rule["min_length"] * 2:
            return True, "본문 %d자 (표지 문자열은 앞부분에 없음)" % row["length"]
        return False, "기대 문자열 %r 이 없습니다" % rule["must_contain"]
    return True, "본문 %d자" % row["length"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("base_url", help="예: https://kbo-api.xxx.workers.dev")
    args = ap.parse_args()

    url = args.base_url.rstrip("/") + "/probe/external"
    with urllib.request.urlopen(url, timeout=60) as r:
        data = json.loads(r.read().decode("utf-8"))

    print("%-14s %-6s %8s %7s  %s" % ("도메인", "판정", "상태", "소요", "사유"))
    print("-" * 78)
    failed = []
    for row in data["results"]:
        ok, why = judge(row)
        if not ok:
            failed.append(row["name"])
        print("%-14s %-6s %8s %6dms  %s" % (
            row["name"], "통과" if ok else "실패",
            row.get("status"), row.get("ms", 0), why))

    print()
    if failed:
        print("차단 의심 %d곳: %s" % (len(failed), ", ".join(failed)))
        print("설계 문서 §7 위험 2 의 대응을 검토하십시오.")
        return 1
    print("네 곳 모두 도달합니다. 위험 2 해소.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: 판정을 실행합니다**

```powershell
py migration/probe_external.py https://kbo-api.<계정>.workers.dev
```

- [ ] **Step 6: 결과에 따라 갈립니다**

| 결과 | 판정 | 다음 |
|---|---|---|
| 네 곳 모두 통과 | 위험 2 해소 | Task 3 으로 그대로 진행합니다 |
| `naver` 만 실패 | `/schedule` 만 영향 | 1군 실시간 경기 화면을 잃습니다. `/schedule/futures` 로 퓨처스는 남습니다 |
| `kbo_html` / `kbo_json` 실패 | `/standings`, `/schedule/futures` 영향 | 두 응답을 **GitHub Actions 가 미리 만들어 R2 에 올리고** Worker 가 R2 를 읽는 구조로 바꿉니다. 순위는 5분, 퓨처스는 30초 캐시라 신선도가 떨어지지만 기능은 남습니다 |
| `google_news` 실패 | `/players/:id/news` 영향 | 뉴스 목록을 비웁니다. 원본도 실패 시 빈 배열을 돌려주므로 화면은 깨지지 않습니다 |

**R2 우회가 왜 KBO 에만 통하는가**: `/standings` 와 `/schedule/futures` 는 전체 사용자에게 같은 내용입니다. 미리 만들어 두고 나눠 줘도 됩니다. `/players/:id/news` 는 선수마다 다르고 `/schedule` 은 날짜마다 달라 미리 만들기 어렵습니다.

- [ ] **Step 7: 판정 결과를 설계 문서에 기록합니다**

`docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md` 의 §7 위험 2 끝에 아래 형식으로 넣습니다. 대괄호는 실제 값으로 채웁니다.

```markdown
#### 판정 (2026-MM-DD)

배포된 Worker(`/probe/external`)에서 확인했습니다.

| 도메인 | 결과 | 실측 |
|---|---|---|
| `api-gw.sports.naver.com` | [통과/차단] | HTTP [상태], 본문 [N]자, [N]ms |
| `www.koreabaseball.com` (HTML) | [통과/차단] | HTTP [상태], 본문 [N]자, [N]ms |
| `www.koreabaseball.com` (POST) | [통과/차단] | HTTP [상태], 본문 [N]자, [N]ms |
| `news.google.com` | [통과/차단] | HTTP [상태], 본문 [N]자, [N]ms |

**대응**: [사유를 한 문장으로]
```

- [ ] **Step 8: 커밋합니다**

```powershell
git add src/index.js migration/probe_external.py docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md
git commit -m "feat(workers): 외부 도달 판정 엔드포인트 추가와 위험 2 판정"
```

---

## Task 3: /standings 이식

**Files:**
- Create: `src/lib/html.js`
- Create: `src/lib/cache.js`
- Create: `src/routes/standings.js`
- Modify: `src/index.js`
- Create: `test/html.test.js`
- Create: `test/standings_parse.test.js`

**Interfaces:**
- Consumes: Task 1 의 `json`, 라우터
- Produces:
  - `stripTags(html) -> string` — 태그를 지우고 엔티티를 풉니다
  - `decodeEntities(text) -> string` — `&amp;` `&nbsp;` `&#39;` `&#x27;` 형태를 풉니다
  - `ttlCache(ttlSeconds) -> {get(key), set(key, value)}` — 초 단위 TTL 캐시
  - `parseStandings(html) -> Array<object>` — 순위표 행 배열
  - `KBO_TEAM_CODE: Record<string,string>` — 팀명 → 코드. 다른 라우트도 씁니다

가장 먼저 옮기는 엔드포인트입니다. 외부 HTML 파싱, 캐시, 팀 코드 매핑이 다 들어 있어 뒤 태스크가 쓸 조각이 여기서 나옵니다.

**원본**: `api/main.py:1474-1520`. 파싱이 BeautifulSoup 이 아니라 **정규식**이라 JS 로 거의 그대로 옮겨집니다.

- [ ] **Step 1: HTML 유틸 테스트를 작성합니다**

`test/html.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { decodeEntities, stripTags } from '../src/lib/html.js';

test('이름 있는 엔티티를 풉니다', () => {
  assert.equal(decodeEntities('a&amp;b'), 'a&b');
  assert.equal(decodeEntities('&lt;tag&gt;'), '<tag>');
  assert.equal(decodeEntities('&quot;x&quot;'), '"x"');
});

test('nbsp 를 보통 공백으로 바꿉니다', () => {
  // KBO 순위표의 게임차 칸에 nbsp 가 들어갑니다. 그대로 두면
  // trim 이 먹지 않아 값이 어긋납니다.
  assert.equal(decodeEntities('a&nbsp;b'), 'a b');
});

test('십진 수치 참조를 풉니다', () => {
  assert.equal(decodeEntities('&#39;'), "'");
});

test('십육진 수치 참조를 풉니다', () => {
  assert.equal(decodeEntities('&#x27;'), "'");
});

test('엔티티가 없으면 원문 그대로입니다', () => {
  assert.equal(decodeEntities('평범한 문자열'), '평범한 문자열');
});

test('태그를 지웁니다', () => {
  assert.equal(stripTags('<td><a href="x">LG</a></td>'), 'LG');
});

test('태그를 지우면서 엔티티도 풉니다', () => {
  assert.equal(stripTags('<td>3&nbsp;.5</td>'), '3 .5');
});

test('속성 안의 부등호에 속지 않습니다', () => {
  assert.equal(stripTags('<td class="a>b">값</td>'), 'b">값');
});
```

마지막 테스트는 정규식 파싱의 한계를 명시적으로 남긴 것입니다. 원본 Python 도 `re.sub(r'<[^>]+>', '', c)` 라 똑같이 동작합니다. **원본과 같게 두는 것이 목적이므로 고치지 않습니다.**

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/html.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 3: HTML 유틸을 작성합니다**

`src/lib/html.js` 를 만듭니다.

```javascript
// HTML 엔티티 디코드와 태그 제거.
//
// 원본 api/main.py 는 `html.unescape` 와 `re.sub(r'<[^>]+>', '', c)` 를 씁니다.
// 동작을 같게 맞추는 것이 목적이라, 더 똑똑한 파서를 쓰지 않습니다.
// Workers 의 HTMLRewriter 는 스트리밍 변환용이라 문자열 추출에는 맞지 않습니다.

const NAMED = {
  amp: '&', lt: '<', gt: '>', quot: '"', apos: "'",
  nbsp: ' ', ensp: ' ', emsp: ' ', thinsp: ' ',
};

export function decodeEntities(text) {
  return String(text).replace(/&(#x?[0-9a-fA-F]+|[a-zA-Z]+);/g, (whole, body) => {
    if (body[0] === '#') {
      const hex = body[1] === 'x' || body[1] === 'X';
      const code = Number.parseInt(hex ? body.slice(2) : body.slice(1),
                                   hex ? 16 : 10);
      return Number.isNaN(code) ? whole : String.fromCodePoint(code);
    }
    const v = NAMED[body.toLowerCase()];
    return v === undefined ? whole : v;
  });
}

export function stripTags(html) {
  return decodeEntities(String(html).replace(/<[^>]+>/g, ''));
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/html.test.js
```

기대: 8개 모두 pass

- [ ] **Step 5: 순위표 파싱 테스트를 작성합니다**

`test/standings_parse.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { parseStandings } from '../src/routes/standings.js';

const PAGE = `
<html><body>
<table summary="팀간승패표 입니다">
  <tbody><tr><td>1</td><td>속임수</td><td>0</td><td>0</td>
  <td>0</td><td>0</td><td>0</td><td>0</td></tr></tbody>
</table>
<table summary="순위 입니다">
  <tbody>
    <tr>
      <td>1</td><td>LG</td><td>144</td><td>90</td><td>50</td><td>4</td>
      <td>0.643</td><td>-</td><td>7-3-0</td><td>2승</td>
    </tr>
    <tr>
      <td>2</td><td>한화</td><td>144</td><td>85</td><td>55</td><td>4</td>
      <td>0.607</td><td>5.0</td><td>5-5-0</td><td>1패</td>
    </tr>
    <tr><td colspan="10">합계 행처럼 숫자가 아닌 첫 칸</td></tr>
  </tbody>
</table>
</body></html>`;

test('순위표만 읽고 팀간승패표는 건너뜁니다', () => {
  const rows = parseStandings(PAGE);
  assert.equal(rows.length, 2);
  assert.equal(rows[0].team, 'LG');
  assert.equal(rows[1].team, '한화');
});

test('첫 칸이 숫자가 아닌 행은 버립니다', () => {
  const rows = parseStandings(PAGE);
  assert.ok(rows.every((r) => typeof r.rank === 'number'));
});

test('rank 는 정수이고 나머지 수치는 문자열입니다', () => {
  // 원본이 rank 만 int() 로 바꾸고 나머지는 문자열로 둡니다.
  // 여기서 타입이 어긋나면 골든 비교가 바로 잡아냅니다.
  const [first] = parseStandings(PAGE);
  assert.equal(first.rank, 1);
  assert.equal(first.games, '144');
  assert.equal(first.pct, '0.643');
  assert.equal(first.gb, '-');
});

test('팀 코드를 붙입니다', () => {
  const [first] = parseStandings(PAGE);
  assert.equal(first.code, 'LG');
});

test('모르는 팀명이면 코드는 빈 문자열입니다', () => {
  const page = PAGE.replace('<td>한화</td>', '<td>없는팀</td>');
  const rows = parseStandings(page);
  assert.equal(rows[1].code, '');
});

test('순위표가 없으면 빈 배열입니다', () => {
  assert.deepEqual(parseStandings('<html></html>'), []);
});

test('칸이 8개 미만인 행은 버립니다', () => {
  const page = `<table summary="순위">
    <tbody><tr><td>1</td><td>LG</td><td>144</td></tr></tbody></table>`;
  assert.deepEqual(parseStandings(page), []);
});

test('last10 과 streak 이 없으면 빈 문자열입니다', () => {
  const page = `<table summary="순위"><tbody><tr>
    <td>1</td><td>LG</td><td>144</td><td>90</td><td>50</td><td>4</td>
    <td>0.643</td><td>-</td></tr></tbody></table>`;
  const [first] = parseStandings(page);
  assert.equal(first.last10, '');
  assert.equal(first.streak, '');
});
```

- [ ] **Step 6: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/standings_parse.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 7: 캐시 유틸을 작성합니다**

`src/lib/cache.js` 를 만듭니다.

```javascript
// 초 단위 TTL 메모리 캐시.
//
// 원본의 _STANDINGS_CACHE / _SCHEDULE_CACHE 를 대신합니다.
//
// Workers 의 전역 변수는 isolate 가 살아 있는 동안만 유지됩니다. 언제 버려질지
// 보장이 없어 적중률은 원본보다 낮습니다. 그래도 두는 이유는, 같은 isolate 가
// 연속 요청을 받을 때 외부 사이트를 반복해서 때리지 않기 위함입니다.
// 정확성에는 영향이 없습니다. 캐시가 비면 그냥 다시 가져옵니다.

export function ttlCache(ttlSeconds) {
  const store = new Map();
  return {
    get(key) {
      const hit = store.get(key);
      if (!hit) return undefined;
      if (Date.now() - hit.at > ttlSeconds * 1000) {
        store.delete(key);
        return undefined;
      }
      return hit.value;
    },
    set(key, value) {
      store.set(key, { at: Date.now(), value });
      return value;
    },
  };
}
```

- [ ] **Step 8: /standings 를 작성합니다**

`src/routes/standings.js` 를 만듭니다. 원본 `api/main.py:1474-1520` 과 나란히 놓고 대조하며 씁니다.

```javascript
import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { stripTags } from '../lib/html.js';

// 원본 api/main.py:1399-1402 의 _KBO_TEAM_CODE 입니다.
// KBO 표기명 -> 대시보드 엠블럼 코드(assets/logos/{code}.png).
export const KBO_TEAM_CODE = {
  LG: 'LG', KT: 'KT', 두산: 'OB', 삼성: 'SS', KIA: 'HT',
  롯데: 'LT', SSG: 'SK', NC: 'NC', 키움: 'WO', 한화: 'HH',
};

// 역매핑. 원본 1406 행의 _KBO_CODE_TO_TEAM 입니다.
// /schedule 의 투수 이름을 players.player_id 로 맞출 때 팀을 좁히는 데 씁니다.
export const KBO_CODE_TO_TEAM = Object.fromEntries(
  Object.entries(KBO_TEAM_CODE).map(([team, code]) => [code, team]),
);

const cache = ttlCache(300); // 원본 _STANDINGS_TTL = 300

/**
 * TeamRank.aspx 의 순위표를 읽습니다.
 *
 * summary="순위..." 인 표만 봅니다. 같은 페이지에 summary="팀간승패표" 인
 * 표가 또 있어서, 그걸 같이 읽으면 행이 두 배가 됩니다.
 */
export function parseStandings(page) {
  const table = /<table[^>]*summary="순위[^"]*"[^>]*>([\s\S]*?)<\/table>/.exec(page);
  if (!table) return [];

  const tbody = /<tbody>([\s\S]*?)<\/tbody>/.exec(table[1]);
  const body = tbody ? tbody[1] : table[1];

  const teams = [];
  for (const tr of body.matchAll(/<tr[^>]*>([\s\S]*?)<\/tr>/g)) {
    const cells = [...tr[1].matchAll(/<td[^>]*>([\s\S]*?)<\/td>/g)]
      .map((m) => stripTags(m[1]).trim());
    // 원본 조건: len(cells) >= 8 and cells[0].isdigit()
    if (cells.length < 8) continue;
    if (!/^\d+$/.test(cells[0])) continue;

    const name = cells[1];
    teams.push({
      rank: Number.parseInt(cells[0], 10),
      team: name,
      code: KBO_TEAM_CODE[name] || '',
      games: cells[2],
      wins: cells[3],
      losses: cells[4],
      draws: cells[5],
      pct: cells[6],
      gb: cells[7],
      last10: cells.length > 8 ? cells[8] : '',
      streak: cells.length > 9 ? cells[9] : '',
    });
  }
  return teams;
}

export async function standings() {
  try {
    const hit = cache.get('rank');
    if (hit) return json(hit);

    const res = await fetch(
      'https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx',
      { headers: { 'user-agent': 'Mozilla/5.0' } },
    );
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const page = await res.text();

    const teams = parseStandings(page);
    const result = {
      count: teams.length,
      teams,
      source: 'koreabaseball.com',
    };
    // 원본도 teams 가 비면 캐시하지 않습니다. 일시 실패를 5분간 물고 있지
    // 않으려는 것입니다.
    if (teams.length) cache.set('rank', result);
    return json(result);
  } catch (err) {
    // 원본은 예외 시 200 과 함께 error 필드를 돌려줍니다. 500 이 아닙니다.
    return json({
      count: 0,
      teams: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
```

- [ ] **Step 9: 팀 코드 표가 원본과 같은지 대조합니다**

```powershell
py -c "import io;print(''.join(io.open('api/main.py',encoding='utf-8').readlines()[1398:1403]))"
```

기대: 위 코드의 `KBO_TEAM_CODE` 와 열 개 항목이 모두 일치합니다.
하나라도 다르면 로고가 깨지고 `/standings` 의 `code` 필드가 어긋납니다.

- [ ] **Step 10: 라우트를 등록합니다**

`src/index.js` 에 더합니다.

```javascript
import { standings } from './routes/standings.js';

router.add('GET', '/standings', standings);
```

- [ ] **Step 11: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/
```

기대: Task 1 의 11개 + html 8개 + standings 8개 = 27개 pass

- [ ] **Step 12: 실제 응답을 정답지와 비교합니다**

Worker 를 띄웁니다.

```powershell
npx wrangler dev --remote --port 8787
```

다른 창에서 `/standings` 하나만 떠서 비교합니다.

```powershell
py -c "
import json, urllib.request, pathlib
r = urllib.request.urlopen('http://127.0.0.1:8787/standings', timeout=60)
body = json.loads(r.read().decode('utf-8'))
out = pathlib.Path('migration/golden/actual')
out.mkdir(parents=True, exist_ok=True)
(out / 'standings.json').write_text(
    json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
               sort_keys=True, indent=2), encoding='utf-8')
print('저장했습니다')
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

기대: `일치 1건 (그중 라이브 구조 비교 1건)`

`/standings` 는 라이브 응답이라 값이 아니라 **구조**로 비교됩니다. 순위는 시시각각 바뀌므로 값 일치를 요구할 수 없습니다. 구조가 어긋나면(키 이름이 다르거나 `rank` 가 문자열로 나오거나) 여기서 잡힙니다.

- [ ] **Step 13: 커밋합니다**

```powershell
git add src/lib/html.js src/lib/cache.js src/routes/standings.js src/index.js test/
git commit -m "feat(workers): /standings 이식"
```

---

## Task 4: /schedule 이식

**Files:**
- Create: `src/lib/kst.js`
- Create: `src/routes/schedule.js`
- Modify: `src/index.js`
- Create: `test/kst.test.js`

**Interfaces:**
- Consumes: Task 3 의 `ttlCache`, `KBO_TEAM_CODE`
- Produces:
  - `kstToday() -> string` — `YYYY-MM-DD` 형태의 KST 오늘
  - `schedule(request, env)` — `/schedule` 핸들러

**원본**: `api/main.py:1177-1227` 과 헬퍼 `1091-1176`.

원본은 `ThreadPoolExecutor(max_workers=8)` 로 경기 상세를 병렬로 가져옵니다. Workers 에서는 `Promise.all` 을 씁니다. **CPU 10ms 한도는 CPU 시간이라 fetch 대기는 세지 않습니다.** 경기 5개 + 종료 경기 보강 5개 = 최대 11번의 subrequest 이고, 무료 한도가 요청당 50개라 여유가 있습니다.

- [ ] **Step 1: KST 테스트를 작성합니다**

`test/kst.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { kstDateOf, kstToday } from '../src/lib/kst.js';

test('UTC 를 9시간 밀어 KST 날짜를 만듭니다', () => {
  // 2026-08-17T00:30Z 는 KST 로 같은 날 09:30 입니다.
  assert.equal(kstDateOf(Date.UTC(2026, 7, 17, 0, 30)), '2026-08-17');
});

test('UTC 자정 직전은 KST 로 다음 날입니다', () => {
  // 2026-08-17T15:30Z 는 KST 2026-08-18 00:30 입니다.
  assert.equal(kstDateOf(Date.UTC(2026, 7, 17, 15, 30)), '2026-08-18');
});

test('월말을 넘깁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 7, 31, 16, 0)), '2026-09-01');
});

test('연말을 넘깁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 11, 31, 16, 0)), '2027-01-01');
});

test('한 자리 월과 일을 0 으로 채웁니다', () => {
  assert.equal(kstDateOf(Date.UTC(2026, 0, 5, 0, 0)), '2026-01-05');
});

test('kstToday 는 YYYY-MM-DD 형태입니다', () => {
  assert.match(kstToday(), /^\d{4}-\d{2}-\d{2}$/);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/kst.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 3: KST 유틸을 작성합니다**

`src/lib/kst.js` 를 만듭니다.

```javascript
// KST 날짜 계산.
//
// 원본은 `datetime.utcnow() + timedelta(hours=9)` 로 구합니다. 서머타임이
// 없는 고정 오프셋이라 이렇게 해도 맞습니다. 같은 방식으로 옮깁니다.
// Intl.DateTimeFormat 을 쓰면 더 정확해 보이지만, 원본과 결과가 달라질
// 여지를 만들 이유가 없습니다.

const KST_OFFSET_MS = 9 * 60 * 60 * 1000;

export function kstDateOf(epochMs) {
  const d = new Date(epochMs + KST_OFFSET_MS);
  const y = d.getUTCFullYear();
  const m = String(d.getUTCMonth() + 1).padStart(2, '0');
  const day = String(d.getUTCDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export function kstToday() {
  return kstDateOf(Date.now());
}
```

- [ ] **Step 4: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/kst.test.js
```

기대: 6개 모두 pass

- [ ] **Step 5: 원본의 네이버 응답 정규화 로직을 읽습니다**

`/schedule` 본체를 쓰기 전에 헬퍼 네 개를 정확히 파악해야 합니다. 추측해서 쓰면 필드가 어긋납니다.

```powershell
py -c "import io;print(''.join(io.open('api/main.py',encoding='utf-8').readlines()[1090:1177]))"
```

읽어야 할 것:

| 헬퍼 | 원본 행 | 하는 일 |
|---|---|---|
| `_kbo_fetch_json` | 1091-1096 | User-Agent 붙여 GET 후 JSON 파싱 |
| `_kbo_game_meta` | 1097-1103 | 경기 하나의 상세 |
| `_kbo_normalize_game` | 1104-1152 | 네이버 응답을 화면용 형태로 변환. **필드 이름이 여기서 정해집니다** |
| `_kbo_game_decisions` | 1153-1176 | 종료 경기의 승/패/세이브 투수 |

`_attach_pitcher_ids`(1446-1473)도 봅니다. 투수 이름을 `players` 테이블의 `player_id` 로 바꿔 붙이는데, **D1 쿼리가 들어가는 부분**이라 Workers 에서 형태가 달라집니다.

- [ ] **Step 6: /schedule 을 작성합니다**

`src/routes/schedule.js` 를 만듭니다. 아래는 뼈대이고, 표시한 자리에 Step 5 에서 읽은 내용을 옮깁니다.

```javascript
import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { kstToday } from '../lib/kst.js';

const cache = ttlCache(30); // 원본 _SCHEDULE_TTL = 30

const NAVER = 'https://api-gw.sports.naver.com';

async function fetchJson(url) {
  const res = await fetch(url, { headers: { 'user-agent': 'Mozilla/5.0' } });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function gameMeta(gameId) {
  return fetchJson(`${NAVER}/schedule/games/${gameId}`);
}

function gameDecisions(gameId) {
  return fetchJson(`${NAVER}/schedule/games/${gameId}/record`)
    .then((data) => {
      // 원본 _kbo_game_decisions(api/main.py:1153-1176) 를 그대로 옮깁니다.
      throw new Error('구현 필요: 원본 1153-1176 참조');
    })
    .catch(() => null); // 원본도 실패 시 조용히 넘어갑니다
}

function normalizeGame(meta) {
  // 원본 _kbo_normalize_game(api/main.py:1104-1152) 를 그대로 옮깁니다.
  // 여기서 응답 필드 이름이 정해지므로 한 글자도 바꾸지 마십시오.
  //
  // 필드 구성은 위 "응답 계약" 절의 /schedule/futures 항목과 거의 같습니다.
  // 두 엔드포인트가 같은 화면을 채우기 때문입니다. 다만 출처가 네이버라
  // 세부가 다를 수 있으니, Task 0 으로 다시 뜬 정답지를 열어 실제 키를
  // 확인하십시오.
  //
  //   py -c "import json;d=json.load(open('migration/golden/expected/schedule_date_2025_04_01.json',encoding='utf-8'));print(json.dumps(d['body']['games'][0],ensure_ascii=False,indent=2))"
  //
  throw new Error('구현 필요: 원본 1104-1152 참조');
}

async function attachPitcherIds(db, games) {
  // 원본 _attach_pitcher_ids(api/main.py:1446-1473) 를 옮깁니다.
  // 원본은 요청마다 players 를 조회합니다. D1 은 호출당 쿼리 50개 한도가
  // 있으므로, 이름 목록을 모아 IN 절 한 번으로 끝냅니다.
  throw new Error('구현 필요: 원본 1446-1473 참조');
}

export async function schedule(request, env) {
  const url = new URL(request.url);
  let date = url.searchParams.get('date');
  try {
    if (!date) date = kstToday();
    const target = date.replaceAll('-', '');

    const hit = cache.get(date);
    if (hit) return json(hit);

    const cal = await fetchJson(
      `${NAVER}/schedule/calendar`
      + `?upperCategoryId=kbaseball&categoryIds=kbo&date=${date}`,
    );

    const gids = [];
    for (const d of cal?.result?.dates || []) {
      const dkey = String(d.ymd ?? d.date ?? '').replaceAll('-', '');
      if (dkey === target) {
        for (const gi of d.gameInfos || []) {
          if (gi.gameId) gids.push(gi.gameId);
        }
        break;
      }
    }

    let games = [];
    if (gids.length) {
      const metas = await Promise.all(gids.map(gameMeta));
      games = metas.map(normalizeGame).filter(Boolean);

      const finals = games.filter((g) => g.final && g.gameId);
      if (finals.length) {
        const decs = await Promise.all(finals.map((g) => gameDecisions(g.gameId)));
        finals.forEach((g, i) => { g.decisions = decs[i]; });
      }

      // 원본: games.sort(key=lambda x: ((x.get("datetime") or ""), (x.get("gameId") or "")))
      games.sort((a, b) => {
        const ka = `${a.datetime || ''} ${a.gameId || ''}`;
        const kb = `${b.datetime || ''} ${b.gameId || ''}`;
        return ka < kb ? -1 : ka > kb ? 1 : 0;
      });
    }

    await attachPitcherIds(env.DB, games);
    const result = { date, count: games.length, games };
    cache.set(date, result);
    return json(result);
  } catch (err) {
    // 원본은 예외 시 200 과 함께 error 필드를 돌려줍니다.
    return json({
      date,
      count: 0,
      games: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
```

**`throw new Error('구현 필요')` 를 남긴 채로 넘어가지 마십시오.** Step 5 에서 읽은 원본을 옮겨 세 함수를 완성해야 이 태스크가 끝납니다.

- [ ] **Step 7: 라우트를 등록합니다**

```javascript
import { schedule } from './routes/schedule.js';

router.add('GET', '/schedule', schedule);
```

- [ ] **Step 8: 정답지와 비교합니다**

Worker 를 띄우고 `/schedule` 두 건(기본, 날짜 지정)을 뜹니다.

```powershell
py -c "
import json, urllib.request, pathlib
out = pathlib.Path('migration/golden/actual'); out.mkdir(parents=True, exist_ok=True)
for name, path in [('schedule', '/schedule'),
                   ('schedule_date_20250401', '/schedule?date=20250401')]:
    r = urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60)
    body = json.loads(r.read().decode('utf-8'))
    (out / (name + '.json')).write_text(
        json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
                   sort_keys=True, indent=2), encoding='utf-8')
print('저장했습니다')
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

정답지 파일 이름은 `migration/golden/expected/` 를 열어 실제 이름으로 맞추십시오.

```powershell
Get-ChildItem migration\golden\expected\schedule*.json | Select-Object Name
```

- [ ] **Step 9: 커밋합니다**

```powershell
git add src/lib/kst.js src/routes/schedule.js src/index.js test/kst.test.js
git commit -m "feat(workers): /schedule 이식"
```

---

## Task 5: /schedule/futures 이식

**Files:**
- Create: `src/routes/futures.js`
- Modify: `src/index.js`

**Interfaces:**
- Consumes: Task 3 의 `ttlCache`, Task 4 의 `kstToday`
- Produces: `futures(request, env)` — `/schedule/futures` 핸들러

**원본**: `api/main.py:1276-1373` 과 헬퍼 `1242-1275`.

두 가지가 까다롭습니다.

**POST 폼 전송**: 원본은 `requests.post(data={...})` 로 `application/x-www-form-urlencoded` 를 보냅니다. JS 에서는 `URLSearchParams` 를 body 로 주면 같은 형식이 됩니다.

**BOM**: 원본은 `r.content.decode("utf-8-sig")` 로 BOM 을 떼어 냅니다. `res.json()` 을 그대로 쓰면 BOM 때문에 파싱이 실패합니다. `res.text()` 로 받아 앞의 `﻿` 를 지우고 `JSON.parse` 해야 합니다.

- [ ] **Step 1: 원본을 읽습니다**

```powershell
py -c "import io;print(''.join(io.open('api/main.py',encoding='utf-8').readlines()[1234:1374]))"
```

읽어야 할 것:

| 대상 | 원본 행 | 비고 |
|---|---|---|
| `_FUTURES_STATE`, `_FUTURES_SRID`, `_FUTURES_SB_URL` | 1237-1239 | 상수. 그대로 옮깁니다 |
| `_futures_teams_map` | 1242-1249 | `futures_teams` 테이블 조회 → D1 로 |
| `_futures_scoreboard` | 1252-1266 | POST + BOM |
| `_futures_int` | 1269-1273 | 숫자 변환 실패 시 `null` |
| 본체 | 1276-1373 | 정규화와 응답 조립 |

- [ ] **Step 2: /schedule/futures 를 작성합니다**

`src/routes/futures.js` 를 만듭니다.

```javascript
import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { kstToday } from '../lib/kst.js';

const cache = ttlCache(30); // 원본 _FUTURES_SCHED_TTL = 30

// 원본 api/main.py:1237-1239 의 상수를 그대로 옮깁니다.
const STATE = { 1: 'scheduled', 2: 'live', 3: 'final' };
const SRID = '0,9,10';
const SB_URL = 'https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList';

/**
 * GetKboGameList 를 POST 로 부릅니다.
 *
 * 응답 앞에 UTF-8 BOM 이 붙어 옵니다. res.json() 을 바로 쓰면 그 BOM 때문에
 * 파싱이 실패합니다. 원본이 utf-8-sig 로 디코드하는 것과 같은 처리를 합니다.
 */
async function scoreboard(ymd) {
  const res = await fetch(SB_URL, {
    method: 'POST',
    body: new URLSearchParams({ leId: '2', srId: SRID, date: ymd }),
    headers: {
      'user-agent': 'Mozilla/5.0',
      'referer': 'https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx',
      'x-requested-with': 'XMLHttpRequest',
    },
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const text = (await res.text()).replace(/^﻿/, '');
  const data = JSON.parse(text);
  return data.game || [];
}

/** 원본 _futures_int: 숫자로 못 바꾸면 null 입니다. 0 이 아닙니다. */
function toIntOrNull(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number.parseInt(v, 10);
  return Number.isNaN(n) ? null : n;
}

async function teamsMap(db) {
  // 원본 _futures_teams_map(1242-1249) 를 D1 로 옮깁니다.
  const { results } = await db
    .prepare('SELECT code, display_name, division FROM futures_teams')
    .all();
  const map = {};
  for (const r of results) map[r.code] = r;
  return map;
}

export async function futures(request, env) {
  const url = new URL(request.url);
  let date = url.searchParams.get('date');
  try {
    if (!date) date = kstToday();
    // 원본 1276-1373 의 정규화와 응답 조립을 그대로 옮깁니다.
    // 만들어야 할 필드는 위 "응답 계약" 절의 /schedule/futures 표에 있습니다.
    // score 가 null 인지 0 인지, final/live/cancel 이 bool 인지 특히 주의하십시오.
    throw new Error('구현 필요: 원본 1276-1373 참조');
  } catch (err) {
    return json({
      date,
      count: 0,
      games: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
```

**`throw new Error('구현 필요')` 를 남긴 채로 넘어가지 마십시오.**

- [ ] **Step 3: 라우트를 등록합니다**

```javascript
import { futures } from './routes/futures.js';

router.add('GET', '/schedule/futures', futures);
```

**등록 순서에 주의하십시오.** `/schedule/futures` 를 `/schedule` 보다 **먼저** 넣으십시오. 이 라우터는 세그먼트 개수가 같아야 매칭하므로 실제로는 충돌하지 않지만, 나중에 패턴을 고칠 때 순서가 안전망이 됩니다.

- [ ] **Step 4: 정답지와 비교합니다**

```powershell
py -c "
import json, urllib.request, pathlib
out = pathlib.Path('migration/golden/actual'); out.mkdir(parents=True, exist_ok=True)
for name, path in [('schedule_futures', '/schedule/futures'),
                   ('schedule_futures_date_20250401', '/schedule/futures?date=20250401')]:
    r = urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60)
    body = json.loads(r.read().decode('utf-8'))
    (out / (name + '.json')).write_text(
        json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
                   sort_keys=True, indent=2), encoding='utf-8')
print('저장했습니다')
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

파일 이름은 실제 정답지에 맞추십시오.

- [ ] **Step 5: 커밋합니다**

```powershell
git add src/routes/futures.js src/index.js
git commit -m "feat(workers): /schedule/futures 이식"
```

---

## Task 6: /players/:id/news 이식

**Files:**
- Create: `src/routes/news.js`
- Modify: `src/index.js`
- Create: `test/news_parse.test.js`

**Interfaces:**
- Consumes: Task 1 의 `json`, 라우터
- Produces:
  - `parseRssItems(xml) -> Array<{title, link, press}>` — RSS 항목 파서
  - `news(request, env, ctx, params)` — 핸들러

**원본**: `api/main.py:150-212`.

원본은 `xml.etree.ElementTree` 로 파싱합니다. Workers 에는 XML 파서가 없습니다. RSS 구조가 단순하고 필요한 필드가 셋뿐이라 정규식으로 뽑습니다.

- [ ] **Step 1: RSS 파서 테스트를 작성합니다**

`test/news_parse.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { parseRssItems } from '../src/routes/news.js';

const RSS = `<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>채널 제목입니다</title>
  <item>
    <title>김선수 홈런 - 스포츠조선</title>
    <link>https://example.com/a</link>
    <source url="https://sportschosun.com">스포츠조선</source>
  </item>
  <item>
    <title>제목에 하이픈 - 이 - 여럿 - 매일경제</title>
    <link>https://example.com/b</link>
    <source url="https://mk.co.kr">매일경제</source>
  </item>
  <item>
    <title>출처 없는 기사</title>
    <link>https://example.com/c</link>
  </item>
</channel></rss>`;

test('item 만 읽고 채널 제목은 건너뜁니다', () => {
  const items = parseRssItems(RSS);
  assert.equal(items.length, 3);
  assert.ok(!items.some((i) => i.title === '채널 제목입니다'));
});

test('제목 끝의 " - 언론사" 를 뗍니다', () => {
  const [first] = parseRssItems(RSS);
  assert.equal(first.title, '김선수 홈런');
});

test('하이픈이 여럿이면 마지막 것만 뗍니다', () => {
  // 원본은 rsplit(" - ", 1) 을 씁니다. 앞쪽 하이픈은 남아야 합니다.
  const items = parseRssItems(RSS);
  assert.equal(items[1].title, '제목에 하이픈 - 이 - 여럿');
});

test('source 가 없으면 Google News 입니다', () => {
  const items = parseRssItems(RSS);
  assert.equal(items[2].press, 'Google News');
});

test('link 를 읽습니다', () => {
  const [first] = parseRssItems(RSS);
  assert.equal(first.link, 'https://example.com/a');
});

test('item 이 없으면 빈 배열입니다', () => {
  assert.deepEqual(parseRssItems('<rss><channel></channel></rss>'), []);
});

test('제목의 엔티티를 풉니다', () => {
  const xml = `<rss><channel><item>
    <title>A&amp;B 승리 - 연합</title><link>x</link></item></channel></rss>`;
  const [first] = parseRssItems(xml);
  assert.equal(first.title, 'A&B 승리');
});

test('CDATA 로 감싼 제목을 읽습니다', () => {
  const xml = `<rss><channel><item>
    <title><![CDATA[대괄호 제목 - 언론]]></title><link>x</link></item></channel></rss>`;
  const [first] = parseRssItems(xml);
  assert.equal(first.title, '대괄호 제목');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/news_parse.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 3: /players/:id/news 를 작성합니다**

`src/routes/news.js` 를 만듭니다.

```javascript
import { json } from '../lib/respond.js';
import { decodeEntities } from '../lib/html.js';

function tagText(block, tag) {
  const m = new RegExp(`<${tag}[^>]*>([\\s\\S]*?)</${tag}>`).exec(block);
  if (!m) return null;
  const cdata = /^\s*<!\[CDATA\[([\s\S]*?)\]\]>\s*$/.exec(m[1]);
  return decodeEntities(cdata ? cdata[1] : m[1]).trim();
}

/**
 * Google News RSS 에서 항목을 뽑습니다.
 *
 * Workers 에 XML 파서가 없어 정규식으로 처리합니다. 필요한 필드가
 * title / link / source 셋뿐이고 구조가 단순해 이 정도로 충분합니다.
 */
export function parseRssItems(xml) {
  const items = [];
  for (const m of String(xml).matchAll(/<item[^>]*>([\s\S]*?)<\/item>/g)) {
    const block = m[1];
    let title = tagText(block, 'title') || 'No Title';
    const link = tagText(block, 'link') || '#';
    const press = tagText(block, 'source') || 'Google News';

    // 원본: if " - " in title: title = title.rsplit(" - ", 1)[0]
    const cut = title.lastIndexOf(' - ');
    if (cut !== -1) title = title.slice(0, cut);

    items.push({ title, link, press });
  }
  return items;
}

export async function news(request, env, ctx, params) {
  const playerId = params.id;
  try {
    // 원본 robust 조회: 문자열로 먼저, 숫자면 정수로 한 번 더.
    // players.player_id 가 문자열과 정수가 섞여 들어 있어 생긴 처리입니다.
    const sql = `
      SELECT p.player_name, t.team_name
      FROM players p
      LEFT JOIN teams t ON p.team_id = t.team_id
      WHERE p.player_id = ?`;
    let row = await env.DB.prepare(sql).bind(playerId).first();
    if (!row && /^\d+$/.test(playerId)) {
      row = await env.DB.prepare(sql).bind(Number.parseInt(playerId, 10)).first();
    }
    if (!row) {
      return json({
        player_name: 'Unknown',
        news: [],
        error: 'Player lookup failed',
      });
    }

    const playerName = row.player_name;
    const teamName = row.team_name || '';
    const query = `${teamName} ${playerName} 야구`;
    const url = 'https://news.google.com/rss/search'
      + `?q=${encodeURIComponent(query)}&hl=ko&gl=KR&ceid=KR:ko`;

    const res = await fetch(url);
    const xml = await res.text();

    // 원본은 앞 5건만 씁니다. desc 와 thumb 은 늘 고정값입니다.
    const newsItems = parseRssItems(xml).slice(0, 5).map((i) => ({
      title: i.title,
      link: i.link,
      press: i.press,
      desc: '',
      thumb: null,
    }));

    return json({ player_name: playerName, news: newsItems });
  } catch (err) {
    // 원본은 예외 시 player_name 을 "Error" 로 돌려줍니다. 그대로 맞춥니다.
    return json({
      player_name: 'Error',
      news: [],
      error: String(err && err.message ? err.message : err),
    });
  }
}
```

- [ ] **Step 4: 라우트를 등록합니다**

```javascript
import { news } from './routes/news.js';

router.add('GET', '/players/:id/news', news);
```

- [ ] **Step 5: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/
```

기대: 앞선 27개 + news 8개 = 35개 pass

- [ ] **Step 6: 정답지와 비교합니다**

정답지에 있는 뉴스 요청을 모두 뜹니다. 존재하지 않는 선수 ID 건도 있으니 함께 봅니다.

```powershell
Get-ChildItem migration\golden\expected\*news*.json | Select-Object Name
```

```powershell
py -c "
import json, urllib.request, pathlib, sys
out = pathlib.Path('migration/golden/actual'); out.mkdir(parents=True, exist_ok=True)
# 아래 목록을 위 Get-ChildItem 결과에 맞춰 채우십시오.
cases = [('players_50030_news', '/players/50030/news'),
         ('players_99999999_news_nonexistent', '/players/99999999/news')]
for name, path in cases:
    r = urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60)
    body = json.loads(r.read().decode('utf-8'))
    (out / (name + '.json')).write_text(
        json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
                   sort_keys=True, indent=2), encoding='utf-8')
print('저장했습니다')
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

- [ ] **Step 7: 커밋합니다**

```powershell
git add src/routes/news.js src/index.js test/news_parse.test.js
git commit -m "feat(workers): /players/:id/news 이식"
```

---

## Task 7: /leaders 이식

**Files:**
- Create: `src/routes/leaders.js`
- Modify: `src/index.js`
- Create: `test/leaders_calc.test.js`

**Interfaces:**
- Consumes: Task 3 의 `ttlCache`, `KBO_TEAM_CODE`
- Produces:
  - `ipToOuts(text) -> number` — `"68 1/3"` 형태를 아웃 수로
  - `WOBA_CONST: Record<number, number[]>` — 연도별 상수
  - `leaders(request, env)` — 핸들러

**원본**: `api/main.py:1594-1742` 과 헬퍼 `1524-1593`.

외부 의존이 없는데도 이 계획에 넣은 이유는 **위험 4(이식 과정의 계산 오차)** 때문입니다. 나눗셈, 반올림, 정렬 순서, NULL 처리가 한 곳에 다 모여 있는 엔드포인트라, 나머지 23개를 옮기기 전에 여기서 문제를 겪어 보는 편이 낫습니다.

**주의할 지점 셋**

1. **정렬 안정성.** 원본은 SQL `ORDER BY ... DESC LIMIT 5` 로 뽑습니다. 동점자 순서는 SQLite 구현에 달려 있습니다. D1 도 SQLite 라 같은 결과가 나올 가능성이 높지만, 다르면 골든 비교가 잡아냅니다. **JS 에서 다시 정렬하지 마십시오.** SQL 이 준 순서를 그대로 씁니다.
2. **숫자 포맷.** 원본은 `"%.3f" % float(val)` 로 문자열을 만듭니다. JS 의 `toFixed(3)` 은 반올림 방식이 다를 수 있습니다(0.5 경계). 값이 어긋나면 골든 비교에 나타납니다.
3. **NULL.** 원본은 값이 `None` 이면 `"-"` 를 넣습니다. D1 은 `null` 을 돌려주므로 `== null` 로 걸러야 합니다. `!value` 로 쓰면 `0` 이 `"-"` 가 되어 틀립니다.

- [ ] **Step 1: 계산 테스트를 작성합니다**

`test/leaders_calc.test.js` 를 만듭니다.

```javascript
import { test } from 'node:test';
import assert from 'node:assert/strict';

import { ipToOuts, fmt3 } from '../src/routes/leaders.js';

test('정수 이닝을 아웃으로 바꿉니다', () => {
  assert.equal(ipToOuts('68'), 204);
});

test('분수만 있는 이닝을 바꿉니다', () => {
  assert.equal(ipToOuts('1/3'), 1);
});

test('정수와 분수가 섞인 이닝을 바꿉니다', () => {
  assert.equal(ipToOuts('68 1/3'), 205);
  assert.equal(ipToOuts('68 2/3'), 206);
});

test('빈 값은 0 입니다', () => {
  assert.equal(ipToOuts(''), 0);
  assert.equal(ipToOuts(null), 0);
});

test('숫자가 아닌 값은 0 으로 칩니다', () => {
  assert.equal(ipToOuts('abc'), 0);
});

test('소수 세 자리로 포맷합니다', () => {
  assert.equal(fmt3(0.3125), '0.313');
  assert.equal(fmt3(0.5), '0.500');
});

test('null 은 하이픈입니다', () => {
  assert.equal(fmt3(null), '-');
  assert.equal(fmt3(undefined), '-');
});

test('0 은 하이픈이 아닙니다', () => {
  // !value 로 거르면 0 이 "-" 가 되어 틀립니다.
  assert.equal(fmt3(0), '0.000');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인합니다**

```powershell
node --test test/leaders_calc.test.js
```

기대: `Cannot find module` 로 실패합니다.

- [ ] **Step 3: 원본을 읽습니다**

```powershell
py -c "import io;print(''.join(io.open('api/main.py',encoding='utf-8').readlines()[1523:1742]))"
```

읽어야 할 것:

| 대상 | 원본 행 |
|---|---|
| `_LEADERS_TTL` | 1525 |
| `_WOBA_CONST` (2011~2026) | 1529-1546 |
| `_ip_to_outs` | 1549-1564 |
| `_team_park_factors` | 1567-1593 |
| 본체 | 1594-1742 |

`_WOBA_CONST` 는 Step 4 의 코드에 이미 옮겨 두었습니다. 값이 원본과 같은지만 대조하십시오.

```powershell
py -c "import io;print(''.join(io.open('api/main.py',encoding='utf-8').readlines()[1528:1547]))"
```

- [ ] **Step 4: /leaders 를 작성합니다**

`src/routes/leaders.js` 를 만듭니다. 아래 조각은 완성본이고, 본체는 Step 3 에서 읽은 내용으로 채웁니다.

```javascript
import { json } from '../lib/respond.js';
import { ttlCache } from '../lib/cache.js';
import { KBO_TEAM_CODE } from './standings.js';

const cache = ttlCache(600); // 원본 _LEADERS_TTL = 600

// 원본 api/main.py:1529-1546 의 _WOBA_CONST 입니다.
// 출처는 research/data/statiz_yearly_constants.csv 이고,
// (woba_scale, ebb, single_w, double_w, triple_w, hr_w) 순서입니다.
export const WOBA_CONST = {
  2011: [1.081, 0.407, 0.581, 0.972, 1.168, 1.364],
  2012: [1.134, 0.395, 0.565, 0.947, 1.162, 1.377],
  2013: [1.235, 0.314, 0.479, 0.821, 1.134, 1.442],
  2014: [1.094, 0.334, 0.513, 0.853, 1.169, 1.430],
  2015: [1.107, 0.375, 0.505, 0.808, 1.071, 1.419],
  2016: [1.095, 0.354, 0.502, 0.859, 1.258, 1.424],
  2017: [1.097, 0.353, 0.507, 0.869, 1.081, 1.398],
  2018: [1.074, 0.370, 0.509, 0.831, 1.167, 1.440],
  2019: [1.196, 0.357, 0.493, 0.802, 1.170, 1.433],
  2020: [1.109, 0.378, 0.516, 0.879, 1.081, 1.431],
  2021: [1.169, 0.362, 0.499, 0.867, 1.063, 1.460],
  2022: [1.211, 0.361, 0.484, 0.804, 1.210, 1.441],
  2023: [1.198, 0.355, 0.495, 0.865, 1.191, 1.408],
  2024: [1.093, 0.389, 0.519, 0.852, 1.046, 1.418],
  2025: [1.173, 0.371, 0.502, 0.801, 1.131, 1.406],
  2026: [1.191, 0.364, 0.493, 0.802, 1.175, 1.411],
};

/** 원본 _ip_to_outs(1549-1564): '68 1/3' -> 205 */
export function ipToOuts(s) {
  let whole = 0;
  let frac = 0;
  for (const part of String(s ?? '').split(/\s+/)) {
    if (part.includes('/')) {
      const n = Number.parseInt(part.split('/')[0], 10);
      frac = Number.isNaN(n) ? 0 : n;
    } else {
      const n = Number.parseInt(part, 10);
      whole = Number.isNaN(n) ? 0 : n;
    }
  }
  return whole * 3 + frac;
}

/**
 * 원본의 `"%.3f" % float(val)` 과 같은 문자열을 만듭니다.
 * 값이 없으면 '-' 입니다. 0 은 값이 있는 것이므로 '-' 가 아닙니다.
 */
export function fmt3(val) {
  if (val === null || val === undefined) return '-';
  return Number(val).toFixed(3);
}

export async function leaders(request, env) {
  // 원본 1594-1742 를 옮깁니다.
  // - season 미지정 시 MAX(season) FROM kbo_official_batter_stats
  // - qual_pa = round(3.1 * team_g), qual_outs = team_g * 3
  // - 타자 6종(avg, obp, slg, ops, woba, wrc), 투수 6종(ip, k, era, kpct, bbpct, kbb)
  // - D1 은 호출당 쿼리 50개 한도입니다. 원본의 쿼리 수를 세어 보고
  //   넘으면 UNION ALL 로 묶으십시오.
  //
  // 만들어야 할 응답 형태는 위 "응답 계약" 절의 /leaders 표에 있습니다.
  // 배열 원소의 value 가 문자열이라는 점, 데이터 없는 시즌에도 12개 배열이
  // 빈 배열로 전부 존재해야 한다는 점을 지키십시오.
  throw new Error('구현 필요: 원본 1594-1742 참조');
}
```

**`throw new Error('구현 필요')` 를 남긴 채로 넘어가지 마십시오.**

- [ ] **Step 5: D1 쿼리 수를 셉니다**

원본은 지표마다 쿼리를 따로 날립니다. 타자 4 + wRC+ 1 + wOBA 1 + 투수 6 + 메타 2 = 14 안팎입니다. 한도 50 안이지만, 구현 후 실제 개수를 세어 확인하십시오.

```powershell
npx wrangler dev --remote --port 8787
```

`wrangler dev` 콘솔에 D1 쿼리가 찍힙니다. `/leaders` 를 한 번 부르고 개수를 셉니다.

- [ ] **Step 6: 라우트를 등록합니다**

```javascript
import { leaders } from './routes/leaders.js';

router.add('GET', '/leaders', leaders);
```

- [ ] **Step 7: 테스트가 통과하는지 확인합니다**

```powershell
node --test test/
```

기대: 앞선 35개 + leaders 8개 = 43개 pass

- [ ] **Step 8: 정답지와 비교합니다**

`/leaders` 는 라이브가 아니라 **DB 기반**입니다. 따라서 구조가 아니라 **값까지 정확히 일치**해야 합니다. 위험 4 를 여기서 판정합니다.

```powershell
Get-ChildItem migration\golden\expected\leaders*.json | Select-Object Name
```

```powershell
py -c "
import json, urllib.request, pathlib
out = pathlib.Path('migration/golden/actual'); out.mkdir(parents=True, exist_ok=True)
cases = [('leaders', '/leaders'),
         ('leaders_season_2025', '/leaders?season=2025'),
         ('leaders_season_1990', '/leaders?season=1990')]
for name, path in cases:
    r = urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60)
    body = json.loads(r.read().decode('utf-8'))
    (out / (name + '.json')).write_text(
        json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
                   sort_keys=True, indent=2), encoding='utf-8')
print('저장했습니다')
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

**주의**: D1 에 `play_by_play` 적재가 아직 끝나지 않았다면(계획 A Task 8, 10일 일정) `/leaders` 응답이 정답지와 다를 수 있습니다. `_team_park_factors` 가 `games` 를 쓰는지 `play_by_play` 를 쓰는지 원본에서 확인하십시오. `play_by_play` 를 쓴다면 이 Step 은 적재 완료 후에 실행합니다. 그때까지는 Step 7 의 단위 테스트까지만 통과시키고 넘어갑니다.

- [ ] **Step 9: 불일치가 나오면 원인을 분류합니다**

| 증상 | 원인 | 조치 |
|---|---|---|
| 값이 소수점 끝자리만 다름 | 반올림 방식 | `toFixed` 대신 원본과 같은 방식으로 |
| 정수가 실수로 나옴 (`1` vs `1.0`) | D1 의 타입 변환 | 명시적 `Math.trunc` 또는 SQL `CAST` |
| 동점자 순서가 다름 | `ORDER BY` 동점 처리 | SQL 에 2차 정렬 키를 넣지 말고, 원본과 같은 쿼리인지 먼저 확인 |
| `null` 이 `"-"` 가 아니라 `"NaN"` | `fmt3` 를 안 거침 | 포맷 함수를 통과시킵니다 |
| 행 수가 다름 | 적재 미완 또는 규정타석 계산 차이 | `qual_pa` 계산을 원본과 대조 |

- [ ] **Step 10: 커밋합니다**

```powershell
git add src/routes/leaders.js src/index.js test/leaders_calc.test.js
git commit -m "feat(workers): /leaders 이식"
```

---

## Task 8: 정리와 판정 기록

**Files:**
- Modify: `src/index.js`
- Modify: `docs/superpowers/specs/2026-08-17-cloudflare-migration-design.md`
- Create: `docs/superpowers/plans/2026-08-17-plan-b-workers-external.md` (이 파일에 결과 추가)

- [ ] **Step 1: 판정용 임시 엔드포인트를 제거합니다**

Task 2 에서 넣은 `/probe/external` 을 `src/index.js` 에서 지웁니다. 판정은 이미 끝났고, 외부로 나가는 경로를 열어 둘 이유가 없습니다.

`migration/probe_external.py` 는 남깁니다. 나중에 다시 판정할 때 씁니다. 그때는 라우트를 임시로 되살리면 됩니다.

- [ ] **Step 2: 다섯 엔드포인트를 한꺼번에 비교합니다**

```powershell
npx wrangler dev --remote --port 8787
```

```powershell
py -c "
import json, urllib.request, pathlib
out = pathlib.Path('migration/golden/actual'); out.mkdir(parents=True, exist_ok=True)
# 이 계획이 옮긴 다섯 엔드포인트의 정답지 이름을 모두 채우십시오.
cases = []  # [(name, path), ...]
for name, path in cases:
    r = urllib.request.urlopen('http://127.0.0.1:8787' + path, timeout=60)
    body = json.loads(r.read().decode('utf-8'))
    (out / (name + '.json')).write_text(
        json.dumps({'status': 200, 'body': body}, ensure_ascii=False,
                   sort_keys=True, indent=2), encoding='utf-8')
print('%d건 저장했습니다' % len(cases))
"
py migration/golden_compare.py migration/golden/expected migration/golden/actual
```

기대: 옮긴 건수만큼 `일치`, `불일치 0건`. 아직 안 옮긴 엔드포인트는 `응답 파일 없음` 으로 나오는데 정상입니다.

- [ ] **Step 3: 전체 테스트를 돌립니다**

```powershell
node --test test/
py -m pytest tests/ -q
```

기대: JS 43개 pass, Python 64개 pass

- [ ] **Step 4: 배포하고 실물로 확인합니다**

```powershell
npx wrangler deploy
```

```powershell
curl.exe https://kbo-api.<계정>.workers.dev/standings
curl.exe https://kbo-api.<계정>.workers.dev/leaders
```

- [ ] **Step 5: 설계 문서에 진행 상태를 갱신합니다**

§11 마일스톤 표의 M3 행 상태를 채웁니다.

- [ ] **Step 6: 커밋합니다**

```powershell
git add src/index.js docs/
git commit -m "chore(workers): 판정 엔드포인트 제거와 계획 B 완료 기록"
git push
```

---

## 완료 기준

계획 B 가 끝나면 아래가 모두 참이어야 합니다.

- [ ] `node --test test/` 가 전부 통과합니다 (43개)
- [ ] `py -m pytest tests/ -q` 가 전부 통과합니다 (66개. Task 0 이 2개를 더합니다)
- [ ] `/schedule` 정답지의 `games` 가 비어 있지 않습니다 (Task 0)
- [ ] `npx wrangler deploy` 가 성공하고 `workers.dev` 주소가 응답합니다
- [ ] 옮긴 엔드포인트 5개가 골든 비교에서 `불일치 0건` 입니다
- [ ] `/probe/external` 이 코드에서 제거되었습니다
- [ ] 설계 문서 §7 위험 2 에 판정 결과가 기록되어 있습니다
- [ ] 설계 문서 §11 M3 행에 진행 상태가 적혀 있습니다

## 계획 B 에서 하지 않는 것

- **나머지 24개 엔드포인트**: 계획 B2 에서 합니다. 위험 2 판정이 먼저입니다.
- **프론트엔드**: 계획 C 에서 합니다. API 주소만 바꾸면 되는 작업이라 API 이식이 끝난 뒤가 맞습니다.
- **Cron Trigger 등록, R2 CSV 내보내기**: 계획 D 에서 합니다.
- **`_call_anthropic_with_failover` 이식**: **옮기지 않습니다.** `api/main.py:784-817` 에 정의만 있고 부르는 곳이 없는 죽은 코드입니다. 설계 문서 §8 이 `ANTHROPIC_API_KEY` 를 Workers 시크릿에 두라고 했는데, 쓰이지 않으므로 시크릿도 만들지 않습니다. 나중에 AI 기능을 실제로 붙일 때 그때 다룹니다.
- **D1 적재 완료 대기**: 적재(계획 A Task 8)는 10일에 걸쳐 병행됩니다. 이 계획의 다섯 엔드포인트 중 `play_by_play` 를 읽는 것은 없으므로, 적재를 기다릴 필요가 없습니다. 단 Task 7 Step 8 의 주의 사항을 확인하십시오.
