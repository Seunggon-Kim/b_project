# 화면의 시즌 하드코딩 정리(2027 대비) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 팀·선수·요인 통계가 "기록이 있는 가장 최근 시즌 = 진행 중"이나 글자로 박은 연도 대신 한국 시각과 그 시즌의 마지막 경기 종류로 진행 중을 판단하고, 참조 표·요인 표를 끝까지 받고, 저장 캐시에 유효기간을 두고, 아티클·홈·api.js 의 낡은 연도 글자를 정리합니다.

**Architecture:** 새 공용 모듈 `js/stats/season.js`(`window.TeamStats.season`)가 `/games?season=Y&limit=80` 한 번으로 진행 중 판단 재료를 만듭니다(순수 함수 + `loadSeasonState`). `js/stats/data.js` 는 `/db/table` 을 500행씩 끝까지 받는 `getTable`, 6시간 저장 캐시, 한국 시각 대체 시즌 목록을 맡습니다. 팀·선수 통계 page.js 와 요인 통계 인라인 스크립트는 이 둘을 불러 "진행 중"이 필요한 곳만 바꾸고, 아티클·홈·api.js 는 기본값과 글자만 고칩니다. API·Worker 는 바꾸지 않습니다.

**Tech Stack:** 순수 JavaScript(빌드 없음, IIFE 브라우저 모듈), Node 24 `node --test`(저장소 밖, vm 으로 모듈 실행), 헤드리스 Edge(CDP) 캡처, Python(계보 다시 만들기·pytest 는 실행만).

**설계 문서:** `C:/Users/김승곤/Desktop/b_project/docs/superpowers/specs/2026-10-05-season-hardcoding-cleanup-design.md`

## Global Constraints

- 진행 중 = 정규시즌이 끝날 때까지입니다. 시즌 Y 는 (Y = 한국 시각 올해)이고 (Y 의 가장 최근 경기가 '정규시즌')이면 진행 중입니다. 순위결정전은 '정규시즌'으로 들어옵니다. 실시간 순위(`/standings`)는 진행 중인 시즌에만 씁니다.
- 판단 실패 시: "올해면 진행 중"으로 보고, 팀·선수 통계는 알림 줄에 "진행 중 여부를 확인하지 못해 올해 시즌을 진행 중으로 봅니다"(끝에 마침표, `TeamStats.season.FAIL_TEXT` 한 곳에 둠)를 띄웁니다. 요인 통계는 콘솔에만 남깁니다.
- 저장소 `C:/Users/김승곤/Desktop/b_project`, 브랜치 `main`, 브랜치를 바꾸지 않습니다. 다른 세션과 작업 폴더를 같이 씁니다.
- 고칠 수 있는 곳은 `dashboard_js/` 안뿐입니다(이 계획·설계 문서 빼고). `src/`·`crawler/`·`migration/`·`test/`·`tests/`·`scripts/`·`wrangler.toml`·`package.json`·`package-lock.json`·`.github/` 는 읽기 전용입니다(`scripts/build_lineage.py`·`py -m pytest tests` 는 실행만). API·Worker 변경 없음.
- git: `git add -A`·`git add .`·`git commit -a`·`git stash`·`git reset`·`git restore`·`git checkout --` 금지. 새 파일만 경로를 적어 `git add <경로>` 하고, 커밋은 `git commit -m "…" -- <자기 파일들>` 로 자기 파일만 넣습니다. 커밋 전 `git status --short`·`git diff --cached --name-status` 를 봅니다. push·배포·`npm install`·DB 쓰기는 하지 않습니다.
- 파일을 고치기 전에 `git diff --quiet HEAD -- <파일>; echo $?` 가 `0` 인지 봅니다. `1` 이면 다른 세션의 커밋 안 된 변경이 있는 것이니 그 파일은 손대지 않고 보고합니다. 선수 분석 세션이 `dashboard_js/js/api.js` 를 자주 고칩니다(계획을 쓰는 동안 `getPitchTrend` 변경이 작업 트리에 있다가 adbd5ed 로 커밋됨). 그래서 Task 6 이 api.js 를 따로 확인하고 따로 커밋합니다.
- 커밋 메시지: `<type>(<scope>): 한국어 설명` + 빈 줄 + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 사용자에게 보이는 글은 습니다/합니다, 쉬운 말, 이모지 없음, 새 글에 줄표(—) 없음(`·`, `:`, 괄호를 씀). 기존 줄표(요인 통계 안내 상자 머리, 빈 칸 `—`)는 이번 범위 밖이라 그대로 둡니다. 새 설명은 그 페이지가 이미 쓰는 자리(알림 줄·표 아래 주의 문구·안내 상자)에 둡니다. 툴팁을 새로 만들지 않습니다.
- 줄 끝: 작업 폴더에서 CRLF 인 파일은 `js/stats/data.js`·`js/team-stats/page.js`·`pages/factor-stats.html`·`pages/article.html`, LF 인 파일은 `js/player-stats/page.js`·`pages/team-stats.html`·`pages/player-stats.html`·`index.html`·`js/api.js` 입니다. 그대로 지킵니다(Edit 도구로 정확히 맞춰 고침). 새 `js/stats/season.js` 는 다른 `js/stats` 파일처럼 CRLF 로 둡니다. BOM 없음. 고친 뒤 `git ls-files --eol <파일>` 의 `w/` 가 바꾸기 전과 같아야 합니다(`w/mixed` 면 고칩니다).
- 모듈 틀은 `js/stats` 의 다른 모듈과 같습니다: `(function (root) { … })(typeof window !== 'undefined' ? window : globalThis)` 안에서 `root.TeamStats.<이름>` 에 붙임. 저장소 `package.json` 이 `"type": "module"` 이라 `.cjs` 로 바꾸지 않습니다.
- 시험은 저장소 밖 `C:/tmp/bstats-team-stats-check/tests/` 에 있습니다. 도우미 `_load.js` 의 `load(name)` 은 `js/stats/<name>.js` 다음 `js/team-stats/<name>.js` 를 vm 으로 실행해 `TeamStats[name]` 을 꺼내고, `loadAs(rel, globalName)`·`fixture(name)`·`REPO_JS` 도 줍니다. 전체 실행: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js` (지금 **190개 통과**).
- 미리보기 `http://127.0.0.2:8765` 는 이미 떠 있습니다. 띄우거나 끄지 않습니다. 캡처 도구 `C:/tmp/bstats-team-stats-check/lineage_shot.mjs` 는 고치지 않습니다. Git Bash 에서 `MSYS_NO_PATHCONV=1` 을 붙여 부르고(9초 기다린 뒤 찍음), 결과 `C:/Users/김승곤/Desktop/bstats_lin_<이름>.png` 를 `mv` 로 `C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup/<이름>.png` 로 옮겨 Read 로 봅니다(폴더는 처음에 `mkdir -p`). 미리보기 페이지는 운영 API(`https://kbo-api.bstats-baseball.workers.dev`)를 부릅니다. 확인용 API 호출은 GET 만 합니다.
- 팀 통계 주소는 `tab`(bat·pit·rec)·`group`·`season`·`team`·`start`·`end`·`sort`·`dir`·`cols`, 선수 통계 주소는 `tab`(bat·pit)·`group`·`season`·`team`·`pos`·`min`·`sort`·`dir`·`page`·`size`·`cols` 를 읽습니다(캡처 주소는 이것만 씀).

## 파일 지도

| 파일 | 맡는 일 | Task |
|---|---|---|
| `dashboard_js/js/stats/season.js` (새) | 진행 중 판단: `kstToday`·`isoOf`·`isLive`·`summarize`·`loadSeasonState`·`FAIL_TEXT`·`LIMIT` | 1 |
| `dashboard_js/js/stats/data.js` | `/db/table` 이어 받기 `getTable`, 저장 캐시 6시간(`CACHE_TTL_MS`), 한국 시각 대체 시즌 목록 `fallbackSeasons` | 2 |
| `dashboard_js/js/team-stats/page.js`, `dashboard_js/pages/team-stats.html` | 실시간 순위·불일치 알림·진행 중 안내를 진행 중 판단으로, 기간 기본값 `rangeDefault` | 3 |
| `dashboard_js/js/player-stats/page.js`, `dashboard_js/pages/player-stats.html` | 규정용 실시간 순위·진행 중 안내를 진행 중 판단으로 | 4 |
| `dashboard_js/pages/factor-stats.html` | 진행 중 문장·배지를 판단으로, 두 표를 `getTable` 로 끝까지 | 5 |
| `dashboard_js/pages/article.html`, `dashboard_js/index.html`, `dashboard_js/js/api.js`, (`dashboard_js/data/table_lineage.json`) | 아티클 기본 시즌·문구, 홈 일정 문구·7일 빈 일정, api.js 기본값, 계보 다시 만들기 | 6 |

시험(저장소 밖): `season.test.js`(새, Task 1), `data.test.js`(Task 2), `page.test.js`·`layout.test.js`·`season.pages.test.js`(새, Task 3), `player-page.test.js`·`player-html.test.js`(Task 4), `season.pages.test.js`(Task 4·5·6 에서 더함).

---

### Task 1: 진행 중 판단 모듈(season.js)

