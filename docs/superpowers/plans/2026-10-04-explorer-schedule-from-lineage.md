# 데이터 탐색 수집 일정 표를 계보로 만들기 · 두 탭 잇기 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 데이터 탐색 탭의 손으로 적은 '자동 수집 스케줄' 표를 계보 파일로 자동 생성하고, 데이터 탐색 ↔ 테이블 계보 두 탭을 버튼으로 잇습니다.

**Architecture:** 새 모듈 `js/lineage/schedule.js` 가 계보 파일의 작업·단계·스크립트와 `/jobs/status` 로 표 몸통을 만듭니다(순수 함수 + `mount`). `view.js` 는 계보 파일을 한 번만 받는 `loadLineage()` 와 표를 고른 채 여는 `open(selectId)`, 상세 카드 '데이터 보기' 버튼(이벤트 `lineage:show-table`)을 더합니다. 페이지는 빈 표 자리·버튼·이벤트 받기만 둡니다.

**Tech Stack:** 순수 JavaScript(빌드 없음), Node 24 `node --test`, 헤드리스 Edge(CDP) 캡처.

**설계 문서:** `C:/Users/김승곤/Desktop/b_project/docs/superpowers/specs/2026-10-04-explorer-schedule-from-lineage-design.md`

## Global Constraints

- 저장소 `C:/Users/김승곤/Desktop/b_project` (브랜치 `main`, 다른 세션과 폴더를 같이 씀). 고칠 수 있는 곳은 `dashboard_js/` 안뿐이고, 이 계획에서는 `js/lineage/schedule.js`(새), `js/lineage/view.js`, `css/lineage.css`, `pages/database-explorer.html` 만 고칩니다. `data/table_lineage.json`·`js/stats/*`·다른 페이지·`src/`·`scripts/`·`tests/`·`database/` 는 고치지 않습니다(Task 2 에서 `py scripts/build_lineage.py`·`py -m pytest tests` 를 실행만, 결과 JSON 이 바뀌면 그것만 커밋).
- git: 브랜치를 바꾸지 않습니다. `git add -A`·`git add .`·`git commit -a`·`git stash`·`git reset`·`git restore`·`git checkout --` 금지. 커밋 전 `git status --short`·`git diff --cached --name-status`, 커밋은 `git commit -m "…" -- <자기 파일들>`. 다른 세션 변경은 그대로 둡니다. push·배포는 하지 않습니다.
- 커밋 메시지 `feat(explorer): 한국어 설명` 꼴 + 빈 줄 + `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- 모듈 틀은 계보 모듈과 같음(전역 `window.Lineage.<이름>`, Node 는 vm, 저장소 package.json 이 `"type": "module"` 이라 `.cjs` 로 바꾸지 않음). 시험 도우미 `tests/_load.js` 의 `loadLineage(name)` 는 `js/lineage/<name>.js` 를 읽습니다.
- 저장소 파일 CRLF. Edit 도구로 정확히 맞춰 고치고 이스케이프는 이스케이프로 둡니다(새·고친 파일 `grep -c $'\xEF\xBB\xBF'` 0).
- 사용자 글은 습니다/합니다, 쉬운 말, 이모지·줄표(—) 없음. 툴팁에 DB 용어를 늘어놓지 않습니다.
- 응답 이상은 가리지 않고 이유를 보입니다(계보 파일 실패 → 표 자리 문구, 실행 기록 실패 → 마지막 업데이트 '-').
- 데이터 탐색 탭의 다른 기능(데이터 현황, 테이블 목록, 표 상세·CSV)과 사이트맵 탭, 계보 탭의 기존 동작은 바꾸지 않습니다.
- 미리보기 `127.0.0.2:8765`(이미 떠 있지 않으면 `py C:/tmp/bstats-team-stats-check/preview.py` 를 백그라운드로 띄우고 끝나면 끕니다). 캡처 도구 `C:/tmp/bstats-team-stats-check/lineage_shot.mjs`(고치지 않음, Git Bash 면 앞에 `MSYS_NO_PATHCONV=1`).
- Node 시험 전체: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"` (지금 171개 통과).

---

### Task 1: 수집 일정 표 모듈(schedule.js)

