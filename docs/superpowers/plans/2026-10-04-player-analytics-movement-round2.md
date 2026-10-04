# 선수 분석 무브먼트 2차 변경 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 제목 아이콘 빼기, 무브먼트 설명을 `?` 툴팁으로, 고리 눈금 15cm 단위, 투수 프로필 아래 시즌 타일을 Savant 식 구종 구사율로 바꾸기.

**Architecture:** 순수 함수는 `js/player-analytics/movement.js` 에 덧붙입니다(`usageHtml`). 페이지는 마크업·툴팁·구사율 자리 바꾸기·불러오기만 합니다. 데이터는 기존 `/players/{id}/usage?season=`.

**Tech Stack:** 순수 HTML/CSS/JS, Node `node:test`(저장소 밖), 헤드리스 Edge(CDP).

설계: `docs/superpowers/specs/2026-10-04-player-analytics-movement-card-design.md` §7

## Global Constraints

- 저장소 `C:/Users/김승곤/Desktop/b_project`, 브랜치 `main`. 화면 세션(계보 탭)이 같은 폴더에서 `dashboard_js/js/lineage/*` 를 고치는 중입니다. `git add -A`·`git add .`·stash·reset·restore·checkout·브랜치 변경 금지. 커밋은 자기 파일만 경로를 붙여서. 메시지 끝에 빈 줄 + `Co-Authored-By: <모델 이름> <noreply@anthropic.com>`. push·배포 금지.
- 남의 파일(`dashboard_js/js/lineage/*`, `dashboard_js/css/lineage.css`, `dashboard_js/pages/database-explorer.html`, `dashboard_js/data/table_lineage.json`)은 건드리지 않습니다.
- 공용 `js/stats/*`, `css/stats.css`, `css/style.css` 는 고치지 않습니다. `js/api.js` 는 덧붙이기만(인자 없는 호출은 이전과 같은 주소).
- 미리보기 서버는 꺼져 있을 수 있습니다. 꺼져 있으면(`curl http://127.0.0.2:8765/` 실패) `py C:/tmp/bstats-team-stats-check/preview.py` 를 **백그라운드로** 한 번만 띄우고, 다 쓴 뒤 보고서에 "띄워 둠"이라고 적습니다. 이미 떠 있으면 새로 띄우지 않습니다.
- 시험: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"` (지금 27개 통과).
- 캡처: `node C:/tmp/bstats-player-analytics-check/cdp_shot.mjs <이름> "<경로?쿼리>" [desktop|mobile] [dark|light]` → `C:/tmp/bstats-player-analytics-check/shots/<이름>.png`. 폭은 환경변수 `W`.
- 사용자 노출 한국어는 습니다체, 이모지 없음.

---

### Task 1: 순수 함수(눈금·본문·구사율)

**Files:**
- Modify: `dashboard_js/js/player-analytics/movement.js`
- Modify: `C:/tmp/bstats-player-analytics-check/tests/movement.test.js`

**Interfaces:**
- Produces: `PlayerAnalytics.movement.usageHtml(data, season) → string` (data = usage API 응답 `{usage:[{pitch_type, count, usage_all, usage_l, usage_r}]}`), `HELP` 상수(툴팁 글자). `bodyHtml(pitches, total)` 은 추적 비율 줄 하나만 남깁니다.

- [ ] **Step 1: 시험 고치기·더하기(실패하게)**

`movement.test.js` 에서:

(a) `bodyHtml` 시험의 기대값을 바꿉니다. 첫 안내 줄과 보조 줄은 더 이상 나오지 않습니다:

```js
  assert.ok(!html.includes('포수 시점'));
  assert.ok(!html.includes('pa-mv-note--sub'));
  assert.ok(html.includes('<p class="pa-mv-note">공 4개 추적</p>'));
```

그리고 total 을 준 경우 기대값은 `<p class="pa-mv-note">공 4개 추적 (정규시즌 8구 대비 50%)</p>` 처럼 **그 한 줄**만 확인하고, `pa-mv-note--sub` 가 없음을 확인합니다. (기존 1,903/3,207·100% 상한 시험은 같은 방식으로 한 줄만 보도록 고칩니다.)

(b) `svgHtml` 시험에 눈금 넷을 더합니다:

```js
  for (const cm of [15, 30, 45, 60]) assert.ok(svg.includes('>' + cm + '</text>'), cm + 'cm 눈금');
  assert.equal((svg.match(/class="pa-mv-tick"/g) || []).length, 4);
```

(c) 새 시험을 파일 끝에 더합니다:

```js
const U = { usage: [
  { pitch_type: '슬라이더', count: 767, usage_all: 30, usage_l: 40.9, usage_r: 19.9 },
  { pitch_type: '직구', count: 1207, usage_all: 47.2, usage_l: 50.1, usage_r: 44.5 },
  { pitch_type: '<b>', count: 1, usage_all: 0.1, usage_l: 0, usage_r: 0.2 },
] };

test('usageHtml: 제목·머리·줄(전체 비율 큰 순)·막대 색·이스케이프', () => {
  const html = M.usageHtml(U, 2026);
  assert.ok(html.startsWith('<div class="pa-usage-title">2026 구종 구사율</div>'));
  assert.ok(html.includes('<div class="pa-usage-head"><span>좌타 상대</span><span></span><span>구종 (전체)</span><span></span><span>우타 상대</span></div>'));
  const rows = html.match(/<div class="pa-usage-row">/g) || [];
  assert.equal(rows.length, 3);
  assert.ok(html.indexOf('직구') < html.indexOf('슬라이더'), '전체 비율 큰 순');
  assert.ok(html.includes('<span class="pa-usage-pct">50.1%</span><span class="pa-usage-bar pa-usage-bar--l"><i style="width:50.1%;background:#D22D49"></i></span><span class="pa-usage-name">직구 <b>47.2%</b></span><span class="pa-usage-bar"><i style="width:44.5%;background:#D22D49"></i></span><span class="pa-usage-pct">44.5%</span>'));
  assert.ok(html.includes('&lt;b&gt;') && !html.includes('<span class="pa-usage-name"><b>'));
});

test('usageHtml: 빈 데이터 문구', () => {
  assert.equal(M.usageHtml({ usage: [] }, 2019), '<div class="pa-usage-title">2019 구종 구사율</div><p class="pa-mv-empty">이 시즌은 구종 구사율 데이터가 없습니다.</p>');
  assert.equal(M.usageHtml(null, 2019), '<div class="pa-usage-title">2019 구종 구사율</div><p class="pa-mv-empty">이 시즌은 구종 구사율 데이터가 없습니다.</p>');
});

test('HELP: 툴팁 글자', () => {
  assert.equal(M.HELP, '포수 시점입니다. 수평 +는 1루 쪽, 수직 +는 위입니다.\n추적 수는 문자중계 기준이라 공식 투구 수와 조금 다를 수 있습니다.');
});
```

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/movement.test.js"` → 고친·새 시험 FAIL.

- [ ] **Step 2: 눈금 넷**

`svgHtml` 의 `[30, 60].forEach(function (cm) {` 를 `RINGS.forEach(function (cm) {` 로 바꿉니다(눈금 글자 위치 식은 그대로).

- [ ] **Step 3: 본문은 추적 비율 한 줄만**

`bodyHtml` 에서 `'<p class="pa-mv-note">포수 시점 · 수평 +는 1루 쪽 · 수직 +는 위</p>'` 와 보조 줄(`pa-mv-note--sub`) 을 지웁니다. 추적 비율 줄은 그대로 둡니다. 함수 위 주석에 "설명은 카드 제목 옆 툴팁(HELP)에 있습니다"를 적습니다.

- [ ] **Step 4: HELP·usageHtml 더하기**

`bodyHtml` 다음에 넣습니다:

```js
  /** 카드 제목 옆 `?` 툴팁 글자입니다(그림 아래 설명을 옮김). */
  const HELP = '포수 시점입니다. 수평 +는 1루 쪽, 수직 +는 위입니다.\n'
    + '추적 수는 문자중계 기준이라 공식 투구 수와 조금 다를 수 있습니다.';

  function pct1(v) {
    const n = num(v);
    return n === null ? 0 : Math.max(0, Math.min(100, n));
  }

  /**
   * 구종 구사율(Savant Pitch Usage 참고)입니다.
   * 좌타 상대 % · 왼쪽 막대 · 구종(전체 %) · 오른쪽 막대 · 우타 상대 %. 전체 비율 큰 순.
   * data 는 /players/{id}/usage 응답입니다.
   */
  function usageHtml(data, season) {
    const title = '<div class="pa-usage-title">' + esc(season) + ' 구종 구사율</div>';
    const rows = ((data && data.usage) || []).slice().sort(function (a, b) { return pct1(b.usage_all) - pct1(a.usage_all); });
    if (!rows.length) return title + '<p class="pa-mv-empty">이 시즌은 구종 구사율 데이터가 없습니다.</p>';
    return title + '<div class="pa-usage-grid">'
      + '<div class="pa-usage-head"><span>좌타 상대</span><span></span><span>구종 (전체)</span><span></span><span>우타 상대</span></div>'
      + rows.map(function (u) {
        const c = colorOf(u.pitch_type), l = pct1(u.usage_l), r = pct1(u.usage_r);
        return '<div class="pa-usage-row">'
          + '<span class="pa-usage-pct">' + f1(l) + '%</span>'
          + '<span class="pa-usage-bar pa-usage-bar--l"><i style="width:' + f1(l) + '%;background:' + c + '"></i></span>'
          + '<span class="pa-usage-name">' + esc(u.pitch_type) + ' <b>' + f1(pct1(u.usage_all)) + '%</b></span>'
          + '<span class="pa-usage-bar"><i style="width:' + f1(r) + '%;background:' + c + '"></i></span>'
          + '<span class="pa-usage-pct">' + f1(r) + '%</span>'
          + '</div>';
      }).join('')
      + '</div>';
  }
```