**Files:**
- Create: `dashboard_js/js/stats/season.js`
- Test (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/season.test.js`

**Interfaces:**
- Consumes: 없음(혼자 섭니다. `data.js` 에 기대지 않아 어느 페이지에서나 실을 수 있습니다).
- Produces (`window.TeamStats.season`):
  - `LIMIT` = `80`, `FAIL_TEXT` = `'진행 중 여부를 확인하지 못해 올해 시즌을 진행 중으로 봅니다.'`
  - `kstToday(now?)` → `{ y, m, d, iso: 'YYYY-MM-DD' }` (now 는 ms 숫자나 Date, 없으면 지금)
  - `isoOf(n)` → `'YYYY-MM-DD'` | `null` (n 은 `20261004` 같은 경기 날짜)
  - `isLive(season, { kstYear, lastGame })` → boolean
  - `summarize(season, games, kstYear)` → `{ live, lastGame, lastRegularDate, firstDate }`
  - `loadSeasonState(base, season, opts?)` (opts = `{ fetch, now }`) → Promise of 성공 `{ season, kstYear, failed: false, live, lastGame, lastRegularDate, firstDate }` | 실패 `{ season, kstYear, failed: true, error, live: season === kstYear, lastGame: null, lastRegularDate: null, firstDate: null }` (절대 reject 하지 않음)

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/season.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture } = require('./_load');
const SE = load('season');

// 2025 경기 결과 736경기(최신순). 맨 위 16경기가 포스트시즌(2025-10-06~10-31), 정규시즌 마지막은 2025-10-04.
const G = fixture('games_2025').games;
// 9월 15일까지의 정규시즌(시즌 중 모양).
const REG_0915 = G.filter(x => x.game_type === '정규시즌' && x.game_date <= 20250915);

function fakeFetch(status, body) {
  const f = async url => {
    f.calls.push(url);
    return { ok: status < 400, status: status, json: async () => body };
  };
  f.calls = [];
  return f;
}

test('kstToday: 한국 시각 날짜, 해 넘김, 숫자·Date 모두 받음, isoOf', () => {
  assert.deepEqual(SE.kstToday(Date.UTC(2026, 11, 31, 14, 59)), { y: 2026, m: 12, d: 31, iso: '2026-12-31' });
  assert.deepEqual(SE.kstToday(Date.UTC(2026, 11, 31, 15, 0)), { y: 2027, m: 1, d: 1, iso: '2027-01-01' });
  assert.deepEqual(SE.kstToday(new Date(Date.UTC(2026, 9, 4, 20, 0))), { y: 2026, m: 10, d: 5, iso: '2026-10-05' });
  assert.ok(SE.kstToday().y >= 2026);
  assert.equal(SE.isoOf(20261004), '2026-10-04');
  assert.equal(SE.isoOf('20261004'), '2026-10-04');
  assert.equal(SE.isoOf('2026-10-04'), null);
  assert.equal(SE.isoOf(null), null);
});

test('isLive: 올해 시즌의 가장 최근 경기가 정규시즌이면 진행 중', () => {
  const reg = { season: 2026, game_date: 20261004, game_type: '정규시즌' };
  const ps = { season: 2026, game_date: 20261008, game_type: '포스트시즌' };
  assert.equal(SE.isLive(2026, { kstYear: 2026, lastGame: reg }), true);
  assert.equal(SE.isLive(2026, { kstYear: 2026, lastGame: ps }), false);
  assert.equal(SE.isLive(2026, { kstYear: 2027, lastGame: reg }), false);
  assert.equal(SE.isLive(2026, { kstYear: 2026, lastGame: null }), false);
  assert.equal(SE.isLive(2027, { kstYear: 2027, lastGame: reg }), false);
  assert.equal(SE.isLive(2026, null), false);
});

test('summarize: 정규시즌 중(9월 15일까지 자른 2025)', () => {
  const s = SE.summarize(2025, REG_0915.slice(0, 80), 2025);
  assert.equal(s.live, true);
  assert.equal(s.lastGame.game_date, 20250915);
  assert.equal(s.lastRegularDate, '2025-09-15');
  assert.equal(s.firstDate, null);
});

test('summarize: 포스트시즌이 시작되면 끝난 시즌, 마지막 정규시즌 날짜는 그대로', () => {
  const s = SE.summarize(2025, G.slice(0, 80), 2025);
  assert.equal(s.live, false);
  assert.equal(s.lastGame.game_type, '포스트시즌');
  assert.equal(s.lastRegularDate, '2025-10-04');
  assert.equal(s.firstDate, null);
  // 포스트시즌 첫 경기 하나만 들어와도 끝난 시즌입니다.
  const firstPs = G.filter(x => x.game_type === '포스트시즌').slice(-1);
  const s2 = SE.summarize(2025, firstPs.concat(G.filter(x => x.game_type === '정규시즌').slice(0, 79)), 2025);
  assert.equal(s2.live, false);
  assert.equal(s2.lastGame.game_date, 20251006);
  assert.equal(s2.lastRegularDate, '2025-10-04');
});

test('summarize: 해가 바뀐 비시즌, 아직 경기가 없는 새 시즌', () => {
  assert.equal(SE.summarize(2025, G.slice(0, 80), 2026).live, false);
  assert.equal(SE.summarize(2025, REG_0915.slice(0, 80), 2026).live, false);
  assert.deepEqual(SE.summarize(2027, [], 2027), { live: false, lastGame: null, lastRegularDate: null, firstDate: null });
  assert.deepEqual(SE.summarize(2027, null, 2027), { live: false, lastGame: null, lastRegularDate: null, firstDate: null });
});

test('summarize: 시즌 초반은 첫 경기 날짜, 80경기면 null, 순서가 섞여도 같음', () => {
  assert.equal(SE.LIMIT, 80);
  const early = G.filter(x => x.game_date <= 20250326);   // 20경기(3/22~3/26)
  const a = SE.summarize(2025, early, 2025);
  assert.deepEqual([a.live, a.lastRegularDate, a.firstDate], [true, '2025-03-26', '2025-03-22']);
  const b = SE.summarize(2025, early.slice().reverse(), 2025);
  assert.deepEqual([b.live, b.lastRegularDate, b.firstDate, b.lastGame.game_date], [true, '2025-03-26', '2025-03-22', 20250326]);
  assert.equal(early[0].game_date, 20250326, '입력 목록을 바꾸지 않습니다');
  assert.equal(SE.summarize(2025, REG_0915.slice(0, 79), 2025).firstDate, '2025-08-23');
  assert.equal(SE.summarize(2025, REG_0915.slice(0, 80), 2025).firstDate, null);
});

test('loadSeasonState: /games?season=Y&limit=80 한 번, 요약에 season·kstYear·failed 를 붙임', async () => {
  const f = fakeFetch(200, { games: G.slice(0, 80), season: 2025 });
  const r = await SE.loadSeasonState('B', 2025, { fetch: f, now: Date.UTC(2025, 10, 5) });
  assert.deepEqual(f.calls, ['B/games?season=2025&limit=80']);
  assert.deepEqual([r.season, r.kstYear, r.failed, r.live, r.lastRegularDate], [2025, 2025, false, false, '2025-10-04']);
  const mid = await SE.loadSeasonState('B', 2025, { fetch: fakeFetch(200, { games: REG_0915.slice(0, 80) }), now: Date.UTC(2025, 8, 15, 12) });
  assert.equal(mid.live, true);
  const next = await SE.loadSeasonState('B', 2027, { fetch: fakeFetch(200, { games: [] }), now: Date.UTC(2027, 0, 10) });
  assert.deepEqual([next.failed, next.live, next.lastGame, next.firstDate], [false, false, null, null]);
});

test('loadSeasonState: 받기 실패는 올해면 진행 중으로 보고 failed·error 를 남김', async () => {
  const NOW = Date.UTC(2026, 9, 5, 3);
  const a = await SE.loadSeasonState('B', 2026, { fetch: fakeFetch(500, {}), now: NOW });
  assert.deepEqual([a.season, a.kstYear, a.failed, a.live, a.error, a.lastRegularDate, a.firstDate], [2026, 2026, true, true, 'HTTP 500', null, null]);
  const b = await SE.loadSeasonState('B', 2025, { fetch: fakeFetch(500, {}), now: NOW });
  assert.deepEqual([b.failed, b.live], [true, false]);
  const c = await SE.loadSeasonState('B', 2026, { fetch: async () => { throw new Error('net down'); }, now: NOW });
  assert.match(c.error, /net down/);
  assert.equal(c.live, true);
  const d = await SE.loadSeasonState('B', 2026, { fetch: fakeFetch(200, { detail: 'D1_ERROR: x' }), now: NOW });
  assert.match(d.error, /D1_ERROR/);
  const e = await SE.loadSeasonState('B', 2026, { fetch: fakeFetch(200, { season: 2026 }), now: NOW });
  assert.match(e.error, /games/);
  assert.equal(SE.FAIL_TEXT, '진행 중 여부를 확인하지 못해 올해 시즌을 진행 중으로 봅니다.');
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test season.test.js`
Expected: FAIL (`season.js 를 stats, team-stats 에서 찾지 못했습니다`).

- [ ] **Step 3: season.js 쓰기**

`dashboard_js/js/stats/season.js`:

```js
/*
 * 시즌 진행 중 판단입니다(2027 대비 시즌 하드코딩 정리).
 *
 * 진행 중 = 정규시즌이 끝날 때까지입니다. 시즌 Y 는 (Y = 한국 시각 올해)이고
 * (Y 의 가장 최근 경기가 '정규시즌')이면 진행 중입니다. 그해 포스트시즌 첫
 * 경기가 들어오면 끝난 시즌입니다(정규시즌 기록은 그때부터 바뀌지 않음).
 * 순위결정전은 '정규시즌'으로 들어옵니다. 판단은 화면에서 하고 API 는 그대로 둡니다.
 *
 * 위쪽 순수 함수는 Node 로 검증하고, loadSeasonState 만 서버(/games)를 부릅니다.
 * data.js 에 기대지 않아 어느 페이지에서나 혼자 실을 수 있습니다.
 * 근거: docs/superpowers/specs/2026-10-05-season-hardcoding-cleanup-design.md
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  // /games 에서 한 번에 받을 경기 수입니다. 포스트시즌(많아야 20경기쯤)을 넘어 마지막
  // 정규시즌 경기까지 닿고, 시즌이 2주쯤 지나기 전이면 첫 경기까지 다 들어옵니다.
  const LIMIT = 80;
  const KST_OFFSET_MS = 9 * 3600000;
  // 진행 중 판단을 못 받았을 때 팀·선수 통계 알림 줄에 띄우는 말입니다(설계 6장).
  const FAIL_TEXT = '진행 중 여부를 확인하지 못해 올해 시즌을 진행 중으로 봅니다.';

  const z = n => String(n).padStart(2, '0');

  /** 한국 시각 오늘 { y, m, d, iso: 'YYYY-MM-DD' } 입니다. now 는 ms 숫자나 Date(없으면 지금)입니다. */
  function kstToday(now) {
    let ms = Date.now();
    if (typeof now === 'number') ms = now;
    else if (now && typeof now.getTime === 'function') ms = now.getTime();
    const t = new Date(ms + KST_OFFSET_MS);
    const y = t.getUTCFullYear(), m = t.getUTCMonth() + 1, d = t.getUTCDate();
    return { y: y, m: m, d: d, iso: `${y}-${z(m)}-${z(d)}` };
  }

  /** 경기 날짜(YYYYMMDD) → 'YYYY-MM-DD' 입니다. 모양이 다르면 null 입니다. */
  function isoOf(n) {
    const s = String(n === null || n === undefined ? '' : n);
    return /^\d{8}$/.test(s) ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : null;
  }

  /**
   * 진행 중인지입니다(순수). state = { kstYear, lastGame }.
   * season 이 한국 시각 올해이고, lastGame 이 그 시즌의 '정규시즌' 경기면 true 입니다.
   */
  function isLive(season, state) {
    const y = Number(season);
    const g = state && state.lastGame;
    return !!g && y === state.kstYear && Number(g.season) === y && g.game_type === '정규시즌';
  }

  /**
   * /games?season=Y 의 경기 목록을 요약합니다(순수). 서버는 최신순으로 주지만 순서에 기대지 않습니다.
   * 반환 { live, lastGame, lastRegularDate, firstDate }
   *   lastGame: 가장 최근 경기(없으면 null)
   *   lastRegularDate: 가장 최근 '정규시즌' 경기 날짜 'YYYY-MM-DD'(없으면 null)
   *   firstDate: 받은 경기가 LIMIT 보다 적으면(시즌 처음부터 다 받음) 가장 이른 날짜, 아니면 null
   */
  function summarize(season, games, kstYear) {
    const raw = Array.isArray(games) ? games : [];
    const list = raw.filter(g => g && isoOf(g.game_date))
      .sort((a, b) => Number(b.game_date) - Number(a.game_date));
    const lastGame = list.length ? list[0] : null;
    const reg = list.find(g => g.game_type === '정규시즌');
    return {
      live: isLive(season, { kstYear: kstYear, lastGame: lastGame }),
      lastGame: lastGame,
      lastRegularDate: reg ? isoOf(reg.game_date) : null,
      firstDate: list.length && raw.length < LIMIT ? isoOf(list[list.length - 1].game_date) : null,
    };
  }

  /**
   * 그 시즌의 진행 중 판단 재료를 받습니다(브라우저). /games?season=Y&limit=80 한 번입니다.
   * opts = { fetch, now }. 실패해도 reject 하지 않고 { failed: true, error, live: season === kstYear }
   * 를 돌려줍니다('올해면 진행 중'은 이 판단을 넣기 전 동작과 같습니다).
   */
  async function loadSeasonState(base, season, opts) {
    opts = opts || {};
    const y = Number(season);
    const kstYear = kstToday(opts.now).y;
    const f = opts.fetch || root.fetch.bind(root);
    try {
      const res = await f(`${base}/games?season=${y}&limit=${LIMIT}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      if (!json || typeof json !== 'object') throw new Error('응답이 비어 있습니다');
      if (json.detail || json.error) throw new Error(String(json.detail || json.error));
      if (!Array.isArray(json.games)) throw new Error('games 목록이 없습니다');
      return Object.assign({ season: y, kstYear: kstYear, failed: false }, summarize(y, json.games, kstYear));
    } catch (e) {
      return {
        season: y, kstYear: kstYear, failed: true, error: String((e && e.message) || e),
        live: y === kstYear, lastGame: null, lastRegularDate: null, firstDate: null,
      };
    }
  }

  const api = { LIMIT, FAIL_TEXT, kstToday, isoOf, isLive, summarize, loadSeasonState };
  TS.season = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

줄 끝을 CRLF 로 맞춥니다(두 번 돌려도 안전).

```bash
node -e "const fs=require('fs');const f=process.argv[1];fs.writeFileSync(f,fs.readFileSync(f,'utf8').replace(/\r?\n/g,'\r\n'))" "C:/Users/김승곤/Desktop/b_project/dashboard_js/js/stats/season.js"
file "C:/Users/김승곤/Desktop/b_project/dashboard_js/js/stats/season.js"
grep -c $'\xEF\xBB\xBF' "C:/Users/김승곤/Desktop/b_project/dashboard_js/js/stats/season.js"
```