**Files:**
- Create: `dashboard_js/js/lineage/schedule.js`
- Test (저장소 밖): `C:/tmp/bstats-team-stats-check/tests/lineage.schedule.test.js`

**Interfaces:**
- Produces (`window.Lineage.schedule`): `HELPER`(정규식), `JOB_ORDER`, `scheduleRows(lin)` → `[{ path, name, desc, runs: [{ job, schedule, key }] }]`, `runText(run, details)` → 글자, `scheduleHtml(rows, details)` → tbody 안 HTML(`<tr>` 4칸: `.dbx-cron-mods`·`.dbx-cron-desc`·`.dbx-cron-kst`·`.dbx-cron-upd`, 실행마다 `span.dbx-run`(실패면 `.fail`, 메모는 title)), `scheduleSummary(rows, lin)` → "총 N개 스크립트 · 작업 M개", `mount({ tbody, summary, lineage, jobs })` (lineage·jobs 는 `{ ok, data } | { ok: false, error }` 로 끝나는 Promise).

- [ ] **Step 1: 실패하는 시험 쓰기**

`C:/tmp/bstats-team-stats-check/tests/lineage.schedule.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { loadLineage, fixture } = require('./_load');
const S = loadLineage('schedule');
const lin = fixture('lineage');
const det = fixture('jobs_status').details;
const text = h => h.replace(/<br>/g, ' / ').replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim();

test('scheduleRows: 스크립트마다 한 줄, 거들기 단계는 빼고 작업 순서(daily→roster→weekly→monthly)', () => {
  const rows = S.scheduleRows(lin);
  assert.equal(rows.length, 22);
  assert.equal(rows[0].name, 'daily_pbp_to_d1.py');
  assert.ok(!rows.some(r => /record_job_run\.py|ci_proxy\.sh/.test(r.path)));
  const names = rows.map(r => r.name);
  assert.ok(names.indexOf('futures_records.py') > names.indexOf('reconcile.py'));
  assert.ok(names.indexOf('mysql_to_sqlite.py') > names.indexOf('futures_records.py'));
  assert.equal(names[names.length - 1], 'heal_player_photos.py');
  assert.ok(names.includes('build_woba_weights.py'));
  assert.equal(new Set(names).size, names.length);
});

test('scheduleRows: 두 작업에서 도는 스크립트는 한 줄에 실행이 둘, 기록 키는 작업마다', () => {
  const rows = S.scheduleRows(lin);
  const roster = rows.find(r => r.name === 'roster_to_d1.py');
  assert.deepEqual(roster.runs.map(x => [x.job, x.schedule, x.key]), [['daily', '매일 03:33', 'roster'], ['roster', '매일 16:07', 'roster_pm']]);
  const fr = rows.find(r => r.name === 'futures_records.py');
  assert.deepEqual(fr.runs.map(x => [x.job, x.key]), [['roster', 'futures_records']]);
  const sync = rows.find(r => r.name === 'sync_players_from_roster.py');
  assert.deepEqual(sync.runs.map(x => x.key), [null, null]);
});

test('scheduleRows: 설명은 desc 가 있으면 그것, 없으면 단계 이름(겹치면 한 번)과 note', () => {
  const rows = S.scheduleRows(lin);
  assert.equal(rows.find(r => r.name === 'futures_to_d1.py').desc, '퓨처스 일정 적재');
  assert.match(rows.find(r => r.name === 'daily_pbp_to_d1.py').desc, /^PBP 수집·적재\. /);
  const copy = JSON.parse(JSON.stringify(lin));
  copy.scripts.find(s => s.path.endsWith('futures_to_d1.py')).desc = '손으로 쓴 설명입니다.';
  assert.equal(S.scheduleRows(copy).find(r => r.name === 'futures_to_d1.py').desc, '손으로 쓴 설명입니다.');
  assert.deepEqual(S.scheduleRows({}), []);
});

test('runText: 시각과 결과, 기록 키 없음·기록 못 받음은 -, 기록 전은 아직 기록 없음', () => {
  const run = (key, schedule) => ({ job: 'daily', schedule: schedule || '매일 03:33', key: key });
  assert.equal(S.runText(run('games'), det), '매일 03:33: 2026-10-03 07:27');
  assert.equal(S.runText(run('futures'), det), '매일 03:33: 2026-10-03 07:27 (실패)');
  assert.equal(S.runText(run('team_ranks'), det), '매일 03:33: 아직 기록 없음');
  assert.equal(S.runText(run(null), det), '매일 03:33: -');
  assert.equal(S.runText(run('games'), null), '매일 03:33: -');
  assert.equal(S.runText(run('x'), { x: { status: 'skip', last_run_at: '2026-10-04 10:29' } }), '매일 03:33: 2026-10-04 10:29 (건너뜀)');
  assert.equal(S.runText(run('x'), { x: { status: 'running', last_run_at: '2026-10-04 10:29' } }), '매일 03:33: 2026-10-04 10:29 (running)');
});

test('scheduleHtml: 네 칸, 실패는 표시, 메모는 title, 글자는 이스케이프', () => {
  const rows = S.scheduleRows(lin);
  const h = S.scheduleHtml(rows, det);
  assert.equal((h.match(/<tr>/g) || []).length, 22);
  assert.match(h, /<td class="dbx-cron-mods">roster_to_d1\.py<span class="sub">data_collection\/roster_to_d1\.py<\/span><\/td>/);
  assert.match(h, /<td class="dbx-cron-kst">매일 03:33<br>매일 16:07<\/td>/);
  assert.match(h, /<span class="dbx-run fail"[^>]*>매일 03:33: 2026-10-03 07:27 \(실패\)<\/span>/);
  assert.match(h, /title="내려받기 success \/ 계산 skipped"/);
  const evil = S.scheduleHtml([{ path: 'a/<b>.py', name: '<b>.py', desc: '"x" & y', runs: [] }], null);
  assert.ok(!evil.includes('<b>'));
  assert.match(evil, /&lt;b&gt;\.py/);
  assert.match(evil, /&quot;x&quot; &amp; y/);
  assert.match(text(S.scheduleHtml(rows.slice(0, 1), null)), /매일 03:33: -$/);
});

test('scheduleSummary', () => {
  assert.equal(S.scheduleSummary(S.scheduleRows(lin), lin), '총 22개 스크립트 · 작업 4개');
});
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/lineage.schedule.test.js"`
Expected: FAIL (`ENOENT … js\lineage\schedule.js`).

