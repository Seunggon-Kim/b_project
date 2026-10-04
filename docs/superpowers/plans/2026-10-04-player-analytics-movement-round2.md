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