Expected: `… with CRLF line terminators`, BOM `0`.

- [ ] **Step 4: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **198개 통과**(190 + 8), 실패 0.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/stats/season.js
git diff --cached --name-status
git commit -m "feat(season): 진행 중 시즌 판단 모듈(정규시즌 끝날 때까지, 한국 시각)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/stats/season.js
```

---

### Task 2: 공용 데이터(data.js): 이어 받기·캐시 유효기간·한국 시각 대체 목록

**Files:**
- Modify: `dashboard_js/js/stats/data.js` (CRLF)
- Test (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/data.test.js` (고침·더함)

**Interfaces:**
- Consumes: 기존 `getJson(url, listKey, fetchImpl)` → `{ ok, data } | { ok: false, error }`.
- Produces (`window.TeamStats.data` 에 더함):
  - `CACHE_TTL_MS` = `21600000`(6시간)
  - `getTable(base, name, opts?)` (opts = `{ fetch }`) → Promise `{ ok: true, data: 행 목록 } | { ok: false, error }`. 첫 쪽 실패는 `getJson` 의 이유 그대로, 중간 쪽 실패는 `'<이유> · <offset+1>행부터'`(예: `'HTTP 500 · 501행부터'`).
  - `fallbackSeasons(now?)` → `[올해 또는 작년, …, 1982]`
  - `loadRefs(base, opts)`·`loadSeasons(base, opts)` 가 `opts.now`(ms)를 더 받습니다(시험용). 저장 키는 `ts_ref_<표>_v2`·`teamstats_seasons_v3`, 저장 모양은 `{ t: 넣은 시각, v: 값 }`.

- [ ] **Step 1: 시험 고치고 더하기**

(1) `data.test.js` 의 `loadRefs: 성공한 표만 저장하고, 실패는 이름과 이유를 남김` 시험에서 세 줄만 바꿉니다.

- `assert.ok(f.calls.includes('B/db/table/self_park_factor?limit=500'));` → `assert.ok(f.calls.includes('B/db/table/self_park_factor?limit=500&offset=0'));`
- `assert.equal(store.getItem('ts_ref_self_park_factor_v1'), null);` → `assert.equal(store.getItem('ts_ref_self_park_factor_v2'), null);`
- `assert.ok(store.getItem('ts_ref_kbo_woba_weights_by_season_v1'));` → `assert.ok(store.getItem('ts_ref_kbo_woba_weights_by_season_v2'));`

(2) 파일 끝에 붙입니다.

```js

// 행 n 개짜리 표를 500행씩 주는 가짜 서버입니다. failAt 쪽(offset)은 HTTP 500, noTotal 이면 total 없이 줍니다.
function pagedFetch(n, failAt, noTotal) {
  const f = async url => {
    f.calls.push(url);
    const off = Number((/offset=(\d+)/.exec(url) || [0, 0])[1]);
    if (off === failAt) return { ok: false, status: 500, json: async () => ({}) };
    const rows = [];
    for (let i = off; i < Math.min(n, off + 500); i++) rows.push({ i: i });
    const body = noTotal ? { rows: rows } : { rows: rows, total: n, limit: 500, offset: off };
    return { ok: true, status: 200, json: async () => body };
  };
  f.calls = [];
  return f;
}

test('getTable: 500행씩 끝까지 이어 받음(total 에 닿거나 덜 찬 쪽에서 멈춤)', async () => {
  const f = pagedFetch(1203);
  const r = await D.getTable('B', 're24_matrix_by_season', { fetch: f });
  assert.equal(r.ok, true);
  assert.equal(r.data.length, 1203);
  assert.equal(r.data[1202].i, 1202);
  assert.deepEqual(f.calls, [
    'B/db/table/re24_matrix_by_season?limit=500&offset=0',
    'B/db/table/re24_matrix_by_season?limit=500&offset=500',
    'B/db/table/re24_matrix_by_season?limit=500&offset=1000',
  ]);
  const exact = pagedFetch(1000);
  assert.equal((await D.getTable('B', 't', { fetch: exact })).data.length, 1000);
  assert.equal(exact.calls.length, 2);
  const noTotal = pagedFetch(1000, -1, true);
  assert.equal((await D.getTable('B', 't', { fetch: noTotal })).data.length, 1000);
  assert.equal(noTotal.calls.length, 3);
  const small = pagedFetch(373);
  assert.equal((await D.getTable('B', 't', { fetch: small })).data.length, 373);
  assert.equal(small.calls.length, 1);
});

test('getTable: 중간 쪽 실패는 표 전체 실패, 첫 쪽이 비면 실패', async () => {
  const mid = await D.getTable('B', 't', { fetch: pagedFetch(1203, 500) });
  assert.deepEqual(mid, { ok: false, error: 'HTTP 500 · 501행부터' });
  const first = await D.getTable('B', 't', { fetch: pagedFetch(1203, 0) });
  assert.deepEqual(first, { ok: false, error: 'HTTP 500' });
  const empty = await D.getTable('B', 't', { fetch: pagedFetch(0) });
  assert.equal(empty.ok, false);
  assert.match(empty.error, /비어/);
});

test('loadRefs: 이어 받다 실패한 표는 반쪽을 쓰지 않고 저장하지 않음', async () => {
  const store = fakeStore();
  // 네 표 모두 같은 가짜 서버라 모두 500행 뒤에서 실패합니다.
  const r = await D.loadRefs('B', { fetch: pagedFetch(700, 500), store });
  assert.deepEqual(r.rank, []);
  assert.equal(r.errors.length, 4);
  assert.ok(r.errors.every(e => e.error === 'HTTP 500 · 501행부터'));
  assert.equal(store.getItem('ts_ref_team_season_rank_v2'), null);
  const ok = await D.loadRefs('B', { fetch: pagedFetch(700), store });
  assert.equal(ok.rank.length, 700);
  assert.deepEqual(ok.errors, []);
});

test('저장 캐시: 6시간 안이면 저장값, 지나면 다시 받음(시즌 목록 v3·참조 표 v2)', async () => {
  assert.equal(D.CACHE_TTL_MS, 6 * 3600000);
  const T0 = Date.UTC(2026, 9, 5, 0, 0);
  const store = fakeStore();
  await D.loadSeasons('B', { fetch: fakeFetch({ '/stats/seasons': { body: { seasons: [2026, 2025] } } }), store, now: T0 });
  assert.deepEqual(JSON.parse(store.getItem('teamstats_seasons_v3')), { t: T0, v: [2026, 2025] });
  const f1 = fakeFetch({});
  assert.deepEqual((await D.loadSeasons('B', { fetch: f1, store, now: T0 + D.CACHE_TTL_MS - 1 })).seasons, [2026, 2025]);
  assert.equal(f1.calls.length, 0);
  const f2 = fakeFetch({ '/stats/seasons': { body: { seasons: [2027, 2026, 2025] } } });
  assert.deepEqual((await D.loadSeasons('B', { fetch: f2, store, now: T0 + D.CACHE_TTL_MS })).seasons, [2027, 2026, 2025]);
  assert.equal(f2.calls.length, 1);
  // 옛 모양(값만 저장)은 쓰지 않습니다.
  const old = fakeStore();
  old.setItem('teamstats_seasons_v3', JSON.stringify([1999]));
  const f3 = fakeFetch({ '/stats/seasons': { body: { seasons: [2026] } } });
  assert.deepEqual((await D.loadSeasons('B', { fetch: f3, store: old, now: T0 })).seasons, [2026]);
  // 참조 표도 같은 유효기간입니다.
  const rs = fakeStore();
  await D.loadRefs('B', { fetch: pagedFetch(3), store: rs, now: T0 });
  assert.equal(JSON.parse(rs.getItem('ts_ref_team_season_rank_v2')).t, T0);
  const f4 = pagedFetch(3);
  await D.loadRefs('B', { fetch: f4, store: rs, now: T0 + 3600000 });
  assert.equal(f4.calls.length, 0);
  await D.loadRefs('B', { fetch: f4, store: rs, now: T0 + D.CACHE_TTL_MS });
  assert.equal(f4.calls.length, 4);
});

test('loadSeasons: 실패하면 한국 시각 올해(4월 전이면 작년)부터 1982', async () => {
  const top = async now => (await D.loadSeasons('B', { fetch: fakeFetch({}), store: fakeStore(), now })).seasons[0];
  assert.equal(await top(Date.UTC(2026, 9, 5, 3)), 2026);
  assert.equal(await top(Date.UTC(2026, 11, 31, 15, 0)), 2026);   // 한국 2027-01-01
  assert.equal(await top(Date.UTC(2027, 2, 31, 14, 59)), 2026);   // 한국 2027-03-31 23:59
  assert.equal(await top(Date.UTC(2027, 2, 31, 15, 0)), 2027);    // 한국 2027-04-01 00:00
  const list = D.fallbackSeasons(Date.UTC(2027, 1, 10));
  assert.equal(list[0], 2026);
  assert.equal(list[list.length - 1], 1982);
  assert.equal(list.length, 2026 - 1982 + 1);
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test data.test.js`
Expected: 고친 `loadRefs` 시험과 새 시험 5개가 FAIL(`offset=0` 주소 없음, `D.getTable is not a function` 등).

- [ ] **Step 3: data.js 고치기** (먼저 `git diff --quiet HEAD -- dashboard_js/js/stats/data.js; echo $?` 가 `0` 인지 봅니다)

(1) 머리 주석의 ` * 실패한 응답은 sessionStorage 에 넣지 않습니다.` 줄 바로 다음에 한 줄을 넣습니다.

```js
 * 넣어 둔 값은 6시간이 지나면 다시 받습니다(CACHE_TTL_MS).
```

(2) `function storeOf(opts) {` 부터 `cacheSet` 함수 끝(`    } catch (e) { /* 저장 공간이 없으면 넘어갑니다 */ }` 다음 `  }`)까지를 아래로 바꿉니다.

```js
  function storeOf(opts) {
    if (opts && opts.store) return opts.store;
    try { return root.sessionStorage || null; } catch (e) { return null; }
  }
  function nowOf(opts) {
    return opts && typeof opts.now === 'number' ? opts.now : Date.now();
  }

  // 저장 캐시 유효기간입니다. 탭을 오래 열어 두어도 시즌 목록·참조 표가 반나절 넘게 낡지 않게 둡니다.
  const CACHE_TTL_MS = 6 * 3600000;

  // 저장 모양은 { t: 넣은 시각(ms), v: 값 } 입니다. 유효기간이 지났거나 모양이 다르면 없는 것으로 봅니다.
  function cacheGet(key, opts) {
    try {
      const s = storeOf(opts);
      const raw = s ? s.getItem(key) : null;
      if (!raw) return null;
      const o = JSON.parse(raw);
      if (!o || typeof o !== 'object' || typeof o.t !== 'number' || !('v' in o)) return null;
      const age = nowOf(opts) - o.t;
      return age >= 0 && age < CACHE_TTL_MS ? o.v : null;
    } catch (e) { return null; }
  }
  function cacheSet(key, val, opts) {
    try {
      const s = storeOf(opts);
      if (s) s.setItem(key, JSON.stringify({ t: nowOf(opts), v: val }));
    } catch (e) { /* 저장 공간이 없으면 넘어갑니다 */ }
  }
```

(3) `async function loadRefs(base, opts) {` 함수 전체(그 함수의 `    return out;` 다음 `  }` 까지)를 아래로 바꿉니다(바로 위 `REF_TABLES`·`REF_LABEL` 은 그대로).