- [ ] **Step 2: schedule.js 쓰기**

`dashboard_js/js/lineage/schedule.js`:

```js
/*
 * 데이터 탐색 탭의 '자동 수집 스케줄' 표입니다. 계보 파일(table_lineage.json)의
 * 작업·단계·스크립트와 /jobs/status 실행 기록으로 만듭니다. 손으로 적은 표는
 * 수집 작업이 바뀔 때마다 어긋나서 이것으로 바꿨습니다.
 *
 * 위쪽 HTML 을 만드는 함수는 Node 로 검증하고, mount() 만 브라우저에서 돕니다.
 * 근거: docs/superpowers/specs/2026-10-04-explorer-schedule-from-lineage-design.md
 */
(function (root) {
  'use strict';
  const L = root.Lineage = root.Lineage || {};

  // 표에 싣지 않는 거들기 단계입니다(실행 기록 남기기·DB 연결).
  const HELPER = /(^|\/)(record_job_run\.py|ci_proxy\.sh)$/;
  // 작업을 보여 줄 순서입니다(하루 흐름: 새벽 daily → 오후 roster → 주간 → 월간).
  const JOB_ORDER = ['daily', 'roster', 'weekly', 'monthly'];

  function esc(s) {
    return String(s === null || s === undefined ? '' : s)
      .replace(/[&<>"]/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]));
  }

  function baseName(path) { return String(path || '').split('/').pop(); }

  function jobRank(id) {
    const i = JOB_ORDER.indexOf(id);
    return i < 0 ? JOB_ORDER.length : i;
  }

  /**
   * 표의 줄입니다. 스크립트 하나에 한 줄이고, 처음 나오는 작업·단계 순서를 따릅니다.
   * 반환 [{ path, name, desc, runs: [{ job, schedule, key }] }]
   *   desc: scripts[].desc 가 있으면 그것, 없으면 단계 이름들(겹치면 한 번)과 note
   *   runs: 그 스크립트가 도는 작업마다 하나. key 는 그 작업에서 그 스크립트 단계의 기록 키(없으면 null)
   */
  function scheduleRows(lin) {
    const jobs = (lin && lin.jobs ? lin.jobs.slice() : [])
      .sort((a, b) => jobRank(a.id) - jobRank(b.id) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
    const scripts = {};
    ((lin && lin.scripts) || []).forEach(s => { scripts[s.path] = s; });
    const rows = [];
    const byPath = {};
    jobs.forEach(function (j) {
      (j.steps || []).forEach(function (st) {
        if (!st.script || HELPER.test(st.script)) return;
        let row = byPath[st.script];
        if (!row) {
          row = byPath[st.script] = { path: st.script, name: baseName(st.script), stepNames: [], runs: [] };
          rows.push(row);
        }
        if (st.name && !row.stepNames.includes(st.name)) row.stepNames.push(st.name);
        let run = row.runs.find(r => r.job === j.id);
        if (!run) {
          run = { job: j.id, schedule: j.schedule_kst || '', key: null };
          row.runs.push(run);
        }
        if (!run.key && st.status_key) run.key = st.status_key;
      });
    });
    return rows.map(function (r) {
      const s = scripts[r.path] || {};
      const desc = s.desc ? String(s.desc) : [r.stepNames.join(' · '), s.note || ''].filter(Boolean).join('. ');
      return { path: r.path, name: r.name, desc: desc, runs: r.runs };
    });
  }

  const RESULT = { ok: '', skip: ' (건너뜀)', fail: ' (실패)' };

  /**
   * 마지막 업데이트 칸 한 줄입니다. 실행 기록을 따로 남기지 않는 단계와 실행 기록을
   * 못 받았을 때는 '-' 입니다(표 아래 안내문이 뜻을 적어 둡니다).
   */
  function runText(run, details) {
    if (!run.key || !details) return `${run.schedule}: -`;
    const rec = details[run.key];
    if (!rec) return `${run.schedule}: 아직 기록 없음`;
    const st = rec.status === null || rec.status === undefined ? '' : String(rec.status);
    const mark = Object.prototype.hasOwnProperty.call(RESULT, st) ? RESULT[st] : ` (${st})`;
    return `${run.schedule}: ${rec.last_run_at || '-'}${mark}`;
  }

  /** 표 몸통(tbody 안) HTML 입니다. */
  function scheduleHtml(rows, details) {
    return rows.map(function (r) {
      const sched = r.runs.map(x => esc(x.schedule)).join('<br>');
      const upd = r.runs.map(function (x) {
        const t = runText(x, details);
        const fail = details && x.key && details[x.key] && details[x.key].status === 'fail';
        const note = details && x.key && details[x.key] && details[x.key].note;
        return `<span class="dbx-run${fail ? ' fail' : ''}"${note ? ` title="${esc(note)}"` : ''}>${esc(t)}</span>`;
      }).join('<br>');
      return '<tr>'
        + `<td class="dbx-cron-mods">${esc(r.name)}<span class="sub">${esc(r.path)}</span></td>`
        + `<td class="dbx-cron-desc">${esc(r.desc)}</td>`
        + `<td class="dbx-cron-kst">${sched}</td>`
        + `<td class="dbx-cron-upd">${upd}</td>`
        + '</tr>';
    }).join('');
  }

  /** 카드 제목 옆 요약입니다. 예: '총 20개 스크립트 · 작업 4개' */
  function scheduleSummary(rows, lin) {
    return `총 ${rows.length}개 스크립트 · 작업 ${((lin && lin.jobs) || []).length}개`;
  }

  // ===== 화면(브라우저에서만) =====

  /**
   * 표를 채웁니다. opts = { tbody, summary, lineage: Promise<{ok,data|error}>, jobs: Promise<{ok,data|error}> }
   * 계보 파일을 못 받으면 표 자리에 이유를 보이고, 실행 기록만 못 받으면 마지막 업데이트를 '-' 로 둡니다.
   */
  async function mount(opts) {
    const tbody = opts.tbody;
    try {
      const res = await Promise.all([opts.lineage, opts.jobs]);
      const lin = res[0];
      if (!lin || !lin.ok) {
        tbody.innerHTML = `<tr><td colspan="4" class="dbx-cron-error">수집 일정을 불러오지 못했습니다 (${esc((lin && lin.error) || '빈 응답')}).</td></tr>`;
        return;
      }
      const js = res[1];
      const det = js && js.ok && js.data && js.data.details && typeof js.data.details === 'object' ? js.data.details : null;
      const rows = scheduleRows(lin.data);
      tbody.innerHTML = scheduleHtml(rows, det);
      if (opts.summary) opts.summary.textContent = scheduleSummary(rows, lin.data);
    } catch (e) {
      console.error(e);
      tbody.innerHTML = `<tr><td colspan="4" class="dbx-cron-error">수집 일정을 불러오지 못했습니다 (${esc(String((e && e.message) || e))}).</td></tr>`;
    }
  }

  const api = { HELPER, JOB_ORDER, scheduleRows, runText, scheduleHtml, scheduleSummary, mount };
  L.schedule = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 3: 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 177개 통과(171 + 6), 실패 0. BOM 0.

- [ ] **Step 4: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/lineage/schedule.js
git diff --cached --name-status
git commit -m "feat(explorer): 수집 일정 표를 계보 파일로 만드는 모듈

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/lineage/schedule.js
```

