# 선수 통계 팬그래프 방식 개편 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bstats 선수 통계 페이지(`dashboard_js/pages/player-stats.html`)를 팀 통계와 같은 틀(묶음 탭·고급 지표·지수 색·설명 창·규정 이상·쪽 넘기기·CSV·주소 저장)로 새로 씁니다.

**Architecture:** 팀 통계의 공용 부품(metrics·columns·data·table)을 `dashboard_js/js/stats/` 로 옮기고 스타일을 `dashboard_js/css/stats.css` 로 뺍니다. 공용 부품에 선수용 함수(선수 행·규정 판정·선수 칸·앞 칸 구성·쪽 나누기)를 더하고, 선수 페이지 조립은 `dashboard_js/js/player-stats/page.js` 가 맡습니다. 순수 함수는 Node 로, 화면은 헤드리스 Edge(DOM 덤프·PNG)로 확인합니다.

**Tech Stack:** 순수 JavaScript(빌드 도구 없음, `<script>` 태그), Node 24 내장 테스트(`node --test`), Python 미리보기 서버, 헤드리스 Edge.

**설계 문서:** `C:/Users/김승곤/Desktop/b_project/docs/superpowers/specs/2026-10-04-player-stats-fangraphs-design.md`

## Global Constraints

- 저장소: `C:/Users/김승곤/Desktop/b_project` (브랜치 `main`, 다른 세션과 폴더를 같이 씀).
- **고칠 수 있는 곳은 `dashboard_js/` 안뿐입니다.** `src/`, `crawler/`, `migration/`, `test/`, `tests/`, `data_collection/`, `park_factors/`, `wrangler.toml`, `package*.json`, `.github/` 는 읽기만 합니다.
- **git:** 브랜치를 바꾸지 않습니다. `git add -A`, `git add .`, `git commit -a`, `git stash`, `git reset`, `git restore`, `git checkout --` 를 쓰지 않습니다. 커밋 전에 `git status --short` 와 `git diff --cached --name-status` 를 보고, 자기 파일만 고릅니다. 커밋은 `git commit -m "…" -- <자기 파일들>` 처럼 경로를 붙여 합니다(옆 세션이 올려 둔 파일이 섞이지 않게). 다른 변경(예: `src/`)이 보이면 옆 세션 것이니 그대로 둡니다.
- 커밋 메시지는 `feat(player-stats): 한국어 설명` 형식이고(범위는 `stats`·`player-stats`·`team-stats` 중 맞는 것), 끝에 빈 줄 다음 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙입니다.
- **push·배포는 하지 않습니다.** evan 이 건마다 허락합니다.
- **DB 에 쓰지 않습니다.** 데이터 확인은 배포된 API(`https://kbo-api.bstats-baseball.workers.dev`)를 부르되 같은 주소를 반복해서 부르지 않습니다. 화면 확인(캡처·DOM 덤프)은 계획에 적힌 것만 합니다. 시험 데이터는 `C:/tmp/bstats-team-stats-check/fixtures/` 에 이미 있습니다.
- **팀 통계 화면은 바뀌면 안 됩니다.** `dashboard_js/js/team-stats/page.js`·`record.js` 는 고치지 않습니다(설계 6장). 공용 파일(metrics·columns·data·table·stats.css)은 기존 동작을 그대로 두고 덧붙이기만 합니다. 팀 통계 Node 테스트 78개가 계속 통과해야 합니다.
- 전역 이름은 그대로 `window.TeamStats` 입니다. 모듈 틀:

```js
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  // ...
  TS.<이름> = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- 저장소 `package.json` 이 `"type": "module"` 이라 Node 테스트는 `require` 가 아니라 `vm.runInThisContext` 로 모듈을 읽습니다(`tests/_load.js`). 파일 이름을 `.cjs` 로 바꾸지 않습니다.
- 저장소 파일은 CRLF 줄끝입니다(`core.autocrlf=true`). 파일을 스크립트로 고칠 때 `\r?\n` 을 생각합니다.
- 검증 스크립트는 저장소 밖 `C:/tmp/bstats-team-stats-check/tests/` 에 둡니다. 전체 실행: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`.
- 미리보기는 `127.0.0.2:8765` 입니다(`C:/tmp/bstats-team-stats-check/preview.py`, `dashboard_js` 를 그대로 내보냄). `localhost`·`127.0.0.1` 로 열면 `js/config.js` 가 API 를 `localhost:8000` 으로 돌려 데이터가 안 나옵니다.
- 캡처는 헤드리스 Edge 로 하고, 호출마다 `--user-data-dir` 를 다르게 줍니다(`shot.sh`·`dom.sh`·`mobile_shot.mjs` 가 그렇게 합니다). PNG 는 바탕화면(`C:/Users/김승곤/Desktop/bstats_ts_<이름>.png`)에 둡니다.
- 사용자에게 보이는 글은 `습니다/합니다` 정중체, 짧은 문장, 쉬운 말로 씁니다. 이모지와 줄표(—)는 쓰지 않습니다.
- API 응답이 이상하면(빈 목록, `detail`·`error` 필드) 화면에서 가리지 말고 표 위 알림으로 보여 줍니다. 계산할 수 없는 값은 0 이 아니라 `null`(화면 '-')입니다.
- 지수 칸 색: 좋을수록 빨강(`ts-up*`), 나쁠수록 파랑(`ts-down*`). 링크 복사 버튼의 `title` 은 "지금 보는 화면 그대로 열리는 주소를 복사합니다." 입니다.

## 파일 구조

| 파일 | 책임 | 바뀌는 것 |
|---|---|---|
| `dashboard_js/js/stats/metrics.js` | 공용 계산 | 팀 통계에서 옮김(Task 1). 타격·투구 표를 "기준값 + 한 줄" 함수로 나누고 선수 표·규정 판정을 더함(Task 2) |
| `dashboard_js/js/stats/columns.js` | 칸 정의·값 형식 | 옮김. 선수 칸(`PBAT`·`PPIT`·`PGROUPS`·`PORDER`·`pdef`)을 더함(Task 3) |
| `dashboard_js/js/stats/data.js` | API 받기 | 옮김. `loadRegulation` 을 더함(Task 3) |
| `dashboard_js/js/stats/table.js` | 표 HTML·CSV | 옮김. 앞 칸 구성(`idCols`)과 쪽 나누기(`page`·`pageOf`)를 더함(Task 4) |
| `dashboard_js/css/stats.css` | 팀·선수 통계 공용 스타일 | team-stats.html 의 `<style>` 을 옮김(Task 1). 선수 칸·쪽 넘기기 규칙을 뒤에 붙임(Task 4·6) |
| `dashboard_js/js/team-stats/record.js`, `page.js` | 팀 전용 | 고치지 않음 |
| `dashboard_js/pages/team-stats.html` | 팀 페이지 뼈대 | `<style>` 을 `stats.css` 링크로, 스크립트 경로를 `js/stats/` 로(Task 1) |
| `dashboard_js/js/player-stats/page.js` | 선수 페이지 상태·주소·조립·이벤트 | 새 파일(Task 5 순수 함수, Task 6 화면) |
| `dashboard_js/pages/player-stats.html` | 선수 페이지 뼈대 | 새로 씀(Task 6) |

검증 폴더(저장소 밖, 커밋하지 않음):

```
C:/tmp/bstats-team-stats-check/
  fixtures/  batters_2025.json pitchers_2025.json db_*.json ...  (이미 있음)
  tests/     _load.js(Task 1 에서 고침), 기존 *.test.js 9개(78개 시험),
             새 파일: layout.test.js, metrics.player.test.js, columns.player.test.js,
             data.player.test.js, table.player.test.js, player-page.test.js, player-html.test.js
  preview.py   미리보기 서버(127.0.0.2:8765)
  shot.sh      PNG 캡처: bash shot.sh <이름> <경로와 쿼리> [폭] [높이]
  dom.sh       DOM 덤프(Task 1 에서 만듦): bash dom.sh <경로와 쿼리> <저장 파일>
  mobile_shot.mjs  390px 휴대폰 캡처: node mobile_shot.mjs <이름> <경로와 쿼리>
```

---

### Task 1: 공용 부품을 js/stats·css/stats.css 로 옮기기(팀 통계 그대로)