```js
  // /db/table 은 한 번에 500행까지 줍니다(서버 상한). 표가 커져도 잘리지 않게 끝까지 이어 받습니다.
  const PAGE_ROWS = 500;
  // 2만 행에서 멈춥니다. 서버가 offset 을 무시해 같은 쪽을 계속 주더라도 끝없이 돌지 않게 합니다.
  const MAX_PAGES = 40;

  /**
   * /db/table/<name> 을 500행씩 끝까지 받습니다. 반환 { ok: true, data: 행 목록 } | { ok: false, error }.
   * 응답의 total 에 닿거나 덜 찬 쪽이 오면 멈춥니다. 중간 쪽이 실패하면 표 전체를 실패로
   * 돌려줍니다(반쪽 표를 쓰지 않음). 첫 쪽이 비면 실패입니다(지금까지와 같음).
   */
  async function getTable(base, name, opts) {
    opts = opts || {};
    const rows = [];
    for (let i = 0; i < MAX_PAGES; i++) {
      const offset = i * PAGE_ROWS;
      const r = await getJson(`${base}/db/table/${name}?limit=${PAGE_ROWS}&offset=${offset}`, i === 0 ? 'rows' : null, opts.fetch);
      if (!r.ok) return { ok: false, error: i === 0 ? r.error : `${r.error} · ${offset + 1}행부터` };
      const page = r.data.rows;
      if (!Array.isArray(page)) return { ok: false, error: `rows 목록이 없습니다 · ${offset + 1}행부터` };
      for (const row of page) rows.push(row);
      const total = r.data.total;
      if (page.length < PAGE_ROWS || (typeof total === 'number' && rows.length >= total)) return { ok: true, data: rows };
    }
    return { ok: false, error: `${PAGE_ROWS * MAX_PAGES}행이 넘어 끝까지 받지 못했습니다` };
  }

  async function loadRefs(base, opts) {
    opts = opts || {};
    const out = { errors: [] };
    await Promise.all(Object.keys(REF_TABLES).map(async function (k) {
      const name = REF_TABLES[k];
      const key = `ts_ref_${name}_v2`;
      const hit = cacheGet(key, opts);
      if (Array.isArray(hit) && hit.length) { out[k] = hit; return; }
      const r = await getTable(base, name, opts);
      if (r.ok) {
        out[k] = r.data;
        cacheSet(key, r.data, opts);
      } else {
        out[k] = [];
        out.errors.push({ what: REF_LABEL[k], error: r.error });
      }
    }));
    return out;
  }
```

(4) `  /** 공식 기록이 있는 시즌(내림차순)과 오류 목록입니다. 실패하면 올해~1982 와 오류 한 건을 돌려줍니다. */` 줄부터 `loadSeasons` 함수 끝까지를 아래로 바꿉니다.

```js
  /**
   * 시즌 목록을 못 받았을 때 쓰는 목록입니다. 한국 시각 올해부터(4월 전이면 작년부터) 1982 까지입니다.
   * 4월 전에는 새 시즌 기록이 아직 없어, 빈 시즌이 기본으로 뜨지 않게 합니다.
   * (js/stats/season.js 를 싣지 않는 페이지도 이 파일을 써서 한국 시각을 여기서 셉니다.)
   */
  function fallbackSeasons(now) {
    const t = new Date((typeof now === 'number' ? now : Date.now()) + 9 * 3600000);
    const top = t.getUTCMonth() < 3 ? t.getUTCFullYear() - 1 : t.getUTCFullYear();
    const list = [];
    for (let y = top; y >= 1982; y--) list.push(y);
    return list;
  }

  /** 공식 기록이 있는 시즌(내림차순)과 오류 목록입니다. 실패하면 fallbackSeasons 와 오류 한 건을 돌려줍니다. */
  async function loadSeasons(base, opts) {
    opts = opts || {};
    const KEY = 'teamstats_seasons_v3';
    const desc = list => list.map(Number).filter(Number.isFinite).sort((a, b) => b - a);
    const hit = cacheGet(KEY, opts);
    if (Array.isArray(hit) && hit.length) return { seasons: desc(hit), errors: [] };
    const r = await getJson(`${base}/stats/seasons`, 'seasons', opts.fetch);
    if (r.ok) {
      cacheSet(KEY, r.data.seasons, opts);
      return { seasons: desc(r.data.seasons), errors: [] };
    }
    return { seasons: fallbackSeasons(nowOf(opts)), errors: [{ what: '시즌 목록', error: r.error }] };
  }
```

(5) 맨 아래 내보내기 줄을 바꿉니다.

`  const api = { badReason, getJson, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons, loadRegulation };`
→
`  const api = { CACHE_TTL_MS, badReason, getJson, getTable, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons, fallbackSeasons, loadRegulation };`

- [ ] **Step 4: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **203개 통과**(198 + 5), 실패 0. 그리고:

```bash
cd C:/Users/김승곤/Desktop/b_project
git ls-files --eol dashboard_js/js/stats/data.js
grep -c $'\xEF\xBB\xBF' dashboard_js/js/stats/data.js
grep -n "getFullYear" dashboard_js/js/stats/data.js
```

Expected: `w/crlf`, BOM `0`, `getFullYear` 줄 없음(출력 없음).

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git diff --cached --name-status
git commit -m "fix(stats): 참조 표 끝까지 이어 받기·저장 캐시 6시간·대체 시즌 목록을 한국 시각으로

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/stats/data.js
```

---

### Task 3: 팀 통계에 진행 중 판단 붙이기

**Files:**
- Modify: `dashboard_js/js/team-stats/page.js` (CRLF), `dashboard_js/pages/team-stats.html` (LF)
- Test (저장소 밖): `page.test.js`(더함), `layout.test.js`(고침), `season.pages.test.js`(새)

**Interfaces:**
- Consumes: Task 1 `TeamStats.season.kstToday()`, `TeamStats.season.loadSeasonState(base, season)` → `{ season, kstYear, failed, live, lastRegularDate, firstDate, error? }`, `TeamStats.season.FAIL_TEXT`. Task 2 의 `loadSeasons`·`loadRefs` 는 이름·반환 모양이 그대로입니다.
- Produces: `TeamStats.page.rangeDefault(y, state, today)` → `{ start: 'YYYY-MM-DD', end: 'YYYY-MM-DD' }` (state 는 `loadSeasonState` 결과나 `null`, today 는 `kstToday()` 결과).

바뀌는 판단(설계 5장): `S.pbpMax`(시즌 목록 맨 앞)는 기간 입력의 '기록 있음'(`y >= PBP_MIN && y <= S.pbpMax`)에만 남깁니다. 실시간 순위 받기·붙이기, 끝난 시즌 순위 불일치 알림, "진행 중인 시즌은…" 안내는 `liveSeason(y)` 로 바꿉니다.

- [ ] **Step 1: 시험 먼저 쓰기**

(1) `page.test.js` 끝에 붙입니다.

```js

test('rangeDefault: 진행 중이면 오늘까지, 끝난 시즌은 마지막 정규시즌 날짜까지, 모르면 9월 30일', () => {
  const today = { y: 2026, m: 10, d: 5, iso: '2026-10-05' };
  assert.deepEqual(P.rangeDefault(2026, { live: true, lastRegularDate: '2026-10-04', firstDate: null }, today), { start: '2026-09-22', end: '2026-10-05' });
  assert.deepEqual(P.rangeDefault(2025, { live: false, lastRegularDate: '2025-10-04', firstDate: null }, today), { start: '2025-09-21', end: '2025-10-04' });
  assert.deepEqual(P.rangeDefault(2025, null, today), { start: '2025-09-17', end: '2025-09-30' });
  assert.deepEqual(P.rangeDefault(2024, { live: false, failed: true, lastRegularDate: null, firstDate: null }, today), { start: '2024-09-17', end: '2024-09-30' });
  // 판단을 못 받았지만 올해면 진행 중으로 보고 오늘까지입니다.
  assert.deepEqual(P.rangeDefault(2026, { live: true, failed: true, lastRegularDate: null, firstDate: null }, today), { start: '2026-09-22', end: '2026-10-05' });
});

test('rangeDefault: 시즌 초반에는 첫 경기 날짜보다 앞서지 않음, 달을 넘겨 셈', () => {
  const today = { y: 2027, m: 4, d: 2, iso: '2027-04-02' };
  assert.deepEqual(P.rangeDefault(2027, { live: true, lastRegularDate: '2027-04-01', firstDate: '2027-03-28' }, today), { start: '2027-03-28', end: '2027-04-02' });
  assert.deepEqual(P.rangeDefault(2027, { live: true, lastRegularDate: '2027-04-01', firstDate: '2027-03-01' }, today), { start: '2027-03-20', end: '2027-04-02' });
});
```

(2) `layout.test.js` 의 `team-stats.html: stats.css 를 쓰고 스크립트를 이 순서로 부름` 시험에서 기대 목록의 줄
`    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/table.js',`
를
`    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/season.js', '../js/stats/table.js',`
로 바꿉니다.

(3) 새 파일 `C:/tmp/bstats-team-stats-check/tests/season.pages.test.js`:

```js
// 시즌 하드코딩 정리(2026-10-05 설계)의 글자 검사입니다. 페이지가 진행 중 판단을
// js/stats/season.js 로 하는지, 연도를 글자로 박아 두지 않았는지 봅니다.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { REPO_JS } = require('./_load');

const ROOT = path.join(REPO_JS, '..');
const read = rel => fs.readFileSync(path.join(ROOT, rel), 'utf8');
const scripts = html => [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);

test('team-stats page.js: 진행 중 판단은 season.js, pbpMax 는 기록 있음에만', () => {
  const src = read('js/team-stats/page.js');
  assert.equal((src.match(/S\.pbpMax/g) || []).length, 2, 'pbpMax 는 기간 입력의 기록 있음 판단과 init 에서만 씁니다');
  assert.match(src, /const has = y >= PBP_MIN && y <= S\.pbpMax;/);
  assert.match(src, /S\.pbpMax = S\.seasons\[0\];/);
  assert.ok(!src.includes('getFullYear()'), '브라우저 연도를 쓰는 곳이 남아 있습니다');
  assert.match(src, /TS\.season\.loadSeasonState\(base, S\.kst\.y\)/);
  assert.match(src, /need\.season && liveSeason\(y\) && stale\(S\.standings\)/);
  assert.match(src, /if \(!liveSeason\(S\.st\.season\) \|\| !S\.standings\) return null;/);
  assert.match(src, /if \(splits && !liveSeason\(y\)\) \{/);
  assert.match(src, /\(liveSeason\(y\) \? LIVE_SEASON_CAVEAT : ''\)/);
  assert.match(src, /const LIVE_CAVEAT = ' 진행 중인 시즌의 승패와 경기 수는 KBO 실시간 순위입니다\.';/);
  assert.ok(!src.includes('올해 승패'));
  assert.match(src, /text: TS\.season\.FAIL_TEXT/);
  assert.match(src, /const def = rangeDefault\(y, S\.state\[y\] \|\| null, S\.kst\);/);
  assert.match(src, /if \(!S\.state\[y\]\) loadStateFor\(y, def\);/);
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test page.test.js layout.test.js season.pages.test.js`
Expected: 새 rangeDefault 시험 2개(`P.rangeDefault is not a function`), layout 스크립트 목록 시험, season.pages 시험이 FAIL.

- [ ] **Step 3: page.js 고치기** (먼저 `git diff --quiet HEAD -- dashboard_js/js/team-stats/page.js dashboard_js/pages/team-stats.html; echo $?` 가 `0`)

(1) `csvName` 함수 끝과 `  // ===== 화면(브라우저에서만) =====` 사이에 넣습니다.

```js

  /**
   * 기간 입력의 기본값 { start, end } 입니다(두 주, 순수 함수).
   * 끝: 진행 중인 시즌이면 오늘(한국 시각), 아니면 그 시즌 마지막 정규시즌 경기 날짜,
   *     그 날짜를 아직 모르거나 못 받았으면 9월 30일입니다.
   * 시작: 끝 − 13일. 첫 경기 날짜를 알면 그보다 앞서지 않습니다.
   * state 는 season.js loadSeasonState 결과(없으면 null), today 는 kstToday() 결과입니다.
   */
  function rangeDefault(y, state, today) {
    const end = state && state.live ? today.iso : (state && state.lastRegularDate) || `${y}-09-30`;
    let start = new Date(Date.parse(end + 'T00:00:00Z') - 13 * 86400000).toISOString().slice(0, 10);
    if (state && state.firstDate && start < state.firstDate) start = state.firstDate;
    return { start: start, end: end };
  }
```