---

### Task 2: 페이지에 붙이기와 두 탭 잇기

**Files:**
- Modify: `dashboard_js/js/lineage/view.js`, `dashboard_js/css/lineage.css`, `dashboard_js/pages/database-explorer.html`
- Test (저장소 밖): `tests/lineage.view.test.js`(고침·더함), `tests/lineage.html.test.js`(고침·더함)

**Interfaces:**
- Consumes: Task 1 `Lineage.schedule.mount`. 기존 `Lineage.view`(load·render·applyFocus·bind·open·detailHtml), 페이지 인라인 `switchTab`·`selectTable(name)`·`state.table`·`API.getJobsStatus()`.
- Produces: `Lineage.view.loadLineage()` → 계보 파일 Promise(한 번만 받음), `Lineage.view.open(selectId?)`, 창 이벤트 `lineage:show-table`(`detail.name`), 페이지 id `dbx-cron-body`·`dbx-cron-summary`·`btn-lineage`.

- [ ] **Step 1: 시험 먼저 고치고 더하기**

(1) `tests/lineage.view.test.js`
- 상세 카드 글자 시험의 머리 부분이 바뀝니다: `games 받아 온 표 닫기` → `games 받아 온 표 데이터 보기 닫기`, `teams 손 작업 표 닫기` → `teams 손 작업 표 데이터 보기 닫기`. 그 두 기대 정규식만 고칩니다.
- 시험 하나를 더합니다.

