# 테이블 계보 탭 화면 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 데이터 탐색 페이지(`dashboard_js/pages/database-explorer.html`)에 세 번째 탭 "테이블 계보"(`#lineage`)를 만들어, 원천 → 수집 작업 → 표 → 계산 표 → 화면 흐름과 표마다의 운영 상태를 한 장으로 보여 줍니다.

**Architecture:** 계산(`js/lineage/model.js`: 노드·선·경로·상태·배치)과 화면(`js/lineage/view.js`: HTML 만들기 + 데이터 받기·그리기·누르기)을 나눕니다. 그림은 라이브러리 없이 HTML 상자 + SVG 곡선입니다. 데이터는 DB 세션이 만든 `dashboard_js/data/table_lineage.json` 과 기존 API `/db/tables`·`/jobs/status` 만 씁니다. 순수 함수는 Node 로, 화면은 헤드리스 Edge(CDP) 캡처로 확인합니다.

**Tech Stack:** 순수 JavaScript(빌드 도구 없음, `<script>` 태그), SVG, Node 24 내장 테스트(`node --test`), Python 미리보기 서버, 헤드리스 Edge(CDP).

**설계 문서:** `C:/Users/김승곤/Desktop/b_project/docs/superpowers/specs/2026-10-04-table-lineage-screen-design.md` (앞선 설계: `2026-10-04-table-lineage-design.md`)

## Global Constraints

- 저장소: `C:/Users/김승곤/Desktop/b_project` (브랜치 `main`, 다른 세션과 폴더를 같이 씀).
- **고칠 수 있는 곳은 `dashboard_js/` 안뿐입니다.** `src/`, `scripts/`, `tests/`, `test/`, `database/`, `crawler/`, `migration/`, `data_collection/`, `park_factors/`, `wrangler.toml`, `package*.json`, `.github/` 는 읽기만 합니다(Task 4 에서 `py scripts/build_lineage.py`·`py -m pytest tests` 를 **실행**만 합니다).
- **`dashboard_js/data/table_lineage.json` 은 손으로 고치지 않습니다**(DB 세션 생성물). 다시 만들기 결과로 바뀔 때만 커밋합니다.
- 데이터 탐색 페이지의 기존 두 탭("데이터 탐색"·"사이트맵")의 내용과 동작은 바꾸지 않습니다. `switchTab` 을 세 탭으로 넓히기만 합니다.
- **git:** 브랜치를 바꾸지 않습니다. `git add -A`, `git add .`, `git commit -a`, `git stash`, `git reset`, `git restore`, `git checkout --` 를 쓰지 않습니다. 커밋 전에 `git status --short` 와 `git diff --cached --name-status` 를 보고 자기 파일만 고르며, 커밋은 `git commit -m "…" -- <자기 파일들>` 처럼 경로를 붙여 합니다. 다른 세션의 변경(예: `dashboard_js/pages/player-analytics.html`)은 그대로 둡니다.
- 커밋 메시지는 `feat(lineage): 한국어 설명` 형식이고, 끝에 빈 줄 다음 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙입니다.
- **push·배포는 하지 않습니다.** evan 이 건마다 허락합니다. Worker 배포(`wrangler deploy`)는 하지 않습니다.
- **DB 에 쓰지 않습니다.** 새 API 를 만들지 않습니다. 화면은 계보 파일·`/db/tables`·`/jobs/status` 만 읽습니다.
- 저장소 `package.json` 이 `"type": "module"` 이라 Node 테스트는 `vm.runInThisContext` 로 모듈을 읽습니다(`tests/_load.js`). 파일 이름을 `.cjs` 로 바꾸지 않습니다.
- 모듈 틀: `(function (root) { 'use strict'; const L = root.Lineage = root.Lineage || {}; … L.<이름> = api; if (typeof module === 'object' && module.exports) module.exports = api; })(typeof window !== 'undefined' ? window : globalThis);`
- 저장소 파일은 CRLF 줄끝입니다(`core.autocrlf=true`). 이스케이프(`\uFEFF` 같은 것)를 눈에 안 보이는 글자로 바꾸지 않습니다. 새 파일을 쓴 뒤 `grep -c $'\xEF\xBB\xBF' <파일>` 이 0 이어야 합니다.
- 검증 스크립트는 저장소 밖 `C:/tmp/bstats-team-stats-check/tests/` 에 둡니다. 전체 실행: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"` (지금 131개 통과).
- 미리보기는 이미 `127.0.0.2:8765` 에 떠 있습니다(`C:/tmp/bstats-team-stats-check/preview.py`, `dashboard_js` 를 그대로 내보냄). 새로 띄우지 않습니다. `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.2:8765/pages/database-explorer.html` 이 200 이 아니면 멈추고 알립니다.
- 캡처는 헤드리스 Edge 로 하고 호출마다 `--user-data-dir` 를 다르게 줍니다(`lineage_shot.mjs` 가 그렇게 함). PNG 는 바탕화면에 둡니다.
- 사용자에게 보이는 글은 `습니다/합니다` 정중체, 짧은 문장, 쉬운 말. 이모지와 줄표(—)를 쓰지 않습니다. 상태 점·요약 숫자에는 `data-tooltip`(정의·기준)을 둡니다.
- API 응답이 이상하면(HTTP 오류, `error`·`detail` 필드, 빈 목록) 가리지 않고 탭 안 알림으로 이유를 보입니다.
- 상태 판정: 나쁜 순서 실패 > 오래됨 > 기록 없음 > 정상. 기준 시간은 계보 파일 `jobs[].stale_hours`(daily·roster 36, weekly 192, monthly 840). 손 작업 표는 점 대신 "손 작업".

## 파일 구조

| 파일 | 책임 |
|---|---|
| `dashboard_js/js/lineage/model.js` (새) | 순수 계산: 칸별 노드·묶음 처리한 선(`buildGraph`), 경로(`reach`), 상태(`keyState`·`tableStatus`·`jobStatus`·`summarize`), 문구(`itemText`·`dotText`), 배치(`layout`·`edgePath`) |
| `dashboard_js/js/lineage/view.js` (새) | HTML 만들기(`summaryHtml`·`graphHtml`·`listHtml`·`detailHtml`, Node 로 검증) + 화면 부분(데이터 받기·그리기·누르기·설명 창·`open`) |
| `dashboard_js/css/lineage.css` (새) | 계보 탭 스타일(라이트·다크·휴대폰) |
| `dashboard_js/pages/database-explorer.html` | `lineage.css` 링크, 세 번째 탭 버튼·탭 칸, 스크립트 셋, `switchTab`·`#lineage` |

검증 폴더(저장소 밖, 커밋하지 않음):

```
C:/tmp/bstats-team-stats-check/
  fixtures/  lineage.json(계보 파일 사본) jobs_status.json db_tables.json  (이미 있음)
  tests/     _load.js(Task 1 에서 loadLineage 추가)
             새 파일: lineage.graph.test.js, lineage.status.test.js, lineage.layout.test.js,
                     lineage.view.test.js, lineage.html.test.js
  lineage_shot.mjs  계보 탭 캡처(Task 3 에서 만듦)
```

시험 기준 시각은 한국 시각 2026-10-04 12:00(`Date.UTC(2026, 9, 4, 3, 0)`)입니다. 시험 데이터 기준 요약은 정상 4 · 실패 7 · 오래됨 0 · 기록 없음 5 · 손 작업 11 입니다.

---

### Task 1: 계보 계산(model.js)

**Files:**
- Create: `dashboard_js/js/lineage/model.js`
- Modify (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/_load.js` (`loadLineage` 추가)
- Test (저장소 밖): `tests/lineage.graph.test.js`, `tests/lineage.status.test.js`, `tests/lineage.layout.test.js`

**Interfaces:**
- Consumes: 계보 파일 모양(설계 문서 3절, DB 세션 설계 3절). `scripts[].status_keys` 는 `{작업 id: 기록 키}`, `jobs[].steps[].status_key` 는 null 일 수 있음.
- Produces (`window.Lineage.model`):
  - 상수 `COLS = ['source','job','table','derived','page']`, `COL_LABEL`, `GROUP_ID = 'group:manual'`, `RANK`, `BOX_H = 36`, `GAP = 10`, `MIN_BOX_W = 150`, `COL_PAD = 36`
  - `nodeType(id)`, `nodeName(id)`, `pageLabel(page)`
  - `buildGraph(lin, { manualOpen })` → `{ cols: {source:[node],…}, nodes: {id: node}, edges: [{from, to}] }`, `node = { id, col, label, sub, kind, ref }`, `kind` ∈ `source·job·collected·manual·group·derived·page`
  - `reach(graph, lin, startId)` → `{ nodes: Set<id>, edges: Set<선 번호> }`
  - `kstMs(s)`, `shortTime(s)`, `keyState(rec, staleHours, nowMs)` → `{ state, at, status, note, unknown? }`
  - `tableStatus(lin, table, details, nowMs)` / `jobStatus(lin, job, details, nowMs)` → `{ state, items: [{ script|step, job, key, staleHours, state, at, status, note }] }` (`state` ∈ `ok·fail·stale·none`, 손 작업 표는 `manual`)
  - `summarize(lin, details, nowMs)` → `{ ok, fail, stale, none, manual, byTable: {이름: state} }`
  - `itemText(lin, item)`, `dotText(lin, status, manualNote)` → 문구
  - `layout(graph, width)` → `{ width, height, colW, boxW, boxes: {id: {x, y, w, h}} }`, `edgePath(lay, edge)` → SVG path 글자

- [ ] **Step 1: 시험 도우미에 loadLineage 더하기**

`C:/tmp/bstats-team-stats-check/tests/_load.js` 에서 `function loadAs(rel, globalName) {…}` 함수 바로 뒤에 넣습니다.

```js

/** 계보 모듈(js/lineage/<name>.js)을 불러 전역 Lineage 에 붙은 것을 꺼냅니다. */
function loadLineage(name) {
  run(path.join(REPO_JS, 'lineage', name + '.js'));
  return globalThis.Lineage[name];
}
```

마지막 줄을 바꿉니다.

```js
module.exports = { load, loadAs, loadLineage, fixture, refs, near, REPO_JS };
```

- [ ] **Step 2: 실패하는 시험 셋 쓰기**

`C:/tmp/bstats-team-stats-check/tests/lineage.graph.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadLineage, fixture } = require('./_load');
const M = loadLineage('model');
const lin = fixture('lineage');
const counts = g => Object.fromEntries(M.COLS.map(c => [c, g.cols[c].length]));

test('buildGraph: 접힌 손 작업 표는 묶음 하나, meta·데이터 탐색 페이지는 숨김', () => {
  const g = M.buildGraph(lin, {});
  assert.deepEqual(counts(g), { source: 7, job: 4, table: 11, derived: 6, page: 7 });
  assert.equal(g.edges.length, 100);
  const grp = g.nodes[M.GROUP_ID];
  assert.equal(grp.label, '손 작업 표 11개');
  assert.equal(grp.sub, '펼치기');
  assert.equal(grp.kind, 'group');
  assert.equal(grp.ref.members.length, 11);
  assert.equal(g.cols.table[g.cols.table.length - 1].id, M.GROUP_ID);
  assert.ok(!Object.keys(g.nodes).some(id => id.includes('meta_')));
  assert.ok(!g.nodes['page:pages/database-explorer.html']);
});

test('buildGraph: 묶음 선은 겹치지 않고, 펼치면 원래 선 108개', () => {
  const g = M.buildGraph(lin, {});
  const fromGroup = g.edges.filter(e => e.from === M.GROUP_ID).map(e => e.to).sort();
  assert.deepEqual(fromGroup, ['page:index.html', 'page:pages/article.html', 'page:pages/player-stats.html',
    'page:pages/team-record.html', 'page:pages/team-stats.html', 'table:weighted_pf_by_batter_season', 'table:wrc_plus_comparison']);
  assert.equal(new Set(g.edges.map(e => e.from + '>' + e.to)).size, g.edges.length);
  const open = M.buildGraph(lin, { manualOpen: true });
  assert.deepEqual(counts(open), { source: 7, job: 4, table: 22, derived: 6, page: 7 });
  assert.equal(open.edges.length, 108);
  assert.equal(open.nodes[M.GROUP_ID].sub, '접기');
  assert.equal(open.cols.table[10].id, M.GROUP_ID);
  assert.equal(open.cols.table[11].id, 'table:franchises');
  assert.equal(open.nodes['table:teams'].kind, 'manual');
  assert.ok(!open.edges.some(e => e.from === M.GROUP_ID || e.to === M.GROUP_ID));
});