`const api = { … }` 에 `HELP, usageHtml` 을 더합니다.

- [ ] **Step 5: 통과 확인** — `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"` 모두 PASS(30개 안팎).

- [ ] **Step 6: 커밋** — `git commit -m "feat(player-analytics): 무브먼트 눈금 15cm·설명 툴팁 글자·구종 구사율 순수 함수" -- dashboard_js/js/player-analytics/movement.js`

---

### Task 2: 화면 연결

**Files:**
- Modify: `dashboard_js/pages/player-analytics.html`, `dashboard_js/css/player-analytics.css`, `dashboard_js/js/api.js`
- Modify: `C:/tmp/bstats-player-analytics-check/tests/page-html.test.js`

**Interfaces:**
- Consumes: `PlayerAnalytics.movement.{usageHtml, HELP, bodyHtml}`, `API.getPitchUsage(playerId, season)`.

- [ ] **Step 1: 구조 시험 더하기(실패하게)** — `page-html.test.js` 끝에:

```js
test('2차: 제목 아이콘 없음, 툴팁 버튼, 구사율 연결', () => {
  assert.ok(html.includes('<h1 class="fade-in">선수 분석</h1>'));
  assert.ok(!html.includes('person_search'));
  assert.match(html, /<button type="button" class="pa-help" id="pa-move-help" aria-label="무브먼트 설명">\?<\/button>/);
  for (const used of ['API.getPitchUsage(playerId, season)', 'M.usageHtml(', 'M.HELP', "id = 'pa-usage'"]) {
    assert.ok(html.includes(used), used);
  }
});
```

Run → FAIL.

- [ ] **Step 2: api.js** — `getPitchUsage` 를 `getPitchArsenal` 과 같은 방식으로 바꿉니다:

```js
    /**
     * Get Pitch Usage (By Stands)
     * season 을 주면 그 시즌, 안 주면 서버 기본(올해)입니다.
     */
    static async getPitchUsage(playerId, season) {
        try {
            const q = season ? `?season=${encodeURIComponent(season)}` : '';
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/usage${q}`);
```

(그 아래는 그대로.)

- [ ] **Step 3: 제목 아이콘 빼기** — `<h1 class="fade-in"><span class="material-symbols-outlined">person_search</span> 선수 분석</h1>` → `<h1 class="fade-in">선수 분석</h1>`.

- [ ] **Step 4: 툴팁 버튼** — 무브먼트 카드 제목줄의 `<span class="pa-card-tab">무브먼트 (Induced Break)</span>` 를 아래로 바꿉니다(select 는 그대로 그 다음):

```html
                        <span class="pa-card-tabs-left">
                            <span class="pa-card-tab">무브먼트 (Induced Break)</span>
                            <button type="button" class="pa-help" id="pa-move-help" aria-label="무브먼트 설명">?</button>
                        </span>
```

`setupMovementCard` 첫 줄 `const M = …` 다음에 넣습니다(글자는 모듈 한 곳에서 관리):

```js
            const help = document.getElementById('pa-move-help');
            if (help) { help.dataset.tip = M.HELP; help.title = M.HELP; }
```

- [ ] **Step 5: 구사율 자리와 불러오기**

`setupMovementCard` 에서 `if (!seasons.length) { hideMovementCard(); return; }` 바로 다음에 넣습니다(투수면 시즌 타일 자리를 구사율 자리로 바꿈):

```js
            // 투수는 시즌 타일 대신 구종 구사율을 둡니다(연도는 무브먼트와 같이 바뀜).
            const profile = document.getElementById('player-card');
            const holder = document.createElement('div');
            holder.className = 'pa-usage';
            holder.id = 'pa-usage';
            const tiles = profile.querySelector('.pa-tiles');
            if (tiles) tiles.replaceWith(holder); else profile.appendChild(holder);
```

(위 `holder.id = 'pa-usage'` 줄은 구조 시험이 찾는 글자 `id = 'pa-usage'` 를 담습니다.)

`mvCache` 선언 아래에 `const usageCache = {};` 를 넣고, `loadMovement` 를 아래로 바꿉니다:

```js
        async function loadMovement(playerId, season, total) {
            const M = window.PlayerAnalytics.movement;
            const body = document.getElementById('pa-move-body');
            const usageBox = document.getElementById('pa-usage');
            const token = ++mvToken;
            const key = playerId + ':' + season;
            let pitches = mvCache[key];
            let usage = usageCache[key];
            if (!pitches || !usage) {
                body.innerHTML = createLoadingSpinner();
                if (usageBox) usageBox.innerHTML = createLoadingSpinner();
                const [a, u] = await Promise.all([
                    pitches ? null : API.getPitchArsenal(playerId, season),
                    usage ? null : API.getPitchUsage(playerId, season),
                ]);
                if (!pitches) { pitches = (a && a.arsenal) || []; if (pitches.length) mvCache[key] = pitches; }
                if (!usage) { usage = u || { usage: [] }; if ((usage.usage || []).length) usageCache[key] = usage; }
            }
            if (token !== mvToken) return;  // 그사이 다른 선수·시즌을 골랐습니다.
            body.innerHTML = M.bodyHtml(pitches, total);
            if (usageBox) usageBox.innerHTML = M.usageHtml(usage, season);
        }