```js
test('detailHtml: 표 카드에만 데이터 보기 버튼(표 이름 이스케이프)', () => {
  const g = M.buildGraph(lin, {});
  const ctx = { graph: g, status: V.statusMap(lin, det, NOW), rows: rows };
  assert.match(V.detailHtml(g.nodes['table:games'], lin, ctx), /<button type="button" class="lin-close" data-show-table="games">데이터 보기<\/button><button type="button" class="lin-close" data-close="1">닫기<\/button>/);
  for (const id of ['job:daily', 'source:kbo_record', 'page:pages/team-stats.html']) {
    assert.ok(!V.detailHtml(g.nodes[id], lin, ctx).includes('data-show-table'), id);
  }
  const evil = { id: 'table:x', kind: 'collected', label: 'x', ref: { name: 'a"b<c', kind: 'collected', desc: '', written_by: [], routes: [], pages: [] } };
  assert.match(V.detailHtml(evil, lin, ctx), /data-show-table="a&quot;b&lt;c"/);
});
```

(2) `tests/lineage.html.test.js`
- 스크립트 목록 기대값 끝에 `'../js/lineage/schedule.js'` 를 더합니다(view.js 다음).
- switchTab 시험의 두 정규식을 바꿉니다: `if (tab === 'lineage' && window.Lineage && window.Lineage.view) window.Lineage.view.open(opts && opts.select);` 를 찾고, `function switchTab(tab, opts)` 도 찾습니다.
- 시험 하나를 더합니다.