test('buildGraph: 칸 안 순서와 이름', () => {
  const g = M.buildGraph(lin, {});
  assert.deepEqual(g.cols.job.map(n => n.label), ['daily', 'monthly', 'roster', 'weekly']);
  assert.equal(g.nodes['job:daily'].sub, '매일 03:33');
  assert.deepEqual(g.cols.page.map(n => n.label), ['KBO 야구 데이터 대시보드', '아티클', '요인 통계', '선수 분석', '선수 통계', '팀 기록실', '팀 통계']);
  assert.equal(g.cols.table[0].label, 'futures_games');
  assert.equal(M.pageLabel({ path: 'pages/x.html', title: '팀 통계 - Bstats' }), '팀 통계');
  assert.equal(M.pageLabel({ path: 'pages/x.html', title: '' }), 'pages/x.html');
  assert.equal(M.nodeType('page:pages/a.html'), 'page');
  assert.equal(M.nodeName('page:pages/a.html'), 'pages/a.html');
});

const others = (r, id) => [...r.nodes].filter(x => x !== id).sort();

test('reach: games 는 그 표를 쓰는 스크립트의 원천만 거슬러 켬', () => {
  const g = M.buildGraph(lin, {});
  const r = M.reach(g, lin, 'table:games');
  const got = others(r, 'table:games');
  assert.deepEqual(got.filter(x => x.startsWith('source:')), ['source:naver_relay']);
  assert.ok(got.includes('job:daily'));
  assert.ok(got.includes('table:wrc_plus_comparison'));
  assert.ok(got.includes('page:pages/team-stats.html'));
  assert.ok(!got.includes('table:players'));
  assert.equal(r.nodes.size, 14);
  assert.equal(r.edges.size, 25);
});

test('reach: 원천이 적히지 않은 스크립트면 작업의 원천을 모두 켬', () => {
  const g = M.buildGraph(lin, {});
  const r = M.reach(g, lin, 'table:kbo_official_batter_stats');
  assert.deepEqual(others(r, 'x').filter(x => x.startsWith('source:')),
    ['source:kbo_futures', 'source:kbo_player_search', 'source:kbo_record', 'source:kbo_register', 'source:naver_relay']);
});

test('reach: 원천에서 내려가면 그 원천을 받는 스크립트가 쓰는 표만', () => {
  const g = M.buildGraph(lin, {});
  const r = M.reach(g, lin, 'source:naver_relay');
  const got = others(r, 'source:naver_relay');
  assert.ok(got.includes('table:games'));
  assert.ok(got.includes('table:play_by_play'));
  assert.ok(!got.includes('table:futures_games'));
  assert.ok(!got.includes('table:team_season_rank'));
  const live = M.reach(g, lin, 'source:kbo_live');
  assert.deepEqual(others(live, 'source:kbo_live'), ['page:index.html', 'page:pages/player-analytics.html', 'page:pages/player-stats.html', 'page:pages/team-stats.html']);
});

test('reach: 작업을 누르면 그 작업의 표를 모두 켬, 묶음도 앞으로 이어짐', () => {
  const g = M.buildGraph(lin, {});
  const w = others(M.reach(g, lin, 'job:weekly'), 'job:weekly');
  assert.deepEqual(w.filter(x => x.startsWith('table:')), ['table:kbo_run_values_by_season', 'table:kbo_woba_weights_by_season',
    'table:re24_matrix_by_season', 'table:self_park_factor', 'table:weighted_pf_by_batter_season', 'table:wrc_plus_comparison']);
  const grp = M.reach(g, lin, M.GROUP_ID);
  assert.ok(grp.nodes.has('page:pages/team-record.html'));
  assert.ok(!grp.nodes.has('job:daily'));
});
```

`C:/tmp/bstats-team-stats-check/tests/lineage.status.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadLineage, fixture } = require('./_load');
const M = loadLineage('model');
const lin = fixture('lineage');
const det = fixture('jobs_status').details;
// 한국 시각 2026-10-04 12:00
const NOW = Date.UTC(2026, 9, 4, 3, 0);
const H = 3600 * 1000;

test('kstMs·shortTime: 한국 시각 글자를 읽음', () => {
  assert.equal(M.kstMs('2026-10-04 12:00'), NOW);
  assert.equal(M.kstMs('2026-10-04T12:00:59'), NOW);
  assert.equal(M.kstMs(''), null);
  assert.equal(M.kstMs('어제'), null);
  assert.equal(M.shortTime('2026-10-03 07:27'), '10/03 07:27');
  assert.equal(M.shortTime('bad'), 'bad');
});

test('keyState: 실패·기록 없음·오래됨(경계)·정상·건너뜀·모르는 값', () => {
  assert.equal(M.keyState(undefined, 36, NOW).state, 'none');
  assert.equal(M.keyState({ status: 'fail', last_run_at: '2026-10-04 11:00' }, 36, NOW).state, 'fail');
  assert.equal(M.keyState({ status: 'ok', last_run_at: '2026-10-03 00:00' }, 36, NOW).state, 'ok');      // 36시간 딱
  assert.equal(M.keyState({ status: 'ok', last_run_at: '2026-10-02 23:59' }, 36, NOW).state, 'stale');   // 36시간 1분
  assert.equal(M.keyState({ status: 'skip', last_run_at: '2026-10-04 08:00' }, 36, NOW).state, 'ok');
  assert.equal(M.keyState({ status: 'ok', last_run_at: null }, 36, NOW).state, 'stale');
  const odd = M.keyState({ status: 'running', last_run_at: '2026-10-04 11:00' }, 36, NOW);
  assert.equal(odd.state, 'stale');
  assert.equal(odd.unknown, true);
  assert.equal(odd.status, 'running');
});

test('tableStatus: 쓰는 스크립트 기록 키 중 가장 나쁜 것, 손 작업은 manual', () => {
  const t = name => lin.tables.find(x => x.name === name);
  assert.equal(M.tableStatus(lin, t('games'), det, NOW).state, 'ok');
  assert.equal(M.tableStatus(lin, t('futures_games'), det, NOW).state, 'fail');
  assert.equal(M.tableStatus(lin, t('team_season_rank'), det, NOW).state, 'none');
  assert.equal(M.tableStatus(lin, t('wrc_plus_comparison'), det, NOW).state, 'fail');
  assert.equal(M.tableStatus(lin, t('teams'), det, NOW).state, 'manual');
  const players = M.tableStatus(lin, t('players'), det, NOW);
  assert.equal(players.state, 'none');
  assert.ok(players.items.some(it => it.key === 'player_info' && it.state === 'ok'));
  assert.ok(players.items.some(it => it.key === 'add_new_players' && it.state === 'none'));
  // 기록 키가 없는 스크립트(sync_players_from_roster.py)는 항목이 생기지 않음
  assert.ok(!players.items.some(it => it.script.includes('sync_players_from_roster')));
  // 같은 기록 키라도 7일 지나면 daily 기준(36시간)으로 오래됨
  assert.equal(M.tableStatus(lin, t('games'), det, NOW + 7 * 24 * H).state, 'stale');
  // 운영 정보가 비면 기록 없음
  assert.equal(M.tableStatus(lin, t('games'), {}, NOW).state, 'none');
});

test('jobStatus: 단계 기록 키 중 가장 나쁜 것(같은 키는 한 번)', () => {
  const job = id => lin.jobs.find(j => j.id === id);
  assert.equal(M.jobStatus(lin, job('daily'), det, NOW).state, 'fail');
  assert.equal(M.jobStatus(lin, job('monthly'), det, NOW).state, 'ok');
  assert.equal(M.jobStatus(lin, job('roster'), det, NOW).state, 'none');
  const weekly = M.jobStatus(lin, job('weekly'), det, NOW);
  assert.equal(weekly.state, 'fail');
  assert.equal(weekly.items.length, 1);
  assert.equal(weekly.items[0].key, 'park_factors');
});

test('summarize: 손 작업 11 따로, 상태별 합 16', () => {
  const s = M.summarize(lin, det, NOW);
  assert.deepEqual([s.ok, s.fail, s.stale, s.none, s.manual], [4, 7, 0, 5, 11]);
  assert.equal(s.ok + s.fail + s.stale + s.none, 16);
  assert.equal(s.byTable.games, 'ok');
  assert.equal(s.byTable.teams, 'manual');
  assert.ok(!('meta_job_runs' in s.byTable));
});

test('itemText·dotText: 사람이 읽는 문구', () => {
  const t = name => lin.tables.find(x => x.name === name);
  const wrc = M.tableStatus(lin, t('wrc_plus_comparison'), det, NOW);
  assert.equal(M.dotText(lin, wrc), 'weekly · park_factors: 마지막 실행 실패 09/22 09:25');
  const games = M.tableStatus(lin, t('games'), det, NOW);
  assert.equal(M.dotText(lin, games), 'daily · games: 마지막 갱신 10/03 07:27 · 성공');
  const old = M.tableStatus(lin, t('games'), det, NOW + 7 * 24 * H);
  assert.equal(M.dotText(lin, old), 'daily · games: 36시간 넘게 갱신이 없습니다(기준: 매일 03:33 실행) · 마지막 10/03 07:27');
  assert.equal(M.dotText(lin, M.tableStatus(lin, t('team_season_rank'), det, NOW)), 'daily · team_ranks: 실행 기록이 아직 없습니다');
  assert.equal(M.dotText(lin, { state: 'manual', items: [] }, '손으로 채웠습니다.'), '손 작업으로 채운 표입니다: 손으로 채웠습니다.');
  assert.equal(M.dotText(lin, { state: 'none', items: [] }), '실행 기록이 아직 없습니다');
  const odd = { job: 'daily', key: 'pbp', state: 'stale', unknown: true, status: 'running', at: '2026-10-04 11:00' };
  assert.equal(M.itemText(lin, odd), 'daily · pbp: 알 수 없는 상태(running) 10/04 11:00');
});
```

`C:/tmp/bstats-team-stats-check/tests/lineage.layout.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadLineage, fixture } = require('./_load');
const M = loadLineage('model');
const lin = fixture('lineage');

test('layout: 5칸 x 순서, 같은 칸 상자는 겹치지 않음, 높이는 가장 긴 칸', () => {
  const g = M.buildGraph(lin, {});
  const lay = M.layout(g, 1300);
  assert.deepEqual([lay.width, lay.height, lay.boxW], [1300, 496, 224]);
  assert.deepEqual(lay.boxes['table:games'], { x: 520, y: 92, w: 224, h: 36 });
  const xs = M.COLS.map(c => lay.boxes[g.cols[c][0].id].x);
  assert.deepEqual(xs, [0, 260, 520, 780, 1040]);
  M.COLS.forEach(function (c) {
    const ys = g.cols[c].map(n => lay.boxes[n.id].y);
    ys.forEach((y, i) => { if (i) assert.ok(y >= ys[i - 1] + 36, `${c} ${i}`); });
  });
  const open = M.layout(M.buildGraph(lin, { manualOpen: true }), 1300);
  assert.equal(open.height, 22 * 46 - 10);
});

test('layout: 좁으면 상자 최소 폭을 지키고 그림을 넓힘', () => {
  const lay = M.layout(M.buildGraph(lin, {}), 400);
  assert.equal(lay.width, 5 * (M.MIN_BOX_W + M.COL_PAD));
  assert.equal(lay.boxW, M.MIN_BOX_W);
  assert.equal(M.layout({ cols: { source: [], job: [], table: [], derived: [], page: [] } }, 800).height, 0);
});

test('edgePath: 다른 칸은 오른쪽→왼쪽 곡선, 같은 칸은 오른쪽으로 부푼 곡선', () => {
  const lay = { boxes: {
    a: { x: 0, y: 0, w: 100, h: 36 }, b: { x: 200, y: 46, w: 100, h: 36 }, c: { x: 200, y: 138, w: 100, h: 36 },
  } };
  assert.equal(M.edgePath(lay, { from: 'a', to: 'b' }), 'M100,18 C150,18 150,64 200,64');
  assert.equal(M.edgePath(lay, { from: 'b', to: 'c' }), 'M300,64 C326,64 326,156 300,156');
  assert.equal(M.edgePath(lay, { from: 'a', to: 'zz' }), '');
});
```

- [ ] **Step 3: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/lineage.graph.test.js" "C:/tmp/bstats-team-stats-check/tests/lineage.status.test.js" "C:/tmp/bstats-team-stats-check/tests/lineage.layout.test.js"`
Expected: FAIL (`ENOENT … js\lineage\model.js`).