```

- [ ] **Step 6: CSS** — `css/player-analytics.css` 끝에 넣습니다:

```css

/* ---------- 2차: 툴팁·구종 구사율 ---------- */
.pa-card-tabs-left { display: inline-flex; align-items: center; }
.pa-help { position: relative; margin-left: 0.35rem; width: 1.15rem; height: 1.15rem; padding: 0; border: 1px solid var(--border-color); border-radius: 50%; background: var(--bg-card); color: var(--text-secondary); font: inherit; font-size: 0.72rem; font-weight: 700; line-height: 1; cursor: help; }
.pa-help::after { content: attr(data-tip); position: absolute; top: calc(100% + 6px); left: 0; z-index: 20; width: 15rem; padding: 0.5rem 0.6rem; border-radius: 6px; background: var(--text-primary); color: var(--bg-card); font-size: 0.75rem; font-weight: 400; line-height: 1.45; text-align: left; white-space: pre-line; opacity: 0; visibility: hidden; pointer-events: none; transition: opacity 0.12s; }
.pa-help:hover::after, .pa-help:focus-visible::after { opacity: 1; visibility: visible; }
.pa-usage { margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid var(--border-color); }
.pa-usage-title { margin-bottom: 0.5rem; font-size: 0.8rem; font-weight: 700; color: var(--text-secondary); }
.pa-usage-head, .pa-usage-row { display: grid; grid-template-columns: 3rem minmax(0, 1fr) 6.5rem minmax(0, 1fr) 3rem; align-items: center; gap: 0.35rem; }
.pa-usage-head { margin-bottom: 0.25rem; font-size: 0.7rem; font-weight: 600; color: var(--text-muted); }
.pa-usage-head span:first-child { text-align: right; }
.pa-usage-head span:nth-child(3) { text-align: center; }
.pa-usage-row { padding: 0.2rem 0; font-size: 0.8rem; font-variant-numeric: tabular-nums; color: var(--text-primary); }
.pa-usage-pct:first-child { text-align: right; }
.pa-usage-name { text-align: center; white-space: nowrap; }
.pa-usage-name b { font-weight: 700; color: var(--text-secondary); font-size: 0.72rem; }
.pa-usage-bar { display: flex; height: 0.7rem; background: var(--bg-secondary); border-radius: 999px; overflow: hidden; }
.pa-usage-bar--l { justify-content: flex-end; }
.pa-usage-bar i { display: block; height: 100%; border-radius: 999px; }
```

- [ ] **Step 7: 설계 문서 확인** — §7 은 이미 적혀 있습니다(손대지 않음).

- [ ] **Step 8: 시험·계보** — `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"` 모두 PASS. 이어서:

```bash
cd "C:/Users/김승곤/Desktop/b_project"
PYTHONUTF8=1 py scripts/build_lineage.py
PYTHONUTF8=1 py -m pytest tests -q
git diff --stat -- dashboard_js/data/table_lineage.json
```

`table_lineage.json` 이 내용으로 바뀌면 커밋하지 않고 DONE_WITH_CONCERNS 로 보고(남의 파일). 줄 끝만 다르면 그대로 둡니다.

- [ ] **Step 9: 화면 확인** — 투수 `?id=65933` 데스크톱: 제목 아이콘 없음, 무브먼트 제목 옆 `?`(CDP 로 `#pa-move-help` 에 focus 를 주고 캡처해 툴팁이 카드 안에 보이는지), 고리 눈금 15·30·45·60, 그림 아래 추적 비율 한 줄, 프로필 아래 "2026 구종 구사율" 막대. 연도를 2019 로 바꾸면(CDP: select 값 바꾸고 change 이벤트) 구사율 제목도 2019 로 바뀜. 타자 `?id=76232`: 시즌 타일 그대로.

- [ ] **Step 10: 커밋** — `git commit -m "feat(player-analytics): 제목 아이콘 빼기·무브먼트 설명 툴팁·투수 구종 구사율" -- dashboard_js/pages/player-analytics.html dashboard_js/css/player-analytics.css dashboard_js/js/api.js`

---

### Task 3: 화면 확인(PNG)

**Files:** 고치는 파일 없음(문제가 나오면 Task 2 파일만 최소로 고치고 따로 커밋).