```js
test('database-explorer.html: 수집 일정 표는 계보로 만들고, 두 탭을 잇는 버튼과 이벤트', () => {
  assert.match(html, /<tbody id="dbx-cron-body">/);
  assert.ok(!html.includes('data-job='), '손으로 적은 수집 일정 줄이 남아 있습니다');
  assert.ok(!html.includes('function loadCronStatus'));
  assert.match(html, /Lineage\.schedule\.mount\(\{/);
  assert.match(html, /lineage: Lineage\.view\.loadLineage\(\)/);
  assert.match(html, /id="dbx-cron-summary"/);
  assert.match(html, /id="btn-lineage"[^>]*>계보에서 보기<\/button>/);
  assert.match(html, /switchTab\('lineage', \{ select: 'table:' \+ state\.table \}\)/);
  assert.match(html, /window\.addEventListener\('lineage:show-table'/);
});
```

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/lineage.view.test.js" "C:/tmp/bstats-team-stats-check/tests/lineage.html.test.js"` → 고친·더한 시험이 실패해야 합니다.

- [ ] **Step 2: view.js 고치기**

(1) `async function load()` 바로 앞에 넣습니다.

```js
  let linOnce = null;
  /**
   * 계보 파일을 한 번만 받습니다. 데이터 탐색 탭의 수집 일정 표(schedule.js)도 이것을 씁니다.
   * 반환 Promise<{ ok, data } | { ok: false, error }>
   */
  function loadLineage() {
    if (!linOnce) linOnce = root.TeamStats.data.getJson('../data/table_lineage.json', 'tables');
    return linOnce;
  }
```

그리고 `load()` 안의 `D.getJson('../data/table_lineage.json', 'tables'),` 를 `loadLineage(),` 로 바꿉니다.

(2) `detailHtml` 의 마지막 `return` 을 바꿉니다.

```js
    const dataBtn = node.kind === 'collected' || node.kind === 'derived' || node.kind === 'manual'
      ? `<button type="button" class="lin-close" data-show-table="${esc(node.ref.name)}">데이터 보기</button>`
      : '';
    return `<div class="card-header"><h3 class="card-title">${title}</h3>`
      + `<span class="lin-actions">${dataBtn}<button type="button" class="lin-close" data-close="1">닫기</button></span></div>`
      + `<div class="card-body">${body}</div>`;
```

(3) `bind()` 의 클릭 처리에서 `if (e.target.closest('[data-close]')) {` 바로 앞에 넣습니다.

```js
      // 표 상세 카드의 '데이터 보기': 페이지(database-explorer.html)가 받아 데이터 탐색 탭에서 그 표를 엽니다.
      const show = e.target.closest('[data-show-table]');
      if (show) {
        root.dispatchEvent(new CustomEvent('lineage:show-table', { detail: { name: show.getAttribute('data-show-table') } }));
        return;
      }
```

(4) `open()` 을 아래로 바꾸고, 그 바로 앞에 `select` 를 넣습니다.

```js
  /** 다른 탭에서 넘어올 때 표 하나를 고른 채 엽니다. 손 작업 표면 묶음을 펼칩니다. */
  function select(id) {
    const t = (S.lin.tables || []).find(x => 'table:' + x.name === id);
    if (!t || t.kind === 'meta') return;
    if (t.kind === 'manual') S.manualOpen = true;
    S.filter = null;
    S.sel = id;
    render();
    const box = document.querySelector(`#lin-graph .lin-box[data-id="${root.CSS && root.CSS.escape ? root.CSS.escape(id) : id}"]`);
    if (box) box.scrollIntoView({ block: 'center', inline: 'center' });
  }

  /**
   * 탭을 열 때 부릅니다(database-explorer.html 의 switchTab). 처음이면 데이터를 받아
   * 그립니다. selectId('table:<이름>')를 주면 그 표를 고른 채 엽니다. 그 밖에 다시 열면
   * 그사이 폭이 바뀌었을 때만 다시 그립니다.
   */
  function open(selectId) {
    const first = !S.loading;
    if (first) {
      bind();
      $('lin-graph').innerHTML = typeof root.createLoadingSpinner === 'function' ? root.createLoadingSpinner() : '';
      S.loading = load().then(render).catch(function (e) {
        console.error(e);
        S.linError = String((e && e.message) || e);
        render();
      });
    }
    return S.loading.then(function () {
      if (selectId && S.lin) {
        select(selectId);
        return;
      }
      const box = $('lin-graph');
      if (!first && S.lin && box && box.clientWidth !== S.width) render();
    });
  }