- [ ] **Step 4: model.js 쓰기**

`dashboard_js/js/lineage/model.js`:

```js
/*
 * 테이블 계보 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.Lineage.model 로, Node 검증 스크립트에서는 vm 으로
 * 불러 씁니다. 근거는 docs/superpowers/specs/2026-10-04-table-lineage-screen-design.md
 * 입니다. 데이터는 dashboard_js/data/table_lineage.json(DB 세션 생성물)입니다.
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};

  // 그림의 칸 순서입니다.
  const COLS = ['source', 'job', 'table', 'derived', 'page'];
  const COL_LABEL = { source: '원천', job: '수집 작업', table: '표', derived: '계산 표', page: '화면' };
  const GROUP_ID = 'group:manual';

  function nodeType(id) { return String(id).slice(0, String(id).indexOf(':')); }
  function nodeName(id) { return String(id).slice(String(id).indexOf(':') + 1); }
  function byName(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  /** 화면 제목에서 ' - Bstats' 꼬리를 뗍니다. 제목이 없으면 경로입니다. */
  function pageLabel(p) {
    return String((p && (p.title || p.path)) || '').replace(/\s*-\s*Bstats\s*$/, '');
  }

  /**
   * 그림에 쓸 노드와 선입니다.
   *   opts.manualOpen  손 작업 표를 펼쳤으면 true
   * 반환 { cols: {source:[], job:[], table:[], derived:[], page:[]}, nodes: {id: node}, edges: [{from, to}] }
   *   node = { id, col, label, sub, kind, ref }   ref 는 계보 파일의 원래 항목
   * 숨김: kind 'meta' 표, explorer 페이지. 손 작업 표가 접혀 있으면 묶음 노드 하나로 바꾸고,
   * 펼쳐 있으면 묶음 노드(접기)를 맨 위에 두고 손 작업 표를 그 아래에 둡니다.
   */
  function buildGraph(lin, opts) {
    opts = opts || {};
    const cols = { source: [], job: [], table: [], derived: [], page: [] };
    const nodes = {};
    const add = function (n) { nodes[n.id] = n; cols[n.col].push(n); };
    const alias = {};   // 원래 id → 그림 id (접힌 손 작업 표 → 묶음)

    (lin.sources || []).slice().sort((a, b) => byName(a.id, b.id)).forEach(function (s) {
      add({ id: 'source:' + s.id, col: 'source', label: s.name, sub: '', kind: 'source', ref: s });
    });
    (lin.jobs || []).slice().sort((a, b) => byName(a.id, b.id)).forEach(function (j) {
      add({ id: 'job:' + j.id, col: 'job', label: j.id, sub: j.schedule_kst || '', kind: 'job', ref: j });
    });
    const tables = (lin.tables || []).slice().sort((a, b) => byName(a.name, b.name));
    tables.filter(t => t.kind === 'collected').forEach(function (t) {
      add({ id: 'table:' + t.name, col: 'table', label: t.name, sub: '', kind: 'collected', ref: t });
    });
    // 손 작업 표 묶음 상자는 접었을 때 '펼치기', 펼쳤을 때 '접기' 로 늘 둡니다(다시 접을 수 있게).
    const manual = tables.filter(t => t.kind === 'manual');
    if (manual.length) {
      add({ id: GROUP_ID, col: 'table', label: `손 작업 표 ${manual.length}개`, sub: opts.manualOpen ? '접기' : '펼치기', kind: 'group', ref: { members: manual.map(t => t.name) } });
    }
    manual.forEach(function (t) {
      if (opts.manualOpen) add({ id: 'table:' + t.name, col: 'table', label: t.name, sub: '', kind: 'manual', ref: t });
      else alias['table:' + t.name] = GROUP_ID;
    });
    tables.filter(t => t.kind === 'derived').forEach(function (t) {
      add({ id: 'table:' + t.name, col: 'derived', label: t.name, sub: '', kind: 'derived', ref: t });
    });
    (lin.pages || []).filter(p => !p.explorer).slice().sort((a, b) => byName(a.path, b.path)).forEach(function (p) {
      add({ id: 'page:' + p.path, col: 'page', label: pageLabel(p), sub: p.path, kind: 'page', ref: p });
    });

    const seen = new Set();
    const edges = [];
    (lin.edges || []).forEach(function (e) {
      const from = alias[e.from] || e.from;
      const to = alias[e.to] || e.to;
      if (!nodes[from] || !nodes[to] || from === to) return;
      const k = from + '>' + to;
      if (seen.has(k)) return;
      seen.add(k);
      edges.push({ from: from, to: to });
    });
    return { cols: cols, nodes: nodes, edges: edges };
  }

  /** 작업 job 에서 표 table 을 쓰는 스크립트들이 받는 원천 id 집합입니다. */
  function sourcesFor(lin, tableId, jobId) {
    const t = nodeName(tableId), j = nodeName(jobId);
    const out = new Set();
    (lin.scripts || []).forEach(function (s) {
      if ((s.writes || []).includes(t) && (s.jobs || []).includes(j)) {
        (s.sources || []).forEach(src => out.add('source:' + src));
      }
    });
    return out;
  }

  /** 작업 job 에서 원천 source 를 받는 스크립트들이 쓰는 표 id 집합입니다. */
  function tablesFor(lin, sourceId, jobId) {
    const src = nodeName(sourceId), j = nodeName(jobId);
    const out = new Set();
    (lin.scripts || []).forEach(function (s) {
      if ((s.sources || []).includes(src) && (s.jobs || []).includes(j)) {
        (s.writes || []).forEach(w => out.add('table:' + w));
      }
    });
    return out;
  }

  /**
   * 누른 노드에서 선을 따라 앞으로·뒤로 끝까지 이어진 노드와 선입니다.
   *
   * 원천 → 작업 → 표 구간은 스크립트 단위로 좁힙니다. 작업 하나가 여러 원천에서
   * 여러 표를 받으므로 선만 따라가면 games 를 눌렀을 때 퓨처스 원천까지 켜집니다.
   * 그래서 표에서 작업으로 거슬러 가면 그 표를 쓰는 스크립트의 원천만, 원천에서
   * 작업으로 내려가면 그 원천을 받는 스크립트가 쓰는 표만 따라갑니다. 작업 자체를
   * 누르면 그 작업의 원천과 표를 모두 켭니다. 스크립트에 원천이 적혀 있지 않으면 좁히지 않습니다.
   * 반환 { nodes: Set(id), edges: Set(선 번호) }
   */
  function reach(graph, lin, startId) {
    const edges = graph.edges;
    const nodes = new Set([startId]);
    const used = new Set();
    function walk(dir) {
      const todo = [{ id: startId, allow: null }];
      const seen = new Set();
      while (todo.length) {
        const cur = todo.pop();
        const key = cur.id + '|' + (cur.allow ? [...cur.allow].sort().join(',') : '*');
        if (seen.has(key)) continue;
        seen.add(key);
        edges.forEach(function (e, i) {
          const a = dir === 'down' ? e.from : e.to;
          const b = dir === 'down' ? e.to : e.from;
          if (a !== cur.id || (cur.allow && !cur.allow.has(b))) return;
          let allow = null;
          if (nodeType(b) === 'job' && dir === 'up' && nodeType(a) === 'table') allow = sourcesFor(lin, a, b);
          if (nodeType(b) === 'job' && dir === 'down' && nodeType(a) === 'source') allow = tablesFor(lin, a, b);
          // 스크립트가 원천을 적지 않았으면(예: csv_to_d1.py) 좁히지 않습니다. 빠뜨리는 것보다 넓게 보이는 편이 낫습니다.
          if (allow && !allow.size) allow = null;
          used.add(i);
          nodes.add(b);
          todo.push({ id: b, allow: allow });
        });
      }
    }
    walk('down');
    walk('up');
    return { nodes: nodes, edges: used };
  }

  // ===== 상태 =====

  // 나쁜 순서입니다. 숫자가 클수록 나쁩니다.
  const RANK = { ok: 0, none: 1, stale: 2, fail: 3 };

  /** 'YYYY-MM-DD HH:MM'(한국 시각) 글자를 ms 로 읽습니다. 못 읽으면 null. */
  function kstMs(s) {
    const m = String(s || '').match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);
    if (!m) return null;
    return Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4] - 9, +m[5]);
  }

  /**
   * 기록 키 하나의 상태입니다. rec 는 /jobs/status 의 details[키](없으면 undefined).
   * 반환 { state: 'ok'|'fail'|'stale'|'none', at, status, note }
   *   - 실패: status 가 'fail'
   *   - 기록 없음: rec 가 없음
   *   - 오래됨: status 가 ok·skip 인데 last_run_at 이 staleHours 보다 오래됐거나 시각을 못 읽음,
   *            또는 화면이 모르는 status 값
   *   - 정상: status 가 ok·skip 이고 기준 시간 안
   */
  function keyState(rec, staleHours, nowMs) {
    if (!rec) return { state: 'none', at: null, status: null, note: null };
    const status = rec.status === null || rec.status === undefined ? '' : String(rec.status);
    const base = { at: rec.last_run_at || null, status: status, note: rec.note || null };
    if (status === 'fail') return Object.assign({ state: 'fail' }, base);
    if (status !== 'ok' && status !== 'skip') return Object.assign({ state: 'stale', unknown: true }, base);
    const at = kstMs(rec.last_run_at);
    const fresh = at !== null && nowMs - at <= staleHours * 3600 * 1000;
    return Object.assign({ state: fresh ? 'ok' : 'stale' }, base);
  }

  function worst(items) {
    if (!items.length) return 'none';
    return items.reduce((w, it) => (RANK[it.state] > RANK[w] ? it.state : w), 'ok');
  }

  function jobById(lin, id) { return (lin.jobs || []).find(j => j.id === id) || null; }
  function scriptByPath(lin, path) { return (lin.scripts || []).find(s => s.path === path) || null; }

  /**
   * 표의 상태입니다. 손 작업 표는 'manual'.
   * 반환 { state, items: [{ script, job, key, state, at, status, note, staleHours }] }
   * details 는 /jobs/status 의 details 객체입니다.
   */
  function tableStatus(lin, t, details, nowMs) {
    if (t.kind === 'manual') return { state: 'manual', items: [] };
    const items = [];
    (t.written_by || []).forEach(function (path) {
      const s = scriptByPath(lin, path);
      const keys = (s && s.status_keys) || {};
      Object.keys(keys).sort(byName).forEach(function (job) {
        const key = keys[job];
        if (!key) return;
        const j = jobById(lin, job);
        const staleHours = j ? j.stale_hours : 36;
        items.push(Object.assign({ script: path, job: job, key: key, staleHours: staleHours },
          keyState((details || {})[key], staleHours, nowMs)));
      });
    });
    return { state: worst(items), items: items };
  }

  /** 작업 상자의 상태입니다. 기록 키가 있는 단계만 봅니다(같은 키는 한 번). */
  function jobStatus(lin, job, details, nowMs) {
    const items = [];
    const seen = new Set();
    (job.steps || []).forEach(function (st) {
      const key = st.status_key;
      if (!key || seen.has(key)) return;
      seen.add(key);
      items.push(Object.assign({ step: st.name, script: st.script, job: job.id, key: key, staleHours: job.stale_hours },
        keyState((details || {})[key], job.stale_hours, nowMs)));
    });
    return { state: worst(items), items: items };
  }

  /** 요약 줄 숫자입니다. meta 를 빼고 셉니다. 반환 { ok, fail, stale, none, manual, byTable: {name: state} } */
  function summarize(lin, details, nowMs) {
    const out = { ok: 0, fail: 0, stale: 0, none: 0, manual: 0, byTable: {} };
    (lin.tables || []).forEach(function (t) {
      if (t.kind === 'meta') return;
      const st = tableStatus(lin, t, details, nowMs).state;
      out[st] += 1;
      out.byTable[t.name] = st;
    });
    return out;
  }

  /** 'YYYY-MM-DD HH:MM' → 'MM/DD HH:MM'. 못 읽으면 글자 그대로입니다. */
  function shortTime(s) {
    const m = String(s || '').match(/^\d{4}-(\d{2})-(\d{2})[ T](\d{2}:\d{2})/);
    return m ? `${m[1]}/${m[2]} ${m[3]}` : String(s || '');
  }

  const STATE_WORD = { ok: '성공', skip: '건너뜀', fail: '실패' };

  /** 키 상태 하나를 사람이 읽는 문구로 바꿉니다. it 는 tableStatus/jobStatus 의 items 항목. */
  function itemText(lin, it) {
    if (it.state === 'none') return `${it.job} · ${it.key}: 실행 기록이 아직 없습니다`;
    if (it.state === 'fail') return `${it.job} · ${it.key}: 마지막 실행 실패 ${shortTime(it.at)}`;
    if (it.state === 'stale') {
      if (it.unknown) return `${it.job} · ${it.key}: 알 수 없는 상태(${it.status}) ${shortTime(it.at)}`;
      const j = jobById(lin, it.job);
      return `${it.job} · ${it.key}: ${it.staleHours}시간 넘게 갱신이 없습니다(기준: ${j ? j.schedule_kst : ''} 실행) · 마지막 ${shortTime(it.at)}`;
    }
    return `${it.job} · ${it.key}: 마지막 갱신 ${shortTime(it.at)} · ${STATE_WORD[it.status] || it.status}`;
  }

  /** 점에 붙일 설명 문구입니다. st = tableStatus/jobStatus 결과. manualNote 는 손 작업 표 설명. */
  function dotText(lin, st, manualNote) {
    if (st.state === 'manual') return `손 작업으로 채운 표입니다${manualNote ? ': ' + manualNote : ''}`;
    if (!st.items.length) return '실행 기록이 아직 없습니다';
    return st.items.map(it => itemText(lin, it)).join('\n');
  }

  // ===== 배치 =====

  const BOX_H = 36;      // 상자 높이
  const GAP = 10;        // 상자 사이
  const HEAD = 0;        // 칸 제목은 그림 밖(HTML)에 둡니다
  const MIN_BOX_W = 150; // 상자 최소 폭
  const COL_PAD = 36;    // 칸 사이 여백(선이 지나갈 자리)
  const ARC = 26;        // 같은 칸 안 선이 오른쪽으로 부푸는 정도

  /**
   * 상자 좌표입니다. width = 그림을 그릴 폭(px).
   * 반환 { width, height, colW, boxW, boxes: {id: {x, y, w, h}} }
   * 칸이 좁으면 폭을 넓혀(가로로 밀어 볼 수 있게) 상자가 MIN_BOX_W 보다 좁아지지 않게 합니다.
   */
  function layout(graph, width) {
    const total = Math.max(Number(width) || 0, COLS.length * (MIN_BOX_W + COL_PAD));
    const colW = total / COLS.length;
    const boxW = colW - COL_PAD;
    const boxes = {};
    let rows = 0;
    COLS.forEach(function (c, ci) {
      graph.cols[c].forEach(function (n, ri) {
        boxes[n.id] = { x: Math.round(ci * colW), y: HEAD + ri * (BOX_H + GAP), w: Math.round(boxW), h: BOX_H };
      });
      rows = Math.max(rows, graph.cols[c].length);
    });
    const height = rows ? HEAD + rows * (BOX_H + GAP) - GAP : 0;
    return { width: Math.round(total), height: height, colW: colW, boxW: Math.round(boxW), boxes: boxes };
  }

  /**
   * 선 하나의 SVG path 글자입니다. 다른 칸이면 왼쪽 상자 오른쪽 가운데 → 오른쪽 상자
   * 왼쪽 가운데로 가는 3차 곡선, 같은 칸이면 두 상자 오른쪽을 잇는 오른쪽으로 부푼 곡선입니다.
   */
  function edgePath(lay, e) {
    const a = lay.boxes[e.from], b = lay.boxes[e.to];
    if (!a || !b) return '';
    const ay = a.y + a.h / 2, by = b.y + b.h / 2;
    if (a.x === b.x) {
      const x = a.x + a.w;
      return `M${x},${ay} C${x + ARC},${ay} ${x + ARC},${by} ${x},${by}`;
    }
    const x1 = a.x + a.w, x2 = b.x;
    const mid = (x1 + x2) / 2;
    return `M${x1},${ay} C${mid},${ay} ${mid},${by} ${x2},${by}`;
  }

  const api = {
    COLS, COL_LABEL, GROUP_ID, RANK, BOX_H, GAP, MIN_BOX_W, COL_PAD,
    nodeType, nodeName, pageLabel, buildGraph, reach,
    kstMs, keyState, tableStatus, jobStatus, summarize, shortTime, itemText, dotText,
    layout, edgePath,
  };
  L.model = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 5: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 147개 통과(131 + graph 7 + status 6 + layout 3), 실패 0. `grep -c $'\xEF\xBB\xBF' dashboard_js/js/lineage/model.js` → 0.

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/lineage/model.js
git diff --cached --name-status
git commit -m "feat(lineage): 계보 계산(노드·경로·상태·배치)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/lineage/model.js
```