(2) `  const LIVE_CAVEAT = ' 올해 승패와 경기 수는 KBO 실시간 순위입니다.';`
→ `  const LIVE_CAVEAT = ' 진행 중인 시즌의 승패와 경기 수는 KBO 실시간 순위입니다.';`

(3) `const S = { … };` 를 바꿉니다.

```js
  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, games: {}, range: {}, standings: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    seasonErrors: [], seq: 0, last: null, pbpMax: new Date().getFullYear(),
  };
```
→
```js
  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, games: {}, range: {}, standings: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    // pbpMax: 기록이 있는 가장 최근 시즌(시즌 목록 맨 앞). '기록 있음' 판단에만 씁니다.
    // kst: 한국 시각 오늘. state: 시즌 → season.js loadSeasonState 결과(진행 중 판단·기간 기본값).
    seasonErrors: [], seq: 0, last: null, pbpMax: 0,
    kst: null, state: {}, stateLoading: {},
  };
```

(4) 이제 쓰지 않는 `fmtDate` 를 지웁니다(아래 네 줄 통째로).

```js
  function fmtDate(dt) {
    const z = n => String(n).padStart(2, '0');
    return `${dt.getFullYear()}-${z(dt.getMonth() + 1)}-${z(dt.getDate())}`;
  }
```

(5) `  function keysNow() {` 함수(세 줄) 바로 다음에 넣습니다.

```js

  /** 진행 중인 시즌인지입니다(js/stats/season.js 판단). 한국 시각 올해 시즌 판단은 init 에서 받아 둡니다. */
  function liveSeason(y) {
    const s = S.state[y];
    return !!(s && s.live);
  }
```

(6) `syncRange` 의 끝부분을 바꿉니다.

```js
    if (mode() === 'range') { a.value = S.st.start; b.value = S.st.end; return; }
    // 기본 두 주입니다. 올해면 오늘까지, 지난 시즌이면 9월 말까지입니다.
    const now = new Date();
    const end = y === now.getFullYear() ? now : new Date(y, 8, 30);
    a.value = fmtDate(new Date(end.getTime() - 13 * 86400000));
    b.value = fmtDate(end);
    note.textContent = '';
  }
```
→
```js
    if (mode() === 'range') { a.value = S.st.start; b.value = S.st.end; return; }
    // 기본 두 주입니다(rangeDefault). 그 시즌 경기 일정을 아직 모르면 9월 30일 기준으로 두었다가 받으면 다시 맞춥니다.
    const def = rangeDefault(y, S.state[y] || null, S.kst);
    a.value = def.start;
    b.value = def.end;
    note.textContent = '';
    if (!S.state[y]) loadStateFor(y, def);
  }

  /**
   * 그 시즌의 경기 일정 요약(season.js)을 받아 기간 기본값을 다시 맞춥니다. 받는 동안
   * 다른 시즌·기간으로 옮겼거나 날짜를 고쳤으면 덮어쓰지 않습니다. 실패하면 콘솔에만
   * 남기고 9월 30일 기준을 그대로 둡니다.
   */
  function loadStateFor(y, shown) {
    if (S.stateLoading[y]) return;
    S.stateLoading[y] = TS.season.loadSeasonState(root.KBO_API_BASE, y).then(function (r) {
      S.state[y] = r;
      if (r.failed) console.warn(`${y} 시즌 경기 일정을 받지 못해 기간 기본값을 9월 30일 기준으로 둡니다`, r.error);
      if (S.st.season === y && mode() !== 'range'
        && $('range-start').value === shown.start && $('range-end').value === shown.end) syncRange();
    });
  }
```

(7) `ensureData` 의 마지막 받기 두 줄을 바꿉니다.

```js
    // 올해(가장 최근 시즌)는 승패·경기 수를 실시간 순위로 받습니다.
    if (need.season && y === S.pbpMax && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
```
→
```js
    // 진행 중인 시즌은 승패·경기 수를 실시간 순위로 받습니다(끝난 시즌에 다음 해 순위가 붙지 않게).
    if (need.season && liveSeason(y) && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
```

(8) `liveRank` 의 주석 첫 줄과 첫 조건을 바꿉니다.

`   * 올해면 실시간 순위, 아니면 null(저장된 순위표를 씀)입니다.` → `   * 진행 중인 시즌이면 실시간 순위, 아니면 null(저장된 순위표를 씀)입니다.`

`    if (S.st.season !== S.pbpMax || !S.standings) return null;` → `    if (!liveSeason(S.st.season) || !S.standings) return null;`

(9) `render()` 의 `    errAlerts(alerts, S.refs.errors);` 줄 바로 다음에 넣습니다.

```js
    // 진행 중 판단을 못 받았으면 올해 시즌을 진행 중으로 보고 있음을 알립니다(올해 시즌을 볼 때만).
    const ks = S.kst ? S.state[S.kst.y] : null;
    if (ks && ks.failed && y === S.kst.y) alerts.push({ kind: 'warn', text: TS.season.FAIL_TEXT });
```

(10) 순위 불일치 알림 조건: `        if (splits && y < S.pbpMax) {` → `        if (splits && !liveSeason(y)) {` (바로 위 두 줄 주석 "끝난 시즌에서 … 알리지 않습니다." 는 그대로 맞습니다).

(11) 시즌 누적 주의 문구: `(y === S.pbpMax ? LIVE_SEASON_CAVEAT : '')` → `(liveSeason(y) ? LIVE_SEASON_CAVEAT : '')`

(12) `init()` 의 받기 부분을 바꿉니다.

```js
      const base = root.KBO_API_BASE;
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.pbpMax = S.seasons[0];
```
→
```js
      const base = root.KBO_API_BASE;
      S.kst = TS.season.kstToday();
      // 한국 시각 올해 시즌만 진행 중일 수 있어, 그 해 판단을 시즌 목록과 함께 받습니다.
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base), TS.season.loadSeasonState(base, S.kst.y)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.state[S.kst.y] = got[2];
      if (got[2].failed) console.warn(TS.season.FAIL_TEXT, got[2].error);
      S.pbpMax = S.seasons[0];
```

(13) 내보내기: `  const api = { parseState, toSearch, visibleKeys, defaultSort, pickSort, csvName, dataReady };`
→ `  const api = { parseState, toSearch, visibleKeys, defaultSort, pickSort, csvName, dataReady, rangeDefault };`

- [ ] **Step 4: team-stats.html 에 season.js 싣기**

`    <script src="../js/stats/data.js"></script>` 줄 바로 다음에 넣습니다.

```html
    <script src="../js/stats/season.js"></script>
```

- [ ] **Step 5: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **206개 통과**(203 + page 2 + season.pages 1), 실패 0. 그리고:

```bash
cd C:/Users/김승곤/Desktop/b_project
git ls-files --eol dashboard_js/js/team-stats/page.js dashboard_js/pages/team-stats.html
grep -c $'\xEF\xBB\xBF' dashboard_js/js/team-stats/page.js dashboard_js/pages/team-stats.html
```

Expected: page.js `w/crlf`, html `w/lf`, BOM 둘 다 `0`.

- [ ] **Step 6: 지금 2026 이 진행 중인지 보고 캡처하기**

```bash
curl -s "https://kbo-api.bstats-baseball.workers.dev/games?season=2026&limit=80" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const g=JSON.parse(s).games;const r=g.find(x=>x.game_type==='정규시즌');console.log('최근', g[0].game_date, g[0].game_type, '/ 마지막 정규시즌', r && r.game_date)})"
```

최근 경기가 `정규시즌` 이면 **A(2026 진행 중)**, `포스트시즌` 이면 **B(2026 끝남)** 로 아래 표를 봅니다(계획을 쓴 2026-10-05 에는 A: 최근 20261004 정규시즌).

```bash
mkdir -p "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup"
cd C:/tmp/bstats-team-stats-check
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ts_2026 "/pages/team-stats.html?season=2026"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ts_2026_rec "/pages/team-stats.html?tab=rec&season=2026"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ts_2025 "/pages/team-stats.html?season=2025"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ts_2025_rec "/pages/team-stats.html?tab=rec&season=2025"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ts_2026_mobile "/pages/team-stats.html?season=2026" --mobile
for n in ts_2026 ts_2026_rec ts_2025 ts_2025_rec ts_2026_mobile; do mv "C:/Users/김승곤/Desktop/bstats_lin_$n.png" "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup/$n.png"; done
```

| 캡처 | 맞아야 하는 것 |
|---|---|
| ts_2026 | A: 기간 입력이 (오늘−13일) ~ 오늘(10월 5일 실행이면 2026-09-22 ~ 2026-10-05), 표 아래 주의 문구에 "진행 중인 시즌은 최신 일일 갱신 기준…"과 "진행 중인 시즌의 승패와 경기 수는 KBO 실시간 순위입니다." B: 기간 입력이 (마지막 정규시즌 날짜−13일) ~ 마지막 정규시즌 날짜, 두 문장 없음. 둘 다 알림 줄에 "진행 중 여부를 확인하지 못해…" 없음 |
| ts_2026_rec | A: 주의 문구 끝이 "진행 중인 시즌의 승패와 경기 수는 KBO 실시간 순위입니다.", 경기 결과 불일치(파란) 알림 없음. B: 그 문장 없음(경기 결과가 공식 기록과 다른 팀이 있으면 파란 알림) |
| ts_2025 | 기간 입력 2025-09-21 ~ 2025-10-04(바꾸기 전에는 09-17 ~ 09-30), "진행 중" 문장 없음 |
| ts_2025_rec | "진행 중"·"실시간 순위" 문장 없음 |
| ts_2026_mobile | 출력 `doc` ≤ 390, 기간 입력·알림이 화면 안에 들어옴 |

PNG 는 Read 로 열어 봅니다. 맞지 않으면 Task 3 파일 안에서 고치고 시험·캡처를 다시 합니다.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git diff --cached --name-status
git commit -m "fix(team-stats): 실시간 순위·진행 중 안내를 진행 중 판단으로, 기간 기본값을 마지막 정규시즌 날짜로

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/team-stats/page.js dashboard_js/pages/team-stats.html
```

---

### Task 4: 선수 통계에 진행 중 판단 붙이기

**Files:**
- Modify: `dashboard_js/js/player-stats/page.js` (LF), `dashboard_js/pages/player-stats.html` (LF)
- Test (저장소 밖): `player-page.test.js`(더함), `player-html.test.js`(고침), `season.pages.test.js`(더함)

**Interfaces:**
- Consumes: Task 1 `TeamStats.season.kstToday()`, `TeamStats.season.loadSeasonState(base, season)`, `TeamStats.season.FAIL_TEXT`.
- Produces: `TeamStats.playerPage.caveatText(st, liveSeason, live)` 의 두 번째 인자 뜻이 "가장 최근 시즌"에서 "진행 중인 시즌(없으면 `null`)"으로 바뀝니다(기존 시험 호출 `caveatText(st, 2026, …)` 은 그대로 맞습니다). 페이지 안에서는 새 함수 `liveYear()`(진행 중인 시즌 또는 `null`)를 넘깁니다. 인자 이름을 `liveYear` 로 하지 않는 것은 그 함수를 가리지 않으려는 것입니다.

- [ ] **Step 1: 시험 먼저 쓰기**

(1) `player-page.test.js` 끝에 붙입니다.

```js

test('caveatText: 진행 중인 시즌이 없으면(null) 진행 중 문구 없음, 실시간 문구는 진행 중인 시즌의 …', () => {
  const ended = P.caveatText(st({ season: 2026 }), null, false);
  assert.ok(!/진행 중/.test(ended));
  assert.ok(!/실시간/.test(ended));
  const live = P.caveatText(st({ season: 2026 }), 2026, true);
  assert.match(live, / 진행 중인 시즌의 소속팀 경기 수는 KBO 실시간 순위입니다\./);
  assert.match(live, / 진행 중인 시즌은 최신 일일 갱신 기준/);
  assert.ok(!/올해/.test(live));
  assert.ok(!/진행 중/.test(P.caveatText(st({ season: 2025 }), 2026, false)));
});
```

(2) `player-html.test.js` 의 스크립트 순서 시험에서 기대 목록의 줄
`    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/table.js',`
를
`    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/season.js', '../js/stats/table.js',`
로 바꿉니다.