- [ ] 캡처해서 `C:/Users/김승곤/Desktop/pa8_<이름>.png` 로 복사하고 Read 로 봅니다: `pitcher`(1789 light), `pitcher_help`(툴팁 펼친 상태), `pitcher_2019`, `dark`, `mobile`, `w1100`(W=1100), `batter`.
- [ ] 확인: 세 카드 높이(1789)·구사율 막대 좌우 방향·색·글자 겹침 없음·휴대폰 가로 넘침 없음·툴팁이 카드에 잘리지 않음.
- [ ] 시험 다시 실행, `git log origin/main..main --oneline` 을 보고서에 적습니다.

---

### Task 2b: 포수·투수 시점 전환 (evan 요청, Task 2 뒤)

**Files:** `dashboard_js/js/player-analytics/movement.js`, `dashboard_js/pages/player-analytics.html`, `dashboard_js/css/player-analytics.css`, 시험 `movement.test.js`·`page-html.test.js`

- [ ] **Step 1: 시험 먼저(실패하게)** — `movement.test.js` 끝에:

```js
test('시점 전환: 투수 시점은 수평을 뒤집음, 툴팁 글자', () => {
  const s = M.summarize(P);
  assert.equal(M.HELP, M.helpFor('catcher'));
  assert.equal(M.helpFor('pitcher'), '투수 시점입니다. 수평 +는 3루 쪽, 수직 +는 위입니다.\n추적 수는 문자중계 기준이라 공식 투구 수와 조금 다를 수 있습니다.');
  assert.ok(M.svgHtml(P, s, 'pitcher').includes('cx="123.8" cy="123.8"'), '직구 첫 공이 왼쪽으로');
  assert.ok(M.svgHtml(P, s).includes('cx="276.2" cy="123.8"'), '기본은 포수 시점');
  const lp = M.legendHtml(s, 'pitcher');
  assert.ok(lp.includes('직구</td><td>50.0%</td><td>142.0</td><td>25.4</td><td>-12.7</td>'));
  assert.ok(lp.includes('커브</td><td>25.0%</td><td>-</td><td>-12.7</td><td>12.7</td>'));
  assert.ok(M.svgHtml(P, s, 'pitcher').includes('수평 -12.7cm'));
  assert.equal(M.bodyHtml(P, 8), M.bodyHtml(P, 8, 'catcher'));
  assert.notEqual(M.bodyHtml(P, 8, 'pitcher'), M.bodyHtml(P, 8, 'catcher'));
});
```

`page-html.test.js` 의 2차 시험에서 `'M.HELP'` 를 `'M.helpFor('` 로 바꾸고, 시험을 더합니다:

```js
test('시점 전환 단추', () => {
  assert.match(html, /<div class="pa-mv-view" role="group" aria-label="무브먼트 시점">/);
  assert.match(html, /<button type="button" class="pa-mv-view-btn active" data-view="catcher" aria-pressed="true">포수 시점<\/button>/);
  assert.match(html, /<button type="button" class="pa-mv-view-btn" data-view="pitcher" aria-pressed="false">투수 시점<\/button>/);
  for (const used of ["let mvView = 'catcher'", 'M.bodyHtml(pitches, total, mvView)', 'mvLast']) assert.ok(html.includes(used), used);
});
```

- [ ] **Step 2: movement.js**

`HELP` 정의를 아래로 바꿉니다(HELP 는 포수 시점 글자 그대로):

```js
  /** 시점별 툴팁 글자입니다. view: 'catcher'(기본) | 'pitcher' */
  function helpFor(view) {
    return (view === 'pitcher'
      ? '투수 시점입니다. 수평 +는 3루 쪽, 수직 +는 위입니다.\n'
      : '포수 시점입니다. 수평 +는 1루 쪽, 수직 +는 위입니다.\n')
      + '추적 수는 문자중계 기준이라 공식 투구 수와 조금 다를 수 있습니다.';
  }
  const HELP = helpFor('catcher');

  /** 투수 시점이면 수평을 뒤집습니다(포수 시점 기준 값에 곱함). */
  function flipOf(view) { return view === 'pitcher' ? -1 : 1; }
```

(HELP 와 flipOf 는 svgHtml 보다 **위**에 둡니다.) `svgHtml(pitches, summary, view)`·`legendHtml(summary, view)`·`bodyHtml(pitches, total, view)` 에 view 인자를 더하고, 수평 값(점 cx, 평균 원 cx, title 의 `수평`, 표의 수평 칸)에 `flipOf(view)` 를 곱합니다. 수직은 그대로입니다. `bodyHtml` 은 view 를 svgHtml·legendHtml 에 넘깁니다. `api` 에 `helpFor` 를 더합니다.

- [ ] **Step 3: 페이지** — 무브먼트 카드에서 `<div class="pa-card-body" id="pa-move-body"></div>` 바로 앞에:

```html
                    <div class="pa-mv-view" role="group" aria-label="무브먼트 시점">
                        <button type="button" class="pa-mv-view-btn active" data-view="catcher" aria-pressed="true">포수 시점</button>
                        <button type="button" class="pa-mv-view-btn" data-view="pitcher" aria-pressed="false">투수 시점</button>
                    </div>
```