---

### Task 2: 계보 화면 HTML 만들기(view.js 순수 부분)

**Files:**
- Create: `dashboard_js/js/lineage/view.js` (HTML 만들기 부분)
- Test (저장소 밖): `tests/lineage.view.test.js`

**Interfaces:**
- Consumes: Task 1 의 `window.Lineage.model` 전부.
- Produces (`window.Lineage.view`, Task 3 이 같은 파일에 화면 부분을 더함):
  - `esc(s)`, `pageHref(path)` (`'pages/x.html'` → `'x.html'`, 그 밖 → `'../' + path`)
  - `statusMap(lin, details, nowMs)` → `null`(운영 정보 없음) 또는 `{ tables: {이름: tableStatus}, jobs: {id: jobStatus}, sum: summarize }`
  - `summaryHtml(sum, active)`, `graphHtml(graph, lay, lin, status)`, `listHtml(graph, lin, status)`, `detailHtml(node, lin, { graph, status, rows })` → HTML 글자
  - 상수 `STATE_LABEL`, `SUM_TIP`
  - HTML 클래스·속성(Task 3 CSS·이벤트가 씀): `.lin-sum-btn[data-state]`(켜지면 `.on`), `.lin-heads > .lin-head`, `.lin-canvas`, `svg.lin-svg > path.lin-edge[data-i]`, `button.lin-box.lin-k-<kind>[data-id]`, `.lin-dot.lin-<state>[data-tooltip]`, `.lin-tag`, `.lin-label`, `.lin-sub`, `.lin-list-col > ul.lin-list`, `.lin-next`, 상세 카드 `.card-header > h3.card-title` + `button.lin-close[data-close]` + `.card-body .lin-dl`

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/lineage.view.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadLineage, fixture } = require('./_load');
const M = loadLineage('model');
const V = loadLineage('view');
const lin = fixture('lineage');
const det = fixture('jobs_status').details;
const rows = {};
fixture('db_tables').tables.forEach(t => { rows[t.name] = t.rows; });
const NOW = Date.UTC(2026, 9, 4, 3, 0);
const text = h => h.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();
const count = (h, re) => (h.match(re) || []).length;

test('pageHref·esc', () => {
  assert.equal(V.pageHref('pages/team-stats.html'), 'team-stats.html');
  assert.equal(V.pageHref('index.html'), '../index.html');
  assert.equal(V.esc('<a href="x">&'), '&lt;a href=&quot;x&quot;&gt;&amp;');
});

test('statusMap: 운영 정보가 없으면 null, 있으면 표·작업·요약', () => {
  assert.equal(V.statusMap(lin, null, NOW), null);
  const st = V.statusMap(lin, det, NOW);
  assert.equal(st.tables.games.state, 'ok');
  assert.equal(st.jobs.weekly.state, 'fail');
  assert.equal(st.sum.fail, 7);
});