(3) `season.pages.test.js` 끝에 붙입니다.

```js

test('player-stats page.js: 진행 중 판단은 season.js(가장 최근 시즌·브라우저 연도 아님)', () => {
  const src = read('js/player-stats/page.js');
  assert.ok(!src.includes('S.latest'));
  assert.ok(!src.includes('getFullYear()'), '브라우저 연도를 쓰는 곳이 남아 있습니다');
  assert.match(src, /TS\.season\.loadSeasonState\(base, kst\.y\)/);
  assert.match(src, /if \(y === liveYear\(\) && S\.standings\) \{/);
  assert.match(src, /st\.min === 'q' && y === liveYear\(\) && stale\(S\.standings\)/);
  assert.match(src, /caveatText\(st, liveYear\(\), live\)/);
  assert.match(src, /const LIVE_QUAL_CAVEAT = ' 진행 중인 시즌의 소속팀 경기 수는 KBO 실시간 순위입니다\.';/);
  assert.ok(!src.includes('올해 소속팀'));
  assert.match(src, /text: TS\.season\.FAIL_TEXT/);
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test player-page.test.js player-html.test.js season.pages.test.js`
Expected: 새 caveatText 시험(옛 "올해 소속팀" 문구), 스크립트 순서 시험, player-stats page.js 글자 시험이 FAIL.

- [ ] **Step 3: page.js 고치기** (먼저 `git diff --quiet HEAD -- dashboard_js/js/player-stats/page.js dashboard_js/pages/player-stats.html; echo $?` 가 `0`)

(1) `  const LIVE_QUAL_CAVEAT = ' 올해 소속팀 경기 수는 KBO 실시간 순위입니다.';`
→ `  const LIVE_QUAL_CAVEAT = ' 진행 중인 시즌의 소속팀 경기 수는 KBO 실시간 순위입니다.';`

(2) `caveatText` 의 주석·인자·진행 중 조건을 바꿉니다.

```js
  /** 표 아래 출처·주의 문구입니다. latest 는 가장 최근 시즌, live 는 실시간 순위로 규정을 셌는지입니다. */
  function caveatText(st, latest, live) {
    return CAVEAT + TRADE_CAVEAT
      + (st.min === 'q' ? QUAL_CAVEAT + (live ? LIVE_QUAL_CAVEAT : '') : '')
      + (st.season === latest ? LIVE_SEASON_CAVEAT : '')
```
→
```js
  /**
   * 표 아래 출처·주의 문구입니다. liveSeason 은 진행 중인 시즌(없으면 null, js/stats/season.js 판단),
   * live 는 실시간 순위로 규정을 셌는지입니다.
   */
  function caveatText(st, liveSeason, live) {
    return CAVEAT + TRADE_CAVEAT
      + (st.min === 'q' ? QUAL_CAVEAT + (live ? LIVE_QUAL_CAVEAT : '') : '')
      + (liveSeason && st.season === liveSeason ? LIVE_SEASON_CAVEAT : '')
```

(3) `S` 의 마지막 줄을 바꿉니다.

`    seasonErrors: [], seq: 0, last: null, latest: new Date().getFullYear(),`
→
```js
    seasonErrors: [], seq: 0, last: null,
    // 한국 시각 올해 시즌의 진행 중 판단(js/stats/season.js loadSeasonState 결과)입니다. init 에서 채웁니다.
    liveState: null,
```

(4) `  function keysNow() { return visibleKeys(S.st.tab, S.st.group, S.st.season, S.custom[S.st.tab]); }` 줄 바로 다음에 넣습니다.

```js

  /** 진행 중인 시즌(없으면 null)입니다. 한국 시각 올해 시즌만 진행 중일 수 있습니다. */
  function liveYear() {
    return S.liveState && S.liveState.live ? S.liveState.season : null;
  }
```

(5) `rankNow` 의 주석 첫 줄과 첫 조건을 바꿉니다.

`   * 규정에 쓸 순위표 { rank, live } 입니다. 올해는 실시간 순위, 아니면 저장된`
→ `   * 규정에 쓸 순위표 { rank, live } 입니다. 진행 중인 시즌은 실시간 순위, 아니면 저장된`

`    if (y === S.latest && S.standings) {` → `    if (y === liveYear() && S.standings) {`

(6) `ensureData`: `    if (st.min === 'q' && y === S.latest && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));`
→ `    if (st.min === 'q' && y === liveYear() && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));`

(7) `render()` 의 `    errAlerts(alerts, S.refs.errors);` 줄 바로 다음에 넣습니다.

```js
    // 진행 중 판단을 못 받았으면 올해 시즌을 진행 중으로 보고 있음을 알립니다(올해 시즌을 볼 때만).
    if (S.liveState && S.liveState.failed && y === S.liveState.season) alerts.push({ kind: 'warn', text: TS.season.FAIL_TEXT });
```

(8) `    $('caveat-note').textContent = caveatText(st, S.latest, live);`
→ `    $('caveat-note').textContent = caveatText(st, liveYear(), live);`

(9) `init()` 의 받기 부분을 바꿉니다.

```js
      const base = root.KBO_API_BASE;
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.latest = S.seasons[0];
```
→
```js
      const base = root.KBO_API_BASE;
      // 한국 시각 올해 시즌만 진행 중일 수 있어, 그 해 판단을 시즌 목록과 함께 받습니다.
      const kst = TS.season.kstToday();
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base), TS.season.loadSeasonState(base, kst.y)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.liveState = got[2];
      if (S.liveState.failed) console.warn(TS.season.FAIL_TEXT, S.liveState.error);
```

- [ ] **Step 4: player-stats.html 에 season.js 싣기**

`    <script src="../js/stats/data.js"></script>` 줄 바로 다음에 넣습니다.

```html
    <script src="../js/stats/season.js"></script>
```

- [ ] **Step 5: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **208개 통과**(206 + 2), 실패 0. 그리고:

```bash
cd C:/Users/김승곤/Desktop/b_project
git ls-files --eol dashboard_js/js/player-stats/page.js dashboard_js/pages/player-stats.html
grep -c $'\xEF\xBB\xBF' dashboard_js/js/player-stats/page.js dashboard_js/pages/player-stats.html
```

Expected: 둘 다 `w/lf`, BOM `0`.

- [ ] **Step 6: 캡처**

먼저 2026 이 진행 중인지 다시 봅니다(A: 최근 경기 정규시즌, B: 포스트시즌).

```bash
curl -s "https://kbo-api.bstats-baseball.workers.dev/games?season=2026&limit=80" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const g=JSON.parse(s).games;const r=g.find(x=>x.game_type==='정규시즌');console.log('최근', g[0].game_date, g[0].game_type, '/ 마지막 정규시즌', r && r.game_date)})"
mkdir -p "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup"
cd C:/tmp/bstats-team-stats-check
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ps_2026 "/pages/player-stats.html?season=2026"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs ps_2025 "/pages/player-stats.html?season=2025"
for n in ps_2026 ps_2025; do mv "C:/Users/김승곤/Desktop/bstats_lin_$n.png" "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup/$n.png"; done
```

| 캡처 | 맞아야 하는 것 |
|---|---|
| ps_2026 | A: 표 아래 주의 문구에 "진행 중인 시즌의 소속팀 경기 수는 KBO 실시간 순위입니다."와 "진행 중인 시즌은 최신 일일 갱신 기준…", 제목 "타자 (2026, 규정 이상 N명)" 의 N 이 0 보다 큼. B: 두 문장 없음. 둘 다 알림 줄에 "진행 중 여부를 확인하지 못해…" 없음 |
| ps_2025 | 두 문장 없음, 제목 "타자 (2025, 규정 이상 N명)" 의 N 이 0 보다 큼 |

PNG 는 Read 로 엽니다. 맞지 않으면 Task 4 파일 안에서 고치고 시험·캡처를 다시 합니다.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git diff --cached --name-status
git commit -m "fix(player-stats): 규정용 실시간 순위·진행 중 안내를 진행 중 판단으로

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/player-stats/page.js dashboard_js/pages/player-stats.html
```

---

### Task 5: 요인 통계의 진행 중 문장·배지와 두 표 끝까지 받기

설계는 "season.js 싣기"만 적었지만, 두 표를 500행씩 끝까지 받는 일은 Task 2 의 `getTable`(시험된 이어 받기)을 그대로 쓰려고 `data.js` 도 함께 싣습니다(인라인으로 같은 고리를 한 번 더 쓰지 않음).

**Files:**
- Modify: `dashboard_js/pages/factor-stats.html` (CRLF)
- Test (저장소 밖): `season.pages.test.js`(더함)

**Interfaces:**
- Consumes: Task 2 `TeamStats.data.getTable(base, name)` → `{ ok, data } | { ok: false, error }`. Task 1 `TeamStats.season.kstToday()`, `.loadSeasonState(base, season)`, `.FAIL_TEXT`.
- Produces: 페이지 id `pf-live-note`(문장 묶음, 진행 중 시즌이 없으면 `hidden`)·`pf-live-year`(연도 칸). 인라인 전역 `LIVE_YEAR`(진행 중인 시즌 또는 `null`).

- [ ] **Step 1: 시험 먼저 쓰기**

`season.pages.test.js` 끝에 붙입니다.

```js

test('factor-stats.html: data.js·season.js 를 싣고 2026 을 글자로 두지 않음, 두 표는 끝까지', () => {
  const html = read('pages/factor-stats.html');
  assert.deepEqual(scripts(html), ['../js/config.js', '../js/theme-toggle.js', '../js/nav.js', '../js/stats/data.js', '../js/stats/season.js']);
  assert.ok(!html.includes('2026'), '연도 2026 이 글자로 남아 있습니다');
  assert.ok(!/season >= \d{4}/.test(html));
  assert.match(html, /<span id="pf-live-note" hidden><strong id="pf-live-year"><\/strong>은 진행 중이라 표본이 누적되며 값이 안정화됩니다\.<\/span>/);
  assert.equal((html.match(/\$\{season === LIVE_YEAR \? '<span class="badge-live">진행 중<\/span>' : ''\}/g) || []).length, 2);
  assert.match(html, /const r = await D\.getTable\(API, name\);/);
  assert.ok(!html.includes('?limit=500'), '500행만 받는 주소가 남아 있습니다');
  assert.match(html, /SEASON\.loadSeasonState\(API, kst\.y\)/);
  assert.match(html, /LIVE_YEAR = live\.live \? live\.season : null;/);
  assert.match(html, /document\.getElementById\('pf-live-note'\)\.hidden = !LIVE_YEAR;/);
  assert.match(html, /if \(live\.failed\) console\.warn\(SEASON\.FAIL_TEXT, live\.error\);/);
});
```

- [ ] **Step 2: 실패 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test season.pages.test.js`
Expected: factor-stats 시험 FAIL(스크립트 목록·'2026' 글자).

- [ ] **Step 3: factor-stats.html 고치기** (먼저 `git diff --quiet HEAD -- dashboard_js/pages/factor-stats.html; echo $?` 가 `0`)

(1) 머리의 `    <script src="../js/nav.js"></script>` 줄 바로 다음에 넣습니다.

```html
    <script src="../js/stats/data.js"></script>
    <script src="../js/stats/season.js"></script>
```

(2) 파크 팩터 안내 상자의 셋째 줄
`                <strong>2026</strong>은 진행 중 시즌이라 표본이 누적되며 값이 안정화됩니다.`
→
`                <span id="pf-live-note" hidden><strong id="pf-live-year"></strong>은 진행 중이라 표본이 누적되며 값이 안정화됩니다.</span>`

(연도 칸에는 "2026 시즌" 처럼 "시즌"까지 넣어, 연도 끝자리에 따라 은/는 이 바뀌는 문제를 피합니다.)

(3) 인라인 스크립트 머리를 바꿉니다.

```js
        // 주소는 js/config.js 가 정합니다.
        const API = window.KBO_API_BASE;
```
→
```js
        // 주소는 js/config.js 가 정합니다.
        const API = window.KBO_API_BASE;
        // 표 이어 받기는 js/stats/data.js, 진행 중 판단은 js/stats/season.js 가 합니다.
        const D = window.TeamStats.data, SEASON = window.TeamStats.season;
```