스크립트: `mvCache` 선언 근처에 `let mvView = 'catcher';` 와 `let mvLast = null;  // 마지막으로 그린 {pitches, total}(시점만 바꿀 때 다시 부르지 않음)`. `loadMovement` 의 그리기 줄을 `mvLast = { pitches, total };` 다음 `body.innerHTML = M.bodyHtml(pitches, total, mvView);` 로 바꿉니다. `hideMovementCard` 에서 `mvLast = null;`. `setupMovementCard` 의 툴팁 줄을 `help.dataset.tip = M.helpFor(mvView); help.title = help.dataset.tip;` 로 바꿉니다. 단추 처리(한 번만 등록, 스크립트 아래쪽 popstate 처리 근처):

```js
        // 무브먼트 포수·투수 시점 전환입니다. 데이터는 다시 부르지 않고 다시 그립니다.
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.pa-mv-view-btn');
            if (!btn || btn.dataset.view === mvView) return;
            const M = window.PlayerAnalytics.movement;
            mvView = btn.dataset.view;
            document.querySelectorAll('.pa-mv-view-btn').forEach(b => {
                const on = b === btn;
                b.classList.toggle('active', on);
                b.setAttribute('aria-pressed', on ? 'true' : 'false');
            });
            const help = document.getElementById('pa-move-help');
            if (help) { help.dataset.tip = M.helpFor(mvView); help.title = help.dataset.tip; }
            if (mvLast) document.getElementById('pa-move-body').innerHTML = M.bodyHtml(mvLast.pitches, mvLast.total, mvView);
        });
```

- [ ] **Step 4: CSS** — 끝에:

```css
.pa-mv-view { display: flex; justify-content: flex-end; padding: 0.5rem 0.75rem 0; }
.pa-mv-view-btn { padding: 0.2rem 0.6rem; border: 1px solid var(--border-color); background: var(--bg-card); color: var(--text-secondary); font: inherit; font-size: 0.75rem; font-weight: 600; cursor: pointer; }
.pa-mv-view-btn:first-child { border-radius: 6px 0 0 6px; }
.pa-mv-view-btn:last-child { border-radius: 0 6px 6px 0; border-left: 0; }
.pa-mv-view-btn.active { background: var(--primary); border-color: var(--primary); color: #fff; }
```

- [ ] **Step 5: 확인** — 시험 모두 PASS. 캡처: 65933 포수 시점·투수 시점(CDP 로 `.pa-mv-view-btn[data-view=pitcher]` 클릭) 두 장, 그림이 좌우로 뒤집히고 표 수평 부호가 바뀌는지, 툴팁 글자가 바뀌는지(`#pa-move-help` 의 data-tip). 투수 시점 상태에서 연도를 2019 로 바꿔도 투수 시점이 유지되는지.

- [ ] **Step 6: 커밋** — `git commit -m "feat(player-analytics): 무브먼트 포수·투수 시점 전환" -- dashboard_js/js/player-analytics/movement.js dashboard_js/pages/player-analytics.html dashboard_js/css/player-analytics.css`

---

### Task 3: 투수 Quick Look 지표 더하기 (evan 의견: 빈칸 없애기)

**Files:** `dashboard_js/js/player-analytics/quicklook.js`, 시험 `C:/tmp/bstats-player-analytics-check/tests/quicklook.test.js`

- [ ] **Step 1: 시험 먼저** — `build 투수(구창모)` 시험의 줄 목록 기대값을 바꾸고 값 시험을 더합니다:

```js
  assert.deepEqual(m.rows.map(r => r[0]), ['팀', 'W', 'L', 'SV', 'HLD', 'G', 'GS', 'IP', 'K%', 'BB%', 'K-BB%', 'K/9', 'BB/9', 'HR/9', 'BABIP', 'ERA', 'WHIP']);
  assert.deepEqual(row(m, 'K-BB%'), ['K-BB%', '-', '25.4%', '12.1%', '14.9%']);
  assert.deepEqual(row(m, 'K/9'), ['K/9', '-', '11.30', '7.39', '8.76']);
  assert.deepEqual(row(m, 'BB/9'), ['BB/9', '-', '1.88', '2.68', '3.10']);
  assert.deepEqual(row(m, 'HR/9'), ['HR/9', '-', '0.63', '1.19', '1.03']);
  assert.deepEqual(row(m, 'BABIP'), ['BABIP', '-', '.351', '.302', '.304']);
```

(타자 줄 목록은 그대로입니다.) Run → FAIL.

- [ ] **Step 2: ROWS.pit** — `quicklook.js` 의 `ROWS.pit` 에서 `['BB%', 'bbpct', 'pct'],` 다음에 넣습니다:

```js
      ['K-BB%', 'kbbpct', 'pct'], ['K/9', 'k9', 'f2'], ['BB/9', 'bb9', 'f2'], ['HR/9', 'hr9', 'f2'], ['BABIP', 'babip', 'avg3'],
```