```

(5) `const api = { … }` 에 `loadLineage` 를 더합니다(`open` 앞).

- [ ] **Step 3: lineage.css 끝에 붙이기**

```css

/* 상세 카드 제목 줄 버튼 묶음(데이터 보기·닫기) */
.lin-actions { display: flex; align-items: center; gap: 0.4rem; }

/* 데이터 탐색 탭의 수집 일정 표(schedule.js): 실패한 실행, 불러오기 실패 줄 */
.dbx-run.fail { color: var(--danger); }
.dbx-cron-error { color: var(--text-secondary); padding: 0.8rem; }
```

- [ ] **Step 4: database-explorer.html 고치기**

(1) 수집 일정 표 몸통: `<table class="dbx-cron-table">` 안의 `<tbody>` 부터 그 `</tbody>` 까지(손으로 적은 14줄, 지금 약 533~675행)를 아래 한 덩어리로 바꿉니다. 줄이 길어 손으로 고치기 어렵다면 `C:/tmp/bstats-team-stats-check/` 에 작은 Node 스크립트(첫 `<table class="dbx-cron-table">` 뒤 첫 `<tbody>`~짝 `</tbody>` 를 찾아 바꿈, CRLF 유지)를 만들어 바꿉니다.

```html
                            <tbody id="dbx-cron-body">
                                <tr><td colspan="4" class="text-muted">불러오는 중…</td></tr>
                            </tbody>
```

(2) 카드 제목 옆 요약: `<span class="text-muted" style="font-size: 0.875rem;">총 14개 작업</span>` → `<span class="text-muted" id="dbx-cron-summary" style="font-size: 0.875rem;"></span>`

(3) 첫 안내 문단(`GitHub Actions에서 자동 실행되는 수집·집계 모듈입니다.` 로 시작) 끝 `늦을 수 있습니다.` 뒤에 한 문장을 더합니다: ` 이 표는 계보 파일(테이블 계보 탭과 같은 자료)로 만듭니다.`

(4) 표 아래 안내문 끝 `서버 자동 배포(auto_deploy)는 Pages·Workers 배포로 대체되어 없어졌습니다.` 뒤에 더합니다: ` 마지막 업데이트가 '-'인 단계는 실행 기록을 따로 남기지 않습니다. 같은 작업의 다른 단계 기록을 보면 됩니다.`

(5) 표 상세 머리: `<span id="detail-summary" class="text-muted" style="font-size: 0.875rem;"></span>` 바로 다음 줄에 넣습니다.

```html
                    <button type="button" class="dbx-btn ghost" id="btn-lineage">계보에서 보기</button>
```

(6) 스크립트: `    <script src="../js/lineage/view.js"></script>` 다음 줄에 `    <script src="../js/lineage/schedule.js"></script>`

(7) 인라인 스크립트의 `// 자동 수집 스케줄: 작업별 '마지막 업데이트 시간' 채우기` 주석부터 `async function loadCronStatus() { … }` 함수 끝까지 지웁니다(이제 쓰지 않음).

(8) `switchTab`: `function switchTab(tab) {` → `function switchTab(tab, opts) {`, 그리고 `window.Lineage.view.open();` → `window.Lineage.view.open(opts && opts.select);`

(9) `document.querySelectorAll('.atab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.tab)));` 줄 바로 뒤에 넣습니다.

```js

        // 두 탭 잇기: 데이터 탐색의 표 상세 → 계보(그 표를 고른 채), 계보 상세 카드의 '데이터 보기' → 데이터 탐색
        document.getElementById('btn-lineage').addEventListener('click', () => {
            if (state.table) switchTab('lineage', { select: 'table:' + state.table });
        });
        window.addEventListener('lineage:show-table', e => {
            if (!e.detail || !e.detail.name) return;
            switchTab('explorer');
            selectTable(e.detail.name);
            document.getElementById('table-detail').scrollIntoView({ block: 'start' });
        });
```