(4) `dbTable` 과 그 아래 전역 줄을 바꿉니다.

```js
        async function dbTable(name) {
            const r = await fetch(`${API}/db/table/${name}?limit=500`);
            if (!r.ok) throw new Error(`${name} → ${r.status}`);
            return (await r.json()).rows;
        }

        let PF_ROWS = [], RE_ROWS = [], RE_MIN = 0, RE_MAX = 1;
```
→
```js
        // /db/table 은 한 번에 500행까지라 끝까지 이어 받습니다. 중간에 실패하면 표 전체를 실패로 봅니다.
        async function dbTable(name) {
            const r = await D.getTable(API, name);
            if (!r.ok) throw new Error(`${name} → ${r.error}`);
            return r.data;
        }

        // LIVE_YEAR: 진행 중인 시즌(없으면 null). init 에서 채웁니다.
        let PF_ROWS = [], RE_ROWS = [], RE_MIN = 0, RE_MAX = 1, LIVE_YEAR = null;
```

(5) 두 곳(파크 팩터·RE24 제목)의 배지 줄
`                    ${season >= 2026 ? '<span class="badge-live">진행 중</span>' : ''}`
를 모두(replace_all)
`                    ${season === LIVE_YEAR ? '<span class="badge-live">진행 중</span>' : ''}`
로 바꿉니다.

(6) `init` 의 앞부분을 바꿉니다.

```js
                const [pf, re24] = await Promise.all([dbTable('self_park_factor'), dbTable('re24_matrix_by_season')]);
                PF_ROWS = pf;
                RE_ROWS = re24.filter(r => r.season !== 0);     // 통합(0) 제외
                RE_MIN = Math.min(...RE_ROWS.map(r => r.re_value));
                RE_MAX = Math.max(...RE_ROWS.map(r => r.re_value));
                // 시즌 목록(내림차순) — 두 데이터 합집합, 2026 최상단(기본 선택)
```
→
```js
                // 진행 중 판단을 못 받으면 올해를 진행 중으로 보고 콘솔에만 남깁니다(설계 6장).
                const kst = SEASON.kstToday();
                const [pf, re24, live] = await Promise.all([
                    dbTable('self_park_factor'), dbTable('re24_matrix_by_season'), SEASON.loadSeasonState(API, kst.y),
                ]);
                if (live.failed) console.warn(SEASON.FAIL_TEXT, live.error);
                LIVE_YEAR = live.live ? live.season : null;
                document.getElementById('pf-live-year').textContent = LIVE_YEAR ? `${LIVE_YEAR} 시즌` : '';
                document.getElementById('pf-live-note').hidden = !LIVE_YEAR;
                PF_ROWS = pf;
                RE_ROWS = re24.filter(r => r.season !== 0);     // 통합(0) 제외
                RE_MIN = Math.min(...RE_ROWS.map(r => r.re_value));
                RE_MAX = Math.max(...RE_ROWS.map(r => r.re_value));
                // 시즌 목록(내림차순): 두 데이터 합집합, 가장 최근 시즌이 맨 위(기본 선택)
```

- [ ] **Step 4: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **209개 통과**(208 + 1), 실패 0. 그리고:

```bash
cd C:/Users/김승곤/Desktop/b_project
git ls-files --eol dashboard_js/pages/factor-stats.html
grep -c $'\xEF\xBB\xBF' dashboard_js/pages/factor-stats.html
```

Expected: `i/crlf w/crlf`, BOM `0`.

- [ ] **Step 5: 캡처**

```bash
curl -s "https://kbo-api.bstats-baseball.workers.dev/games?season=2026&limit=80" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>{const g=JSON.parse(s).games;const r=g.find(x=>x.game_type==='정규시즌');console.log('최근', g[0].game_date, g[0].game_type, '/ 마지막 정규시즌', r && r.game_date)})"
mkdir -p "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup"
cd C:/tmp/bstats-team-stats-check
MSYS_NO_PATHCONV=1 node lineage_shot.mjs factor "/pages/factor-stats.html"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs factor_re24 "/pages/factor-stats.html" --click '.fs-tab[data-panel="re24"]'
for n in factor factor_re24; do mv "C:/Users/김승곤/Desktop/bstats_lin_$n.png" "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup/$n.png"; done
```

| 캡처 | 맞아야 하는 것 |
|---|---|
| factor | A(2026 진행 중): 안내 상자 끝 "2026 시즌은 진행 중이라 표본이 누적되며 값이 안정화됩니다.", "2026 시즌" 제목 옆 '진행 중' 배지, 구장 표가 바꾸기 전처럼 채워짐. B: 그 문장·배지 없음 |
| factor_re24 | RE24 표 8줄 × 3칸이 채워짐, A 면 제목 옆 '진행 중' 배지, B 면 없음 |

PNG 는 Read 로 엽니다. 맞지 않으면 Task 5 파일 안에서 고치고 시험·캡처를 다시 합니다.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git diff --cached --name-status
git commit -m "fix(factor-stats): 진행 중 문장·배지를 진행 중 판단으로, 두 표를 끝까지 받기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/pages/factor-stats.html
```

---

### Task 6: 아티클·홈·api.js 정리와 계보 다시 만들기

`js/api.js` 는 선수 분석 세션이 자주 고치는 파일이라(계획을 쓰는 동안에도 커밋 안 된 변경이 있었음) Step 1 의 확인을 통과할 때만 고치고 따로 커밋합니다. 통과하지 못하면 api.js 단계와 그 시험을 건너뛰고 보고합니다.

**Files:**
- Modify: `dashboard_js/pages/article.html` (CRLF), `dashboard_js/index.html` (LF), `dashboard_js/js/api.js` (LF, 조건부)
- Maybe: `dashboard_js/data/table_lineage.json` (계보 다시 만들기로 바뀌면)
- Test (저장소 밖): `season.pages.test.js`(더함)

**Interfaces:**
- Consumes: 없음(이 세 파일은 season.js 를 싣지 않습니다. 아티클 기본 시즌은 `/wrc/seasons` 의 `n_batters` 로 정합니다).
- Produces: article.html 인라인 `defaultWrcSeason(rows)` → 시즌 숫자 | `null`. index.html `SCHED_META.<mode>.idle` 글자.

- [ ] **Step 1: 고칠 파일이 깨끗한지 보기**

```bash
cd C:/Users/김승곤/Desktop/b_project
for f in dashboard_js/pages/article.html dashboard_js/index.html dashboard_js/js/api.js; do git diff --quiet HEAD -- $f; echo "$f $?"; done
```

article.html·index.html 이 `1` 이면 멈추고 보고합니다. api.js 가 `1` 이면 아래에서 (api) 표시가 붙은 것을 모두 건너뜁니다.

- [ ] **Step 2: 시험 먼저 쓰기**

`season.pages.test.js` 끝에 붙입니다(api.js 를 건너뛰면 마지막 시험 하나는 붙이지 않습니다).

```js

test('article.html: 기본 시즌은 규정 타자 20명 이상인 가장 최근 시즌, 산출 당시 문구', () => {
  const html = read('pages/article.html');
  assert.ok(html.includes('2015~2025시즌(산출 당시 진행 중이던 2026은 제외)'));
  assert.ok(!html.includes('부분 시즌인 2026은 제외'));
  const m = /function defaultWrcSeason\(rows\) \{[\s\S]*?\r?\n    \}/.exec(html);
  assert.ok(m, 'defaultWrcSeason 이 없습니다');
  const pick = new Function(m[0] + '\nreturn defaultWrcSeason;')();
  assert.equal(pick([{ season: 2026, n_batters: 3 }, { season: 2025, n_batters: 80 }, { season: 2024, n_batters: 89 }]), 2025);
  assert.equal(pick([{ season: 2025, n_batters: 80 }, { season: 2026, n_batters: 20 }]), 2026);
  assert.equal(pick([{ season: 2026, n_batters: 3 }, { season: 2025, n_batters: 5 }]), 2026);
  assert.equal(pick([]), null);
  assert.match(html, /const def = defaultWrcSeason\(seasons\);\r?\n        if \(def !== null\) sel\.value = String\(def\);/);
});

test('index.html: 일정 출처는 시범경기·정규시즌·포스트시즌, 7일 안에 경기가 없으면 오늘에 두고 알림', () => {
  const html = read('index.html');
  assert.ok(!html.includes('(KBO 정규시즌)'));
  assert.equal((html.match(/데이터 출처: Naver 스포츠 \(KBO 시범경기·정규시즌·포스트시즌\) · 30초 캐시/g) || []).length, 2);
  assert.ok(html.includes("idle: '앞으로 7일 안에 KBO 경기가 없습니다(비시즌일 수 있습니다).',"));
  assert.ok(html.includes("idle: '앞으로 7일 안에 퓨처스 경기가 없습니다(비시즌일 수 있습니다).',"));
  assert.match(html, /const start = new Date\(curDate\);/);
  assert.match(html, /curDate = none && autoSkipDays > 0 \? start : d;/);
  assert.match(html, /\$\{autoSkipDays > 0 \? meta\.idle : meta\.empty\}/);
});

test('api.js: 낡은 시즌 기본값(season = 2025) 없음', () => {
  const src = read('js/api.js');
  assert.ok(!/season = 20\d\d/.test(src));
  assert.match(src, /static async getBatterStats\(season, limit = 100, min_pa = 0, teamIds = null\)/);
  assert.match(src, /static async getPitcherStats\(season, limit = 100, min_ip = 0, teamIds = null\)/);
  assert.match(src, /static async getGames\(season, limit = 50\)/);
});
```

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test season.pages.test.js`
Expected: 새 시험 3개(api 를 건너뛰면 2개) FAIL.

- [ ] **Step 3: article.html 고치기**

(1) 1단계 문단의 `2015~2025시즌(부분 시즌인 2026은 제외)` → `2015~2025시즌(산출 당시 진행 중이던 2026은 제외)` (그 문단의 다른 글자는 그대로).

(2) `    async function init() {` 줄 바로 앞에 넣습니다.

```js
    // 기본 시즌: 300타석 이상 타자(n_batters)가 20명 이상인 가장 최근 시즌, 없으면 가장 최근 시즌입니다.
    // 새 시즌 초반에는 규정 타자가 몇 명뿐이라 첫 화면에 두지 않습니다.
    function defaultWrcSeason(rows) {
        const list = (rows || []).slice().sort((a, b) => b.season - a.season);
        const ok = list.find(s => (s.n_batters || 0) >= 20);
        return ok ? ok.season : (list.length ? list[0].season : null);
    }

```

(3) `init()` 안에서 `        });` (option 을 붙이는 forEach 끝) 다음, `        sel.addEventListener('change', () => render(parseInt(sel.value, 10)));` 바로 앞에 넣습니다.

```js
        const def = defaultWrcSeason(seasons);
        if (def !== null) sel.value = String(def);
```

- [ ] **Step 4: index.html 고치기**

(1) 경기 칸 아래 출처: `            <p class="schedule-note" id="schedule-note">데이터 출처: Naver 스포츠 (KBO 정규시즌) · 30초 캐시</p>`
→ `            <p class="schedule-note" id="schedule-note">데이터 출처: Naver 스포츠 (KBO 시범경기·정규시즌·포스트시즌) · 30초 캐시</p>`

(2) `SCHED_META` 를 바꿉니다.