(값은 공용 `pitchingRates` 가 이미 셉니다.) ROWS 위 주석에 "투수는 무브먼트 카드 높이에 맞춰 줄을 더 둡니다(evan 의견)"를 적습니다.

- [ ] **Step 3: 통과·커밋** — 전체 시험 PASS. `git commit -m "feat(player-analytics): 투수 Quick Look 에 K-BB%·K/9·BB/9·HR/9·BABIP" -- dashboard_js/js/player-analytics/quicklook.js`

---

### Task 4: 같은 손 투수 리그 평균 (API 세션의 /stats/movement_avg)

API: `GET /stats/movement_avg?season=YYYY` → `{season, rows:[{throws:'R'|'L', pitch_type, n, pfx_x, pfx_z, speed}]}` (인치·포수 시점, speed 는 null 가능). 운영 Worker 배포 전에는 404 → 페이지는 평균 없이 지금처럼 그립니다. 표시: 그림에 빗금 원, 표에 `좌투 평균`/`우투 평균` 줄. **n ≥ 100** 만.

**Files:** `movement.js`, `pages/player-analytics.html`, `css/player-analytics.css`, `js/api.js`, `database/lineage_writes.json`(unused_routes 에서 `/stats/movement_avg` 한 줄 빼기), `dashboard_js/data/table_lineage.json`(다시 만들어진 것), 시험 두 개

- [ ] **Step 1: 시험 먼저** — `movement.test.js` 끝에:

```js
const AVG = { rows: [
  { throws: 'L', pitch_type: '직구', n: 22991, pfx_x: 7.4, pfx_z: 11, speed: 144.7 },
  { throws: 'L', pitch_type: '커브', n: 50, pfx_x: -3, pfx_z: -5, speed: 118 },
  { throws: 'R', pitch_type: '직구', n: 63588, pfx_x: -5.1, pfx_z: 10.5, speed: 147.1 },
] };

test('avgFor: 손으로 고르고 100구 미만은 뺌, cm', () => {
  const a = M.avgFor(AVG, 'L');
  assert.deepEqual(Object.keys(a), ['직구']);
  assert.ok(Math.abs(a['직구'].x - 18.796) < 1e-9 && Math.abs(a['직구'].z - 27.94) < 1e-9);
  assert.equal(a['직구'].speed, 144.7);
  assert.deepEqual(M.avgFor(AVG, 'S'), {});
  assert.deepEqual(M.avgFor(null, 'L'), {});
  assert.equal(M.handLabel('L'), '좌투');
  assert.equal(M.handLabel('R'), '우투');
  assert.equal(M.handLabel('S'), null);
});

test('리그 평균: 빗금 원·표 평균 줄, 투수 시점은 수평 뒤집음', () => {
  const s = M.summarize(P);
  const ctx = { map: M.avgFor(AVG, 'L'), label: '좌투' };
  const svg = M.svgHtml(P, s, 'catcher', ctx);
  assert.ok(svg.includes('<pattern id="pa-mv-hatch"'));
  assert.equal((svg.match(/class="pa-mv-lg"/g) || []).length, 1);
  assert.ok(svg.includes('cx="256.4" cy="116.2"'));
  assert.ok(svg.includes('<title>좌투 평균 직구 · 수직 27.9cm · 수평 18.8cm</title>'));
  assert.ok(M.svgHtml(P, s, 'pitcher', ctx).includes('cx="143.6" cy="116.2"'));
  const lg = M.legendHtml(s, 'catcher', ctx);
  assert.ok(lg.includes('<tr class="pa-mv-avg-row"><td>좌투 평균</td><td></td><td>144.7</td><td>27.9</td><td>18.8</td></tr>'));
  assert.equal((lg.match(/pa-mv-avg-row/g) || []).length, 1);
  assert.ok(M.legendHtml(s, 'pitcher', ctx).includes('<td>좌투 평균</td><td></td><td>144.7</td><td>27.9</td><td>-18.8</td>'));
  assert.ok(M.bodyHtml(P, 8, 'catcher', ctx).includes('pa-mv-lg'));
  assert.ok(!M.bodyHtml(P, 8, 'catcher').includes('pa-mv-lg'), 'ctx 없으면 평균 없음');
});
```

`page-html.test.js` 끝에:

```js
test('리그 평균 연결', () => {
  for (const used of ['API.getMovementAvg(season)', 'M.avgFor(', 'M.handLabel(']) assert.ok(html.includes(used), used);
});
```

Run → FAIL.