**Files:**
- Move: `dashboard_js/js/team-stats/{metrics,columns,data,table}.js` → `dashboard_js/js/stats/`
- Create: `dashboard_js/css/stats.css`
- Modify: `dashboard_js/pages/team-stats.html` (23~110행 `<style>` 블록, 240~243행 스크립트)
- Modify (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/_load.js`
- Create (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/layout.test.js`, `C:/tmp/bstats-team-stats-check/dom.sh`, `C:/tmp/bstats-team-stats-check/move_css.cjs`

**Interfaces:**
- Consumes: 없음
- Produces: 공용 모듈 경로 `dashboard_js/js/stats/{metrics,columns,data,table}.js`, 공용 스타일 `dashboard_js/css/stats.css`. 테스트 도우미 `load(name)`(js/stats → js/team-stats 순서로 찾음), `loadAs(rel, globalName)`(예: `loadAs('player-stats/page', 'playerPage')`), `REPO_JS`. DOM 덤프 도우미 `dom.sh`.

- [ ] **Step 1: 테스트 도우미를 두 폴더에서 찾도록 고치기**

`C:/tmp/bstats-team-stats-check/tests/_load.js` 전체를 이렇게 바꿉니다.

```js
// 저장소의 통계 모듈과 시험 데이터를 불러옵니다.
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const REPO_JS = 'C:/Users/김승곤/Desktop/b_project/dashboard_js/js';
// 공용 모듈(js/stats)을 먼저 찾고, 팀 전용(js/team-stats)을 다음에 찾습니다.
const DIRS = ['stats', 'team-stats'];
const FIX = path.join(__dirname, '..', 'fixtures');

// 저장소 package.json 이 "type": "module" 이라, require 로 부르면 Node 가
// 이 파일들을 ES 모듈로 읽어 아무것도 내보내지 않습니다. 그래서 브라우저처럼
// 일반 스크립트로 실행하고, 전역 TeamStats 에 붙은 모듈을 꺼냅니다.
// 파일 이름을 .cjs 로 바꾸지 않습니다(브라우저가 .js 로 불러옵니다).
function run(file) {
  vm.runInThisContext(fs.readFileSync(file, 'utf8'), { filename: file });
}

function load(name) {
  const dir = DIRS.find(d => fs.existsSync(path.join(REPO_JS, d, name + '.js')));
  if (!dir) throw new Error(`${name}.js 를 ${DIRS.join(', ')} 에서 찾지 못했습니다`);
  run(path.join(REPO_JS, dir, name + '.js'));
  return globalThis.TeamStats[name];
}

/** 이름이 겹치는 모듈(예: player-stats/page.js)을 경로로 불러와 전역 이름으로 꺼냅니다. */
function loadAs(rel, globalName) {
  run(path.join(REPO_JS, rel + '.js'));
  return globalThis.TeamStats[globalName];
}

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(FIX, name + '.json'), 'utf8'));
}

function refs() {
  return {
    weights: fixture('db_kbo_woba_weights_by_season').rows,
    pf: fixture('db_self_park_factor').rows,
    stadium: fixture('db_team_stadium_by_season').rows,
    rank: fixture('db_team_season_rank').rows,
  };
}

const near = (a, b, eps) => Math.abs(a - b) <= (eps === undefined ? 1e-9 : eps);

module.exports = { load, loadAs, fixture, refs, near, REPO_JS };
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 78개 통과(아직 옮기기 전이라 js/team-stats 에서 찾습니다).

- [ ] **Step 2: 배치 시험을 쓰고 실패 확인**

`C:/tmp/bstats-team-stats-check/tests/layout.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { REPO_JS } = require('./_load');

const ROOT = path.join(REPO_JS, '..');
const has = rel => fs.existsSync(path.join(ROOT, rel));
const read = rel => fs.readFileSync(path.join(ROOT, rel), 'utf8');
const scripts = html => [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);

test('공용 모듈은 js/stats, 팀 전용은 js/team-stats', () => {
  for (const n of ['metrics', 'columns', 'data', 'table']) {
    assert.ok(has(`js/stats/${n}.js`), `js/stats/${n}.js 가 없습니다`);
    assert.ok(!has(`js/team-stats/${n}.js`), `js/team-stats/${n}.js 가 남아 있습니다`);
  }
  for (const n of ['record', 'page']) assert.ok(has(`js/team-stats/${n}.js`), n);
});

test('team-stats.html: stats.css 를 쓰고 스크립트를 이 순서로 부름', () => {
  const html = read('pages/team-stats.html');
  assert.deepEqual(scripts(html), [
    '../js/config.js', '../js/theme-toggle.js', '../js/nav.js',
    '../js/api.js', '../js/components.js',
    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/table.js',
    '../js/team-stats/record.js', '../js/team-stats/page.js',
  ]);
  assert.match(html, /href="\.\.\/css\/style\.css">\r?\n    <link rel="stylesheet" href="\.\.\/css\/stats\.css">/);
  assert.ok(!html.includes('<style>'));
});

test('stats.css: 팀 통계 규칙이 다 옮겨짐', () => {
  const css = read('css/stats.css');
  for (const s of ['[hidden] { display: none !important; }', '.fs-tab.active', '.ts-table th.ts-rank, .ts-table td.ts-rank',
    '.ts-up3', '.ts-hl td', '.ts-h2h td', '.tip-box .f', '.col-panel-head', '.ctrl-divider']) {
    assert.ok(css.includes(s), s);
  }
});

test('어느 파일도 옛 경로(js/team-stats/{metrics,columns,data,table}.js)를 부르지 않음', () => {
  const walk = d => fs.readdirSync(d, { withFileTypes: true })
    .flatMap(e => (e.isDirectory() ? walk(path.join(d, e.name)) : [path.join(d, e.name)]));
  for (const f of walk(ROOT).filter(x => /\.(html|js)$/.test(x))) {
    assert.ok(!/team-stats\/(metrics|columns|data|table)\.js/.test(fs.readFileSync(f, 'utf8')), f);
  }
});
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/layout.test.js"`
Expected: FAIL 4개(`js/stats/metrics.js 가 없습니다` 등).

- [ ] **Step 3: DOM 덤프 도우미를 만들고, 옮기기 전 팀 통계를 저장**

`C:/tmp/bstats-team-stats-check/dom.sh`:

```bash
#!/usr/bin/env bash
# 사용: dom.sh <경로와 쿼리> <저장 파일>
# 헤드리스 Edge 로 페이지를 열어 스크립트가 다 돈 뒤의 DOM 을 파일로 저장합니다.
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
[ -f "$EDGE" ] || EDGE="/c/Program Files/Microsoft/Edge/Application/msedge.exe"
UD="C:/tmp/bstats-team-stats-check/edge_ud/dom_$(date +%s%N)"
"$EDGE" --headless=new --disable-gpu --user-data-dir="$UD" --virtual-time-budget=20000 \
  --dump-dom "http://127.0.0.2:8765$1" > "$2" 2>/dev/null
```

미리보기 서버가 떠 있는지 봅니다.

Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.2:8765/pages/team-stats.html`
Expected: `200`. 아니면 백그라운드로 `py C:/tmp/bstats-team-stats-check/preview.py` 를 띄우고 다시 봅니다.

옮기기 전 상태를 저장합니다.

```bash
cd C:/tmp/bstats-team-stats-check
bash dom.sh "/pages/team-stats.html?season=2025" ts_before.html
bash shot.sh ts_before_move "/pages/team-stats.html?season=2025"
grep -o 'class="ts-rank"' ts_before.html | wc -l
```

Expected: `ts_before.html` 이 생기고 `ts-rank` 가 12 이상(머리글 + 팀 10 + 리그 행). 표는 한 줄로 덤프되므로 `grep -c` 가 아니라 `grep -o | wc -l` 로 셉니다. 바탕화면에 `bstats_ts_ts_before_move.png`.

- [ ] **Step 4: 모듈 네 개를 옮기기**

```bash
cd C:/Users/김승곤/Desktop/b_project
mkdir -p dashboard_js/js/stats
git mv dashboard_js/js/team-stats/metrics.js dashboard_js/js/stats/metrics.js
git mv dashboard_js/js/team-stats/columns.js dashboard_js/js/stats/columns.js
git mv dashboard_js/js/team-stats/data.js dashboard_js/js/stats/data.js
git mv dashboard_js/js/team-stats/table.js dashboard_js/js/stats/table.js
```

파일 내용은 이 Task 에서 고치지 않습니다(이름 바꾸기만 남게).

- [ ] **Step 5: 스타일을 stats.css 로 옮기기**

`C:/tmp/bstats-team-stats-check/move_css.cjs`:

```js
// team-stats.html 의 <style> 블록을 css/stats.css 로 옮기고, 그 자리에 링크를 둡니다.
const fs = require('node:fs');
const HTML = 'C:/Users/김승곤/Desktop/b_project/dashboard_js/pages/team-stats.html';
const CSS = 'C:/Users/김승곤/Desktop/b_project/dashboard_js/css/stats.css';
const html = fs.readFileSync(HTML, 'utf8');
const EOL = html.includes('\r\n') ? '\r\n' : '\n';
const lines = html.split(/\r?\n/);
const a = lines.indexOf('    <style>');
const b = lines.indexOf('    </style>');
if (a < 0 || b < a) throw new Error('<style> 블록을 찾지 못했습니다');
const body = lines.slice(a + 1, b).map(l => l.replace(/^ {8}/, ''));
const head = [
  '/*',
  ' * 팀·선수 통계 페이지 공용 스타일입니다(team-stats.html 에서 옮김).',
  ' * 앞부분은 팀 통계 화면 그대로입니다. 고치지 말고, 선수 통계용 규칙은 뒤에 붙입니다.',
  ' */',
];
fs.writeFileSync(CSS, head.concat(body).join(EOL) + EOL);
lines.splice(a, b - a + 1, '    <link rel="stylesheet" href="../css/stats.css">');
fs.writeFileSync(HTML, lines.join(EOL));
console.log('옮긴 줄', body.length);
```

Run: `node C:/tmp/bstats-team-stats-check/move_css.cjs`
Expected: `옮긴 줄 86`

- [ ] **Step 6: 팀 통계 스크립트 경로 바꾸기**

`dashboard_js/pages/team-stats.html` 아래쪽에서

```html
    <script src="../js/team-stats/metrics.js"></script>
    <script src="../js/team-stats/columns.js"></script>
    <script src="../js/team-stats/data.js"></script>
    <script src="../js/team-stats/table.js"></script>
```

를

```html
    <script src="../js/stats/metrics.js"></script>
    <script src="../js/stats/columns.js"></script>
    <script src="../js/stats/data.js"></script>
    <script src="../js/stats/table.js"></script>
```

로 바꿉니다. `record.js`·`page.js` 줄은 그대로 둡니다.

- [ ] **Step 7: 시험 전체 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 82개 통과(기존 78 + layout 4), 실패 0.

- [ ] **Step 8: 팀 통계 화면이 그대로인지 확인**

```bash
cd C:/tmp/bstats-team-stats-check
bash dom.sh "/pages/team-stats.html?season=2025" ts_after.html
diff <(sed -n '/<main/,/<\/main>/p' ts_before.html) <(sed -n '/<main/,/<\/main>/p' ts_after.html) && echo SAME_MAIN
bash shot.sh ts_after_move "/pages/team-stats.html?season=2025"
cmp "C:/Users/김승곤/Desktop/bstats_ts_ts_before_move.png" "C:/Users/김승곤/Desktop/bstats_ts_ts_after_move.png" && echo SAME_PNG
```

Expected: `SAME_MAIN`. PNG 가 바이트까지 같지 않으면(글꼴·시간 차이로 그럴 수 있음) 두 PNG 를 Read 로 열어 색·간격·고정 칸·선이 같은지 눈으로 확인합니다. 다르면 stats.css 가 빠졌거나 순서가 바뀐 것입니다.

- [ ] **Step 9: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/css/stats.css dashboard_js/pages/team-stats.html
git diff --cached --name-status
```

Expected: `R100 …team-stats/metrics.js → …stats/metrics.js` 등 이름 바꾸기 4개, `A dashboard_js/css/stats.css`, `M dashboard_js/pages/team-stats.html` 만 있습니다.

```bash
git commit -m "refactor(stats): 팀 통계 공용 모듈과 스타일을 js/stats·css/stats.css 로 옮김

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/team-stats dashboard_js/js/stats dashboard_js/css/stats.css dashboard_js/pages/team-stats.html
```

---

### Task 2: 선수 표 계산과 규정 판정(metrics.js)

**Files:**
- Modify: `dashboard_js/js/stats/metrics.js` (머리 주석 1~10행, `battingTable` 147~198행, `pitchingTable` 250~286행, 끝의 `const api` 540~546행)
- Test (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/metrics.player.test.js`

**Interfaces:**
- Consumes: 기존 `num, div, ipOuts, BAT_SUM, BAT_KEYS, battingRates, pfHalf, wobaOf, sumObjects, PIT_SUM, PIT_KEYS, pitchingRates, fipCore, rankFor`.
- Produces (`TS.metrics` 에 추가):
  - `playerBatting(batters, season, ix)` → `{ rows, league, ctx }`. 행: 합계 키(`pa ab h …`) + 비율 + `woba wraa wrc wrcp opsp` + `id name team pos g` + 상황 `risp ph xr gpa ppa`(공식 값, 없으면 null). 리그 행: `{ name: '리그 평균', team: '', isLeague: true }` + 비율 + `woba`, `wraa` 0, `wrcp`·`opsp` 100. 누적 숫자·상황 칸은 없음(undefined/null → 화면 '-'). `ctx` 는 `battingTable` 과 같은 모양 `{ lgWoba, L, scale, lgObp, lgSlg, hasWeights }`.
  - `playerPitching(pitchers, season, ix)` → `{ rows, league, ctx: { lgEra, cfip } }`. 행: 합계 키(`outs h er …`) + 비율 + `fip ef erap fipp` + `id name team g`. 리그 행: 비율 + `fip`(= 리그 ERA), `ef` 0, `erap`·`fipp` 100.
  - `pyRound(x)` → number (.5 는 짝수 쪽).
  - `qualFor(team, rank, reg)` → `{ pa, outs, from: 'rank'|'regulation' }` 또는 `null`. `rank` 는 `{ 팀: { g } }`, `reg` 는 `{ team_games, qual_pa, qual_ip }` 또는 null.

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.player.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture, refs, near } = require('./_load');
const M = load('metrics');

const R = refs();
const ix = M.indexRefs(R);
const b = fixture('batters_2025').batters;
const p = fixture('pitchers_2025').pitchers;

test('pyRound: 파이썬 round 와 같음(.5 는 짝수 쪽)', () => {
  assert.equal(M.pyRound(446.4), 446);
  assert.equal(M.pyRound(424.7), 425);
  assert.equal(M.pyRound(0.5), 0);
  assert.equal(M.pyRound(1.5), 2);
  assert.equal(M.pyRound(2.5), 2);
  assert.equal(M.pyRound(3.5), 4);
});

test('playerBatting: 리그 기준값이 팀 표와 같음', () => {
  const pl = M.playerBatting(b, 2025, ix);
  const tm = M.battingTable(M.sumBatting(b), 2025, ix);
  assert.ok(near(pl.ctx.lgWoba, tm.ctx.lgWoba));
  assert.ok(near(pl.ctx.L, tm.ctx.L));
  assert.ok(near(pl.ctx.lgObp, tm.ctx.lgObp));
  assert.ok(near(pl.ctx.lgSlg, tm.ctx.lgSlg));
  assert.equal(pl.rows.length, 398);
});

test('검증 P1: 50타석 이상 선수의 wOBA·wRAA·wRC+ 가 서버 값과 같음(서버 반올림 안)', () => {
  const pl = M.playerBatting(b, 2025, ix);
  const byId = new Map(pl.rows.map(r => [String(r.id), r]));
  let n = 0;
  for (const x of b) {
    if (x.wrc_plus === null || x.wrc_plus === undefined || Number(x.plate_appearance) < 50) continue;
    const r = byId.get(String(x.player_id));
    assert.ok(near(r.woba, Number(x.woba), 5.0001e-4), `${x.player_name} wOBA ${r.woba} vs ${x.woba}`);
    assert.ok(Math.abs(r.wraa - Number(x.wraa)) < 0.1, `${x.player_name} wRAA ${r.wraa} vs ${x.wraa}`);
    assert.ok(Math.abs(r.wrcp - Number(x.wrc_plus)) < 0.1, `${x.player_name} wRC+ ${r.wrcp} vs ${x.wrc_plus}`);
    n++;
  }
  assert.equal(n, 193);
});

test('playerBatting: 선수 칸과 상황 기록은 공식 값 그대로', () => {
  const pl = M.playerBatting(b, 2025, ix);
  const x = b.find(v => Number(v.plate_appearance) > 400);
  const r = pl.rows.find(v => String(v.id) === String(x.player_id));
  assert.equal(r.name, x.player_name);
  assert.equal(r.team, x.player_team);
  assert.equal(r.pos, x.position);
  assert.equal(r.g, Number(x.games));
  assert.equal(r.pa, Number(x.plate_appearance));
  assert.equal(r.risp, Number(x.runners_in_scoring_position));
  assert.equal(r.ph, Number(x.pinch_hit_batting_average));
  assert.equal(r.xr, Number(x.extended_runs));
  assert.equal(r.gpa, Number(x.gross_production_average));
  assert.equal(r.ppa, Number(x.p_pa));
  assert.equal(r.gw, Number(x.gw_rbi));
  assert.equal(r.multi, Number(x.multi_hits));
});

test('playerBatting: 값이 없는 상황 기록은 0 이 아니라 null, 팀이 없는 행은 뺌', () => {
  const pl = M.playerBatting([
    { player_id: '1', player_name: 'A', player_team: 'LG', plate_appearance: 3, at_bat: 3, single: 1, runners_in_scoring_position: null, p_pa: '' },
    { player_id: '2', player_name: 'B', player_team: null, plate_appearance: 5 },
  ], 2025, ix);
  assert.equal(pl.rows.length, 1);
  assert.equal(pl.rows[0].risp, null);
  assert.equal(pl.rows[0].ppa, null);
  assert.equal(pl.rows[0].pos, '');
});

test('playerBatting: 리그 행은 비율과 지수만, 누적·상황은 비움', () => {
  const pl = M.playerBatting(b, 2025, ix);
  const lg = pl.league;
  assert.equal(lg.isLeague, true);
  assert.equal(lg.name, '리그 평균');
  for (const k of ['g', 'pa', 'ab', 'h', 'hr', 'r', 'rbi', 'single', 'risp', 'ph', 'xr', 'gpa', 'ppa', 'gw', 'multi', 'wrc']) {
    assert.ok(lg[k] === null || lg[k] === undefined, k);
  }
  assert.equal(lg.wrcp, 100);
  assert.equal(lg.opsp, 100);
  assert.equal(lg.wraa, 0);
  assert.ok(near(lg.woba, pl.ctx.lgWoba));
  assert.equal(typeof lg.avg, 'number');
});

test('playerBatting: 1985 는 wOBA·wRC+ 없음, OPS+ 는 보정 없이', () => {
  const one = [
    { player_id: '1', player_name: 'A', player_team: '삼성', plate_appearance: 400, at_bat: 350, single: 110, double: 20, triple: 2, home_run: 15, total_bases: 179, base_on_balls: 40, hit_by_pitch: 5, sacrifice_fly: 5, strikeout: 50, run: 60 },
    { player_id: '2', player_name: 'B', player_team: 'OB', plate_appearance: 400, at_bat: 360, single: 90, double: 15, triple: 1, home_run: 5, total_bases: 122, base_on_balls: 30, hit_by_pitch: 5, sacrifice_fly: 5, strikeout: 70, run: 40 },
  ];
  const pl = M.playerBatting(one, 1985, ix);
  assert.ok(pl.rows.every(r => r.woba === null && r.wrcp === null && typeof r.opsp === 'number'));
  assert.equal(pl.league.wrcp, null);
  assert.equal(pl.league.opsp, 100);
});

test('playerPitching: 리그 기준값이 팀 표와 같고 ERA 는 서버 값과 같음', () => {
  const pl = M.playerPitching(p, 2025, ix);
  const tm = M.pitchingTable(M.sumPitching(p), 2025, ix);
  assert.ok(near(pl.ctx.lgEra, tm.ctx.lgEra));
  assert.ok(near(pl.ctx.cfip, tm.ctx.cfip));
  assert.equal(pl.rows.length, 281);
  let n = 0;
  for (const x of p) {
    if (M.ipOuts(x.innings_pitched) < 30) continue;
    const r = pl.rows.find(v => String(v.id) === String(x.player_id));
    assert.ok(Math.abs(r.era - Number(x.earned_run_average)) < 0.0051, `${x.player_name} ERA ${r.era} vs ${x.earned_run_average}`);
    assert.equal(r.g, Number(x.games));
    n++;
  }
  assert.equal(n, 203);
  const lg = pl.league;
  assert.ok(near(lg.fip, lg.era));
  assert.equal(lg.erap, 100);
  assert.equal(lg.fipp, 100);
  assert.equal(lg.ef, 0);
  for (const k of ['w', 'l', 'g', 'outs', 'so', 'hr']) assert.ok(lg[k] === null || lg[k] === undefined, k);
});

test('qualFor: 순위표 경기 수로 규정, 없으면 시즌 공통 규정, 둘 다 없으면 null', () => {
  const rank = M.rankFor(R.rank, 2025);
  assert.deepEqual(M.qualFor('LG', rank, null), { pa: 446, outs: 432, from: 'rank' });
  assert.deepEqual(M.qualFor('A', { A: { g: 137 } }, null), { pa: 425, outs: 411, from: 'rank' });
  assert.deepEqual(M.qualFor('없는팀', rank, { team_games: 144, qual_pa: 446, qual_ip: 144 }), { pa: 446, outs: 432, from: 'regulation' });
  assert.equal(M.qualFor('없는팀', rank, null), null);
  assert.equal(M.qualFor('A', { A: { g: 0 } }, null), null);
});

test('검증 P2: 2025 규정 이상 타자 43명·투수 22명(144이닝 딱 맞는 2명 포함)', () => {
  const rank = M.rankFor(R.rank, 2025);
  const bat = M.playerBatting(b, 2025, ix).rows.filter(r => r.pa >= M.qualFor(r.team, rank, null).pa);
  const pit = M.playerPitching(p, 2025, ix).rows.filter(r => r.outs >= M.qualFor(r.team, rank, null).outs);
  assert.equal(bat.length, 43);
  assert.equal(pit.length, 22);
  assert.equal(pit.filter(r => r.outs === 432).length, 2);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/metrics.player.test.js"`
Expected: FAIL (`M.pyRound is not a function`, `M.playerBatting is not a function` 등).

- [ ] **Step 3: 타격 표를 "기준값 + 한 줄"로 나누기(동작 그대로)**

`dashboard_js/js/stats/metrics.js` 에서 `/**\n   * 타격 표입니다.` 로 시작하는 주석부터 `battingTable` 함수 끝(`}` , 198행)까지를 아래로 바꿉니다.

```js
  /**
   * 타격 리그 기준값입니다. lg 는 리그 합계(성분)입니다. 팀 표와 선수 표가
   * 같은 기준값을 쓰도록 한 곳에서 셉니다.
   */
  function battingCtx(lg, season, ix) {
    const w = (ix && ix.weights[season]) || null;
    return {
      lgR: battingRates(lg),
      w: w,
      lgWoba: wobaOf(lg, w),
      L: div(lg.r, lg.pa),
      scale: w ? num(w.wOBA_scale) : 0,
    };
  }

  /** 표의 ctx 로 내보내는 리그 기준값입니다. */
  function battingCtxOut(c) {
    return { lgWoba: c.lgWoba, L: c.L, scale: c.scale, lgObp: c.lgR.obp, lgSlg: c.lgR.slg, hasWeights: !!c.w };
  }

  /**
   * 한 줄(팀 하나 또는 선수 한 명)의 타격 지표입니다. t 는 합계(성분)이고,
   * team 은 구장 보정에 쓸 팀입니다.
   */
  function battingRow(t, team, season, ix, c) {
    const row = Object.assign({}, t, battingRates(t));
    const pf = pfHalf(ix, team, season);
    row.woba = wobaOf(t, c.w);
    row.wraa = null;
    row.wrc = null;
    row.wrcp = null;
    if (row.woba !== null && c.lgWoba !== null && c.scale > 0 && t.pa > 0) {
      row.wraa = (row.woba - c.lgWoba) / c.scale * t.pa;
      if (c.L !== null) {
        row.wrc = (row.wraa / t.pa + c.L) * t.pa;
        // 선수 wRC+ 와 같은 식: K + (2 - PF) * 100, K = (wRAA/PA) / L * 100
        if (pf !== null) row.wrcp = (row.wraa / t.pa) / c.L * 100 + (2 - pf) * 100;
      }
    }
    row.opsp = (row.obp !== null && row.slg !== null && c.lgR.obp > 0 && c.lgR.slg > 0 && pf)
      ? 100 * (row.obp / c.lgR.obp + row.slg / c.lgR.slg - 1) / pf
      : null;
    return row;
  }

  /**
   * 타격 표입니다. totals 는 sumBatting 결과(또는 기간별 합계)입니다.
   * keys 는 합계 키 목록입니다(기간별은 응답에 있는 칸만).
   */
  function battingTable(totals, season, ix, keys) {
    keys = keys || BAT_KEYS;
    const teams = Object.values(totals || {});
    const lg = sumObjects(teams, keys);
    const c = battingCtx(lg, season, ix);
    const rows = teams.map(t => battingRow(t, t.team, season, ix, c));

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, c.lgR);
    league.single = c.lgR.single === null ? null : c.lgR.single / n;
    league.woba = c.lgWoba;
    league.wraa = c.lgWoba === null ? null : 0;
    league.wrc = c.lgWoba !== null && c.L !== null ? c.L * lg.pa / n : null;
    league.wrcp = rows.some(r => r.wrcp !== null) ? 100 : null;
    league.opsp = rows.some(r => r.opsp !== null) ? 100 : null;

    return { rows: rows, league: league, ctx: battingCtxOut(c) };
  }
```

- [ ] **Step 4: 투구 표도 같은 방식으로 나누기(동작 그대로)**

`/**\n   * 투구 표입니다. FIP 상수는` 로 시작하는 주석부터 `pitchingTable` 함수 끝까지를 아래로 바꿉니다.

```js
  /** 투구 리그 기준값입니다. FIP 상수는 그해 리그 합으로 직접 셉니다. */
  function pitchingCtx(lg) {
    const lgR = pitchingRates(lg);
    const lgCore = fipCore(lg);
    return { lgR: lgR, cfip: lgR.era !== null && lgCore !== null ? lgR.era - lgCore : null };
  }

  /** 한 줄(팀 하나 또는 선수 한 명)의 투구 지표입니다. team 은 구장 보정에 쓸 팀입니다. */
  function pitchingRow(t, team, season, ix, c) {
    const row = Object.assign({}, t, pitchingRates(t));
    const core = fipCore(t);
    const pf = pfHalf(ix, team, season);
    const lgEra = c.lgR.era;
    row.fip = core !== null && c.cfip !== null ? core + c.cfip : null;
    row.ef = row.era !== null && row.fip !== null ? row.era - row.fip : null;
    row.erap = row.era !== null && lgEra > 0 && pf !== null
      ? 100 * row.era * (2 - pf) / lgEra : null;
    row.fipp = row.fip !== null && lgEra > 0 && pf !== null
      ? 100 * row.fip * (2 - pf) / lgEra : null;
    return row;
  }

  /**
   * 투구 표입니다. FIP 상수는 그해 리그 합으로 직접 셉니다.
   *   cFIP = 리그 ERA − 리그 fipCore
   * 그래서 리그 평균 FIP = 리그 ERA 입니다.
   */
  function pitchingTable(totals, season, ix, keys) {
    keys = keys || PIT_KEYS;
    const teams = Object.values(totals || {});
    const lg = sumObjects(teams, keys);
    const c = pitchingCtx(lg);
    const rows = teams.map(t => pitchingRow(t, t.team, season, ix, c));

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, c.lgR);
    league.fip = c.cfip !== null ? c.lgR.era : null;
    league.ef = league.fip !== null ? 0 : null;
    league.erap = rows.some(r => r.erap !== null) ? 100 : null;
    league.fipp = rows.some(r => r.fipp !== null) ? 100 : null;

    return { rows: rows, league: league, ctx: { lgEra: c.lgR.era, cfip: c.cfip } };
  }
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 기존 82개는 그대로 통과(나누기만 했으므로), metrics.player 만 실패.

- [ ] **Step 5: 선수 표·규정 판정 더하기**

`rangePitchingTable` 함수 뒤, `const api = {` 앞에 넣습니다.

```js
  // ===== 선수 표 =====

  /** 선수 한 명의 공식 기록을 합계와 같은 모양으로 읽습니다. */
  function pick(r, map) {
    const a = {};
    for (const k in map) a[k] = num(r[map[k]]);
    return a;
  }

  /** 값이 없거나 숫자가 아니면 null 입니다. num 과 달리 0 으로 바꾸지 않습니다. */
  function numOrNull(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  // 선수 상황 기록입니다. 성분이 없어 다시 셀 수 없으므로 공식 값 그대로 씁니다.
  const PLAYER_BAT_RAW = {
    risp: 'runners_in_scoring_position', ph: 'pinch_hit_batting_average',
    xr: 'extended_runs', gpa: 'gross_production_average', ppa: 'p_pa',
  };

  /**
   * 선수 타격 표입니다. 리그 기준값은 팀 표와 같게, 팀이 있는 선수 전체의
   * 합으로 셉니다. 행은 선수 한 명씩이고 id·name·team·pos·g 를 붙입니다.
   *
   * 리그 평균 행은 비율과 지수만 둡니다. 선수마다 출장이 달라 누적 숫자의
   * 평균은 뜻이 없어 비웁니다(화면 '-'). wRAA 는 리그 평균 선수가 0 이라
   * 0 으로 둡니다.
   */
  function playerBatting(batters, season, ix) {
    const list = (batters || []).filter(p => p && p.player_team);
    const parts = list.map(p => pick(p, BAT_SUM));
    const c = battingCtx(sumObjects(parts, BAT_KEYS), season, ix);
    const rows = list.map(function (p, i) {
      const row = battingRow(parts[i], p.player_team, season, ix, c);
      row.id = p.player_id;
      row.name = p.player_name;
      row.team = p.player_team;
      row.pos = p.position || '';
      row.g = num(p.games);
      for (const k in PLAYER_BAT_RAW) row[k] = numOrNull(p[PLAYER_BAT_RAW[k]]);
      return row;
    });
    const league = Object.assign({ name: '리그 평균', team: '', isLeague: true }, c.lgR);
    league.single = null;
    league.woba = c.lgWoba;
    league.wraa = c.lgWoba === null ? null : 0;
    league.wrcp = rows.some(r => r.wrcp !== null) ? 100 : null;
    league.opsp = rows.some(r => r.opsp !== null) ? 100 : null;
    return { rows: rows, league: league, ctx: battingCtxOut(c) };
  }

  /** 선수 투구 표입니다. 리그 기준값(리그 ERA·FIP 상수)은 팀 표와 같습니다. */
  function playerPitching(pitchers, season, ix) {
    const list = (pitchers || []).filter(p => p && p.player_team);
    const parts = list.map(p => Object.assign(pick(p, PIT_SUM), { outs: ipOuts(p.innings_pitched) }));
    const c = pitchingCtx(sumObjects(parts, PIT_KEYS));
    const rows = list.map(function (p, i) {
      const row = pitchingRow(parts[i], p.player_team, season, ix, c);
      row.id = p.player_id;
      row.name = p.player_name;
      row.team = p.player_team;
      row.g = num(p.games);
      return row;
    });
    const league = Object.assign({ name: '리그 평균', team: '', isLeague: true }, c.lgR);
    league.fip = c.cfip !== null ? c.lgR.era : null;
    league.ef = league.fip !== null ? 0 : null;
    league.erap = rows.some(r => r.erap !== null) ? 100 : null;
    league.fipp = rows.some(r => r.fipp !== null) ? 100 : null;
    return { rows: rows, league: league, ctx: { lgEra: c.lgR.era, cfip: c.cfip } };
  }

  /**
   * 파이썬 round 와 같습니다(.5 는 짝수 쪽). 서버 src/routes/leaders.js 의
   * pyRound 와 같은 식이라 규정타석이 서버와 같게 나옵니다.
   */
  function pyRound(x) {
    const f = Math.floor(x);
    if (x - f === 0.5) return f % 2 === 0 ? f : f + 1;
    return Math.round(x);
  }

  /**
   * 그 팀 선수의 규정 기준 { pa, outs, from } 입니다. 모르면 null 입니다.
   *   규정타석 = 팀 경기 수 × 3.1(파이썬식 반올림), 규정이닝 = 팀 경기 수
   * 팀 경기 수는 rank(rankFor·rankFromStandings 결과)에서 읽습니다. 그 팀이
   * 없으면 reg(/stats/regulation 의 그 시즌 한 줄 {team_games, qual_pa,
   * qual_ip})를 씁니다.
   */
  function qualFor(team, rank, reg) {
    const k = rank && rank[team];
    if (k && k.g > 0) return { pa: pyRound(3.1 * k.g), outs: k.g * 3, from: 'rank' };
    if (reg && num(reg.team_games) > 0) {
      return { pa: num(reg.qual_pa), outs: num(reg.qual_ip) * 3, from: 'regulation' };
    }
    return null;
  }
```

`const api = {` 블록에 한 줄을 더합니다.

```js
  const api = {
    num, div, clean, ipOuts, BAT_SUM, BAT_KEYS, sumBy, sumBatting, battingRates,
    indexRefs, pfHalf, wobaOf, sumObjects, battingTable,
    PIT_SUM, PIT_KEYS, sumPitching, pitchingRates, fipCore, pitchingTable,
    rankFor, rankFromStandings, pythag, gameSplits, recordTable, recordFromGames, recordMismatches, seasonView,
    RANGE_BAT, RANGE_PIT, rangeTotals, rangeBattingTable, rangePitchingTable,
    playerBatting, playerPitching, pyRound, qualFor,
  };
```

머리 주석의 첫 줄과 근거 문장을 바꿉니다.

```js
/*
 * 팀·선수 통계 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.TeamStats.metrics 로, Node 검증 스크립트에서는
 * vm 으로 불러 씁니다. 식의 근거는 docs/superpowers/specs/ 의
 * 2026-10-03-team-stats-fangraphs-design.md 3장과
 * 2026-10-04-player-stats-fangraphs-design.md 3장입니다.
 *
 * 원칙: 선수 비율을 평균 내지 않습니다. 합계(성분)에서 다시 셉니다.
 * 계산할 수 없는 값은 0 이 아니라 null 입니다. 화면에서 '-' 가 됩니다.
 */
```

- [ ] **Step 6: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 92개 통과(82 + metrics.player 10), 실패 0.

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/stats/metrics.js
git diff --cached --name-status
git commit -m "feat(stats): 선수 표 계산(선수 wOBA·wRC+·FIP)과 규정 판정 추가

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/stats/metrics.js
```

---

### Task 3: 선수 칸 정의(columns.js)와 규정 기준 받기(data.js)

**Files:**
- Modify: `dashboard_js/js/stats/columns.js` (머리 주석 2행, `const TABLES` 142행 뒤에 선수 칸, `const api` 189행)
- Modify: `dashboard_js/js/stats/data.js` (머리 주석 2행, `loadSeasons` 뒤에 `loadRegulation`, `const api` 139행)
- Test (저장소 밖): `tests/columns.player.test.js`, `tests/data.player.test.js`

**Interfaces:**
- Consumes: 기존 `BAT`, `PIT`, `GROUPS`, `ORDER`, `def`, `getJson`.
- Produces:
  - `TS.columns.PBAT`, `PPIT`: 선수 칸 정의(팀 칸 + `risp ph xr gpa ppa`, 설명이 다른 칸은 바꿈).
  - `TS.columns.PGROUPS = { bat: { dash, std, adv, sit }, pit: { dash, std, adv } }` (배열은 복사본).
  - `TS.columns.PORDER = { bat: [...], pit: [...] }` 사용자 지정 칸 순서.
  - `TS.columns.pdef(tab, key)` → `{ key, label, kind, desc, … }` 또는 `null`.
  - `TS.data.loadRegulation(base, opts)` → `{ regulation: { 'YYYY': { team_games, qual_pa, qual_ip } }, errors: [] }`, 실패면 `{ regulation: {}, errors: [{ what: '규정 기준', error }] }`.

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/columns.player.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const C = load('columns');

test('pdef: 선수 칸은 팀 칸 + 상황 칸, 뜻이 다른 칸은 선수 설명', () => {
  assert.equal(C.pdef('bat', 'g').desc, '선수가 출장한 경기 수입니다.');
  assert.ok(C.def('bat', 'g').desc.startsWith('팀이'));
  assert.equal(C.pdef('pit', 'g').desc, '등판한 경기 수입니다.');
  assert.equal(C.pdef('bat', 'gw').label, '결승타');
  assert.equal(C.def('bat', 'gw').label, 'GW RBI');
  assert.equal(C.pdef('bat', 'risp').label, '득점권');
  assert.equal(C.pdef('bat', 'risp').kind, 'avg3');
  assert.equal(C.pdef('bat', 'ph').label, '대타');
  assert.equal(C.pdef('bat', 'xr').kind, 'f1');
  assert.equal(C.pdef('bat', 'gpa').formula, '(1.8 × OBP + SLG) ÷ 4');
  assert.equal(C.pdef('bat', 'ppa').label, 'P/PA');
  assert.equal(C.pdef('bat', 'wrcp').index, 'high');
  assert.equal(C.pdef('pit', 'erap').better, 'low');
  assert.equal(C.pdef('pit', 'risp'), null);
  assert.equal(C.pdef('bat', 'toString'), null);
  assert.equal(C.pdef('rec', 'pct'), null);
});

test('PGROUPS: 설계 2.1 표와 같음', () => {
  assert.deepEqual(C.PGROUPS.bat.dash, ['g', 'pa', 'hr', 'r', 'rbi', 'bbpct', 'kpct', 'iso', 'babip', 'avg', 'obp', 'slg', 'woba', 'wrcp']);
  assert.deepEqual(C.PGROUPS.bat.std, ['g', 'pa', 'ab', 'h', 'single', 'd2', 'd3', 'hr', 'r', 'rbi', 'bb', 'ibb', 'so', 'hbp', 'sf', 'sh', 'gdp', 'avg']);
  assert.deepEqual(C.PGROUPS.bat.adv, ['pa', 'bbpct', 'kpct', 'bbk', 'avg', 'obp', 'slg', 'ops', 'iso', 'babip', 'woba', 'wraa', 'wrc', 'wrcp', 'opsp']);
  assert.deepEqual(C.PGROUPS.bat.sit, ['pa', 'risp', 'ph', 'gw', 'multi', 'xr', 'gpa', 'ppa']);
  assert.deepEqual(C.PGROUPS.pit.dash, ['w', 'l', 'sv', 'g', 'gs', 'outs', 'k9', 'bb9', 'hr9', 'babip', 'lobpct', 'era', 'fip']);
  assert.deepEqual(C.PGROUPS.pit.std, C.GROUPS.pit.std);
  assert.deepEqual(C.PGROUPS.pit.adv, C.GROUPS.pit.adv);
  assert.equal(C.PGROUPS.pit.sit, undefined);
  assert.notEqual(C.PGROUPS.bat.dash, C.GROUPS.bat.dash);
  for (const tab of ['bat', 'pit']) {
    for (const g of Object.keys(C.PGROUPS[tab])) for (const k of C.PGROUPS[tab][g]) assert.ok(C.pdef(tab, k), `${tab}.${g}.${k}`);
  }
});

test('PORDER: 팀 칸 순서 뒤에 상황 칸', () => {
  assert.deepEqual(C.PORDER.bat.slice(0, C.ORDER.bat.length), C.ORDER.bat);
  assert.deepEqual(C.PORDER.bat.slice(C.ORDER.bat.length), ['risp', 'ph', 'xr', 'gpa', 'ppa']);
  assert.deepEqual(C.PORDER.pit, C.ORDER.pit);
});

test('선수 칸 설명에 팀 전용 말이 없음', () => {
  for (const tab of ['bat', 'pit']) {
    for (const k of C.PORDER[tab]) {
      assert.ok(!/팀이 치른|팀 득점 생산량|타선보다|횟수의 합|선수 wRC\+와 같은 방식/.test(C.pdef(tab, k).desc), `${tab}.${k}`);
    }
  }
});
```

`C:/tmp/bstats-team-stats-check/tests/data.player.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const D = load('data');

function fakeFetch(status, body) {
  const f = async url => {
    f.calls.push(url);
    return { ok: status < 400, status: status, json: async () => body };
  };
  f.calls = [];
  return f;
}

test('loadRegulation: 정상 응답', async () => {
  const f = fakeFetch(200, { regulation: { 2025: { team_games: 144, qual_pa: 446, qual_ip: 144 } } });
  const r = await D.loadRegulation('https://x', { fetch: f });
  assert.deepEqual(f.calls, ['https://x/stats/regulation']);
  assert.deepEqual(r.errors, []);
  assert.equal(r.regulation['2025'].qual_pa, 446);
});

test('loadRegulation: HTTP 오류·error 필드·모양 이상은 errors 로', async () => {
  const a = await D.loadRegulation('https://x', { fetch: fakeFetch(500, {}) });
  assert.deepEqual(a, { regulation: {}, errors: [{ what: '규정 기준', error: 'HTTP 500' }] });
  const b = await D.loadRegulation('https://x', { fetch: fakeFetch(200, { error: 'db down' }) });
  assert.deepEqual(b.errors, [{ what: '규정 기준', error: 'db down' }]);
  const c = await D.loadRegulation('https://x', { fetch: fakeFetch(200, { nope: 1 }) });
  assert.deepEqual(c.errors, [{ what: '규정 기준', error: 'regulation 이 없습니다' }]);
  const d = await D.loadRegulation('https://x', { fetch: fakeFetch(200, { regulation: [1, 2] }) });
  assert.equal(d.errors.length, 1);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/columns.player.test.js" "C:/tmp/bstats-team-stats-check/tests/data.player.test.js"`
Expected: FAIL (`C.pdef is not a function`, `D.loadRegulation is not a function`).

- [ ] **Step 3: 선수 칸 정의 더하기**

`dashboard_js/js/stats/columns.js` 의 `const TABLES = { bat: BAT, pit: PIT, rec: REC };` 줄 바로 뒤에 넣습니다.

```js

  // ===== 선수 통계 칸 =====
  // 팀 칸을 그대로 쓰고, 뜻이 다른 칸만 설명을 바꿉니다. 팀 표는 위 BAT·PIT 를 그대로 씁니다.
  const PBAT = Object.assign({}, BAT, {
    g: Object.assign({}, BAT.g, { desc: '선수가 출장한 경기 수입니다.' }),
    multi: Object.assign({}, BAT.multi, { desc: '한 경기에 안타 두 개 이상을 친 경기 수입니다.' }),
    gw: Object.assign({}, BAT.gw, { label: '결승타', desc: '이긴 경기에서 결승점을 낸 타점의 수입니다.' }),
    wraa: Object.assign({}, BAT.wraa, { desc: '리그 평균 타자보다 더 만든 득점입니다. 0이 평균입니다.' }),
    wrc: Object.assign({}, BAT.wrc, { desc: 'wOBA로 잰 득점 생산량입니다.' }),
    wrcp: Object.assign({}, BAT.wrcp, { desc: '타석당 득점 생산을 리그 평균 100에 맞춘 값입니다. 110이면 평균보다 10% 더 만듭니다. 소속팀 홈구장 영향을 반만 덜어 냅니다.' }),
    risp: { label: '득점권', kind: 'avg3', range: false, desc: '주자가 2루나 3루에 있을 때의 타율입니다. KBO 공식 기록 값입니다.' },
    ph: { label: '대타', kind: 'avg3', range: false, desc: '대타로 나왔을 때의 타율입니다. KBO 공식 기록 값입니다.' },
    xr: { label: 'XR', kind: 'f1', range: false, desc: '추정 득점입니다. 안타·볼넷·도루 같은 결과마다 득점 가치를 매겨 더합니다. KBO 공식 기록 값입니다.' },
    gpa: { label: 'GPA', kind: 'avg3', range: false, desc: '출루율에 장타율보다 큰 무게를 둔 타격 지표입니다. KBO 공식 기록 값입니다.', formula: '(1.8 × OBP + SLG) ÷ 4' },
    ppa: { label: 'P/PA', kind: 'f2', range: false, desc: '타석당 상대한 투구 수입니다. KBO 공식 기록 값입니다.' },
  });
  const PPIT = Object.assign({}, PIT, {
    g: Object.assign({}, PIT.g, { desc: '등판한 경기 수입니다.' }),
  });

  const PGROUPS = {
    bat: {
      dash: GROUPS.bat.dash.slice(),
      std: GROUPS.bat.std.slice(),
      adv: GROUPS.bat.adv.slice(),
      sit: ['pa', 'risp', 'ph', 'gw', 'multi', 'xr', 'gpa', 'ppa'],
    },
    pit: {
      dash: GROUPS.pit.dash.slice(),
      std: GROUPS.pit.std.slice(),
      adv: GROUPS.pit.adv.slice(),
    },
  };
  const PORDER = { bat: Object.keys(PBAT), pit: Object.keys(PPIT) };
  const PTABLES = { bat: PBAT, pit: PPIT };

  /** 선수 칸 정의를 key 를 붙여 돌려줍니다. 없으면 null. */
  function pdef(tab, key) {
    const t = PTABLES[tab];
    const d = t && Object.prototype.hasOwnProperty.call(t, key) ? t[key] : null;
    return d ? Object.assign({ key: key }, d) : null;
  }
```

`const api` 줄을 바꿉니다.

```js
  const api = { BAT, PIT, REC, ORDER, GROUPS, REC_KEYS, def, fmt, PBAT, PPIT, PGROUPS, PORDER, pdef };
```

머리 주석 첫 줄 `팀 통계 표의 칸 정의입니다.` 를 `팀·선수 통계 표의 칸 정의입니다.` 로 바꿉니다.

- [ ] **Step 4: 규정 기준 받기 더하기**

`dashboard_js/js/stats/data.js` 의 `loadSeasons` 함수 뒤에 넣습니다.

```js

  /**
   * 시즌별 공통 규정(/stats/regulation)입니다. 순위표에 없는 팀이 있을 때만
   * 씁니다. 모양: { 'YYYY': { team_games, qual_pa, qual_ip } }
   */
  async function loadRegulation(base, opts) {
    const r = await getJson(`${base}/stats/regulation`, null, (opts || {}).fetch);
    const reg = r.ok ? r.data.regulation : null;
    if (reg && typeof reg === 'object' && !Array.isArray(reg)) return { regulation: reg, errors: [] };
    return { regulation: {}, errors: [{ what: '규정 기준', error: r.ok ? 'regulation 이 없습니다' : r.error }] };
  }
```

`const api` 줄을 바꿉니다.

```js
  const api = { badReason, getJson, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons, loadRegulation };
```

머리 주석 첫 줄 `팀 통계 데이터 받기입니다.` 를 `팀·선수 통계 데이터 받기입니다.` 로 바꿉니다.

- [ ] **Step 5: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 98개 통과(92 + columns.player 4 + data.player 2), 실패 0.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/stats/columns.js dashboard_js/js/stats/data.js
git diff --cached --name-status
git commit -m "feat(stats): 선수 칸 정의(상황 묶음)와 규정 기준 받기 추가

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/stats/columns.js dashboard_js/js/stats/data.js
```

---

### Task 4: 표 앞 칸 구성과 쪽 나누기(table.js)

**Files:**
- Modify: `dashboard_js/js/stats/table.js` (전체를 아래 내용으로)
- Modify: `dashboard_js/css/stats.css` (끝에 선수 칸 규칙 붙이기)
- Test (저장소 밖): `tests/table.player.test.js`

**Interfaces:**
- Consumes: `TS.columns.fmt`, `TS.columns.def`(시험).
- Produces:
  - `renderTable(opt)`·`toCsv(opt)` 가 `opt.idCols = [{ key, label, cls, href?(row) }]` 를 받음. 없으면 지금처럼 팀 칸 하나(`{ key: 'team', label: '팀', cls: 'ts-team', href: opt.teamHref }`). 리그 행은 첫 앞 칸에 '리그 평균', 나머지 앞 칸은 빈칸.
  - `renderTable(opt)` 가 `opt.page = { size, index }` 를 받음(size 0 이나 없음 = 전체). # 는 쪽을 넘어 이어짐. 리그 행은 쪽마다 맨 아래. `toCsv` 는 `page` 를 보지 않음(전체).
  - `pageOf(total, page)` → `{ start, end, index, count }` (index 0부터, 범위 밖이면 끝 쪽으로).

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/table.player.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const C = load('columns');
const T = load('table');

const cols = [C.def('bat', 'avg'), C.def('bat', 'wrcp'), C.def('rec', 'home')];
const league = { team: '리그 평균', isLeague: true, avg: 0.263, wrcp: 100, home: null };
const ids = [
  { key: 'name', label: '이름', cls: 'ts-name', href: r => (r.id ? 'player-analytics?id=' + r.id : null) },
  { key: 'team', label: '팀', cls: 'ts-pteam' },
];

test('idCols: # · 이름(링크) · 팀, 리그 행은 이름 칸에 리그 평균', () => {
  const rows = [{ id: '7', name: '김<도>', team: 'KIA', avg: 0.3, wrcp: 140, home: null }, { id: null, name: '무명', team: 'LG', avg: 0.2, wrcp: 80, home: null }];
  const h = T.renderTable({ cols, rows, league, sort: { key: 'avg', dir: 'desc' }, idCols: ids });
  assert.match(h, /<th class="ts-rank">#<\/th><th class="ts-name">이름<\/th><th class="ts-pteam">팀<\/th><th class="sortable/);
  assert.match(h, /<td class="ts-rank">1<\/td><td class="ts-name"><a class="player-link" href="player-analytics\?id=7">김&lt;도&gt;<\/a><\/td><td class="ts-pteam">KIA<\/td>/);
  assert.match(h, /<td class="ts-name">무명<\/td>/);
  assert.match(h, /<tr class="ts-league"><td class="ts-rank"><\/td><td class="ts-name">리그 평균<\/td><td class="ts-pteam"><\/td>/);
  assert.ok(!h.includes('class="ts-team"'));
});

test('idCols: CSV 머리글·앞 칸·리그 행', () => {
  const rows = [{ id: '7', name: '김,도', team: 'KIA', avg: 0.3, wrcp: 140, home: null }];
  const csv = T.toCsv({ cols, rows, league, sort: { key: 'avg', dir: 'desc' }, idCols: ids });
  assert.ok(csv.startsWith('\uFEFF#,이름,팀,AVG,wRC+,홈\r\n'));
  assert.match(csv, /\r\n1,"김,도",KIA,\.300,140,-\r\n/);
  assert.match(csv, /\r\n,리그 평균,,\.263,100,-\r\n$/);
});

test('idCols 가 없으면 지금 팀 표 그대로', () => {
  const rows = [{ team: 'A', avg: 0.25, wrcp: 112, home: null }];
  const h = T.renderTable({ cols, rows, league, sort: { key: 'avg', dir: 'desc' }, teamHref: t => 'team-record?id=' + t });
  assert.match(h, /<th class="ts-rank">#<\/th><th class="ts-team">팀<\/th>/);
  assert.match(h, /<td class="ts-team"><a class="player-link" href="team-record\?id=A">A<\/a><\/td>/);
  assert.match(h, /<td class="ts-team">리그 평균<\/td>/);
});

test('pageOf: 쪽 경계와 범위 밖 맞추기', () => {
  assert.deepEqual(T.pageOf(120, { size: 50, index: 0 }), { start: 0, end: 50, index: 0, count: 3 });
  assert.deepEqual(T.pageOf(120, { size: 50, index: 2 }), { start: 100, end: 120, index: 2, count: 3 });
  assert.deepEqual(T.pageOf(120, { size: 50, index: 9 }), { start: 100, end: 120, index: 2, count: 3 });
  assert.deepEqual(T.pageOf(120, { size: 50, index: -1 }), { start: 0, end: 50, index: 0, count: 3 });
  assert.deepEqual(T.pageOf(120, { size: 0, index: 1 }), { start: 0, end: 120, index: 0, count: 1 });
  assert.deepEqual(T.pageOf(0, { size: 50, index: 0 }), { start: 0, end: 0, index: 0, count: 1 });
  assert.deepEqual(T.pageOf(120, null), { start: 0, end: 120, index: 0, count: 1 });
});

test('page: 그 쪽만 그리고 # 는 이어짐, 리그 행은 맨 아래, CSV 는 쪽과 무관하게 전체', () => {
  const many = Array.from({ length: 120 }, (_, i) => ({ team: 'T' + i, avg: i / 1000, wrcp: 100, home: null }));
  const opt = { cols, rows: many, league, sort: { key: 'avg', dir: 'desc' }, page: { size: 50, index: 1 } };
  const h = T.renderTable(opt);
  assert.equal((h.match(/<td class="ts-rank">\d+<\/td>/g) || []).length, 50);
  assert.match(h, /<td class="ts-rank">51<\/td><td class="ts-team">T69<\/td>/);
  assert.match(h, /<td class="ts-rank">100<\/td><td class="ts-team">T20<\/td>/);
  assert.ok(!h.includes('>T70<'));
  assert.ok(h.lastIndexOf('<tr') === h.indexOf('<tr class="ts-league">'));
  const csv = T.toCsv(opt);
  assert.equal(csv.trim().split('\r\n').length, 1 + 120 + 1);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/table.player.test.js"`
Expected: FAIL (`T.pageOf is not a function`, 이름 칸 없음 등).

- [ ] **Step 3: table.js 를 넓히기**

`dashboard_js/js/stats/table.js` 전체를 이렇게 씁니다(기존 `esc`·`missing`·`indexClass`·`wlPct`·`sortRows`·`sorted`·`rankNo`·`csvCell`·`tipHtml` 은 글자 그대로).

```js
/*
 * 팀·선수 통계 표 그리기입니다. HTML 문자열을 만들 뿐 DOM 에 붙이지는 않습니다
 * (붙이는 일은 각 페이지의 page.js). columns.js 가 먼저 로드되어야 합니다.
 *
 * 앞 칸(고정 칸)은 opt.idCols = [{ key, label, cls, href?(row) }] 로 받습니다.
 * 없으면 팀 칸 하나입니다(팀 통계). opt.page = { size, index } 를 주면 그
 * 쪽만 그립니다(size 0 은 전체). CSV 는 쪽과 상관없이 전체입니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  function C() { return TS.columns; }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  function missing(v) {
    return v === null || v === undefined || (typeof v === 'number' && !Number.isFinite(v));
  }

  /**
   * 지수 칸 색 단계입니다. 리그 평균 100 에서 좋은 쪽으로 2·5·10 이상
   * 떨어지면 ts-up1·2·3, 나쁜 쪽이면 ts-down1·2·3 입니다.
   */
  function indexClass(v, dir) {
    if (missing(v)) return '';
    const d = (Math.round(v) - 100) * (dir === 'low' ? -1 : 1);
    const a = Math.abs(d);
    const lv = a >= 10 ? 3 : a >= 5 ? 2 : a >= 2 ? 1 : 0;
    if (!lv) return '';
    return (d > 0 ? 'ts-up' : 'ts-down') + lv;
  }

  function wlPct(o) {
    const t = o.w + o.l;
    return t ? o.w / t : 0;
  }

  /** 정렬입니다. 값이 없는 행은 방향과 상관없이 맨 아래로 갑니다. */
  function sortRows(rows, key, dir, kind) {
    const sign = dir === 'asc' ? 1 : -1;
    return rows.slice().sort(function (a, b) {
      const av = a[key], bv = b[key];
      const an = missing(av), bn = missing(bv);
      if (an && bn) return 0;
      if (an) return 1;
      if (bn) return -1;
      if (kind === 'wl') return sign * (wlPct(av) - wlPct(bv));
      if (typeof av === 'string' || typeof bv === 'string') {
        return sign * String(av).localeCompare(String(bv), 'ko');
      }
      return sign * (av - bv);
    });
  }

  function sorted(opt) {
    const col = opt.cols.find(c => c.key === opt.sort.key);
    return col ? sortRows(opt.rows, col.key, opt.sort.dir, col.kind) : opt.rows.slice();
  }

  /** # 칸 숫자입니다. opt.rankOf 가 있으면 그 값(팀을 골라 거른 표에서도 전체 순위), 없으면 줄 번호입니다. */
  function rankNo(opt, r, i) {
    if (typeof opt.rankOf !== 'function') return i + 1;
    const n = opt.rankOf(r);
    return missing(n) ? i + 1 : n;
  }

  /** 앞 칸 목록입니다. 없으면 팀 칸 하나(팀 통계)입니다. */
  function idColsOf(opt) {
    if (opt.idCols && opt.idCols.length) return opt.idCols;
    return [{ key: 'team', label: '팀', cls: 'ts-team', href: opt.teamHref ? r => opt.teamHref(r.team) : null }];
  }

  /**
   * 쪽 나누기입니다. size 가 없거나 0 이면 한 쪽에 전부입니다. index 는
   * 0부터이고, 범위를 벗어나면 가까운 끝 쪽으로 맞춥니다.
   */
  function pageOf(total, page) {
    const size = page && page.size > 0 ? page.size : 0;
    if (!size) return { start: 0, end: total, index: 0, count: 1 };
    const count = Math.max(1, Math.ceil(total / size));
    const want = page && Number.isInteger(page.index) ? page.index : 0;
    const index = Math.min(Math.max(0, want), count - 1);
    return { start: index * size, end: Math.min(total, (index + 1) * size), index: index, count: count };
  }

  function rowHtml(r, rank, opt, isLeague) {
    const showRank = opt.rank !== false;
    const cls = isLeague ? ' class="ts-league"' : (opt.highlight && opt.highlight === r.team ? ' class="ts-hl"' : '');
    let h = `<tr${cls}>`;
    if (showRank) h += `<td class="ts-rank">${rank}</td>`;
    idColsOf(opt).forEach(function (c, i) {
      let cell;
      if (isLeague) cell = i === 0 ? '리그 평균' : '';
      else {
        const href = c.href ? c.href(r) : null;
        cell = href ? `<a class="player-link" href="${esc(href)}">${esc(r[c.key])}</a>` : esc(r[c.key]);
      }
      h += `<td class="${c.cls}">${cell}</td>`;
    });
    for (const c of opt.cols) {
      const v = r[c.key];
      const k = [];
      if (c.index && !isLeague) k.push(indexClass(v, c.index));
      if ((c.kind === 'signed0' || c.kind === 'signed1') && !missing(v)) k.push(v > 0 ? 'ts-pos' : v < 0 ? 'ts-neg' : '');
      const cl = k.filter(Boolean).join(' ');
      h += `<td${cl ? ` class="${cl}"` : ''}>${esc(C().fmt(v, c.kind))}</td>`;
    }
    return h + '</tr>';
  }

  /** 표 HTML 입니다. 리그 평균 행은 정렬·쪽과 상관없이 맨 아래입니다. */
  function renderTable(opt) {
    const showRank = opt.rank !== false;
    let h = '<div class="table-container ts-wrap"><table class="table ts-table"><thead><tr>';
    if (showRank) h += '<th class="ts-rank">#</th>';
    for (const c of idColsOf(opt)) h += `<th class="${c.cls}">${esc(c.label)}</th>`;
    for (const c of opt.cols) {
      const on = opt.sort && opt.sort.key === c.key;
      const ind = on ? `<span class="sort-ind">${opt.sort.dir === 'asc' ? '▲' : '▼'}</span>` : '';
      h += `<th class="sortable${on ? ' sorted' : ''}" data-key="${esc(c.key)}">`
        + `<span class="ts-term" data-col="${esc(c.key)}">${esc(c.label)}</span>${ind}</th>`;
    }
    h += '</tr></thead><tbody>';
    const all = sorted(opt);
    const pg = pageOf(all.length, opt.page);
    all.slice(pg.start, pg.end).forEach(function (r, i) { h += rowHtml(r, rankNo(opt, r, pg.start + i), opt, false); });
    if (opt.league) h += rowHtml(opt.league, '', opt, true);
    return h + '</tbody></table></div>';
  }

  function csvCell(s) {
    s = String(s);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /** 지금 보이는 칸·정렬 그대로의 CSV 입니다(쪽과 상관없이 전체). 엑셀용 BOM 을 붙입니다. */
  function toCsv(opt) {
    const ids = idColsOf(opt);
    const lines = [['#'].concat(ids.map(c => c.label), opt.cols.map(c => c.label))];
    sorted(opt).forEach(function (r, i) {
      lines.push([rankNo(opt, r, i)]
        .concat(ids.map(c => (missing(r[c.key]) ? '' : r[c.key])), opt.cols.map(c => C().fmt(r[c.key], c.kind))));
    });
    if (opt.league) {
      lines.push([''].concat(ids.map((c, i) => (i === 0 ? '리그 평균' : '')), opt.cols.map(c => C().fmt(opt.league[c.key], c.kind))));
    }
    return '\uFEFF' + lines.map(l => l.map(csvCell).join(',')).join('\r\n') + '\r\n';
  }

  /** 머리글에 마우스를 올렸을 때 뜨는 설명 창 내용입니다. */
  function tipHtml(d) {
    if (!d) return '';
    let h = `<b>${esc(d.label)}</b>${esc(d.desc)}`;
    if (d.formula) h += `<span class="f">계산식: ${esc(d.formula)}</span>`;
    if (d.since) h += `<span class="f">${d.since}년부터 있습니다.</span>`;
    return h;
  }

  const api = { esc, indexClass, sortRows, pageOf, renderTable, toCsv, tipHtml };
  TS.table = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 선수 칸 스타일 붙이기**

`dashboard_js/css/stats.css` 끝에 붙입니다(앞부분은 고치지 않습니다).

```css

/* ===== 선수 통계 ===== */
/* 선수 표: # · 이름은 가로 스크롤해도 고정, 팀은 고정하지 않음 */
.ts-table th.ts-name, .ts-table td.ts-name { position: sticky; left: 2.6rem; z-index: 3; text-align: left; white-space: nowrap; background: var(--bg-secondary); border-right: 1px solid var(--border-color); font-weight: 600; }
.ts-table thead th.ts-name { z-index: 6; background: var(--bg-tertiary); }
.ts-table tr.ts-league td.ts-name { background: var(--bg-tertiary); }
.ts-table th.ts-pteam, .ts-table td.ts-pteam { text-align: left; white-space: nowrap; }
```

- [ ] **Step 5: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 103개 통과(98 + table.player 5), 실패 0. 기존 `table.test.js` 7개가 그대로 통과해야 팀 표가 안 바뀐 것입니다.

- [ ] **Step 6: 팀 통계 화면 그대로인지 다시 확인**

```bash
cd C:/tmp/bstats-team-stats-check
bash dom.sh "/pages/team-stats.html?season=2025" ts_after4.html
diff <(sed -n '/<main/,/<\/main>/p' ts_before.html) <(sed -n '/<main/,/<\/main>/p' ts_after4.html) && echo SAME_MAIN
```

Expected: `SAME_MAIN`

- [ ] **Step 7: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/stats/table.js dashboard_js/css/stats.css
git diff --cached --name-status
git commit -m "feat(stats): 표 앞 칸 구성(이름·팀)과 쪽 나누기 추가

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/stats/table.js dashboard_js/css/stats.css
```

---

### Task 5: 선수 페이지 상태·거르기·쪽 넘기기 순수 함수(player-stats/page.js)

**Files:**
- Create: `dashboard_js/js/player-stats/page.js` (순수 함수 부분)
- Test (저장소 밖): `tests/player-page.test.js`

**Interfaces:**
- Consumes: `TS.columns.PGROUPS`, `TS.columns.pdef`, `TS.metrics.qualFor`(시험), `TS.table.pageOf`(시험).
- Produces (`TS.playerPage`, Task 6 이 같은 파일 안에서 씀):
  - 상태 `st = { tab: 'bat'|'pit', group: 'dash'|'std'|'adv'|'sit'|'custom', season: number|null, team: string, pos: string, min: 'q'|'all'|number, sort: string, dir: ''|'asc'|'desc', page: number(0부터), size: 50|100|0, cols: string[] }`
  - `parseState(search)`, `toSearch(st)`
  - `visibleKeys(tab, group, season, custom)` → 칸 키 배열
  - `defaultSort(tab, group, keys, rows)`, `pickSort(st, keys, rows)` → `{ key, dir }`
  - `filterRows(rows, st, qualOf)` → 행 배열. `qualOf(row)` → `{ pa, outs } | null`
  - `needRegulation(teams, rank)` → boolean
  - `teamsOf(rows)`, `positionsOf(rows)` → 문자열 배열
  - `minOptions(tab)` → `[{ v, label }]`, `minLabel(tab, min)` → 문자열
  - `titleText(st, n)`, `csvName(st)`, `pagerHtml(pg, total, size)`, `caveatText(st, latest, live)` → 문자열
  - `dataReady(st, store)` → boolean
  - `ID_COLS` → table.js `idCols` 형식 `[{ key: 'name', … }, { key: 'team', … }]`

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/player-page.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, loadAs, fixture, refs } = require('./_load');
const M = load('metrics');
load('columns');
const T = load('table');
const P = loadAs('player-stats/page', 'playerPage');

const DEF = { tab: 'bat', group: 'dash', season: null, team: '', pos: '', min: 'q', sort: '', dir: '', page: 0, size: 50, cols: [] };
const st = o => Object.assign({}, DEF, o);

test('parseState: 기본값', () => {
  assert.deepEqual(P.parseState(''), DEF);
});

test('parseState: 값 읽기', () => {
  const s = P.parseState('?tab=pit&group=adv&season=2025&team=LG&min=30&sort=fip&dir=asc&page=3&size=100&cols=k9,x;y,era');
  assert.deepEqual(s, { tab: 'pit', group: 'adv', season: 2025, team: 'LG', pos: '', min: 30, sort: 'fip', dir: 'asc', page: 2, size: 100, cols: ['k9', 'era'] });
});

test('parseState: 잘못된 값은 기본값', () => {
  assert.deepEqual(P.parseState('?tab=zzz&group=foo&season=20x5&min=55&page=0&size=7&sort=<b>&dir=up'), DEF);
  assert.equal(P.parseState('?tab=pit&group=sit').group, 'dash');
  assert.equal(P.parseState('?tab=bat&group=sit').group, 'sit');
  assert.equal(P.parseState('?tab=pit&pos=%ED%8F%AC%EC%88%98').pos, '');
  assert.equal(P.parseState('?pos=%ED%8F%AC%EC%88%98').pos, '포수');
  assert.equal(P.parseState('?tab=pit&min=200').min, 'q');
  assert.equal(P.parseState('?min=50.5').min, 'q');
  assert.equal(P.parseState('?min=all').min, 'all');
  assert.equal(P.parseState('?size=all').size, 0);
});

test('toSearch ↔ parseState 왕복', () => {
  const s = { tab: 'bat', group: 'custom', season: 2025, team: 'LG', pos: '포수', min: 100, sort: 'wrcp', dir: 'desc', page: 1, size: 0, cols: ['pa', 'wrcp'] };
  assert.equal(P.toSearch(s), '?tab=bat&group=custom&season=2025&team=LG&pos=%ED%8F%AC%EC%88%98&min=100&sort=wrcp&dir=desc&page=2&size=all&cols=pa%2Cwrcp');
  assert.deepEqual(P.parseState(P.toSearch(s)), s);
  const d = st({ season: 2026 });
  assert.equal(P.toSearch(d), '?tab=bat&group=dash&season=2026');
  assert.deepEqual(P.parseState(P.toSearch(d)), d);
  assert.equal(P.toSearch(st({ tab: 'pit', season: 2025, min: 'all', size: 100 })), '?tab=pit&group=dash&season=2025&min=all&size=100');
});

test('visibleKeys: 묶음별 칸, 상황 묶음, 옛 시즌 OPS+', () => {
  assert.deepEqual(P.visibleKeys('bat', 'sit', 2025, null), ['pa', 'risp', 'ph', 'gw', 'multi', 'xr', 'gpa', 'ppa']);
  const old = P.visibleKeys('bat', 'dash', 1985, null);
  assert.equal(old[old.indexOf('wrcp') + 1], 'opsp');
  assert.ok(!P.visibleKeys('bat', 'dash', 2025, null).includes('opsp'));
  assert.equal(P.visibleKeys('pit', 'dash', 2025, null)[0], 'w');
  assert.equal(P.visibleKeys('pit', 'sit', 2025, null)[0], 'w');
  assert.deepEqual(P.visibleKeys('bat', 'custom', 2025, ['pa', 'nope', 'risp']), ['pa', 'risp']);
  assert.equal(P.visibleKeys('bat', 'custom', 2025, null)[0], 'g');
});

test('defaultSort·pickSort', () => {
  const dash = P.visibleKeys('bat', 'dash', 2025, null);
  assert.deepEqual(P.defaultSort('bat', 'dash', dash), { key: 'wrcp', dir: 'desc' });
  assert.deepEqual(P.defaultSort('bat', 'sit', P.visibleKeys('bat', 'sit', 2025, null)), { key: 'risp', dir: 'desc' });
  assert.deepEqual(P.defaultSort('pit', 'dash', P.visibleKeys('pit', 'dash', 2025, null)), { key: 'era', dir: 'asc' });
  assert.deepEqual(P.defaultSort('pit', 'adv', P.visibleKeys('pit', 'adv', 2025, null)), { key: 'fip', dir: 'asc' });
  const old = P.visibleKeys('bat', 'dash', 1985, null);
  assert.deepEqual(P.defaultSort('bat', 'dash', old, [{ wrcp: null, opsp: 120 }]), { key: 'opsp', dir: 'desc' });
  assert.deepEqual(P.pickSort(st({ sort: 'hr', dir: 'asc' }), dash), { key: 'hr', dir: 'asc' });
  assert.deepEqual(P.pickSort(st({ sort: 'era', dir: 'asc' }), dash), { key: 'wrcp', dir: 'desc' });
});

const rows = [
  { team: 'LG', pos: '포수', pa: 500, outs: 0 },
  { team: 'LG', pos: '내야수', pa: 440, outs: 0 },
  { team: 'KT', pos: '포수', pa: 120, outs: 0 },
  { team: 'XX', pos: '외야수', pa: 600, outs: 0 },
];
const rank = { LG: { g: 144 }, KT: { g: 144 } };
const qualOf = r => M.qualFor(r.team, rank, null);
const names = list => list.map(r => r.team + r.pa);

test('filterRows: 규정·최소·팀·포지션', () => {
  assert.deepEqual(names(P.filterRows(rows, st(), qualOf)), ['LG500']);
  assert.equal(P.filterRows(rows, st({ min: 'all' }), qualOf).length, 4);
  assert.deepEqual(names(P.filterRows(rows, st({ min: 100, pos: '포수' }), qualOf)), ['LG500', 'KT120']);
  assert.deepEqual(names(P.filterRows(rows, st({ min: 'all', team: 'LG' }), qualOf)), ['LG500', 'LG440']);
  const withReg = r => M.qualFor(r.team, rank, { team_games: 144, qual_pa: 446, qual_ip: 144 });
  assert.deepEqual(names(P.filterRows(rows, st(), withReg)), ['LG500', 'XX600']);
});

test('filterRows: 투수는 이닝(아웃 수)으로, 포지션은 보지 않음', () => {
  const pr = [{ team: 'LG', outs: 432 }, { team: 'LG', outs: 431 }, { team: 'LG', outs: 299 }];
  assert.equal(P.filterRows(pr, st({ tab: 'pit' }), qualOf).length, 1);
  assert.equal(P.filterRows(pr, st({ tab: 'pit', min: 100 }), qualOf).length, 2);
  assert.equal(P.filterRows(pr, st({ tab: 'pit', pos: '포수', min: 'all' }), qualOf).length, 3);
});

test('filterRows: 2025 픽스처 규정 이상 43명', () => {
  const R = refs();
  const rk = M.rankFor(R.rank, 2025);
  const all = M.playerBatting(fixture('batters_2025').batters, 2025, M.indexRefs(R)).rows;
  assert.equal(P.filterRows(all, st({ season: 2025 }), r => M.qualFor(r.team, rk, null)).length, 43);
});

test('needRegulation: 순위표에 경기 수가 없는 팀이 있을 때만', () => {
  assert.equal(P.needRegulation(['LG', 'KT'], rank), false);
  assert.equal(P.needRegulation(['LG', 'XX'], rank), true);
  assert.equal(P.needRegulation(['LG'], { LG: { g: 0 } }), true);
  assert.equal(P.needRegulation([], {}), false);
});

test('teamsOf·positionsOf', () => {
  assert.deepEqual(P.teamsOf([{ team: '한화' }, { team: 'LG' }, { team: '한화' }, { team: '' }]), ['LG', '한화']);
  assert.deepEqual(P.positionsOf([{ pos: '외야수' }, { pos: '투수' }, { pos: '포수' }, { pos: '' }, { pos: '내야수' }, { pos: '외야수' }]), ['포수', '내야수', '외야수', '투수']);
});

test('minOptions·minLabel·titleText·csvName', () => {
  assert.deepEqual(P.minOptions('bat').map(o => o.label), ['규정 이상', '전체', '50타석', '100타석', '200타석', '300타석']);
  assert.deepEqual(P.minOptions('pit').map(o => o.v), ['q', 'all', 10, 30, 50, 100]);
  assert.equal(P.minLabel('pit', 30), '30이닝 이상');
  assert.equal(P.titleText(st({ season: 2026 }), 62), '타자 (2026, 규정 이상 62명)');
  assert.equal(P.titleText(st({ season: 2025, team: 'LG', pos: '포수', min: 'all' }), 3), '타자 (2025, LG, 포수, 전체 3명)');
  assert.equal(P.titleText(st({ tab: 'pit', season: 2025, min: 50 }), 40), '투수 (2025, 50이닝 이상 40명)');
  assert.equal(P.csvName(st({ season: 2025 })), 'bstats_player_batting_dash_2025.csv');
  assert.equal(P.csvName(st({ tab: 'pit', group: 'adv', season: 1999 })), 'bstats_player_pitching_adv_1999.csv');
});

test('pagerHtml: 쪽이 여럿이면 이전·다음, 끝에서는 막힘, 한 쪽 인원 고르개', () => {
  const h = P.pagerHtml(T.pageOf(120, { size: 50, index: 0 }), 120, 50);
  assert.match(h, /120명 중 1~50/);
  assert.match(h, /<button type="button" class="tabbtn" data-page="prev" disabled>이전<\/button>/);
  assert.match(h, /1 \/ 3쪽/);
  assert.match(h, /<button type="button" class="tabbtn" data-page="next">다음<\/button>/);
  assert.match(h, /<option value="50" selected>50명<\/option>/);
  const last = P.pagerHtml(T.pageOf(120, { size: 50, index: 2 }), 120, 50);
  assert.match(last, /120명 중 101~120/);
  assert.match(last, /data-page="next" disabled/);
  const all = P.pagerHtml(T.pageOf(120, { size: 0, index: 0 }), 120, 0);
  assert.ok(!all.includes('data-page'));
  assert.match(all, /<option value="0" selected>전체<\/option>/);
});

test('caveatText: 조건마다 붙는 말', () => {
  const base = P.caveatText(st({ season: 2025 }), 2026, false);
  assert.match(base, /^출처: KBO 공식 선수 기록입니다\./);
  assert.match(base, /트레이드/);
  assert.match(base, /규정 이상은/);
  assert.ok(!/진행 중/.test(base));
  assert.ok(!/2007년 이전/.test(base));
  const live = P.caveatText(st({ season: 2026 }), 2026, true);
  assert.match(live, /진행 중인 시즌/);
  assert.match(live, /실시간 순위/);
  assert.match(P.caveatText(st({ season: 1985 }), 2026, false), /2007년 이전/);
  assert.match(P.caveatText(st({ season: 2025, group: 'sit' }), 2026, false), /상황 묶음/);
  assert.ok(!/규정 이상은/.test(P.caveatText(st({ season: 2025, min: 'all' }), 2026, false)));
});

test('dataReady·ID_COLS', () => {
  assert.equal(P.dataReady(st({ season: 2025 }), { season: {} }), false);
  assert.equal(P.dataReady(st({ season: 2025 }), { season: { 2025: {} } }), true);
  assert.deepEqual(P.ID_COLS.map(c => [c.key, c.label, c.cls]), [['name', '이름', 'ts-name'], ['team', '팀', 'ts-pteam']]);
  assert.equal(P.ID_COLS[0].href({ id: '62558' }), 'player-analytics?id=62558');
  assert.equal(P.ID_COLS[0].href({ id: null }), null);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/player-page.test.js"`
Expected: FAIL (`ENOENT … player-stats\page.js`).

- [ ] **Step 3: 순수 함수 쓰기**

`dashboard_js/js/player-stats/page.js` 를 만듭니다.

```js
/*
 * 선수 통계 페이지 조립입니다. 상태(탭·묶음·시즌·팀·포지션·최소·정렬·쪽·칸)와
 * 주소, 화면 그리기, 이벤트를 맡습니다.
 *
 * 계산은 stats/metrics.js, 칸 정의는 stats/columns.js(pdef·PGROUPS·PORDER),
 * 데이터는 stats/data.js, 표는 stats/table.js 가 합니다. 위쪽 순수 함수는
 * Node 로 검증하고, 아래 화면 부분은 브라우저에서만 돕니다.
 *
 * 설명 창·CSV·링크 복사는 팀 통계 page.js 와 비슷하지만, 팀 통계를
 * 건드리지 않으려고 따로 둡니다(설계 6장).
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const TABS = ['bat', 'pit'];
  const GROUPS_BY_TAB = { bat: ['dash', 'std', 'adv', 'sit', 'custom'], pit: ['dash', 'std', 'adv', 'custom'] };
  const MIN_STEPS = { bat: [50, 100, 200, 300], pit: [10, 30, 50, 100] };
  const SIZES = [50, 100, 0];
  const POS_ORDER = ['포수', '내야수', '외야수', '지명타자', '투수'];
  const PBP_MIN = 2008;

  const okKey = k => /^[a-z0-9]+$/.test(k || '');

  // 앞 칸입니다. 이름은 선수 분석 페이지로 갑니다(같은 pages/ 폴더).
  const ID_COLS = [
    {
      key: 'name', label: '이름', cls: 'ts-name',
      href: r => (r.id === null || r.id === undefined || r.id === '' ? null : 'player-analytics?id=' + encodeURIComponent(r.id)),
    },
    { key: 'team', label: '팀', cls: 'ts-pteam' },
  ];

  /** 주소의 ?… 를 상태로 읽습니다. 잘못된 값은 기본값으로 둡니다. */
  function parseState(search) {
    const p = new URLSearchParams(search || '');
    const g = k => p.get(k) || '';
    const tab = TABS.includes(g('tab')) ? g('tab') : 'bat';
    const m = g('min');
    let min = 'q';
    if (m === 'all') min = 'all';
    else if (/^\d+$/.test(m) && MIN_STEPS[tab].includes(Number(m))) min = Number(m);
    const pageNo = /^\d{1,4}$/.test(g('page')) ? Number(g('page')) : 1;
    return {
      tab: tab,
      group: GROUPS_BY_TAB[tab].includes(g('group')) ? g('group') : 'dash',
      season: /^\d{4}$/.test(g('season')) ? Number(g('season')) : null,
      team: g('team'),
      pos: tab === 'bat' ? g('pos') : '',
      min: min,
      sort: okKey(g('sort')) ? g('sort') : '',
      dir: g('dir') === 'asc' || g('dir') === 'desc' ? g('dir') : '',
      page: pageNo >= 1 ? pageNo - 1 : 0,
      size: g('size') === '100' ? 100 : g('size') === 'all' ? 0 : 50,
      cols: g('cols').split(',').filter(okKey),
    };
  }

  /** 상태를 주소의 ?… 로 씁니다. 기본값은 적지 않습니다. */
  function toSearch(s) {
    const p = new URLSearchParams();
    p.set('tab', s.tab);
    p.set('group', s.group);
    if (s.season) p.set('season', String(s.season));
    if (s.team) p.set('team', s.team);
    if (s.tab === 'bat' && s.pos) p.set('pos', s.pos);
    if (s.min !== 'q') p.set('min', String(s.min));
    if (s.sort) { p.set('sort', s.sort); p.set('dir', s.dir || 'desc'); }
    if (s.page > 0) p.set('page', String(s.page + 1));
    if (s.size !== 50) p.set('size', s.size ? String(s.size) : 'all');
    if (s.group === 'custom' && s.cols && s.cols.length) p.set('cols', s.cols.join(','));
    return '?' + p.toString();
  }

  /** 지금 보일 칸입니다. */
  function visibleKeys(tab, group, season, custom) {
    const C = TS.columns;
    const G = C.PGROUPS[tab];
    let keys;
    if (group === 'custom') keys = (custom && custom.length ? custom : G.dash).slice();
    else keys = (G[group] || G.dash).slice();
    // 2007 이전은 wRC+ 가 비므로 대시보드에 OPS+ 를 붙입니다(팀 통계와 같음).
    if (tab === 'bat' && group === 'dash' && season < PBP_MIN && !keys.includes('opsp')) {
      const i = keys.indexOf('wrcp');
      keys.splice(i < 0 ? keys.length : i + 1, 0, 'opsp');
    }
    return keys.filter(k => C.pdef(tab, k));
  }

  const SORT_PREF = {
    bat: [['wrcp', 'desc'], ['opsp', 'desc'], ['avg', 'desc'], ['ops', 'desc']],
    sit: [['risp', 'desc']],
    pit: [['era', 'asc'], ['fip', 'asc'], ['whip', 'asc']],
  };

  // rows 를 주면 모든 선수가 값 없음(null)인 칸(예: 2007년 이전 wRC+)은 기본 정렬에서 건너뜁니다.
  function defaultSort(tab, group, keys, rows) {
    const has = k => !rows || !rows.length || rows.some(r => r && r[k] != null && !Number.isNaN(r[k]));
    const pref = tab === 'bat' && group === 'sit' ? SORT_PREF.sit : SORT_PREF[tab];
    for (const [k, d] of pref) if (keys.includes(k) && has(k)) return { key: k, dir: d };
    return { key: keys[0], dir: 'desc' };
  }

  function pickSort(st, keys, rows) {
    if (st.sort && keys.includes(st.sort)) return { key: st.sort, dir: st.dir || 'desc' };
    return defaultSort(st.tab, st.group, keys, rows);
  }

  /**
   * 고른 조건(팀·포지션·최소)에 맞는 선수입니다. 규정 이상(min 'q')은
   * qualOf(row) 가 준 기준 { pa, outs } 로 보고, 기준을 모르면(null) 뺍니다.
   * 투수는 이닝을 아웃 수(outs)로 비교하고 포지션은 보지 않습니다.
   */
  function filterRows(rows, st, qualOf) {
    return (rows || []).filter(function (r) {
      if (st.team && r.team !== st.team) return false;
      if (st.tab === 'bat' && st.pos && r.pos !== st.pos) return false;
      if (st.min === 'all') return true;
      if (typeof st.min === 'number') return st.tab === 'bat' ? r.pa >= st.min : r.outs >= st.min * 3;
      const q = qualOf(r);
      if (!q) return false;
      return st.tab === 'bat' ? r.pa >= q.pa : r.outs >= q.outs;
    });
  }

  /** 순위표에 경기 수가 없는 팀이 있으면 true 입니다(그때만 시즌 공통 규정을 받습니다). */
  function needRegulation(teams, rank) {
    return (teams || []).some(t => !(rank && rank[t] && rank[t].g > 0));
  }

  function teamsOf(rows) {
    return [...new Set((rows || []).map(r => r.team).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
  }

  function positionsOf(rows) {
    const order = p => { const i = POS_ORDER.indexOf(p); return i < 0 ? POS_ORDER.length : i; };
    return [...new Set((rows || []).map(r => r.pos).filter(Boolean))]
      .sort((a, b) => order(a) - order(b) || a.localeCompare(b, 'ko'));
  }

  function minOptions(tab) {
    const unit = tab === 'bat' ? '타석' : '이닝';
    return [{ v: 'q', label: '규정 이상' }, { v: 'all', label: '전체' }]
      .concat(MIN_STEPS[tab].map(n => ({ v: n, label: `${n}${unit}` })));
  }

  function minLabel(tab, min) {
    if (min === 'q') return '규정 이상';
    if (min === 'all') return '전체';
    return `${min}${tab === 'bat' ? '타석' : '이닝'} 이상`;
  }

  /** 표 제목입니다. 예: 타자 (2026, 규정 이상 62명) */
  function titleText(st, n) {
    const parts = [String(st.season)];
    if (st.team) parts.push(st.team);
    if (st.tab === 'bat' && st.pos) parts.push(st.pos);
    parts.push(`${minLabel(st.tab, st.min)} ${n}명`);
    return `${st.tab === 'bat' ? '타자' : '투수'} (${parts.join(', ')})`;
  }

  function csvName(st) {
    return ['bstats', 'player', st.tab === 'bat' ? 'batting' : 'pitching', st.group, String(st.season)].join('_') + '.csv';
  }

  /** 표 아래 쪽 넘기기 줄입니다. pg 는 table.pageOf 결과, size 는 한 쪽 인원(0 = 전체)입니다. */
  function pagerHtml(pg, total, size) {
    const btn = (k, label, off) => `<button type="button" class="tabbtn" data-page="${k}"${off ? ' disabled' : ''}>${label}</button>`;
    let h = `<span class="text-muted">${total}명 중 ${total ? pg.start + 1 : 0}~${pg.end}</span>`;
    if (pg.count > 1) {
      h += btn('prev', '이전', pg.index === 0)
        + `<span class="ts-pager-no">${pg.index + 1} / ${pg.count}쪽</span>`
        + btn('next', '다음', pg.index >= pg.count - 1);
    }
    h += '<label for="page-size">한 쪽</label><select id="page-size" class="input">'
      + SIZES.map(v => `<option value="${v}"${v === size ? ' selected' : ''}>${v ? v + '명' : '전체'}</option>`).join('')
      + '</select>';
    return h;
  }

  const CAVEAT = '출처: KBO 공식 선수 기록입니다. 비율 지표는 성분에서 다시 계산합니다. 리그 평균 행은 고른 조건과 상관없이 그 시즌 리그 전체 선수의 합으로 셉니다.';
  const TRADE_CAVEAT = ' 시즌 중 트레이드된 선수는 공식 기록이 한 줄이라 마지막 팀으로 보이고, 구장 보정도 마지막 팀 홈구장 기준입니다.';
  const QUAL_CAVEAT = ' 규정 이상은 타석이 소속팀 경기 수 × 3.1(반올림) 이상, 이닝이 소속팀 경기 수 이상인 선수입니다.';
  const LIVE_QUAL_CAVEAT = ' 올해 소속팀 경기 수는 KBO 실시간 순위입니다.';
  const LIVE_SEASON_CAVEAT = ' 진행 중인 시즌은 최신 일일 갱신 기준이라 KBO 실시간과 1~2경기 차이가 날 수 있습니다.';
  const OLD_CAVEAT = ' 2007년 이전은 파크팩터가 없어 OPS+·ERA-·FIP-를 구장 보정 없이 계산했고, wOBA·wRC+는 2008년부터 있습니다.';
  const SIT_CAVEAT = ' 상황 묶음(득점권·대타·결승타·멀티히트·XR·GPA·P/PA)은 KBO 공식 기록 값 그대로라 리그 평균은 비워 둡니다.';

  /** 표 아래 출처·주의 문구입니다. latest 는 가장 최근 시즌, live 는 실시간 순위로 규정을 셌는지입니다. */
  function caveatText(st, latest, live) {
    return CAVEAT + TRADE_CAVEAT
      + (st.min === 'q' ? QUAL_CAVEAT + (live ? LIVE_QUAL_CAVEAT : '') : '')
      + (st.season === latest ? LIVE_SEASON_CAVEAT : '')
      + (st.season < PBP_MIN ? OLD_CAVEAT : '')
      + (st.group === 'sit' ? SIT_CAVEAT : '');
  }

  /** 지금 상태를 그리는 데 필요한 시즌 기록이 왔는지 봅니다. */
  function dataReady(st, store) {
    return !!(store.season && store.season[st.season]);
  }

  // ===== 화면(브라우저에서만) =====

  const api = {
    ID_COLS, parseState, toSearch, visibleKeys, defaultSort, pickSort, filterRows, needRegulation,
    teamsOf, positionsOf, minOptions, minLabel, titleText, csvName, pagerHtml, caveatText, dataReady,
  };
  TS.playerPage = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 118개 통과(103 + player-page 15), 실패 0.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/player-stats/page.js
git diff --cached --name-status
git commit -m "feat(player-stats): 선수 통계 상태·거르기·쪽 넘기기 순수 함수

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/player-stats/page.js
```

---

### Task 6: 선수 페이지 화면(player-stats.html 새로 쓰기 + page.js 화면 부분)

**Files:**
- Modify: `dashboard_js/pages/player-stats.html` (전체를 새로)
- Modify: `dashboard_js/js/player-stats/page.js` (`// ===== 화면(브라우저에서만) =====` 줄 뒤, `const api` 앞에 화면 부분, 맨 끝에 자동 시작)
- Modify: `dashboard_js/css/stats.css` (끝에 쪽 넘기기 규칙)
- Test (저장소 밖): `tests/player-html.test.js`

**Interfaces:**
- Consumes: Task 2~5 의 모든 것. 전역 `KBO_API_BASE`(config.js), `createLoadingSpinner`·`createEmptyState`·`createErrorMessage`(components.js).
- Produces: 화면. HTML id: `ps-page`(자동 시작 표시), `ts-tabs`, `ts-groups`, `group-sit`, `season-select`, `team-select`, `pos-group`, `pos-select`, `min-select`, `col-panel`, `col-list`, `col-count`, `col-close`, `ts-alerts`, `ts-title`, `csv-btn`, `link-btn`, `ts-table`, `ts-pager`, `caveat-note`.

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/player-html.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { REPO_JS } = require('./_load');

const html = fs.readFileSync(path.join(REPO_JS, '..', 'pages', 'player-stats.html'), 'utf8');
const page = fs.readFileSync(path.join(REPO_JS, 'player-stats', 'page.js'), 'utf8');

test('player-stats.html: 스크립트 순서·stats.css·인라인 style 없음', () => {
  assert.deepEqual([...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]), [
    '../js/config.js', '../js/theme-toggle.js', '../js/nav.js',
    '../js/api.js', '../js/components.js',
    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/stats/data.js', '../js/stats/table.js',
    '../js/player-stats/page.js',
  ]);
  assert.match(html, /href="\.\.\/css\/style\.css">\r?\n    <link rel="stylesheet" href="\.\.\/css\/stats\.css">/);
  assert.ok(!html.includes('<style>'));
  assert.ok(!/<script>/.test(html));
});

test('player-stats.html: 화면이 쓰는 id 가 모두 있음', () => {
  for (const id of ['ps-page', 'ts-tabs', 'ts-groups', 'group-sit', 'season-select', 'team-select', 'pos-group', 'pos-select',
    'min-select', 'col-panel', 'col-list', 'col-count', 'col-close', 'ts-alerts', 'ts-title', 'csv-btn', 'link-btn',
    'ts-table', 'ts-pager', 'caveat-note']) {
    assert.ok(html.includes(`id="${id}"`), id);
  }
});

test('player-stats.html: 메뉴·탭·묶음·버튼 글자', () => {
  assert.match(html, /<a href="player-stats" class="nav-link active">선수 통계<\/a>/);
  assert.match(html, /<a href="team-stats" class="nav-link">팀 통계<\/a>/);
  assert.match(html, /data-tab="bat">타격<\/button>[\s\S]*data-tab="pit">투구<\/button>/);
  assert.ok(!html.includes('data-tab="rec"'));
  for (const g of ['dash">대시보드', 'std">표준', 'adv">고급', 'sit" id="group-sit">상황', 'custom">사용자 지정']) assert.ok(html.includes(`data-group="${g}`), g);
  assert.match(html, /id="link-btn" class="tabbtn" title="지금 보는 화면 그대로 열리는 주소를 복사합니다\.">링크 복사<\/button>/);
  assert.ok(!html.includes('team-record-link'));
});

test('page.js: ps-page 가 있을 때만 스스로 시작', () => {
  assert.match(page, /document\.getElementById\('ps-page'\)/);
  assert.ok(!page.includes("getElementById('ts-table')"));
});
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/player-html.test.js"`
Expected: FAIL (옛 페이지라 스크립트·id 가 다름).

- [ ] **Step 2: player-stats.html 새로 쓰기**

`dashboard_js/pages/player-stats.html` 전체를 이렇게 씁니다.

```html
<!DOCTYPE html>
<html lang="ko">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>선수 통계 - Bstats</title>
    <meta name="description" content="KBO 선수별 타격·투구 기록 (규정 이상, wOBA·wRC+·FIP·상황 기록)">

    <!-- Google Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0" rel="stylesheet">

    <!-- Favicon (다이아몬드) -->
    <link rel="icon" href="../assets/favicon/diamond.ico" sizes="any">
    <link rel="icon" type="image/svg+xml" href="../assets/favicon/diamond.svg">
    <link rel="apple-touch-icon" href="../assets/favicon/diamond-180.png">

    <!-- Styles -->
    <link rel="stylesheet" href="../css/style.css">
    <link rel="stylesheet" href="../css/stats.css">
    <script src="../js/config.js"></script>
    <script src="../js/theme-toggle.js"></script>
    <script src="../js/nav.js"></script>
</head>

<body>
    <!-- Header -->
    <header class="header">
        <div class="header-content">
            <a href="../" class="logo">
                <img src="../assets/favicon/diamond.svg" alt="" class="logo-icon" width="26" height="26">
                <span>Bstats</span>
            </a>
            <nav class="nav">
                <a href="../" class="nav-link">홈</a>
                <a href="team-stats" class="nav-link">팀 통계</a>
                <a href="player-stats" class="nav-link active">선수 통계</a>
                <a href="player-analytics" class="nav-link">선수 분석</a>
                <a href="article" class="nav-link">아티클</a>
                <a href="factor-stats" class="nav-link">요인 통계</a>
                <a href="database-explorer" class="nav-link">데이터 탐색</a>
            </nav>
        </div>
    </header>

    <main class="container" id="ps-page">
        <h1 class="fade-in">선수 통계</h1>
        <p class="text-secondary mb-3">KBO 선수별 기록입니다. 묶음 탭으로 지표 묶음을 바꿉니다. <span class="ts-term">점선 밑줄</span>이 있는 지표에 마우스를 올리면 뜻과 계산식이 나오고, 누르면 정렬됩니다.</p>

        <div class="fs-tabs" id="ts-tabs">
            <button type="button" class="fs-tab active" data-tab="bat">타격</button>
            <button type="button" class="fs-tab" data-tab="pit">투구</button>
        </div>

        <div class="ts-groups" id="ts-groups">
            <button type="button" class="tabbtn active" data-group="dash">대시보드</button>
            <button type="button" class="tabbtn" data-group="std">표준</button>
            <button type="button" class="tabbtn" data-group="adv">고급</button>
            <button type="button" class="tabbtn" data-group="sit" id="group-sit">상황</button>
            <button type="button" class="tabbtn" data-group="custom">사용자 지정</button>
        </div>

        <div class="card ctrl-card">
            <div class="card-body ctrl-bar">
                <div class="ctrl-group">
                    <label for="season-select"><strong>시즌</strong></label>
                    <select id="season-select" class="input" style="max-width:120px;">
                        <option value="">불러오는 중…</option>
                    </select>
                </div>
                <div class="ctrl-group">
                    <label for="team-select"><strong>팀</strong></label>
                    <select id="team-select" class="input" style="max-width:120px;">
                        <option value="">전체</option>
                    </select>
                </div>
                <div class="ctrl-group" id="pos-group">
                    <label for="pos-select"><strong>포지션</strong></label>
                    <select id="pos-select" class="input" style="max-width:120px;">
                        <option value="">전체</option>
                    </select>
                </div>
                <div class="ctrl-divider" aria-hidden="true"></div>
                <div class="ctrl-group">
                    <label for="min-select"><strong>최소</strong></label>
                    <select id="min-select" class="input" style="max-width:140px;">
                        <option value="q">규정 이상</option>
                    </select>
                </div>
                <div id="col-panel" class="col-panel hidden">
                    <div class="col-panel-head">
                        <strong>보일 칸</strong>
                        <span class="text-muted" id="col-count"></span>
                        <span class="col-panel-btns">
                            <button type="button" data-col-preset="basic" class="tabbtn">대시보드와 같게</button>
                            <button type="button" data-col-preset="all" class="tabbtn">전체</button>
                            <button type="button" id="col-close" class="tabbtn">닫기</button>
                        </span>
                    </div>
                    <div id="col-list" class="col-list"></div>
                </div>
            </div>
        </div>

        <div id="ts-alerts" class="ts-alerts"></div>

        <section>
            <div class="card ts-card">
                <div class="card-header">
                    <h3 class="card-title" id="ts-title">타자</h3>
                    <div class="ts-actions">
                        <button type="button" id="csv-btn" class="tabbtn">CSV</button>
                        <button type="button" id="link-btn" class="tabbtn" title="지금 보는 화면 그대로 열리는 주소를 복사합니다.">링크 복사</button>
                    </div>
                </div>
                <div class="card-body">
                    <div id="ts-table"></div>
                    <div id="ts-pager" class="ts-pager"></div>
                </div>
            </div>

            <div class="card mt-3"
                style="background: linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(139, 92, 246, 0.1) 100%);">
                <div class="card-body">
                    <p class="text-muted" style="font-size:0.85rem;margin:0;" id="caveat-note"></p>
                </div>
            </div>
        </section>
    </main>

    <script src="../js/api.js"></script>
    <script src="../js/components.js"></script>
    <script src="../js/stats/metrics.js"></script>
    <script src="../js/stats/columns.js"></script>
    <script src="../js/stats/data.js"></script>
    <script src="../js/stats/table.js"></script>
    <script src="../js/player-stats/page.js"></script>
</body>

</html>
```

- [ ] **Step 3: page.js 에 화면 부분 넣기**

`dashboard_js/js/player-stats/page.js` 의 `// ===== 화면(브라우저에서만) =====` 줄 바로 뒤(빈 줄 다음, `const api = {` 앞)에 넣습니다.

```js

  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, standings: null, reg: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    seasonErrors: [], seq: 0, last: null, latest: new Date().getFullYear(),
  };

  let tipHide = function () {};

  function $(id) { return document.getElementById(id); }
  function keysNow() { return visibleKeys(S.st.tab, S.st.group, S.st.season, S.custom[S.st.tab]); }

  function writeUrl(replace) {
    const st = S.st;
    st.cols = st.group === 'custom' ? (S.custom[st.tab] || []) : [];
    const url = location.pathname + toSearch(st);
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
  }

  /** 상태를 받은 시즌 목록에 맞춥니다. */
  function normalize() {
    const st = S.st;
    if (!st.season || !S.seasons.includes(st.season)) st.season = S.seasons[0];
    if (st.group === 'custom' && st.cols.length) S.custom[st.tab] = st.cols.slice();
  }

  function errAlerts(list, errors) {
    (errors || []).forEach(function (e) {
      list.push({ kind: 'warn', text: `${e.what} 자료를 받지 못했습니다 (${e.error}). 이 자료가 필요한 칸은 '-'로 둡니다.` });
    });
  }

  function renderAlerts(list) {
    $('ts-alerts').innerHTML = list
      .map(a => `<div class="ts-alert ts-alert-${a.kind}">${TS.table.esc(a.text)}</div>`).join('');
  }

  /**
   * 규정에 쓸 순위표 { rank, live } 입니다. 올해는 실시간 순위, 아니면 저장된
   * 순위표입니다. 실시간 순위를 못 받으면 alerts 에 알리고 저장된 순위표로 갑니다.
   */
  function rankNow(alerts) {
    const M = TS.metrics, y = S.st.season;
    if (y === S.latest && S.standings) {
      if (!S.standings.errors.length && S.standings.teams.length) {
        return { rank: M.rankFromStandings(S.standings.teams), live: true };
      }
      if (alerts) {
        errAlerts(alerts, S.standings.errors);
        alerts.push({ kind: 'warn', text: '실시간 순위를 받지 못해 저장된 순위표의 팀 경기 수로 규정을 셉니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다.' });
      }
    }
    return { rank: M.rankFor(S.refs.rank, y), live: false };
  }

  /** 지금 화면에 필요한 데이터를 받습니다. 받은 것은 기억하고, 실패한 것은 다시 받습니다. */
  async function ensureData() {
    const st = S.st, y = st.season, D = TS.data, base = root.KBO_API_BASE;
    const stale = x => !x || x.errors.length > 0;
    const jobs = [];
    if (stale(S.season[y])) jobs.push(D.loadSeason(base, y).then(r => { S.season[y] = r; }));
    if (st.min === 'q' && y === S.latest && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
    await Promise.all(jobs);
    // 순위표에 경기 수가 없는 팀이 있을 때만 시즌 공통 규정을 받습니다.
    if (st.min === 'q' && stale(S.reg)) {
      const sd = S.season[y];
      const list = (st.tab === 'bat' ? sd.batters : sd.pitchers) || [];
      if (needRegulation(list.map(p => p.player_team).filter(Boolean), rankNow(null).rank)) {
        S.reg = await D.loadRegulation(base);
      }
    }
  }

  function fillSeasons() {
    const el = $('season-select');
    el.innerHTML = S.seasons.map(y => `<option value="${y}">${y}</option>`).join('');
    el.value = String(S.st.season);
  }

  /** 팀·포지션 고르개를 채웁니다. 주소에 있던 값이 목록에 없으면 '전체'로 둡니다. */
  function fillSelect(id, list, key) {
    const el = $(id), esc = TS.table.esc;
    if (S.st[key] && !list.includes(S.st[key])) S.st[key] = '';
    el.innerHTML = '<option value="">전체</option>'
      + list.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    el.value = S.st[key];
  }

  function fillMin() {
    const el = $('min-select');
    el.innerHTML = minOptions(S.st.tab).map(o => `<option value="${o.v}">${o.label}</option>`).join('');
    el.value = String(S.st.min);
  }

  function syncTabs() {
    const st = S.st;
    document.querySelectorAll('#ts-tabs [data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === st.tab));
    document.querySelectorAll('#ts-groups [data-group]').forEach(b => b.classList.toggle('active', b.dataset.group === st.group));
    $('group-sit').hidden = st.tab !== 'bat';
    $('pos-group').hidden = st.tab !== 'bat';
    $('col-panel').classList.toggle('hidden', !(st.group === 'custom' && S.panelOpen));
  }

  function renderColPanel() {
    const tab = S.st.tab, C = TS.columns, esc = TS.table.esc;
    const on = new Set(S.custom[tab] || C.PGROUPS[tab].dash);
    const defs = C.PORDER[tab].map(k => C.pdef(tab, k));
    $('col-list').innerHTML = defs.map(d => `<label class="${on.has(d.key) ? '' : 'off'}" title="${esc(d.desc)}">`
      + `<input type="checkbox" data-col="${d.key}"${on.has(d.key) ? ' checked' : ''}>${esc(d.label)}</label>`).join('');
    $('col-count').textContent = `${defs.filter(d => on.has(d.key)).length}개 / ${defs.length}개`;
  }

  /** 받은 데이터로 지금 탭을 그립니다. 서버를 부르지 않습니다. 데이터가 아직이면 그리지 않습니다. */
  function render() {
    if (!dataReady(S.st, S)) return;
    tipHide();
    const st = S.st, C = TS.columns, M = TS.metrics, T = TS.table;
    const y = st.season;
    const alerts = [];
    errAlerts(alerts, S.seasonErrors);
    errAlerts(alerts, S.refs.errors);
    const sd = S.season[y];
    errAlerts(alerts, sd.errors);
    syncTabs();

    const ix = M.indexRefs(S.refs);
    const tbl = st.tab === 'bat' ? M.playerBatting(sd.batters, y, ix) : M.playerPitching(sd.pitchers, y, ix);
    let qualOf = () => null;
    let live = false;
    if (st.min === 'q') {
      const rk = rankNow(alerts);
      live = rk.live;
      const reg = S.reg && S.reg.regulation ? S.reg.regulation[String(y)] || null : null;
      if (S.reg) errAlerts(alerts, S.reg.errors);
      const miss = teamsOf(tbl.rows).filter(t => !(rk.rank[t] && rk.rank[t].g > 0));
      if (miss.length && reg) {
        alerts.push({ kind: 'info', text: `순위표에 없는 팀(${miss.join(', ')})은 그 시즌 공통 규정(${reg.qual_pa}타석, ${reg.qual_ip}이닝)으로 셉니다.` });
      } else if (miss.length) {
        alerts.push({ kind: 'warn', text: `규정을 셀 팀 경기 수를 몰라 ${miss.join(', ')} 선수는 규정 이상에서 빠집니다. 최소를 '전체'로 바꾸면 보입니다.` });
      }
      qualOf = r => M.qualFor(r.team, rk.rank, reg);
    }

    fillSelect('team-select', teamsOf(tbl.rows), 'team');
    if (st.tab === 'bat') fillSelect('pos-select', positionsOf(tbl.rows), 'pos');
    fillMin();

    const keys = keysNow();
    const cols = keys.map(k => C.pdef(st.tab, k));
    const shown = filterRows(tbl.rows, st, qualOf);
    const sort = pickSort(st, keys, tbl.rows);
    const league = tbl.rows.length ? tbl.league : null;
    const pg = T.pageOf(shown.length, { size: st.size, index: st.page });
    if (pg.index !== st.page) { st.page = pg.index; writeUrl(true); }

    S.last = { cols: cols, rows: shown, league: league, sort: sort, idCols: ID_COLS, all: tbl.rows };
    $('ts-title').textContent = titleText(st, shown.length);
    if (!tbl.rows.length) {
      $('ts-table').innerHTML = createEmptyState('해당 시즌 기록이 없습니다.');
    } else {
      $('ts-table').innerHTML = (shown.length ? '' : '<p class="text-muted ts-empty">조건에 맞는 선수가 없습니다.</p>')
        + T.renderTable({ cols: cols, rows: shown, league: league, sort: sort, idCols: ID_COLS, page: { size: st.size, index: st.page } });
    }
    $('ts-pager').innerHTML = shown.length ? pagerHtml(pg, shown.length, st.size) : '';
    $('caveat-note').textContent = caveatText(st, S.latest, live);
    renderAlerts(alerts);
    if (!$('col-panel').classList.contains('hidden')) renderColPanel();
  }

  /** 주소를 쓰고, 필요한 데이터를 받은 뒤 그립니다. 늦게 온 이전 응답은 버립니다. */
  async function refresh(opt) {
    opt = opt || {};
    const seq = ++S.seq;
    if (!opt.noUrl) writeUrl(opt.replace);
    $('ts-table').innerHTML = createLoadingSpinner();
    $('ts-pager').innerHTML = '';
    try {
      await ensureData();
    } catch (e) {
      if (seq !== S.seq) return;
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('선수 기록을 불러오는데 실패했습니다.');
      return;
    }
    if (seq !== S.seq) return;
    render();
  }

  function downloadCsv() {
    if (!S.last) return;
    const csv = TS.table.toCsv(S.last);
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = csvName(S.st);
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async function copyLink() {
    const btn = $('link-btn');
    try {
      await navigator.clipboard.writeText(location.href);
      btn.textContent = '복사됨';
    } catch (e) {
      root.prompt('이 주소를 복사해 주세요', location.href);
    }
    setTimeout(() => { btn.textContent = '링크 복사'; }, 1500);
  }

  function bindTips() {
    let box = null;
    function hideTip() { if (box) box.style.display = 'none'; }
    tipHide = hideTip;
    window.addEventListener('scroll', hideTip, { passive: true });
    document.addEventListener('touchstart', function (e) {
      if (!(e.target.closest && e.target.closest('.ts-term'))) hideTip();
    }, { passive: true });
    document.addEventListener('mouseover', function (e) {
      const el = e.target.closest && e.target.closest('.ts-term[data-col]');
      if (!el) return;
      const d = TS.columns.pdef(S.st.tab, el.dataset.col);
      if (!d) return;
      if (!box) {
        box = document.createElement('div');
        box.className = 'tip-box';
        document.body.appendChild(box);
      }
      box.innerHTML = TS.table.tipHtml(d);
      box.style.display = 'block';
      const r = el.getBoundingClientRect();
      box.style.left = Math.max(8, Math.min(r.left, window.innerWidth - box.offsetWidth - 12)) + 'px';
      box.style.top = (r.bottom + 6) + 'px';
    });
    document.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('.ts-term[data-col]')) hideTip();
    });
  }

  /** 정렬·쪽을 처음으로 돌립니다(탭·묶음을 바꿀 때). */
  function resetView() {
    S.st.sort = '';
    S.st.dir = '';
    S.st.page = 0;
  }

  function bind() {
    $('ts-tabs').addEventListener('click', function (e) {
      const b = e.target.closest('[data-tab]');
      if (!b || b.dataset.tab === S.st.tab) return;
      const st = S.st;
      st.tab = b.dataset.tab;
      if (!GROUPS_BY_TAB[st.tab].includes(st.group)) st.group = 'dash';
      if (typeof st.min === 'number' && !MIN_STEPS[st.tab].includes(st.min)) st.min = 'q';
      if (st.tab !== 'bat') st.pos = '';
      resetView();
      refresh();
    });
    $('ts-groups').addEventListener('click', function (e) {
      const b = e.target.closest('[data-group]');
      if (!b) return;
      const g = b.dataset.group;
      if (g === 'custom') S.panelOpen = S.st.group === 'custom' ? !S.panelOpen : true;
      if (g !== S.st.group) { S.st.group = g; resetView(); }
      writeUrl();
      render();
    });
    $('season-select').addEventListener('change', function (e) {
      S.st.season = Number(e.target.value);
      S.st.page = 0;
      refresh();
    });
    $('team-select').addEventListener('change', function (e) {
      S.st.team = e.target.value;
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('pos-select').addEventListener('change', function (e) {
      S.st.pos = e.target.value;
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('min-select').addEventListener('change', function (e) {
      const v = e.target.value;
      S.st.min = v === 'q' || v === 'all' ? v : Number(v);
      S.st.page = 0;
      refresh();
    });
    $('csv-btn').addEventListener('click', downloadCsv);
    $('link-btn').addEventListener('click', copyLink);
    $('ts-table').addEventListener('click', function (e) {
      const th = e.target.closest('th.sortable');
      if (!th) return;
      const k = th.dataset.key;
      const cur = pickSort(S.st, keysNow(), S.last && S.last.all);
      if (cur.key === k) S.st.dir = cur.dir === 'asc' ? 'desc' : 'asc';
      else {
        const d = TS.columns.pdef(S.st.tab, k);
        S.st.dir = d && d.better === 'low' ? 'asc' : 'desc';
      }
      S.st.sort = k;
      S.st.page = 0;
      render();
      writeUrl(true);
    });
    $('ts-pager').addEventListener('click', function (e) {
      const b = e.target.closest('[data-page]');
      if (!b || b.disabled) return;
      S.st.page += b.dataset.page === 'next' ? 1 : -1;
      writeUrl();
      render();
      // 표 위가 화면 밖이면 표 제목이 보이게 올립니다(위 고정 머리 높이만큼 띄움).
      const top = $('ts-title').getBoundingClientRect().top;
      if (top < 0) window.scrollBy(0, top - 80);
    });
    $('ts-pager').addEventListener('change', function (e) {
      if (e.target.id !== 'page-size') return;
      S.st.size = Number(e.target.value);
      S.st.page = 0;
      writeUrl();
      render();
    });
    $('col-list').addEventListener('change', function (e) {
      const k = e.target.getAttribute('data-col');
      if (!k) return;
      const tab = S.st.tab;
      const on = new Set(S.custom[tab] || TS.columns.PGROUPS[tab].dash);
      if (e.target.checked) on.add(k); else on.delete(k);
      S.custom[tab] = TS.columns.PORDER[tab].filter(x => on.has(x));
      writeUrl(true);
      render();
    });
    document.querySelectorAll('[data-col-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        const tab = S.st.tab;
        S.custom[tab] = b.dataset.colPreset === 'all' ? TS.columns.PORDER[tab].slice() : TS.columns.PGROUPS[tab].dash.slice();
        writeUrl(true);
        render();
      });
    });
    $('col-close').addEventListener('click', function () {
      S.panelOpen = false;
      syncTabs();
    });
    window.addEventListener('popstate', function () {
      S.st = parseState(location.search);
      normalize();
      fillSeasons();
      refresh({ noUrl: true });
    });
    bindTips();
  }

  async function init() {
    try {
      S.st = parseState(location.search);
      $('ts-table').innerHTML = createLoadingSpinner();
      const base = root.KBO_API_BASE;
      const got = await Promise.all([TS.data.loadSeasons(base), TS.data.loadRefs(base)]);
      S.seasons = got[0].seasons;
      S.seasonErrors = got[0].errors;
      S.refs = got[1];
      S.latest = S.seasons[0];
      normalize();
      if (S.st.group === 'custom') S.panelOpen = true;
      fillSeasons();
      bind();
      await refresh({ replace: true });
    } catch (e) {
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('선수 기록을 불러오는데 실패했습니다.');
    }
  }
```

파일 맨 끝 `if (typeof module === 'object' && module.exports) module.exports = api;` 줄 바로 뒤에 넣습니다.

```js
  if (typeof document !== 'undefined' && document.getElementById('ps-page')) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
```

- [ ] **Step 4: 쪽 넘기기 스타일 붙이기**

`dashboard_js/css/stats.css` 끝에 붙입니다.

```css
/* 선수 표 아래 쪽 넘기기 */
.ts-pager { display: flex; align-items: center; justify-content: flex-end; gap: 0.5rem; flex-wrap: wrap; margin-top: 0.75rem; font-size: 0.85rem; }
.ts-pager:empty { display: none; }
.ts-pager .tabbtn { height: 32px; padding: 0.25rem 0.75rem; box-sizing: border-box; }
.ts-pager label { margin: 0; white-space: nowrap; }
.ts-pager select { width: auto; max-width: 110px; }
.ts-empty { margin: 0 0 0.6rem; font-size: 0.9rem; }
```

- [ ] **Step 5: Node 시험 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 122개 통과(118 + player-html 4), 실패 0.

- [ ] **Step 6: 화면 확인(DOM 덤프로 규정 인원을 서버와 대조)**

서버가 같은 기준으로 센 인원을 한 번씩만 받습니다(2025 는 모든 팀 144경기라 서버의 `min_pa=446`·`min_ip=144` 와 같은 기준).

```bash
cd C:/tmp/bstats-team-stats-check
curl -s "https://kbo-api.bstats-baseball.workers.dev/stats/batters?season=2025&limit=2000&min_pa=446" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log('server bat',JSON.parse(s).batters.length))"
curl -s "https://kbo-api.bstats-baseball.workers.dev/stats/pitchers?season=2025&limit=2000&min_ip=144" | node -e "let s='';process.stdin.on('data',d=>s+=d).on('end',()=>console.log('server pit',JSON.parse(s).pitchers.length))"
bash dom.sh "/pages/player-stats.html?season=2025" ps_bat.html
bash dom.sh "/pages/player-stats.html?tab=pit&season=2025" ps_pit.html
grep -o 'id="ts-title">[^<]*' ps_bat.html ps_pit.html
grep -o 'class="ts-rank">[0-9]' ps_bat.html | wc -l
grep -o 'id="ts-alerts" class="ts-alerts"></div>' ps_bat.html
```

Expected:
- `server bat 43`, `server pit 22`(DB 세션이 2025 기록을 고쳤다면 다를 수 있음. 그때는 아래 제목 숫자가 서버 숫자와 같으면 됩니다).
- `id="ts-title">타자 (2025, 규정 이상 43명)`, `id="ts-title">투수 (2025, 규정 이상 22명)`(서버 숫자와 같아야 함).
- 줄 번호 칸 43개.
- 마지막 grep 이 한 줄 나옴(알림 칸이 비어 있음).

다르면 멈추고 원인을 찾습니다(가리지 않습니다).

- [ ] **Step 7: 첫 캡처**

```bash
cd C:/tmp/bstats-team-stats-check
bash shot.sh ps_bat_dash "/pages/player-stats.html?season=2025"
bash shot.sh ps_now "/pages/player-stats.html"
```

`C:/Users/김승곤/Desktop/bstats_ts_ps_bat_dash.png`·`bstats_ts_ps_now.png` 를 Read 로 열어 봅니다. 볼 것:
- 탭(타격 밑줄 켜짐), 묶음 다섯 개(대시보드 켜짐), 고르개 한 줄(시즌·팀·포지션 | 최소).
- 표 제목 오른쪽에 CSV·링크 복사 두 개만.
- 칸 순서 `# · 이름 · 팀 · G PA HR R RBI BB% K% ISO BABIP AVG OBP SLG wOBA wRC+`, wRC+ 높은 순(▼), wRC+ 칸만 빨강·파랑.
- 맨 아래 리그 평균 행(누적 '-', wRC+ 100).
- 2026(`ps_now`)은 제목 `타자 (2026, 규정 이상 N명)` 이고 설명 문구에 "진행 중인 시즌" 과 "실시간 순위" 가 있음.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/pages/player-stats.html dashboard_js/js/player-stats/page.js dashboard_js/css/stats.css
git diff --cached --name-status
git commit -m "feat(player-stats): 선수 통계 페이지를 팬그래프 방식으로 새로 씀

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/pages/player-stats.html dashboard_js/js/player-stats/page.js dashboard_js/css/stats.css
```

---

### Task 7: 경계 상황 캡처와 팀 통계 회귀 확인

**Files:**
- Modify (문제가 나올 때만): `dashboard_js/js/player-stats/page.js`, `dashboard_js/css/stats.css`, `dashboard_js/pages/player-stats.html`
- 결과: 바탕화면 PNG

**Interfaces:**
- Consumes: Task 6 의 화면.
- Produces: 확인된 캡처. 고친 것이 있으면 커밋 하나.

- [ ] **Step 1: 경계 상황 캡처**

```bash
cd C:/tmp/bstats-team-stats-check
bash shot.sh ps_sit "/pages/player-stats.html?tab=bat&group=sit&season=2025"
bash shot.sh ps_pit_adv "/pages/player-stats.html?tab=pit&group=adv&season=2025"
bash shot.sh ps_1985 "/pages/player-stats.html?tab=bat&group=dash&season=1985"
bash shot.sh ps_team_lg "/pages/player-stats.html?tab=bat&group=dash&season=2025&team=LG&min=all"
bash shot.sh ps_page2 "/pages/player-stats.html?tab=bat&group=std&season=2025&min=all&page=2"
bash shot.sh ps_dark "/__theme/dark?to=/pages/player-stats.html%3Fseason%3D2025"
node mobile_shot.mjs ps_mobile "/pages/player-stats.html?season=2025"
```

PNG 를 하나씩 Read 로 열어 봅니다.

| 캡처 | 맞아야 하는 것 |
|---|---|
| ps_sit | 칸 `PA 득점권 대타 결승타 멀티히트 XR GPA P/PA`, 득점권 높은 순(▼). 리그 행은 PA·상황 칸 모두 '-'. 설명 문구에 "상황 묶음" |
| ps_pit_adv | 묶음에 "상황" 버튼 없음, 포지션 고르개 없음, 최소 목록이 이닝. 칸 `K/9 … ERA- FIP- FIP E−F`, FIP 낮은 순(▲), ERA-·FIP- 만 색. 리그 행 ERA-·FIP- 100, E−F 0.00 |
| ps_1985 | wOBA·wRC+ 칸 '-', wRC+ 뒤에 OPS+, OPS+ 높은 순. 설명 문구에 "2007년 이전" |
| ps_team_lg | LG 선수만, 제목 `타자 (2025, LG, 전체 N명)`, 리그 평균 행은 그대로 맨 아래 |
| ps_page2 | # 가 51부터, 아래에 `N명 중 51~100`, `2 / k쪽`, 이전·다음 둘 다 눌림 가능 |
| ps_dark | 어두운 배경에서 고정 칸(#·이름)·리그 행·쪽 넘기기 글자가 읽힘 |
| ps_mobile | 출력 줄의 `doc` 가 `inner`(390) 이하(가로로 넘치지 않음). 표는 안에서만 가로로 밀림. 고르개가 줄바꿈되어 보임 |

맞지 않는 것이 있으면 Step 3 에서 고칩니다.

- [ ] **Step 2: 팀 통계가 그대로인지 확인**

```bash
cd C:/tmp/bstats-team-stats-check
bash dom.sh "/pages/team-stats.html?season=2025" ts_after7.html
diff <(sed -n '/<main/,/<\/main>/p' ts_before.html) <(sed -n '/<main/,/<\/main>/p' ts_after7.html) && echo SAME_MAIN
bash shot.sh ts_after_all "/pages/team-stats.html?season=2025"
```

Expected: `SAME_MAIN`. `bstats_ts_ts_after_all.png` 를 `bstats_ts_ts_before_move.png` 와 나란히 보고 같은지 확인합니다. DB 세션이 그사이 2025 기록을 고쳐 숫자만 다르면, diff 에서 바뀐 곳이 숫자 칸뿐인지 확인하고 넘어갑니다.

- [ ] **Step 3: (문제가 있을 때만) 고치고 다시 확인**

고친 뒤 `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"` 로 122개 통과를 다시 보고, 문제였던 캡처만 다시 찍습니다. 그리고 커밋합니다.

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add <고친 dashboard_js 파일들>
git diff --cached --name-status
git commit -m "fix(player-stats): <무엇을 고쳤는지 한국어로>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- <고친 dashboard_js 파일들>
```

고칠 것이 없으면 커밋하지 않습니다.

- [ ] **Step 4: 보고**

`git log origin/main..main --oneline` 결과와 캡처 파일 이름 목록을 보고에 적습니다. push·배포는 하지 않습니다(evan 허락 뒤 따로 합니다).