```js
        // 일정 모드(1군/퓨처스)별 엔드포인트·출처문구·빈메시지·렌더러
        const SCHED_META = {
            main: {
                ep: 'schedule',
                note: '데이터 출처: Naver 스포츠 (KBO 정규시즌) · 30초 캐시',
                empty: '이 날짜에 KBO 경기가 없습니다.',
                render: renderGame,
            },
            futures: {
                ep: 'schedule/futures',
                note: '데이터 출처: KBO 공식 (퓨처스리그 실시간) · 30초 캐시',
                empty: '이 날짜에 퓨처스 경기가 없습니다.',
                render: renderFuturesGame,
            },
        };
```
→
```js
        // 일정 모드(1군/퓨처스)별 엔드포인트·출처문구·빈메시지(그날 empty, 앞으로 7일 idle)·렌더러
        const SCHED_META = {
            main: {
                ep: 'schedule',
                note: '데이터 출처: Naver 스포츠 (KBO 시범경기·정규시즌·포스트시즌) · 30초 캐시',
                empty: '이 날짜에 KBO 경기가 없습니다.',
                idle: '앞으로 7일 안에 KBO 경기가 없습니다(비시즌일 수 있습니다).',
                render: renderGame,
            },
            futures: {
                ep: 'schedule/futures',
                note: '데이터 출처: KBO 공식 (퓨처스리그 실시간) · 30초 캐시',
                empty: '이 날짜에 퓨처스 경기가 없습니다.',
                idle: '앞으로 7일 안에 퓨처스 경기가 없습니다(비시즌일 수 있습니다).',
                render: renderFuturesGame,
            },
        };
```

(3) `loadSchedule` 를 통째로 바꿉니다(바로 위 주석 한 줄 포함).

```js
        // autoSkipDays: 초기 로드/오늘 버튼 시 경기 있는 날까지 앞으로 최대 N일 자동 전진
        async function loadSchedule(autoSkipDays = 0) {
            const grid = document.getElementById('games-grid');
            grid.innerHTML = '<div class="schedule-msg">불러오는 중…</div>';
            let d = new Date(curDate);
            let data = null;
            try {
                for (let i = 0; i <= autoSkipDays; i++) {
                    document.getElementById('date-label').textContent = fmtLabel(d);
                    data = await fetchSchedule(d);
                    if (data && data.games && data.games.length > 0) break;
                    if (i < autoSkipDays) d.setDate(d.getDate() + 1);
                }
            } catch (e) {
                document.getElementById('date-label').textContent = fmtLabel(curDate);
                grid.innerHTML = '<div class="schedule-msg error">일정을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</div>';
                return;
            }
            curDate = d;
            document.getElementById('date-label').textContent = fmtLabel(curDate);
            const meta = SCHED_META[scheduleMode];
            if (!data || !data.games || data.games.length === 0) {
                grid.innerHTML = `<div class="schedule-msg">${meta.empty}</div>`;
                return;
            }
            grid.innerHTML = data.games.map(meta.render).join('');
        }
```
→
```js
        // autoSkipDays: 초기 로드/오늘 버튼 시 경기 있는 날까지 앞으로 최대 N일 자동 전진.
        // 그 안에 경기가 하나도 없으면(비시즌 등) 날짜를 처음 날(오늘)에 두고 meta.idle 을 보입니다.
        async function loadSchedule(autoSkipDays = 0) {
            const grid = document.getElementById('games-grid');
            grid.innerHTML = '<div class="schedule-msg">불러오는 중…</div>';
            const start = new Date(curDate);
            let d = new Date(curDate);
            let data = null;
            try {
                for (let i = 0; i <= autoSkipDays; i++) {
                    document.getElementById('date-label').textContent = fmtLabel(d);
                    data = await fetchSchedule(d);
                    if (data && data.games && data.games.length > 0) break;
                    if (i < autoSkipDays) d.setDate(d.getDate() + 1);
                }
            } catch (e) {
                document.getElementById('date-label').textContent = fmtLabel(curDate);
                grid.innerHTML = '<div class="schedule-msg error">일정을 불러오지 못했습니다. 잠시 후 다시 시도해주세요.</div>';
                return;
            }
            const meta = SCHED_META[scheduleMode];
            const none = !data || !data.games || data.games.length === 0;
            curDate = none && autoSkipDays > 0 ? start : d;
            document.getElementById('date-label').textContent = fmtLabel(curDate);
            if (none) {
                grid.innerHTML = `<div class="schedule-msg">${autoSkipDays > 0 ? meta.idle : meta.empty}</div>`;
                return;
            }
            grid.innerHTML = data.games.map(meta.render).join('');
        }
```

- [ ] **Step 5: (api) api.js 기본값 지우기**

세 줄만 바꿉니다(부르는 곳은 모두 시즌을 줍니다: `player-analytics.html` 의 `API.getPitcherStats(season, 2000, 0)`, `getBatterStats`·`getGames` 는 지금 부르는 곳 없음).

- `    static async getBatterStats(season = 2025, limit = 100, min_pa = 0, teamIds = null) {` → `    static async getBatterStats(season, limit = 100, min_pa = 0, teamIds = null) {`
- `    static async getPitcherStats(season = 2025, limit = 100, min_ip = 0, teamIds = null) {` → `    static async getPitcherStats(season, limit = 100, min_ip = 0, teamIds = null) {`
- `    static async getGames(season = 2025, limit = 50) {` → `    static async getGames(season, limit = 50) {`

- [ ] **Step 6: 통과 확인**

Run: `cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8`
Expected: **212개 통과**(209 + 3), api 를 건너뛰었으면 **211개**, 실패 0. 그리고:

```bash
cd C:/Users/김승곤/Desktop/b_project
git ls-files --eol dashboard_js/pages/article.html dashboard_js/index.html dashboard_js/js/api.js
grep -c $'\xEF\xBB\xBF' dashboard_js/pages/article.html dashboard_js/index.html dashboard_js/js/api.js
```

Expected: article `w/crlf`, index·api `w/lf`, BOM 모두 `0`.

- [ ] **Step 7: 캡처**

```bash
mkdir -p "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup"
cd C:/tmp/bstats-team-stats-check
MSYS_NO_PATHCONV=1 node lineage_shot.mjs article_text "/pages/article.html#wrc-plus"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs article_check "/pages/article.html#wrc-plus" --click '.atab[data-tab="check"]' --click '.atab[data-tab="check"]' --click '.atab[data-tab="check"]' --click '.atab[data-tab="check"]'
MSYS_NO_PATHCONV=1 node lineage_shot.mjs index "/index.html"
for n in article_text article_check index; do mv "C:/Users/김승곤/Desktop/bstats_lin_$n.png" "C:/Users/김승곤/Desktop/bstats_미리보기/season_cleanup/$n.png"; done
```

(확인하기 탭을 거듭 누르는 것은 차트가 그려질 시간을 버는 것입니다. 두 번째부터는 다시 불러오지 않습니다.)

| 캡처 | 맞아야 하는 것 |
|---|---|
| article_text | '글' 탭 1단계 문단에 "2015~2025시즌(산출 당시 진행 중이던 2026은 제외)" |
| article_check | 시즌 고르개 기본값이 n 이 20 이상인 가장 최근 시즌(계획을 쓴 때 `/wrc/seasons` 기준 "2026 (n=79)"), 그 시즌 KPI·차트가 채워짐 |
| index | KBO 경기 칸 아래 "데이터 출처: Naver 스포츠 (KBO 시범경기·정규시즌·포스트시즌) · 30초 캐시", 오늘이나 7일 안 경기일의 경기 카드(7일 안에 경기가 없으면 날짜가 오늘이고 "앞으로 7일 안에 KBO 경기가 없습니다(비시즌일 수 있습니다).") |

PNG 는 Read 로 엽니다. 맞지 않으면 Task 6 파일 안에서 고치고 시험·캡처를 다시 합니다.

- [ ] **Step 8: 아티클·홈 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git diff --cached --name-status
git commit -m "fix(article,home): 아티클 기본 시즌·산출 당시 문구, 홈 일정 출처와 7일 빈 일정 안내

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/pages/article.html dashboard_js/index.html
```

- [ ] **Step 9: (api) api.js 커밋**

커밋 직전에 다시 `git diff HEAD -- dashboard_js/js/api.js` 를 보고, 바뀐 줄이 Step 5 의 세 줄뿐인지 확인합니다(다른 세션 변경이 그사이 들어왔으면 커밋하지 않고 보고).

```bash
cd C:/Users/김승곤/Desktop/b_project
git diff HEAD --stat -- dashboard_js/js/api.js
git commit -m "refactor(api): 낡은 시즌 기본값(2025) 지우기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/api.js
```

Expected: `--stat` 이 `3 insertions(+), 3 deletions(-)`.

- [ ] **Step 10: 계보 다시 만들기와 저장소 시험**

```bash
cd C:/Users/김승곤/Desktop/b_project
PYTHONUTF8=1 py scripts/build_lineage.py
PYTHONUTF8=1 py -m pytest tests -q 2>&1 | tail -3
git diff --stat dashboard_js/data/table_lineage.json
git diff dashboard_js/data/table_lineage.json | grep '^[-+]' | grep -v '^[-+][-+]' | head -80
```

pytest 는 모두 통과해야 합니다(실패하면 이름·메시지를 보고하고 고치지 않습니다. `tests/` 는 읽기 전용). `--stat` 이 비면 계보 내용이 그대로라 커밋하지 않습니다. 바뀌었으면 바뀐 줄이 이 계획의 페이지(team-stats·player-stats·factor-stats·article·index)의 routes·tables 와 그 표·주소의 pages 목록(예: player-stats·factor-stats 에 `/games` 가 붙음)뿐인지 봅니다. 그렇다면 커밋합니다.

```bash
git commit -m "chore(lineage): 진행 중 판단으로 바뀐 페이지 API 호출 반영

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/data/table_lineage.json
```

다른 페이지(예: player-analytics)가 바뀌었으면 다른 세션의 커밋 안 된 변경 때문이니 커밋하지 않고 바뀐 곳을 보고합니다(생성 파일이라 다음에 계보를 만드는 쪽이 다시 씁니다).

- [ ] **Step 11: 마무리 확인**

```bash
cd C:/tmp/bstats-team-stats-check/tests && node --test *.test.js 2>&1 | tail -8
cd C:/Users/김승곤/Desktop/b_project
git log --oneline -9
git status --short
grep -rn "getFullYear\|season >= 2026\|season = 2025" dashboard_js/js/stats dashboard_js/js/team-stats dashboard_js/js/player-stats dashboard_js/pages/factor-stats.html dashboard_js/js/api.js
```

Expected: 212(또는 211)개 통과, 이 계획의 커밋들이 보임, `git status` 에 이 계획 파일 말고 이 계획이 고친 파일이 남지 않음(api 를 건너뛰었으면 api.js 는 다른 세션 변경만 남음), 마지막 grep 출력 없음(api 를 건너뛰었으면 api.js 의 `season = 2025` 세 줄만).

---

## 설계 대응

| 설계 | 어디서 |
|---|---|
| §2 진행 중 = 정규시즌 끝날 때까지, /standings 는 진행 중에만, API 변경 없음 | Task 1(판단), Task 3·4(쓰는 곳) |
| §3 `season.js`: kstToday·isLive·summarize·loadSeasonState, 실패 모양 | Task 1 |
| §4 대체 시즌 목록(4월 전이면 작년)·6시간 유효기간·키 버전·이어 받기와 중간 실패 | Task 2 |
| §5 팀 통계(pbpMax 는 기록 있음에만, 실시간 순위·불일치 알림·두 안내, 기간 기본값) | Task 3 |
| §5 선수 통계(규정 실시간 순위·두 안내) | Task 4 |
| §5 요인 통계(season.js, 문장·배지, 두 표 끝까지) | Task 5 |
| §5 아티클·홈·api.js | Task 6 |
| §5 선수 분석 퀵룩 | 범위 밖: 선수 분석 세션 몫(브라우저 연도 대신 min(한국 시각 올해, 최신 시즌), `TeamStats.season.kstToday` 를 쓸 수 있음) |
| §6 오류(판단 실패 알림·콘솔, 시즌 목록 실패, 이어 받기 실패) | Task 1(FAIL_TEXT·실패 모양), Task 2, Task 3·4(알림), Task 5(콘솔) |
| §7 검증(Node 시험·캡처·계보·pytest) | 각 Task 시험·캡처, Task 6 Step 10 |

범위 밖으로 남는 일: push·Pages 배포(evan 허락 뒤, 각각), 배포 전 선수 분석 세션과 맞추기, 2026 포스트시즌이 시작된 뒤 운영에서 팀·선수·요인 통계가 저절로 '끝난 시즌' 모양이 되는지 한 번 더 보기.