(10) 맨 아래 초기화의 `loadCronStatus();` 를 아래로 바꿉니다.

```js
        // 자동 수집 스케줄: 계보 파일(작업·단계·스크립트)과 실행 기록으로 만듭니다(js/lineage/schedule.js).
        Lineage.schedule.mount({
            tbody: document.getElementById('dbx-cron-body'),
            summary: document.getElementById('dbx-cron-summary'),
            lineage: Lineage.view.loadLineage(),
            jobs: API.getJobsStatus().then(d => ({ ok: true, data: d }), e => ({ ok: false, error: String((e && e.message) || e) })),
        });
```

- [ ] **Step 5: 시험 통과 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 179개 통과(177 + view 1 + html 1), 실패 0. 고친 파일 BOM 0.

- [ ] **Step 6: 캡처로 확인**

```bash
cd C:/tmp/bstats-team-stats-check
MSYS_NO_PATHCONV=1 node lineage_shot.mjs sched "/pages/database-explorer.html"
MSYS_NO_PATHCONV=1 node lineage_shot.mjs to_lineage "/pages/database-explorer.html" --click '.dbx-table-card[data-table="games"]' --click '#btn-lineage'
MSYS_NO_PATHCONV=1 node lineage_shot.mjs to_lineage_manual "/pages/database-explorer.html" --click '.dbx-table-card[data-table="teams"]' --click '#btn-lineage'
MSYS_NO_PATHCONV=1 node lineage_shot.mjs to_data "/pages/database-explorer.html#lineage" --click '.lin-box[data-id="table:games"]' --click '[data-show-table="games"]'
MSYS_NO_PATHCONV=1 node lineage_shot.mjs sched_mobile "/pages/database-explorer.html" --mobile
```

| 캡처 | 맞아야 하는 것 |
|---|---|
| sched | 수집 일정 표가 스크립트 줄(운영 데이터 기준 약 21줄)로 채워짐, 제목 옆 "총 N개 스크립트 · 작업 4개", roster_to_d1.py 줄에 실행 시각 두 줄·마지막 업데이트 두 줄, 실패 줄 빨간 글자, 안내문 두 문장 더해짐, 데이터 현황·테이블 목록은 그대로 |
| to_lineage | 출력 `on` 14 이상·`detail` 이 "games 받아 온 표 데이터 보기 닫기" 로 시작, 계보 탭이 켜짐 |
| to_lineage_manual | 출력 `boxes` 45(손 작업 표 펼침), `detail` 이 "teams" 로 시작 |
| to_data | 데이터 탐색 탭이 켜지고 표 상세 제목이 games, 컬럼 구조·데이터가 보임(PNG 로 확인) |
| sched_mobile | 출력 `doc` ≤ 390, 표가 카드 안에서만 가로로 밀림 |

PNG 는 Read 로 열어 봅니다. 맞지 않으면 Task 2 파일 안에서 고치고 시험·캡처를 다시 합니다.

- [ ] **Step 7: 계보 다시 만들기와 저장소 시험**

```bash
cd C:/Users/김승곤/Desktop/b_project
PYTHONUTF8=1 py scripts/build_lineage.py
PYTHONUTF8=1 py -m pytest tests -q 2>&1 | tail -3
git add dashboard_js/data/table_lineage.json
git status --short dashboard_js/data/table_lineage.json
```

pytest 는 모두 통과해야 합니다(실패하면 이름·메시지를 보고하고 고치지 않음). 마지막 줄이 비면 계보 내용이 그대로입니다. `M` 이 남으면 내용이 바뀐 것이니 `git diff --cached` 로 바뀐 곳을 보고서에 적고 Task 2 커밋에 함께 넣습니다.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/lineage/view.js dashboard_js/css/lineage.css dashboard_js/pages/database-explorer.html
git diff --cached --name-status
git commit -m "feat(explorer): 수집 일정 표를 계보로 자동 생성, 데이터 탐색과 계보 탭을 버튼으로 잇기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- dashboard_js/js/lineage/view.js dashboard_js/css/lineage.css dashboard_js/pages/database-explorer.html
```

(Step 7 에서 계보 JSON 이 바뀌었으면 위 두 명령에 `dashboard_js/data/table_lineage.json` 을 더합니다.)