- [ ] **Step 2: movement.js**
  - `const MIN_AVG_N = 100;`
  - `handLabel(t)`: `'L'` → `'좌투'`, `'R'` → `'우투'`, 그 밖 `null`.
  - `avgFor(data, throws)`: `data.rows` 중 `throws` 가 같고 `n ≥ MIN_AVG_N` 이고 pfx 값이 숫자인 줄을 `{ [pitch_type]: { x: pfx_x*IN2CM, z: pfx_z*IN2CM, speed: num(speed), n } }` 로. 손이 R/L 이 아니면 `{}`.
  - `svgHtml(pitches, summary, view, ctx)`: `ctx` 가 있으면 `<defs>` 안에 `<pattern id="pa-mv-hatch" patternUnits="userSpaceOnUse" width="6" height="6"><path class="pa-mv-hatch-line" d="M-1,1 l2,-2 M0,6 l6,-6 M5,7 l2,-2"/></pattern>` 를 넣고, 선수 평균 원을 그리기 **전에** summary 의 구종 중 `ctx.map` 에 있는 것마다 `<circle class="pa-mv-lg" cx=… cy=… r="11" fill="url(#pa-mv-hatch)" stroke="<구종 색>"><title>{label} 평균 {구종} · 수직 {z}cm · 수평 {x·flip}cm</title></circle>` (좌표는 점과 같은 식, 수평은 flip). 구종 이름은 esc.
  - `legendHtml(summary, view, ctx)`: 각 구종 줄 바로 다음, `ctx.map` 에 그 구종이 있으면 `<tr class="pa-mv-avg-row"><td>{label} 평균</td><td></td><td>{speed f1 또는 -}</td><td>{z f1}</td><td>{x·flip f1}</td></tr>`.
  - `bodyHtml(pitches, total, view, ctx)` 는 ctx 를 넘깁니다. `api` 에 `avgFor, handLabel` 추가.

- [ ] **Step 3: api.js** — `getPitchUsage` 다음에(덧붙이기):

```js
    /**
     * 투수 손별 리그 평균 무브먼트(/stats/movement_avg). 없거나 실패하면 rows 가 빈 배열입니다.
     */
    static async getMovementAvg(season) {
        try {
            const response = await fetch(`${API_BASE_URL}/stats/movement_avg?season=${encodeURIComponent(season)}`);
            if (!response.ok) return { rows: [] };
            return await response.json();
        } catch (error) {
            console.error('Error fetching movement average:', error);
            return { rows: [] };
        }
    }
```

- [ ] **Step 4: 페이지** — `usageCache` 옆에 `const avgCache = {};` 와 `let mvHand = null;`. `setupMovementCard` 에서 `mvHand = player.throw || null;`. `loadMovement` 에서 시즌 평균을 함께 부릅니다(`Promise.all` 배열에 세 번째로 `avgCache[season] ? null : API.getMovementAvg(season)`, 빈 결과는 저장 안 함, 키는 시즌). 그리기 직전에 `const label = M.handLabel(mvHand); const ctx = label ? { map: M.avgFor(avg, mvHand), label } : null;` 를 만들고 `mvLast = { pitches, total, ctx };`, `M.bodyHtml(pitches, total, mvView, ctx)`. 시점 전환 처리도 `mvLast.ctx` 를 넘깁니다. (재검토 지적: `setupMovementCard` 시작에서 `mvLast = null;` 로 이전 선수 그림이 시점 전환 때 다시 그려지지 않게 합니다.)

- [ ] **Step 5: CSS** — 끝에:

```css
.pa-mv-lg { stroke-width: 1.5; opacity: 0.9; }
.pa-mv-hatch-line { stroke: var(--text-muted); stroke-width: 1; }
.pa-mv-avg-row td { padding-top: 0; color: var(--text-muted); font-size: 0.7rem; }
.pa-mv-avg-row td:first-child { padding-left: 1.1rem; }
```

- [ ] **Step 6: 계보** — `database/lineage_writes.json` 의 `unused_routes` 에서 `"/stats/movement_avg"` 한 줄을 지우고(다른 줄 손대지 않음), `PYTHONUTF8=1 py scripts/build_lineage.py` → `PYTHONUTF8=1 py -m pytest tests -q`. 둘 다 통과해야 합니다. `dashboard_js/data/table_lineage.json` 이 바뀌면 이번 커밋에 함께 넣습니다(API 세션 안내).

- [ ] **Step 7: 확인** — 운영 API 는 아직 404 일 수 있습니다. CDP 로 `fetch` 를 가로채 `/stats/movement_avg` 에 AVG 와 같은 모양(2026 좌투 직구·슬라이더·포크·커브, n ≥ 100)을 돌려주는 확인용 스크립트(저장소 밖)로 캡처합니다. 빗금 원·평균 줄이 보이는지, 404 일 때는 평균 없이 지금처럼 보이는지 둘 다 확인합니다.

- [ ] **Step 8: 커밋** — `git commit -m "feat(player-analytics): 같은 손 투수 리그 평균(빗금 원·표 평균 줄)" -- dashboard_js/js/player-analytics/movement.js dashboard_js/pages/player-analytics.html dashboard_js/css/player-analytics.css dashboard_js/js/api.js database/lineage_writes.json dashboard_js/data/table_lineage.json`