test('summaryHtml: 상태별 버튼 4개 + 손 작업, 켜진 버튼 표시, 운영 정보 없으면 빈 글자', () => {
  const st = V.statusMap(lin, det, NOW);
  const h = V.summaryHtml(st.sum, 'fail');
  assert.equal(count(h, /class="lin-sum-btn/g), 4);
  assert.match(h, /<button type="button" class="lin-sum-btn on" data-state="fail"/);
  assert.equal(text(h), '정상 4 실패 7 오래됨 0 기록 없음 5 손 작업 11');
  assert.equal(V.summaryHtml(null, null), '');
});

test('graphHtml: 상자 35개·선 100개·칸 제목 5개, 점은 표·작업에만', () => {
  const g = M.buildGraph(lin, {});
  const lay = M.layout(g, 1300);
  const h = V.graphHtml(g, lay, lin, V.statusMap(lin, det, NOW));
  assert.equal(count(h, /class="lin-box /g), 35);
  assert.equal(count(h, /<path class="lin-edge"/g), 100);
  assert.equal(count(h, /class="lin-head"/g), 5);
  assert.equal(count(h, /class="lin-dot lin-/g), 16 + 4);
  assert.match(h, /data-id="table:games" style="left:520px;top:92px;width:224px;height:36px"/);
  assert.match(h, /data-id="page:pages\/team-stats.html"/);
  assert.match(h, /<span class="lin-dot lin-fail" data-tooltip="weekly · park_factors: 마지막 실행 실패 09\/22 09:25"><\/span><span class="lin-label">wrc_plus_comparison<\/span>/);
  assert.match(h, /<span class="lin-label">손 작업 표 11개<\/span><span class="lin-sub">펼치기<\/span>/);
  const none = V.graphHtml(g, lay, lin, null);
  assert.equal(count(none, /lin-dot/g), 0);
});

test('graphHtml: 펼치면 손 작업 표마다 손 작업 표시', () => {
  const g = M.buildGraph(lin, { manualOpen: true });
  const h = V.graphHtml(g, M.layout(g, 1300), lin, V.statusMap(lin, det, NOW));
  assert.equal(count(h, /class="lin-tag"/g), 11);
  assert.match(h, /<span class="lin-label">손 작업 표 11개<\/span><span class="lin-sub">접기<\/span>/);
  assert.equal(count(h, /<path class="lin-edge"/g), 108);
});

test('listHtml: 선 없이 칸 5개, 상자마다 이어지는 곳', () => {
  const g = M.buildGraph(lin, {});
  const h = V.listHtml(g, lin, V.statusMap(lin, det, NOW));
  assert.equal(count(h, /class="lin-list-col"/g), 5);
  assert.ok(!h.includes('<svg'));
  assert.match(h, /data-id="table:games"[^]*?<div class="lin-next">→ 이어지는 곳: [^<]*팀 통계/);
  assert.match(h, /data-id="page:pages\/team-record.html"[^]*?<div class="lin-next">← 가져오는 곳: /);
});

test('detailHtml: 표(행 수·스크립트·마지막 실행·API·화면·참고)', () => {
  const g = M.buildGraph(lin, {});
  const ctx = { graph: g, status: V.statusMap(lin, det, NOW), rows: rows };
  const t = text(V.detailHtml(g.nodes['table:games'], lin, ctx));
  assert.match(t, /^games 받아 온 표 닫기 KBO 경기별 기본 메타정보/);
  assert.match(t, /행 수 12,661행/);
  assert.match(t, /쓰는 스크립트 data_collection\/daily_games_to_d1\.py · daily\(매일 03:33\)/);
  assert.match(t, /마지막 실행 daily · games: 마지막 갱신 10\/03 07:27 · 성공/);
  assert.match(t, /읽는 API 주소 \/dashboard\/stats \/games/);
  assert.match(t, /쓰는 화면 아티클 팀 통계/);
  assert.match(V.detailHtml(g.nodes['table:games'], lin, ctx), /<a href="team-stats.html">팀 통계<\/a>/);
  const spf = text(V.detailHtml(g.nodes['table:self_park_factor'], lin, ctx));
  assert.match(spf, /읽는 API 주소 데이터 탐색 주소\(\/db\/table\)로 읽습니다\./);
  assert.match(spf, /재료 표 /);
  const off = text(V.detailHtml(g.nodes['table:games'], lin, { graph: g, status: null, rows: null }));
  assert.match(off, /행 수 운영 정보 없음/);
  assert.match(off, /마지막 실행 운영 정보 없음/);
});

test('detailHtml: 손 작업 표·작업·원천·화면', () => {
  const open = M.buildGraph(lin, { manualOpen: true });
  const ctx = { graph: open, status: V.statusMap(lin, det, NOW), rows: rows };
  const teams = text(V.detailHtml(open.nodes['table:teams'], lin, ctx));
  assert.match(teams, /^teams 손 작업 표 닫기/);
  assert.match(teams, /행 수 10행 손 작업 현재 10팀 목록입니다/);
  assert.ok(!teams.includes('쓰는 스크립트'));
  const weekly = text(V.detailHtml(open.nodes['job:weekly'], lin, ctx));
  assert.match(weekly, /실행 시각 매주 화 05:47 \(GitHub Actions weekly\.yml \)/);
  assert.match(weekly, /기준 시간 192시간 넘게 갱신이 없으면 오래됨으로 봅니다\./);
  assert.match(weekly, /wRC\+ 계산 · park_factors\/build_wrc_plus\.py · 기록 키 park_factors 실패/);
  const live = text(V.detailHtml(open.nodes['source:kbo_live'], lin, ctx));
  assert.match(live, /받는 작업 - 바로 쓰는 화면 KBO 야구 데이터 대시보드 선수 분석 선수 통계 팀 통계/);
  const page = V.detailHtml(open.nodes['page:pages/team-stats.html'], lin, ctx);
  assert.match(page, /<h3 class="card-title"><a href="team-stats.html">팀 통계<\/a><\/h3>/);
  assert.match(text(page), /부르는 API 주소 /);
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/lineage.view.test.js"`
Expected: FAIL (`ENOENT … js\lineage\view.js`).

- [ ] **Step 3: view.js 쓰기(HTML 만들기 부분)**

`dashboard_js/js/lineage/view.js`:

```js
/*
 * 테이블 계보 탭 화면입니다(database-explorer.html #lineage).
 *
 * 계산은 model.js 가 합니다. 위쪽 HTML 을 만드는 함수는 DOM 을 건드리지 않아
 * Node 로 검증하고, 아래 화면 부분(데이터 받기·그리기·누르기)은 브라우저에서만
 * 돕니다. 데이터 받기는 js/stats/data.js 의 getJson 을 씁니다.
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};
  function M() { return L.model; }

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  const STATE_LABEL = { ok: '정상', fail: '실패', stale: '오래됨', none: '기록 없음', manual: '손 작업' };
  const KIND_LABEL = { collected: '받아 온 표', derived: '계산 표', manual: '손 작업 표' };
  const SUM_TIP = {
    ok: '이 표를 쓰는 작업의 마지막 실행이 성공했고 기준 시간 안에 갱신된 표입니다.',
    fail: '이 표를 쓰는 작업 가운데 마지막 실행이 실패한 것이 있는 표입니다.',
    stale: '기준 시간(daily·roster 36시간, weekly 8일, monthly 35일)보다 오래 갱신되지 않은 표입니다.',
    none: '이 표를 쓰는 작업의 실행 기록이 아직 없는 표입니다.',
    manual: '수집 작업 없이 손으로 채운 표입니다. 상태 점을 붙이지 않습니다.',
  };

  /** 화면 경로(계보 파일의 pages[].path)를 pages/ 안에서 여는 주소로 바꿉니다. */
  function pageHref(path) {
    const p = String(path || '');
    return p.startsWith('pages/') ? p.slice(6) : '../' + p;
  }

  /**
   * 표·작업의 상태를 한 번에 셉니다. details 가 없으면(운영 정보를 못 받음) null.
   * 반환 { tables: {name: tableStatus 결과}, jobs: {id: jobStatus 결과}, sum: summarize 결과 }
   */
  function statusMap(lin, details, nowMs) {
    if (!details) return null;
    const m = M();
    const out = { tables: {}, jobs: {}, sum: m.summarize(lin, details, nowMs) };
    (lin.tables || []).forEach(t => { out.tables[t.name] = m.tableStatus(lin, t, details, nowMs); });
    (lin.jobs || []).forEach(j => { out.jobs[j.id] = m.jobStatus(lin, j, details, nowMs); });
    return out;
  }

  /** 요약 줄입니다. sum 이 없으면(운영 정보 없음) 빈 글자. active 는 켜진 상태 이름. */
  function summaryHtml(sum, active) {
    if (!sum) return '';
    const btn = k => `<button type="button" class="lin-sum-btn${active === k ? ' on' : ''}" data-state="${k}" data-tooltip="${esc(SUM_TIP[k])}">`
      + `<span class="lin-dot lin-${k}"></span>${STATE_LABEL[k]} <b>${sum[k]}</b></button>`;
    return ['ok', 'fail', 'stale', 'none'].map(btn).join('')
      + `<span class="lin-sum-manual" data-tooltip="${esc(SUM_TIP.manual)}">손 작업 <b>${sum.manual}</b></span>`;
  }

  /** 상자 안 상태 표시(점 또는 '손 작업')입니다. 표·작업만 붙입니다. */
  function markHtml(n, lin, status) {
    if (!status) return '';
    const m = M();
    if (n.kind === 'manual') {
      return `<span class="lin-tag" data-tooltip="${esc(m.dotText(lin, { state: 'manual', items: [] }, n.ref.manual_note))}">손 작업</span>`;
    }
    let st = null;
    if (n.kind === 'collected' || n.kind === 'derived') st = status.tables[n.ref.name];
    if (n.kind === 'job') st = status.jobs[n.ref.id];
    if (!st) return '';
    return `<span class="lin-dot lin-${st.state}" data-tooltip="${esc(m.dotText(lin, st))}"></span>`;
  }

  /** 상자에 마우스를 올렸을 때 보이는 설명입니다. */
  function boxTip(n) {
    if (n.kind === 'collected' || n.kind === 'derived' || n.kind === 'manual') return n.ref.desc || n.label;
    if (n.kind === 'job') return `${n.label}: ${n.sub} 실행`;
    if (n.kind === 'page') return `${n.label} (${n.sub})`;
    if (n.kind === 'group') return n.sub === '접기' ? '누르면 손 작업 표를 접습니다.' : '누르면 손 작업 표를 펼칩니다.';
    return n.label;
  }

  function boxHtml(n, lin, status, style) {
    return `<button type="button" class="lin-box lin-k-${n.kind}" data-id="${esc(n.id)}"${style ? ` style="${style}"` : ''} data-tooltip="${esc(boxTip(n))}">`
      + markHtml(n, lin, status)
      + `<span class="lin-label">${esc(n.label)}</span>`
      + (n.sub && n.kind !== 'page' ? `<span class="lin-sub">${esc(n.sub)}</span>` : '')
      + '</button>';
  }

  /** 넓은 화면 그림입니다(칸 제목 + 선 SVG + 상자). */
  function graphHtml(graph, lay, lin, status) {
    const m = M();
    let h = `<div class="lin-heads" style="width:${lay.width}px">`;
    m.COLS.forEach(function (c, i) {
      h += `<div class="lin-head" style="left:${Math.round(i * lay.colW)}px;width:${lay.boxW}px">${esc(m.COL_LABEL[c])}</div>`;
    });
    h += `</div><div class="lin-canvas" style="width:${lay.width}px;height:${lay.height}px">`;
    h += `<svg class="lin-svg" width="${lay.width}" height="${lay.height}" viewBox="0 0 ${lay.width} ${lay.height}" aria-hidden="true">`;
    graph.edges.forEach(function (e, i) {
      h += `<path class="lin-edge" data-i="${i}" d="${m.edgePath(lay, e)}"></path>`;
    });
    h += '</svg>';
    m.COLS.forEach(function (c) {
      graph.cols[c].forEach(function (n) {
        const b = lay.boxes[n.id];
        h += boxHtml(n, lin, status, `left:${b.x}px;top:${b.y}px;width:${b.w}px;height:${b.h}px`);
      });
    });
    return h + '</div>';
  }

  /** 휴대폰 목록입니다. 선 대신 상자마다 이어지는 곳을 적습니다. */
  function listHtml(graph, lin, status) {
    const m = M();
    const label = id => (graph.nodes[id] ? graph.nodes[id].label : id);
    let h = '';
    m.COLS.forEach(function (c) {
      h += `<section class="lin-list-col"><h4>${esc(m.COL_LABEL[c])}</h4><ul class="lin-list">`;
      graph.cols[c].forEach(function (n) {
        const out = graph.edges.filter(e => e.from === n.id).map(e => label(e.to));
        const inn = graph.edges.filter(e => e.to === n.id).map(e => label(e.from));
        const next = out.length ? `→ 이어지는 곳: ${out.join(', ')}` : (inn.length ? `← 가져오는 곳: ${inn.join(', ')}` : '');
        h += `<li>${boxHtml(n, lin, status, '')}${next ? `<div class="lin-next">${esc(next)}</div>` : ''}</li>`;
      });
      h += '</ul></section>';
    });
    return h;
  }

  function statusLine(lin, it) {
    return `<li><span class="lin-status"><span class="lin-dot lin-${it.state}"></span>${esc(M().itemText(lin, it))}</span></li>`;
  }

  function listOrDash(items) {
    return items.length ? `<ul>${items.join('')}</ul>` : '-';
  }

  /**
   * 상세 카드 안쪽 HTML 입니다. ctx = { graph, status(statusMap 결과 또는 null), rows({표: 행 수} 또는 null) }
   */
  function detailHtml(node, lin, ctx) {
    const m = M();
    const g = ctx.graph;
    const label = id => (g.nodes[id] ? g.nodes[id].label : m.nodeName(id));
    const ins = g.edges.filter(e => e.to === node.id).map(e => e.from);
    const outs = g.edges.filter(e => e.from === node.id).map(e => e.to);
    const pageLink = id => {
      const p = g.nodes[id] && g.nodes[id].ref;
      return p ? `<li><a href="${esc(pageHref(p.path))}">${esc(m.pageLabel(p))}</a></li>` : '';
    };
    let title = esc(node.label);
    let body = '';

    if (node.kind === 'collected' || node.kind === 'derived' || node.kind === 'manual') {
      const t = node.ref;
      title += `<span class="lin-kind">${KIND_LABEL[t.kind] || ''}</span>`;
      const rows = ctx.rows ? (ctx.rows[t.name] === undefined ? '-' : `${Number(ctx.rows[t.name]).toLocaleString('ko-KR')}행`) : '운영 정보 없음';
      const st = ctx.status ? ctx.status.tables[t.name] : null;
      const writers = (t.written_by || []).map(function (path) {
        const s = (lin.scripts || []).find(x => x.path === path);
        const jobs = s ? (s.jobs || []).map(j => {
          const jb = (lin.jobs || []).find(x => x.id === j);
          return jb ? `${j}(${jb.schedule_kst})` : j;
        }).join(', ') : '';
        return `<li><code>${esc(path)}</code>${jobs ? ' · ' + esc(jobs) : ''}</li>`;
      });
      const notes = (t.written_by || []).map(p => (lin.scripts || []).find(x => x.path === p)).filter(s => s && s.note).map(s => `<li>${esc(s.note)}</li>`);
      body += `<p class="lin-desc">${esc(t.desc || '설명이 아직 없습니다.')}</p>`;
      if (t.category) body += `<p class="text-muted lin-cat">분류: ${esc(t.category)}</p>`;
      body += '<dl class="lin-dl">';
      body += `<dt>행 수</dt><dd>${esc(rows)}</dd>`;
      if (t.kind !== 'manual') {
        body += `<dt>쓰는 스크립트</dt><dd>${listOrDash(writers)}</dd>`;
        body += `<dt>마지막 실행</dt><dd>${st ? (st.items.length ? `<ul>${st.items.map(it => statusLine(lin, it)).join('')}</ul>` : '실행 기록을 남기는 단계가 없습니다.') : '운영 정보 없음'}</dd>`;
      } else {
        body += `<dt>손 작업</dt><dd>${esc(t.manual_note || '손으로 채운 표입니다.')}</dd>`;
      }
      if ((t.derived_from || []).length) body += `<dt>재료 표</dt><dd>${listOrDash(t.derived_from.map(x => `<li><code>${esc(x)}</code></li>`))}</dd>`;
      body += `<dt>읽는 API 주소</dt><dd>${(t.routes || []).length ? listOrDash(t.routes.map(r => `<li><code>${esc(r)}</code></li>`)) : '데이터 탐색 주소(/db/table)로 읽습니다.'}</dd>`;
      body += `<dt>쓰는 화면</dt><dd>${listOrDash((t.pages || []).map(p => pageLink('page:' + p)).filter(Boolean))}</dd>`;
      if (notes.length) body += `<dt>참고</dt><dd><ul>${notes.join('')}</ul></dd>`;
      body += '</dl>';
    } else if (node.kind === 'job') {
      const j = node.ref;
      const st = ctx.status ? ctx.status.jobs[j.id] : null;
      const byKey = {};
      if (st) st.items.forEach(it => { byKey[it.key] = it; });
      const steps = (j.steps || []).map(function (s) {
        const it = s.status_key && byKey[s.status_key];
        const mark = it ? ` <span class="lin-status"><span class="lin-dot lin-${it.state}"></span>${esc(STATE_LABEL[it.state])}</span>` : '';
        return `<li>${esc(s.name)} · <code>${esc(s.script)}</code>${s.status_key ? ` · 기록 키 <code>${esc(s.status_key)}</code>` : ''}${mark}</li>`;
      });
      body += '<dl class="lin-dl">';
      body += `<dt>실행 시각</dt><dd>${esc(j.schedule_kst)} (GitHub Actions <code>${esc(j.workflow)}</code>)</dd>`;
      body += `<dt>기준 시간</dt><dd>${esc(j.stale_hours)}시간 넘게 갱신이 없으면 오래됨으로 봅니다.</dd>`;
      body += `<dt>마지막 실행</dt><dd>${st ? (st.items.length ? `<ul>${st.items.map(it => statusLine(lin, it)).join('')}</ul>` : '-') : '운영 정보 없음'}</dd>`;
      body += `<dt>단계</dt><dd>${listOrDash(steps)}</dd>`;
      body += `<dt>원천</dt><dd>${listOrDash(ins.map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += `<dt>쓰는 표</dt><dd>${listOrDash(outs.map(id => `<li><code>${esc(label(id))}</code></li>`))}</dd>`;
      body += '</dl>';
    } else if (node.kind === 'source') {
      const s = node.ref;
      body += '<dl class="lin-dl">';
      body += `<dt>주소</dt><dd>${s.url ? `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.url)}</a>` : '-'}</dd>`;
      body += `<dt>받는 작업</dt><dd>${listOrDash(outs.filter(id => m.nodeType(id) === 'job').map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += `<dt>바로 쓰는 화면</dt><dd>${listOrDash(outs.filter(id => m.nodeType(id) === 'page').map(pageLink).filter(Boolean))}</dd>`;
      body += '</dl>';
    } else if (node.kind === 'page') {
      const p = node.ref;
      title = `<a href="${esc(pageHref(p.path))}">${esc(node.label)}</a>`;
      body += '<dl class="lin-dl">';
      body += `<dt>경로</dt><dd><code>${esc(p.path)}</code></dd>`;
      body += `<dt>부르는 API 주소</dt><dd>${listOrDash((p.routes || []).map(r => `<li><code>${esc(r)}</code></li>`))}</dd>`;
      body += `<dt>읽는 표·원천</dt><dd>${listOrDash(ins.map(id => `<li>${esc(label(id))}</li>`))}</dd>`;
      body += '</dl>';
    }
    return `<div class="card-header"><h3 class="card-title">${title}</h3>`
      + '<button type="button" class="lin-close" data-close="1">닫기</button></div>'
      + `<div class="card-body">${body}</div>`;
  }

  // ===== 화면(브라우저에서만) =====

  const api = { esc, pageHref, statusMap, summaryHtml, graphHtml, listHtml, detailHtml, STATE_LABEL, SUM_TIP };
  L.view = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 155개 통과(147 + view 8), 실패 0. BOM 확인 0.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/lineage/view.js
git diff --cached --name-status
git commit -m "feat(lineage): 계보 그림·요약·상세 카드 HTML 만들기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/lineage/view.js
```

---

### Task 3: 계보 탭 붙이기(화면 부분·CSS·데이터 탐색 페이지)와 첫 캡처

**Files:**
- Modify: `dashboard_js/js/lineage/view.js` (`// ===== 화면(브라우저에서만) =====` 뒤에 화면 부분, `const api` 줄 바꿈)
- Create: `dashboard_js/css/lineage.css`
- Modify: `dashboard_js/pages/database-explorer.html` (22행 style.css 링크 뒤, 486~489행 탭 버튼, 765~767행 `</main>` 앞, 770~772행 스크립트, 979~988행 `switchTab`, 1049행 첫 열기)
- Create (저장소 밖): `C:/tmp/bstats-team-stats-check/lineage_shot.mjs`
- Test (저장소 밖): `tests/lineage.html.test.js`

**Interfaces:**
- Consumes: Task 1·2 전부. `window.TeamStats.data.getJson(url, listKey)` (`js/stats/data.js`, `{ ok, data }` 또는 `{ ok: false, error }`), `window.KBO_API_BASE`(config.js), `createLoadingSpinner()`(components.js).
- Produces: `window.Lineage.view.open()` — 탭을 열 때 부름. 처음이면 데이터를 받아 그리고, 다시 열면 폭이 바뀌었을 때만 다시 그림. 화면 id: `tab-lineage`, `lin-alerts`, `lin-summary`, `lin-graph`, `lin-detail`.

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/lineage.html.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { REPO_JS } = require('./_load');

const html = fs.readFileSync(path.join(REPO_JS, '..', 'pages', 'database-explorer.html'), 'utf8');
const scripts = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);

test('database-explorer.html: 계보 파일을 이 순서로 싣고 lineage.css 를 씀', () => {
  assert.deepEqual(scripts, [
    '../js/config.js', '../js/theme-toggle.js', '../js/nav.js',
    '../js/api.js', '../js/components.js',
    '../js/stats/data.js', '../js/lineage/model.js', '../js/lineage/view.js',
  ]);
  assert.match(html, /<link rel="stylesheet" href="\.\.\/css\/style\.css">\r?\n    <link rel="stylesheet" href="\.\.\/css\/lineage\.css">/);
});

test('database-explorer.html: 탭 세 개, 계보 탭 칸과 화면이 쓰는 id', () => {
  assert.match(html, /data-tab="explorer">데이터 탐색<\/button>\s*<button class="atab" type="button" data-tab="sitemap">사이트맵<\/button>\s*<button class="atab" type="button" data-tab="lineage">테이블 계보<\/button>/);
  assert.match(html, /<div id="tab-lineage" class="atab-panel hidden">/);
  for (const id of ['lin-alerts', 'lin-summary', 'lin-graph', 'lin-detail']) assert.ok(html.includes(`id="${id}"`), id);
  assert.match(html, /<div id="lin-detail" class="card lin-detail hidden"><\/div>/);
});

test('database-explorer.html: switchTab 이 세 탭을 다루고 #lineage 로 바로 열림', () => {
  assert.match(html, /const TABS = \['explorer', 'sitemap', 'lineage'\];/);
  assert.match(html, /if \(tab === 'lineage' && window\.Lineage && window\.Lineage\.view\) window\.Lineage\.view\.open\(\);/);
  assert.match(html, /if \(window\.location\.hash === '#sitemap' \|\| window\.location\.hash === '#lineage'\) switchTab\(window\.location\.hash\.slice\(1\)\);/);
  assert.ok(!html.includes("if (window.location.hash === '#sitemap') switchTab('sitemap');"));
});
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/lineage.html.test.js"`
Expected: FAIL 3개(스크립트 목록·탭·switchTab 이 아직 없음).

- [ ] **Step 2: view.js 에 화면 부분 넣기**

`dashboard_js/js/lineage/view.js` 의 `  // ===== 화면(브라우저에서만) =====` 줄 뒤(빈 줄 다음)부터 `  const api = {…};` 줄까지를 아래로 바꿉니다(`const api` 줄에 `open` 이 더해집니다).

```js
  const S = {
    lin: null, rows: null, details: null, linError: null, opsErrors: [],
    graph: null, status: null, sel: null, filter: null, manualOpen: false,
    loading: null, width: 0, mobile: false,
  };
  let tipHide = function () {};

  function $(id) { return document.getElementById(id); }

  /** 계보 파일과 운영 정보 두 가지(행 수·실행 기록)를 받습니다. 실패는 이유를 남깁니다. */
  async function load() {
    const D = root.TeamStats.data;
    const base = root.KBO_API_BASE;
    const res = await Promise.all([
      D.getJson('../data/table_lineage.json', 'tables'),
      D.getJson(`${base}/db/tables`, 'tables'),
      D.getJson(`${base}/jobs/status`, null),
    ]);
    if (res[0].ok) S.lin = res[0].data;
    else S.linError = res[0].error;
    if (res[1].ok) {
      S.rows = {};
      res[1].data.tables.forEach(t => { S.rows[t.name] = t.rows; });
    } else {
      S.opsErrors.push(`행 수: ${res[1].error}`);
    }
    const det = res[2].ok ? res[2].data.details : null;
    if (det && typeof det === 'object' && !Array.isArray(det)) S.details = det;
    else S.opsErrors.push(`실행 기록: ${res[2].ok ? 'details 가 없습니다' : res[2].error}`);
  }

  /** 지금 상태로 그림 전체를 다시 그립니다(데이터를 다시 받지 않음). */
  function render() {
    const box = $('lin-graph');
    if (!box) return;
    tipHide();
    if (S.linError || !S.lin) {
      $('lin-alerts').innerHTML = '';
      $('lin-summary').innerHTML = '';
      $('lin-detail').classList.add('hidden');
      box.innerHTML = `<div class="lin-alert">계보 자료를 불러오지 못했습니다 (${esc(S.linError || '빈 응답')}).</div>`;
      return;
    }
    const m = M();
    S.graph = m.buildGraph(S.lin, { manualOpen: S.manualOpen });
    if (S.sel && !S.graph.nodes[S.sel]) S.sel = null;
    S.status = statusMap(S.lin, S.details, Date.now());
    if (!S.status) S.filter = null;
    S.mobile = root.matchMedia('(max-width: 640px)').matches;
    S.width = box.clientWidth;
    $('lin-alerts').innerHTML = S.opsErrors.length
      ? `<div class="lin-alert">운영 정보 일부를 불러오지 못했습니다 (${esc(S.opsErrors.join(' / '))}). 받지 못한 정보(상태 점·행 수)는 감춥니다.</div>`
      : '';
    box.innerHTML = S.mobile
      ? listHtml(S.graph, S.lin, S.status)
      : graphHtml(S.graph, m.layout(S.graph, S.width), S.lin, S.status);
    applyFocus();
  }

  /** 누른 상자·요약 숫자에 맞춰 진하게/흐리게와 상세 카드를 바꿉니다. */
  function applyFocus() {
    const box = $('lin-graph');
    let on = null, onEdges = null;
    if (S.sel) {
      const r = M().reach(S.graph, S.lin, S.sel);
      on = r.nodes;
      onEdges = r.edges;
    } else if (S.filter && S.status) {
      const by = S.status.sum.byTable;
      on = new Set(Object.keys(by).filter(n => by[n] === S.filter).map(n => 'table:' + n));
      onEdges = new Set();
    }
    const focus = !!on;
    box.classList.toggle('lin-focus', focus);
    box.querySelectorAll('.lin-box[data-id]').forEach(b => b.classList.toggle('on', focus && on.has(b.dataset.id)));
    box.querySelectorAll('.lin-edge').forEach(p => p.classList.toggle('on', focus && onEdges.has(Number(p.dataset.i))));
    $('lin-summary').innerHTML = summaryHtml(S.status && S.status.sum, S.filter);
    const card = $('lin-detail');
    if (S.sel) {
      card.innerHTML = detailHtml(S.graph.nodes[S.sel], S.lin, { graph: S.graph, status: S.status, rows: S.rows });
      card.classList.remove('hidden');
    } else {
      card.classList.add('hidden');
      card.innerHTML = '';
    }
  }

  function bindTips(scope) {
    let box = null;
    function hide() { if (box) box.style.display = 'none'; }
    tipHide = hide;
    root.addEventListener('scroll', hide, { passive: true });
    $('lin-graph').addEventListener('scroll', hide, { passive: true });
    scope.addEventListener('mouseover', function (e) {
      const el = e.target.closest && e.target.closest('[data-tooltip]');
      if (!el || !scope.contains(el)) return;
      if (!box) {
        box = document.createElement('div');
        box.className = 'lin-tip';
        document.body.appendChild(box);
      }
      box.textContent = el.getAttribute('data-tooltip');
      box.style.display = 'block';
      const r = el.getBoundingClientRect();
      box.style.left = Math.max(8, Math.min(r.left, root.innerWidth - box.offsetWidth - 12)) + 'px';
      const below = r.bottom + 6;
      box.style.top = (below + box.offsetHeight > root.innerHeight ? Math.max(8, r.top - box.offsetHeight - 6) : below) + 'px';
    });
    scope.addEventListener('mouseout', function (e) {
      if (e.target.closest && e.target.closest('[data-tooltip]')) hide();
    });
  }

  function bind() {
    const tab = $('tab-lineage');
    tab.addEventListener('click', function (e) {
      const sum = e.target.closest('.lin-sum-btn');
      if (sum) {
        const k = sum.dataset.state;
        S.sel = null;
        S.filter = S.filter === k ? null : k;
        applyFocus();
        return;
      }
      if (e.target.closest('[data-close]')) {
        S.sel = null;
        applyFocus();
        return;
      }
      const b = e.target.closest('.lin-box[data-id]');
      if (b) {
        const id = b.dataset.id;
        if (id === M().GROUP_ID) {
          S.manualOpen = !S.manualOpen;
          render();
          return;
        }
        S.filter = null;
        S.sel = S.sel === id ? null : id;
        applyFocus();
        if (S.sel && S.mobile) $('lin-detail').scrollIntoView({ block: 'nearest' });
        return;
      }
      // 그림의 빈 곳을 누르면 처음으로 돌아갑니다.
      if (e.target.closest('.lin-canvas')) {
        S.sel = null;
        S.filter = null;
        applyFocus();
      }
    });
    let t = null;
    root.addEventListener('resize', function () {
      clearTimeout(t);
      t = setTimeout(function () {
        const box = $('lin-graph');
        if (!S.lin || !box || $('tab-lineage').classList.contains('hidden')) return;
        const mob = root.matchMedia('(max-width: 640px)').matches;
        if (box.clientWidth !== S.width || mob !== S.mobile) render();
      }, 150);
    });
    bindTips(tab);
  }

  /**
   * 탭을 열 때 부릅니다(database-explorer.html 의 switchTab). 처음이면 데이터를 받아
   * 그리고, 다시 열면 그사이 폭이 바뀌었을 때만 다시 그립니다.
   */
  function open() {
    if (!S.loading) {
      bind();
      $('lin-graph').innerHTML = typeof root.createLoadingSpinner === 'function' ? root.createLoadingSpinner() : '';
      S.loading = load().then(render).catch(function (e) {
        console.error(e);
        S.linError = String((e && e.message) || e);
        render();
      });
      return S.loading;
    }
    return S.loading.then(function () {
      const box = $('lin-graph');
      if (S.lin && box && box.clientWidth !== S.width) render();
    });
  }

  const api = { esc, pageHref, statusMap, summaryHtml, graphHtml, listHtml, detailHtml, open, STATE_LABEL, SUM_TIP };
```

- [ ] **Step 3: lineage.css 쓰기**

`dashboard_js/css/lineage.css`:

```css
/*
 * 테이블 계보 탭(database-explorer.html #lineage) 스타일입니다.
 * 색은 style.css 의 var() 토큰을 쓰고, 칸 테두리 색만 다크 모드에서 밝게 바꿉니다.
 */
.lin-alert { border-left: 3px solid var(--warning); background: rgba(245, 158, 11, 0.08); padding: 0.45rem 0.7rem; font-size: 0.85rem; margin-bottom: 0.6rem; border-radius: 6px; color: var(--text-secondary); }
.lin-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 0.4rem; margin-bottom: 0.8rem; }
.lin-summary:empty { display: none; }
.lin-sum-btn { display: inline-flex; align-items: center; gap: 0.35rem; border: 1px solid var(--border-color); background: var(--bg-secondary); color: var(--text-primary); border-radius: 8px; padding: 0.3rem 0.7rem; font: inherit; font-size: 0.85rem; cursor: pointer; }
.lin-sum-btn:hover { border-color: var(--primary); }
.lin-sum-btn.on { border-color: var(--primary); box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25); }
.lin-sum-manual { font-size: 0.85rem; color: var(--text-muted); margin-left: 0.3rem; }

.lin-card:hover, .lin-detail:hover { transform: none; }
.lin-graph { overflow-x: auto; }
.lin-heads { position: relative; height: 1.6rem; margin-bottom: 0.4rem; }
.lin-head { position: absolute; top: 0; font-weight: 700; font-size: 0.9rem; color: var(--text-secondary); }
.lin-canvas { position: relative; }
.lin-svg { position: absolute; left: 0; top: 0; overflow: visible; pointer-events: none; }
.lin-edge { fill: none; stroke: var(--text-muted); stroke-width: 1.2; opacity: 0.35; transition: opacity 0.15s, stroke 0.15s; }

.lin-box { position: absolute; display: flex; align-items: center; gap: 0.4rem; box-sizing: border-box; padding: 0 0.6rem; border: 1.5px solid var(--border-color); border-radius: 8px; background: var(--bg-secondary); color: var(--text-primary); font: inherit; font-size: 0.82rem; text-align: left; cursor: pointer; overflow: hidden; transition: opacity 0.15s, box-shadow 0.15s; }
.lin-box:hover { box-shadow: var(--shadow-sm); }
.lin-label { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-weight: 600; }
.lin-sub { flex: 0 0 auto; font-size: 0.72rem; color: var(--text-muted); white-space: nowrap; }
.lin-k-source { border-color: #0f766e; }
.lin-k-job { border-color: #c2410c; }
.lin-k-collected { border-color: #2563eb; }
.lin-k-manual, .lin-k-group { border-color: #64748b; border-style: dashed; }
.lin-k-derived { border-color: #7c3aed; }
.lin-k-page { border-color: #be123c; }
[data-theme="dark"] .lin-k-source { border-color: #2dd4bf; }
[data-theme="dark"] .lin-k-job { border-color: #fb923c; }
[data-theme="dark"] .lin-k-collected { border-color: #60a5fa; }
[data-theme="dark"] .lin-k-manual, [data-theme="dark"] .lin-k-group { border-color: #94a3b8; }
[data-theme="dark"] .lin-k-derived { border-color: #a78bfa; }
[data-theme="dark"] .lin-k-page { border-color: #fb7185; }

/* 상태 점(초록 정상·빨강 실패·회색 오래됨·기록 없음)과 손 작업 표시 */
.lin-dot { flex: 0 0 auto; display: inline-block; width: 9px; height: 9px; border-radius: 50%; }
.lin-ok { background: var(--success); }
.lin-fail { background: var(--danger); }
.lin-stale, .lin-none { background: #94a3b8; }
.lin-tag { flex: 0 0 auto; font-size: 0.68rem; color: var(--text-muted); border: 1px solid var(--border-color); border-radius: 4px; padding: 0 0.25rem; }

/* 누른 상자·요약 숫자에 이어진 것만 진하게 */
.lin-focus .lin-box { opacity: 0.25; }
.lin-focus .lin-box.on { opacity: 1; box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.35); }
.lin-focus .lin-edge { opacity: 0.06; }
.lin-focus .lin-edge.on { opacity: 1; stroke: var(--primary); stroke-width: 2; }

/* 상세 카드 */
.lin-detail { margin-top: 1rem; }
.lin-detail.hidden { display: none; }
.lin-detail .card-header { display: flex; align-items: center; justify-content: space-between; gap: 0.6rem; }
.lin-close { appearance: none; border: 1px solid var(--border-color); background: transparent; color: inherit; border-radius: 8px; padding: 0.25rem 0.7rem; font: inherit; font-size: 0.85rem; cursor: pointer; }
.lin-kind { font-size: 0.78rem; color: var(--text-muted); font-weight: 500; margin-left: 0.5rem; }
.lin-desc { margin: 0 0 0.3rem; }
.lin-cat { margin: 0; font-size: 0.85rem; }
.lin-dl { display: grid; grid-template-columns: 9rem 1fr; gap: 0.45rem 1rem; margin: 0.8rem 0 0; font-size: 0.88rem; }
.lin-dl dt { color: var(--text-muted); font-weight: 600; }
.lin-dl dd { margin: 0; min-width: 0; overflow-wrap: anywhere; }
.lin-dl ul { margin: 0; padding-left: 1.1rem; }
.lin-status { display: inline-flex; align-items: center; gap: 0.35rem; }

/* 설명 창(마우스를 올리면) */
.lin-tip { position: fixed; z-index: 9999; display: none; max-width: 340px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.45rem 0.65rem; font-size: 0.8rem; line-height: 1.45; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12); pointer-events: none; white-space: pre-line; }

/* 휴대폰 목록(선 대신 이어지는 곳) */
.lin-list-col { margin-bottom: 1rem; }
.lin-list-col h4 { font-size: 0.95rem; margin: 0 0 0.4rem; }
.lin-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 0.45rem; }
.lin-list .lin-box { position: static; width: 100%; height: 36px; }
.lin-next { font-size: 0.78rem; color: var(--text-muted); margin: 0.2rem 0 0 0.3rem; overflow-wrap: anywhere; }
@media (max-width: 640px) {
    .lin-dl { grid-template-columns: 1fr; gap: 0.15rem; }
    .lin-dl dd { margin-bottom: 0.5rem; }
}
```

- [ ] **Step 4: 데이터 탐색 페이지에 탭 붙이기**

`dashboard_js/pages/database-explorer.html` 을 다섯 군데 고칩니다(Edit 도구, CRLF 그대로).

(1) `    <link rel="stylesheet" href="../css/style.css">` 바로 다음 줄에 넣습니다.

```html
    <link rel="stylesheet" href="../css/lineage.css">
```

(2) 탭 버튼: `            <button class="atab" type="button" data-tab="sitemap">사이트맵</button>` 바로 다음 줄에 넣습니다.

```html
            <button class="atab" type="button" data-tab="lineage">테이블 계보</button>
```

(3) 탭 칸: 사이트맵 탭 칸이 끝나는 곳

```html
        </section>
        </div>
    </main>
```

을 아래로 바꿉니다.

```html
        </section>
        </div>

        <!-- ===== 탭: 테이블 계보 ===== -->
        <div id="tab-lineage" class="atab-panel hidden">
        <h1 class="fade-in"><span class="material-symbols-outlined h1-icon">schema</span>테이블 계보</h1>
        <p class="text-secondary mb-3">KBO 원천에서 받은 데이터가 어떤 수집 작업을 거쳐 어느 표에 쌓이고, 어느 화면에 쓰이는지 보여 줍니다.
            선을 따라가면 숫자가 어디서 왔는지 보입니다. 상자를 누르면 이어진 경로만 진하게 보이고, 그림 아래에 자세한 정보가 나옵니다.</p>
        <div id="lin-alerts"></div>
        <div id="lin-summary" class="lin-summary"></div>
        <section>
            <div class="card lin-card">
                <div class="card-body">
                    <div id="lin-graph" class="lin-graph"></div>
                </div>
            </div>
            <div id="lin-detail" class="card lin-detail hidden"></div>
        </section>
        </div>
    </main>
```

(4) 스크립트: `    <script src="../js/components.js"></script>` 바로 다음 줄에 넣습니다.

```html
    <script src="../js/stats/data.js"></script>
    <script src="../js/lineage/model.js"></script>
    <script src="../js/lineage/view.js"></script>
```

(5) `switchTab`: 아래 함수 전체(`// ── 페이지 탭: 데이터 탐색 / 사이트맵 ──` 주석 줄부터 `document.querySelectorAll('.atab').forEach(…)` 줄까지)

```js
        // ── 페이지 탭: 데이터 탐색 / 사이트맵 ──
        function switchTab(tab) {
            document.querySelectorAll('.atab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
            document.getElementById('tab-explorer').classList.toggle('hidden', tab !== 'explorer');
            document.getElementById('tab-sitemap').classList.toggle('hidden', tab !== 'sitemap');
            if (history.replaceState) {
                history.replaceState(null, '',
                    tab === 'sitemap' ? '#sitemap' : window.location.pathname + window.location.search);
            }
        }
        document.querySelectorAll('.atab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
```

을 아래로 바꿉니다.

```js
        // ── 페이지 탭: 데이터 탐색 / 사이트맵 / 테이블 계보 ──
        const TABS = ['explorer', 'sitemap', 'lineage'];
        function switchTab(tab) {
            if (!TABS.includes(tab)) tab = 'explorer';
            document.querySelectorAll('.atab').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
            TABS.forEach(t => document.getElementById('tab-' + t).classList.toggle('hidden', t !== tab));
            if (history.replaceState) {
                history.replaceState(null, '',
                    tab === 'explorer' ? window.location.pathname + window.location.search : '#' + tab);
            }
            // 계보 탭은 처음 열 때 데이터를 받아 그립니다(보이는 폭에 맞춰 그리므로 탭을 보인 뒤에 부름).
            if (tab === 'lineage' && window.Lineage && window.Lineage.view) window.Lineage.view.open();
        }
        document.querySelectorAll('.atab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));
```

그리고 맨 아래 초기화의

```js
        if (window.location.hash === '#sitemap') switchTab('sitemap');
```

를 아래로 바꿉니다.

```js
        if (window.location.hash === '#sitemap' || window.location.hash === '#lineage') switchTab(window.location.hash.slice(1));
```

- [ ] **Step 5: Node 시험 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 158개 통과(155 + html 3), 실패 0. 새 파일 BOM 확인 0.

- [ ] **Step 6: 캡처 도구 만들기**

`C:/tmp/bstats-team-stats-check/lineage_shot.mjs`:

```js
// 데이터 탐색 페이지를 열고(필요하면 상자를 누른 뒤) 화면을 캡처하고 숫자를 잽니다.
// 사용: node lineage_shot.mjs <이름> <경로와 쿼리> [--click <CSS 선택자>]... [--mobile] [--dark] [--width 1400]
// 결과: 바탕화면 bstats_lin_<이름>.png, 콘솔에 { inner, doc, boxes, on, edgesOn, summary, alerts, detail }
import { spawn } from 'node:child_process';
import { writeFileSync, existsSync } from 'node:fs';

const args = process.argv.slice(2);
const name = args[0];
const path = args[1];
const clicks = [];
let mobile = false, dark = false, width = 1400;
for (let i = 2; i < args.length; i++) {
  if (args[i] === '--click') clicks.push(args[++i]);
  else if (args[i] === '--mobile') mobile = true;
  else if (args[i] === '--dark') dark = true;
  else if (args[i] === '--width') width = Number(args[++i]);
}
const BASE = 'http://127.0.0.2:8765';
const EDGE = [
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
].find(existsSync);
const port = 9600 + Math.floor(Math.random() * 300);
const ud = `C:/tmp/bstats-team-stats-check/edge_ud/lin_${Date.now()}`;
const edge = spawn(EDGE, ['--headless=new', '--disable-gpu', `--remote-debugging-port=${port}`, `--user-data-dir=${ud}`, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));

let targets;
for (let i = 0; i < 40; i++) {
  try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); break; } catch { await sleep(250); }
}
const ws = new WebSocket(targets.find(t => t.type === 'page').webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let id = 0;
const pending = new Map();
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
});
const send = (method, params = {}) => new Promise(r => { const i = ++id; pending.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async expression => (await send('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })).result.result.value;

await send('Emulation.setDeviceMetricsOverride', mobile
  ? { width: 390, height: 844, deviceScaleFactor: 2, mobile: true }
  : { width, height: 1000, deviceScaleFactor: 1, mobile: false });
if (mobile) await send('Emulation.setTouchEmulationEnabled', { enabled: true });
await send('Page.enable');
if (dark) {
  await send('Page.navigate', { url: `${BASE}/pages/database-explorer.html` });
  await sleep(1500);
  await evaluate(`localStorage.setItem('kbo-theme-v2', 'dark')`);
}
await send('Page.navigate', { url: BASE + path });
await sleep(9000);
for (const sel of clicks) {
  const ok = await evaluate(`(() => { const el = document.querySelector(${JSON.stringify(sel)}); if (!el) return false; el.click(); return true; })()`);
  if (!ok) console.log('누를 것을 찾지 못했습니다:', sel);
  await sleep(900);
}
const info = await evaluate(`JSON.stringify({
  inner: innerWidth, doc: document.documentElement.scrollWidth,
  boxes: document.querySelectorAll('#lin-graph .lin-box').length,
  on: document.querySelectorAll('#lin-graph .lin-box.on').length,
  edgesOn: document.querySelectorAll('#lin-graph .lin-edge.on').length,
  summary: (document.getElementById('lin-summary') || {}).innerText || '',
  alerts: (document.getElementById('lin-alerts') || {}).innerText || '',
  detail: ((document.getElementById('lin-detail') || {}).innerText || '').slice(0, 160),
})`);
console.log(name, info);
const metrics = await send('Page.getLayoutMetrics');
const size = metrics.result.cssContentSize || metrics.result.contentSize;
const shot = await send('Page.captureScreenshot', {
  format: 'png', captureBeyondViewport: true,
  clip: { x: 0, y: 0, width: mobile ? 390 : Math.max(width, Math.ceil(size.width)), height: Math.min(Math.ceil(size.height), mobile ? 3200 : 2600), scale: 1 },
});
writeFileSync(`C:/Users/김승곤/Desktop/bstats_lin_${name}.png`, Buffer.from(shot.result.data, 'base64'));
ws.close();
edge.kill();
process.exit(0);
```

- [ ] **Step 7: 첫 화면 캡처와 숫자 확인**

```bash
cd C:/tmp/bstats-team-stats-check
node lineage_shot.mjs first "/pages/database-explorer.html#lineage"
node lineage_shot.mjs explorer "/pages/database-explorer.html"
```

Expected:
- `first` 출력: `boxes` 35, `on` 0, `edgesOn` 0, `alerts` 빈 글자, `summary` 가 "정상 N 실패 N 오래됨 N 기록 없음 N 손 작업 11" 꼴(숫자 넷의 합 16), `detail` 빈 글자, `doc` ≤ 1400.
- `bstats_lin_first.png`(바탕화면)를 Read 로 열어 봅니다: 탭 세 개 중 "테이블 계보" 켜짐, 요약 줄, 5칸 제목(원천·수집 작업·표·계산 표·화면), 상자와 옅은 회색 선, 표·작업 상자에 점, "손 작업 표 11개 · 펼치기" 상자, 화면 칸 7개.
- `bstats_lin_explorer.png`: 기존 "데이터 탐색" 탭이 켜져 있고 예전처럼 보임(계보 탭 내용이 보이지 않음).

맞지 않으면 원인을 찾아 고치고 다시 확인합니다(계보 파일·API 응답 이상이면 고치지 말고 알림 문구가 맞게 나오는지만 봅니다).

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/lineage/view.js dashboard_js/css/lineage.css dashboard_js/pages/database-explorer.html
git diff --cached --name-status
git commit -m "feat(lineage): 데이터 탐색 페이지에 테이블 계보 탭

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/lineage/view.js dashboard_js/css/lineage.css dashboard_js/pages/database-explorer.html
```

---

### Task 4: 누르기·휴대폰·다크 확인, 계보 다시 만들기

**Files:**
- Modify (문제가 나올 때만): `dashboard_js/js/lineage/*.js`, `dashboard_js/css/lineage.css`, `dashboard_js/pages/database-explorer.html`
- 다시 만들기 결과가 바뀌면: `dashboard_js/data/table_lineage.json`
- 결과: 바탕화면 PNG

**Interfaces:**
- Consumes: Task 3 의 화면, `lineage_shot.mjs`.
- Produces: 확인된 캡처. 고친 것이 있으면 커밋.

- [ ] **Step 1: 누르기 캡처**

```bash
cd C:/tmp/bstats-team-stats-check
node lineage_shot.mjs games "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="table:games"]'
node lineage_shot.mjs fail "/pages/database-explorer.html#lineage" --click '.lin-sum-btn[data-state="fail"]'
node lineage_shot.mjs manual "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="group:manual"]'
node lineage_shot.mjs manual_close "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="group:manual"]' --click '.lin-box[data-id="group:manual"]'
node lineage_shot.mjs job "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="job:weekly"]'
node lineage_shot.mjs page "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="page:pages/team-stats.html"]'
node lineage_shot.mjs reset "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="table:games"]' --click '.lin-close'
```

| 캡처 | 출력에서 맞아야 하는 것 | PNG 에서 볼 것 |
|---|---|---|
| games | `on` 14, `edgesOn` 25, `detail` 이 "games 받아 온 표" 로 시작 | 원천은 네이버 문자중계만 진함, daily → games → 계산 표 → 화면이 진한 파란 선, 나머지 흐림. 아래 카드에 행 수·쓰는 스크립트·마지막 실행·읽는 API 주소·쓰는 화면 |
| fail | `on` = 요약 줄의 실패 숫자, `edgesOn` 0, `detail` 빈 글자 | 실패 버튼이 켜짐, 빨간 점 표만 진함 |
| manual | `boxes` 46 | 표 칸에 "손 작업 표 11개 · 접기" 다음 손 작업 표 11개(점선 테두리, "손 작업" 표시) |
| manual_close | `boxes` 35 | 다시 접힘 |
| job | `detail` 이 "weekly" 로 시작 | weekly 와 계산 표 6개·화면이 진함, 카드에 실행 시각·기준 시간·단계 목록 |
| page | `detail` 이 "팀 통계" 로 시작 | 팀 통계로 들어오는 표·작업·원천이 진함, 카드 제목이 팀 통계 링크 |
| reset | `on` 0, `detail` 빈 글자 | 처음 화면과 같음 |

- [ ] **Step 2: 다크·휴대폰·기존 탭 캡처**

```bash
cd C:/tmp/bstats-team-stats-check
node lineage_shot.mjs dark "/pages/database-explorer.html#lineage" --dark --click '.lin-box[data-id="table:wrc_plus_comparison"]'
node lineage_shot.mjs mobile "/pages/database-explorer.html#lineage" --mobile
node lineage_shot.mjs mobile_games "/pages/database-explorer.html#lineage" --mobile --click '.lin-box[data-id="table:games"]'
node lineage_shot.mjs sitemap "/pages/database-explorer.html#sitemap"
```

| 캡처 | 맞아야 하는 것 |
|---|---|
| dark | 어두운 배경에서 상자 글자·칸 테두리 색·진한 선·상세 카드가 읽힘 |
| mobile | `doc` ≤ 390(가로 넘침 없음), `boxes` 35, 칸 다섯이 위아래로 쌓이고 선 대신 "→ 이어지는 곳: …" 줄 |
| mobile_games | `on` 14, 상세 카드가 보임 |
| sitemap | 사이트맵 탭이 켜지고 예전처럼 보임 |

맞지 않는 것이 있으면 `dashboard_js` 안 계보 파일에서 고치고, Node 시험 전체를 다시 돌리고(158개), 영향받은 캡처만 다시 찍습니다.

- [ ] **Step 3: 계보 다시 만들기와 저장소 시험**

데이터 탐색 페이지에 스크립트를 더했으므로 계보 생성기를 다시 돌립니다(scripts·tests 는 실행만).

```bash
cd C:/Users/김승곤/Desktop/b_project
py scripts/build_lineage.py
py -m pytest tests -q 2>&1 | tail -3
git add dashboard_js/data/table_lineage.json
git status --short dashboard_js/data/table_lineage.json
```

Expected:
- pytest 가 모두 통과합니다(실패가 있으면 이름과 메시지를 보고하고 고치지 않습니다).
- 마지막 줄이 비어 있으면 계보 내용이 그대로입니다(줄 끝만 다르던 것도 정리됨). 커밋할 것이 없습니다.
- `M  dashboard_js/data/table_lineage.json` 이 남으면 내용이 바뀐 것입니다. `git diff --cached dashboard_js/data/table_lineage.json` 로 바뀐 곳을 보고서에 적고 커밋합니다.

```bash
git commit -m "chore(lineage): 계보 탭을 넣은 뒤 계보 다시 만들기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/data/table_lineage.json
```

- [ ] **Step 4: (고친 것이 있을 때만) 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add <고친 dashboard_js 파일들>
git diff --cached --name-status
git commit -m "fix(lineage): <무엇을 고쳤는지 한국어로>

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- <고친 dashboard_js 파일들>
```

- [ ] **Step 5: 보고**

캡처마다 출력 숫자와 PNG 확인 결과, 다시 만들기 결과, `git log origin/main..main --oneline` 을 보고서에 적습니다. push·배포는 하지 않습니다.
