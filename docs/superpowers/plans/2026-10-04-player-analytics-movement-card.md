# 선수 분석 무브먼트 카드 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 1군 투수 화면 카드 줄에 Savant 식 무브먼트 카드(연도 고르기·원형 SVG·구종 표)를 세 번째 칸으로 더합니다.

**Architecture:** 요약·SVG·표 HTML 은 새 순수 모듈 `js/player-analytics/movement.js`(전역 `PlayerAnalytics.movement`). 페이지는 카드 마크업과 켜기·끄기·불러오기만 합니다. 데이터는 기존 `/players/{id}/arsenal?season=` 입니다.

**Tech Stack:** 순수 HTML/CSS/JS, 인라인 SVG, Node `node:test`(저장소 밖), 헤드리스 Edge(CDP) 캡처.

설계: `docs/superpowers/specs/2026-10-04-player-analytics-movement-card-design.md`

## Global Constraints

- 저장소 `C:/Users/김승곤/Desktop/b_project`, 브랜치 `main`. 다른 Claude 세션(화면 세션: 계보 탭)이 같은 폴더에서 일합니다. `git add -A`·`git add .`·stash·reset·restore·checkout·브랜치 변경 금지. 커밋은 자기 파일만 경로를 붙여서: `git commit -m "…" -- <파일들>`. 메시지 끝에 빈 줄 + `Co-Authored-By: <모델 이름> <noreply@anthropic.com>`. push·배포 금지.
- 남의 파일: `dashboard_js/data/table_lineage.json`(줄 끝만 다른 M 상태), `dashboard_js/pages/database-explorer.html`, `dashboard_js/css/lineage.css`, `dashboard_js/js/lineage/*`. 건드리지 않습니다(계보 재생성 단계 제외, 그 단계 규칙을 따름).
- 공용 `dashboard_js/js/stats/*`, `dashboard_js/css/stats.css`, `dashboard_js/css/style.css` 는 고치지 않습니다. `dashboard_js/js/api.js` 는 덧붙이기만(기존 호출 동작 그대로).
- 미리보기 서버 `http://127.0.0.2:8765/` 는 화면 세션 소유. 새로 띄우지 않습니다. 꺼져 있으면 BLOCKED 로 보고합니다.
- 시험: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"` (지금 20개 통과). 로더 `C:/tmp/bstats-player-analytics-check/tests/_load.js` 는 `vm.runInThisContext` 로 모듈을 불러옵니다(저장소 package.json 이 type:module).
- 단위 cm(인치 × 2.54), 포수 시점, 구종 색표는 아래 Task 1 의 `COLORS` 그대로.
- 사용자 노출 한국어는 `습니다/합니다` 체.

---

### Task 1: 무브먼트 순수 모듈

**Files:**
- Create: `dashboard_js/js/player-analytics/movement.js`
- Modify: `C:/tmp/bstats-player-analytics-check/tests/_load.js` (movement.js 불러오기 한 줄, `M` 내보내기)
- Create: `C:/tmp/bstats-player-analytics-check/tests/movement.test.js`

**Interfaces:**
- Produces: `PlayerAnalytics.movement` =
  - `COLORS`, `colorOf(type) → '#rrggbb'`
  - `summarize(pitches) → [{type, color, n, pct, x, z, speed}]` (x·z cm 평균, speed km/h 평균 또는 null, 많이 던진 순, 같으면 구종 이름 순)
  - `seasonsFor(player) → number[]` (pitcher_seasons 중 2008 이상, 중복 없이 최신순)
  - `svgHtml(pitches, summary) → string` (유효한 공이 없으면 `''`)
  - `legendHtml(summary) → string` (빈 배열이면 `''`)
  - `bodyHtml(pitches) → string` (그림 + 안내 줄 + 표, 없으면 빈 데이터 문구)

- [ ] **Step 1: 로더에 모듈 추가**

`_load.js` 의 `run('player-analytics/quicklook.js');` 아래에 `run('player-analytics/movement.js');` 를 넣고, 내보내기를 바꿉니다:

```js
module.exports = { Q: globalThis.PlayerAnalytics.quicklook, M: globalThis.PlayerAnalytics.movement, fixture, REPO_JS };
```

- [ ] **Step 2: 실패하는 시험 쓰기**

`C:/tmp/bstats-player-analytics-check/tests/movement.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { M } = require('./_load');

const P = [
  { pitch_type: '직구', pfx_x: 10, pfx_z: 10, speed: 140 },
  { pitch_type: '직구', pfx_x: 0, pfx_z: 10, speed: 144 },
  { pitch_type: '커브', pfx_x: -5, pfx_z: -5, speed: '' },
  { pitch_type: 'X구종', pfx_x: 1, pfx_z: 2, speed: 0 },
  { pitch_type: '직구', pfx_x: null, pfx_z: 3, speed: 150 },
];
const near = (a, b) => Math.abs(a - b) < 1e-9;

test('summarize: cm 평균·비율·구속, 빈 무브먼트 제외, 순서, 색', () => {
  const s = M.summarize(P);
  assert.deepEqual(s.map(g => g.type), ['직구', 'X구종', '커브']);
  assert.deepEqual(s.map(g => g.n), [2, 1, 1]);
  assert.deepEqual(s.map(g => g.pct), [50, 25, 25]);
  assert.ok(near(s[0].x, 12.7) && near(s[0].z, 25.4));
  assert.equal(s[0].speed, 142);
  assert.equal(s[1].speed, null);
  assert.equal(s[2].speed, null);
  assert.ok(near(s[2].x, -12.7) && near(s[2].z, -12.7));
  assert.equal(s[0].color, '#D22D49');
  assert.equal(s[1].color, '#3b82f6');
  assert.equal(M.colorOf('싱커'), '#FE9D00');
  assert.deepEqual(M.summarize([]), []);
  assert.deepEqual(M.summarize(null), []);
});

test('seasonsFor: 2008 이상, 중복 없이 최신순, 문자열 시즌도', () => {
  assert.deepEqual(M.seasonsFor({ pitcher_seasons: [{ season: 2007 }, { season: 2016 }, { season: '2019' }, { season: 2019 }] }), [2019, 2016]);
  assert.deepEqual(M.seasonsFor({}), []);
});

test('svgHtml: 점·평균 원 수, 좌표(중심 200, 1cm=3), 잘라내기, 이스케이프', () => {
  const s = M.summarize(P);
  const svg = M.svgHtml(P, s);
  assert.match(svg, /^<svg class="pa-mv-svg" viewBox="0 0 400 400"/);
  assert.equal((svg.match(/class="pa-mv-pt"/g) || []).length, 4);
  assert.equal((svg.match(/class="pa-mv-avg"/g) || []).length, 3);
  assert.ok(svg.includes('cx="276.2" cy="123.8"'), '직구 첫 공 좌표');
  assert.ok(svg.includes('clip-path="url(#pa-mv-clip)"'));
  assert.ok(svg.includes('<title>직구 50.0% · 수직 25.4cm · 수평 12.7cm</title>'));
  const odd = M.svgHtml([{ pitch_type: '<b>', pfx_x: 1, pfx_z: 1 }], M.summarize([{ pitch_type: '<b>', pfx_x: 1, pfx_z: 1 }]));
  assert.ok(odd.includes('&lt;b&gt;') && !odd.includes('<b>'));
  assert.equal(M.svgHtml([], []), '');
});

test('legendHtml: 머리글·줄 글자', () => {
  const html = M.legendHtml(M.summarize(P));
  assert.ok(html.startsWith('<table class="pa-mv-legend">'));
  assert.ok(html.includes('<th>구종</th><th>비율</th><th>구속(km/h)</th><th>수직(cm)</th><th>수평(cm)</th>'));
  assert.ok(html.includes('<span class="pa-mv-dot" style="background:#D22D49"></span>직구</td><td>50.0%</td><td>142.0</td><td>25.4</td><td>12.7</td>'));
  assert.ok(html.includes('커브</td><td>25.0%</td><td>-</td><td>-12.7</td><td>-12.7</td>'));
  assert.equal(M.legendHtml([]), '');
});

test('bodyHtml: 그림·안내 줄·표, 빈 데이터 문구', () => {
  const html = M.bodyHtml(P);
  assert.ok(html.includes('<svg class="pa-mv-svg"'));
  assert.ok(html.includes('<p class="pa-mv-note">포수 시점 · 수평 +는 1루 쪽 · 수직 +는 위 · 공 4개</p>'));
  assert.ok(html.includes('<table class="pa-mv-legend">'));
  assert.equal(M.bodyHtml([]), '<p class="pa-mv-empty">이 시즌은 투구 추적 데이터가 없습니다.</p>');
  assert.equal(M.bodyHtml([{ pitch_type: '직구', pfx_x: null, pfx_z: null }]), '<p class="pa-mv-empty">이 시즌은 투구 추적 데이터가 없습니다.</p>');
});
```

- [ ] **Step 3: 실패 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 로더가 `movement.js` 를 못 찾아 ENOENT 로 모든 파일이 실패합니다.

- [ ] **Step 4: 모듈 쓰기**

`dashboard_js/js/player-analytics/movement.js`:

```js
/*
 * 선수 분석 무브먼트 카드(Savant Movement Profile 참고)를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다. 설계:
 * docs/superpowers/specs/2026-10-04-player-analytics-movement-card-design.md
 *
 * 응답 pfx_x·pfx_z 는 인치입니다. 화면은 cm(× 2.54), 포수 시점입니다.
 * 아래쪽 기존 Movement Profile 카드와 같은 단위·방향·색입니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};

  // 기존 카드(player-analytics.html renderMovementProfile)의 색표와 같습니다.
  const COLORS = {
    '너클볼': '#3C44CD', '스위퍼': '#DDB33A', '슬러브': '#93AFD4',
    '싱커': '#FE9D00', '투심': '#FE9D00', '직구': '#D22D49',
    '체인지업': '#1DBE3A', '커브': '#00D1ED', '커터': '#933F2C',
    '포크': '#3BACAC', '스플리터': '#3BACAC', '슬라이더': '#EEE716',
  };
  const FALLBACK = '#3b82f6';
  const IN2CM = 2.54;
  const C = 200;           // 그림 중심(px)
  const PX_PER_CM = 3;     // 60cm 가 반지름 180px
  const RINGS = [15, 30, 45, 60];
  const FIRST_SEASON = 2008;

  function colorOf(type) {
    return Object.prototype.hasOwnProperty.call(COLORS, type) ? COLORS[type] : FALLBACK;
  }

  function num(v) {
    if (v === null || v === undefined || v === '') return null;
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /** 무브먼트 값이 있는 공만 고릅니다. */
  function valid(pitches) {
    return (pitches || []).filter(function (p) {
      return p && p.pitch_type && num(p.pfx_x) !== null && num(p.pfx_z) !== null;
    });
  }

  /** 구종별 요약입니다. 많이 던진 순, 같으면 구종 이름 순입니다. */
  function summarize(pitches) {
    const vs = valid(pitches);
    const by = {};
    vs.forEach(function (p) {
      const g = by[p.pitch_type] || (by[p.pitch_type] = { type: p.pitch_type, n: 0, sx: 0, sz: 0, sv: 0, nv: 0 });
      g.n++;
      g.sx += num(p.pfx_x) * IN2CM;
      g.sz += num(p.pfx_z) * IN2CM;
      const v = num(p.speed);
      if (v !== null && v > 0) { g.sv += v; g.nv++; }
    });
    return Object.keys(by).map(function (k) {
      const g = by[k];
      return {
        type: g.type, color: colorOf(g.type), n: g.n, pct: g.n * 100 / vs.length,
        x: g.sx / g.n, z: g.sz / g.n, speed: g.nv ? g.sv / g.nv : null,
      };
    }).sort(function (a, b) {
      return b.n - a.n || (a.type < b.type ? -1 : a.type > b.type ? 1 : 0);
    });
  }

  /** 연도 고르기 목록입니다. 1군 투수 기록 시즌 중 2008 이상, 최신순. */
  function seasonsFor(player) {
    const out = [];
    ((player && player.pitcher_seasons) || []).forEach(function (s) {
      const y = Number(s.season);
      if (Number.isFinite(y) && y >= FIRST_SEASON && out.indexOf(y) === -1) out.push(y);
    });
    return out.sort(function (a, b) { return b - a; });
  }

  function f1(v) { return v.toFixed(1); }
  function px(cmX) { return f1(C + cmX * PX_PER_CM); }
  function py(cmZ) { return f1(C - cmZ * PX_PER_CM); }

  /** 원형 무브먼트 그림입니다. 유효한 공이 없으면 빈 글자입니다. */
  function svgHtml(pitches, summary) {
    const vs = valid(pitches);
    if (!vs.length) return '';
    const R = RINGS[RINGS.length - 1] * PX_PER_CM;
    let s = '<svg class="pa-mv-svg" viewBox="0 0 400 400" role="img" aria-label="구종별 무브먼트">'
      + '<defs><clipPath id="pa-mv-clip"><circle cx="200" cy="200" r="' + R + '"/></clipPath></defs>'
      + '<circle class="pa-mv-bg" cx="200" cy="200" r="' + R + '"/>';
    RINGS.forEach(function (cm) {
      s += '<circle class="pa-mv-ring' + (cm % 30 ? ' pa-mv-ring--minor' : '') + '" cx="200" cy="200" r="' + cm * PX_PER_CM + '"/>';
    });
    s += '<line class="pa-mv-axis" x1="' + (C - R) + '" y1="200" x2="' + (C + R) + '" y2="200"/>'
      + '<line class="pa-mv-axis" x1="200" y1="' + (C - R) + '" x2="200" y2="' + (C + R) + '"/>';
    [30, 60].forEach(function (cm) {
      s += '<text class="pa-mv-tick" x="204" y="' + (C - cm * PX_PER_CM + 12) + '">' + cm + '</text>';
    });
    s += '<g clip-path="url(#pa-mv-clip)">';
    vs.forEach(function (p) {
      s += '<circle class="pa-mv-pt" cx="' + px(num(p.pfx_x) * IN2CM) + '" cy="' + py(num(p.pfx_z) * IN2CM)
        + '" r="2.5" fill="' + colorOf(p.pitch_type) + '"/>';
    });
    (summary || []).forEach(function (g) {
      s += '<circle class="pa-mv-avg" cx="' + px(g.x) + '" cy="' + py(g.z) + '" r="9" fill="' + g.color + '">'
        + '<title>' + esc(g.type) + ' ' + f1(g.pct) + '% · 수직 ' + f1(g.z) + 'cm · 수평 ' + f1(g.x) + 'cm</title></circle>';
    });
    return s + '</g></svg>';
  }

  /** 구종 표입니다. 빈 배열이면 빈 글자입니다. */
  function legendHtml(summary) {
    if (!summary || !summary.length) return '';
    return '<table class="pa-mv-legend"><thead><tr><th>구종</th><th>비율</th><th>구속(km/h)</th><th>수직(cm)</th><th>수평(cm)</th></tr></thead><tbody>'
      + summary.map(function (g) {
        return '<tr><td><span class="pa-mv-dot" style="background:' + g.color + '"></span>' + esc(g.type) + '</td>'
          + '<td>' + f1(g.pct) + '%</td><td>' + (g.speed === null ? '-' : f1(g.speed)) + '</td>'
          + '<td>' + f1(g.z) + '</td><td>' + f1(g.x) + '</td></tr>';
      }).join('')
      + '</tbody></table>';
  }

  /** 카드 본문입니다. 그림 + 안내 줄 + 표. 데이터가 없으면 안내 문구입니다. */
  function bodyHtml(pitches) {
    const vs = valid(pitches);
    if (!vs.length) return '<p class="pa-mv-empty">이 시즌은 투구 추적 데이터가 없습니다.</p>';
    const summary = summarize(vs);
    return svgHtml(vs, summary)
      + '<p class="pa-mv-note">포수 시점 · 수평 +는 1루 쪽 · 수직 +는 위 · 공 ' + vs.length + '개</p>'
      + legendHtml(summary);
  }

  const api = { COLORS, colorOf, summarize, seasonsFor, svgHtml, legendHtml, bodyHtml };
  PA.movement = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 5: 통과 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 25개 모두 PASS(기존 20 + 새 5).

- [ ] **Step 6: 커밋**

```bash
cd "C:/Users/김승곤/Desktop/b_project"
git add dashboard_js/js/player-analytics/movement.js
git commit -m "feat(player-analytics): 무브먼트 카드 순수 모듈(요약·원형 SVG·구종 표)" -- dashboard_js/js/player-analytics/movement.js
```

---

### Task 2: 카드 화면 연결

**Files:**
- Modify: `dashboard_js/js/api.js` (`getPitchArsenal`)
- Modify: `dashboard_js/pages/player-analytics.html`
- Modify: `dashboard_js/css/player-analytics.css`
- Modify: `C:/tmp/bstats-player-analytics-check/tests/page-html.test.js`

**Interfaces:**
- Consumes: Task 1 `PlayerAnalytics.movement.{seasonsFor, bodyHtml}`. 페이지 전역 `createLoadingSpinner`(components.js), `API.getPitchArsenal`.
- Produces: 화면. 요소 id `pa-move-card`, `pa-move-season`, `pa-move-body`. 그리드 클래스 `pa-3col`.

- [ ] **Step 1: 구조 시험 고치기(실패하게)**

`page-html.test.js` 첫 시험의 기대 스크립트 목록에서 `'../js/player-analytics/quicklook.js',` 다음에 `'../js/player-analytics/movement.js',` 를 넣고, 같은 시험의 인라인 순서 확인 줄을 `movement.js` 기준으로 바꿉니다:

```js
  assert.ok(html.indexOf('player-analytics/movement.js') < html.search(/<script>\r?\n/), '인라인 스크립트보다 먼저');
```

파일 끝에 시험을 더합니다:

```js
test('무브먼트 카드: 프로필 다음, id·숨김, 켜기·끄기 함수', () => {
  const prof = html.indexOf('class="pa-card pa-card--profile"');
  const move = html.indexOf('id="pa-move-card"');
  assert.ok(prof > 0 && move > prof);
  assert.match(html, /<div class="pa-card pa-card--move hidden" id="pa-move-card">/);
  assert.match(html, /<select id="pa-move-season" class="pa-move-season" aria-label="무브먼트 시즌"><\/select>/);
  assert.match(html, /<div class="pa-card-body" id="pa-move-body"><\/div>/);
  for (const used of ['function setupMovementCard(', 'function hideMovementCard(', 'function loadMovement(', 'setupMovementCard(player, playerId)', 'M.bodyHtml(', 'API.getPitchArsenal(playerId, season)']) {
    assert.ok(html.includes(used), used);
  }
});
```

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/page-html.test.js"` → Expected: 2개 FAIL.

- [ ] **Step 2: api.js 에 선택 인자 덧붙이기**

`getPitchArsenal` 을 아래로 바꿉니다(주석 블록 포함, 나머지 함수는 그대로):

```js
    /**
     * Get Pitch Arsenal
     * season 을 주면 그 시즌, 안 주면 서버 기본(올해)입니다.
     */
    static async getPitchArsenal(playerId, season) {
        try {
            const q = season ? `?season=${encodeURIComponent(season)}` : '';
            const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal${q}`);
```

(그 아래 `if (!response.ok) …` 부터는 그대로입니다.)

- [ ] **Step 3: 스크립트 넣기**

`pages/player-analytics.html` 의 `<script src="../js/player-analytics/quicklook.js"></script>` 바로 아래:

```html
    <script src="../js/player-analytics/movement.js"></script>
```

- [ ] **Step 4: 카드 마크업**

프로필 카드(`<div class="pa-card pa-card--profile">` … 그 카드의 닫는 `</div>`) 바로 다음, 퓨처스 최근 경기 주석 앞에 넣습니다:

```html

                <!-- Savant 식 무브먼트 카드입니다. 1군 투수만 켭니다(setupMovementCard). -->
                <div class="pa-card pa-card--move hidden" id="pa-move-card">
                    <div class="pa-card-tabs">
                        <span class="pa-card-tab">무브먼트 (Induced Break)</span>
                        <select id="pa-move-season" class="pa-move-season" aria-label="무브먼트 시즌"></select>
                    </div>
                    <div class="pa-card-body" id="pa-move-body"></div>
                </div>
```

- [ ] **Step 5: 켜기·끄기·불러오기 함수**

`function profileHtml(items) {` 함수 정의 바로 아래(그 함수 닫는 `}` 다음 빈 줄)에 넣습니다:

```js

        // --- 무브먼트 카드(Savant 참고) ---------------------------------
        // 1군 투수만 보입니다. 연도를 바꾸면 그 시즌 투구를 불러옵니다.
        // 같은 선수·시즌은 다시 부르지 않습니다. 빈 결과(오류 포함)는
        // 저장하지 않아 다음에 다시 시도합니다.
        const mvCache = {};
        let mvToken = 0;

        function hideMovementCard() {
            mvToken++;  // 아직 오는 중인 응답을 버립니다.
            const card = document.getElementById('pa-move-card');
            if (card) card.classList.add('hidden');
            const grid = document.querySelector('.player-details-grid');
            if (grid) grid.classList.remove('pa-3col');
        }

        function setupMovementCard(player, playerId) {
            const M = window.PlayerAnalytics.movement;
            const seasons = player.position === '투수' ? M.seasonsFor(player) : [];
            if (!seasons.length) { hideMovementCard(); return; }
            const select = document.getElementById('pa-move-season');
            select.innerHTML = seasons.map(y => `<option value="${y}">${y}</option>`).join('');
            select.value = String(seasons[0]);
            select.onchange = () => loadMovement(playerId, Number(select.value));
            document.getElementById('pa-move-card').classList.remove('hidden');
            document.querySelector('.player-details-grid').classList.add('pa-3col');
            loadMovement(playerId, seasons[0]);
        }

        async function loadMovement(playerId, season) {
            const M = window.PlayerAnalytics.movement;
            const body = document.getElementById('pa-move-body');
            const token = ++mvToken;
            const key = playerId + ':' + season;
            let pitches = mvCache[key];
            if (!pitches) {
                body.innerHTML = createLoadingSpinner();
                const res = await API.getPitchArsenal(playerId, season);
                pitches = (res && res.arsenal) || [];
                if (pitches.length) mvCache[key] = pitches;
            }
            if (token !== mvToken) return;  // 그사이 다른 선수·시즌을 골랐습니다.
            body.innerHTML = M.bodyHtml(pitches);
        }
```

- [ ] **Step 6: 두 화면에서 부르기**

`loadFuturesPlayer` 안 `hidePbpSections();` 바로 아래에 `hideMovementCard();` 한 줄.

`loadPlayerInfo` 안 `cardDiv.insertAdjacentHTML('beforeend', Q.tilesHtml(Q.seasonTiles(player)));` 바로 아래:

```js
                // 무브먼트 카드(1군 투수만). 타자면 끕니다.
                setupMovementCard(player, playerId);
```

`loadPlayerInfo` 의 `section.classList.remove('hidden');` 바로 아래에도 `hideMovementCard();` 한 줄(이전 선수 카드를 불러오는 동안 감춤).

- [ ] **Step 7: CSS 덧붙이기**

`css/player-analytics.css` 의 `@media (max-width: 1024px) {` 블록 안 `.pa-card--ql, .pa-card--profile { grid-column: 1 / -1; }` 를 `.pa-card--ql, .pa-card--profile, .pa-card--move { grid-column: 1 / -1; }` 로 바꿉니다. 그 블록 **위**(같은 파일, `.pa-card--ql { grid-column: span 2; }` 다음 줄)에 넣습니다:

```css
/* 1군 투수는 무브먼트 카드까지 3칸입니다. Quick Look 을 1칸으로 줄입니다. */
.player-details-grid.pa-3col > .pa-card--ql { grid-column: span 1; }
```

파일 끝에 넣습니다:

```css

/* ---------- 무브먼트(Savant Movement Profile 참고) ---------- */
.pa-card--move .pa-card-tabs { align-items: center; justify-content: space-between; padding-right: 0.5rem; }
.pa-move-season { font: inherit; font-size: 0.85rem; padding: 0.2rem 1.8rem 0.2rem 0.5rem; border: 1px solid var(--border-color); border-radius: 6px; background-color: var(--bg-card); color: var(--text-primary); }
.pa-mv-svg { display: block; width: 100%; max-width: 340px; height: auto; margin: 0.25rem auto 0; }
.pa-mv-bg { fill: var(--bg-secondary); }
.pa-mv-ring { fill: none; stroke: var(--text-muted); stroke-width: 0.8; opacity: 0.55; }
.pa-mv-ring--minor { stroke-dasharray: 3 3; }
.pa-mv-axis { stroke: var(--text-muted); stroke-width: 0.8; opacity: 0.55; }
.pa-mv-tick { fill: var(--text-muted); font-size: 11px; }
.pa-mv-pt { opacity: 0.35; }
.pa-mv-avg { stroke: var(--bg-card); stroke-width: 2.5; }
.pa-mv-note { margin: 0.25rem 0 0.5rem; font-size: 0.75rem; color: var(--text-secondary); text-align: center; }
.pa-mv-legend { width: 100%; border-collapse: collapse; font-size: 0.8rem; font-variant-numeric: tabular-nums; }
.pa-mv-legend th, .pa-mv-legend td { padding: 0.25rem 0.4rem; text-align: right; border-bottom: 1px solid var(--border-color); white-space: nowrap; color: var(--text-primary); }
.pa-mv-legend th { font-weight: 600; color: var(--text-secondary); }
.pa-mv-legend th:first-child, .pa-mv-legend td:first-child { text-align: left; }
.pa-mv-legend tbody tr:last-child td { border-bottom: 0; }
.pa-mv-dot { display: inline-block; width: 0.6rem; height: 0.6rem; margin-right: 0.35rem; border-radius: 50%; vertical-align: middle; }
.pa-mv-empty { padding: 1rem 0; font-size: 0.85rem; color: var(--text-secondary); text-align: center; }
```

- [ ] **Step 8: 시험 통과 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 26개 모두 PASS.

- [ ] **Step 9: 계보 다시 만들기**

```bash
cd "C:/Users/김승곤/Desktop/b_project"
PYTHONUTF8=1 py scripts/build_lineage.py
PYTHONUTF8=1 py -m pytest tests -q
git diff --stat -- dashboard_js/data/table_lineage.json
```

Expected: pytest 모두 통과. `git diff --stat` 이 비면(줄 끝만 다름) 계보 파일은 커밋하지 않습니다. 내용이 바뀌었으면 보고서에 diff 요약을 적고 **커밋하지 않은 채** DONE_WITH_CONCERNS 로 보고합니다(남의 파일이라 컨트롤러가 화면 세션과 맞춥니다).

- [ ] **Step 10: DOM 확인**

미리보기 서버를 새로 띄우지 않습니다. `C:/tmp/bstats-player-analytics-check/cdp_shot.mjs` 로 `pa2col_check /pages/player-analytics.html?id=65933 desktop light` 를 찍고 Read 로 봅니다: 세 카드(Quick Look·프로필·무브먼트)가 한 줄, 무브먼트에 원형 그림·구종 표, 연도 고르기 `2026` 이 보여야 합니다. 타자 `?id=76232` 는 두 칸 그대로여야 합니다.

- [ ] **Step 11: 커밋**

```bash
cd "C:/Users/김승곤/Desktop/b_project"
git commit -m "feat(player-analytics): 1군 투수 카드 줄에 무브먼트 카드(연도 고르기)" -- dashboard_js/js/api.js dashboard_js/pages/player-analytics.html dashboard_js/css/player-analytics.css
```

---

### Task 3: 화면 확인(PNG)

**Files:** 고치는 파일 없음(문제가 나오면 Task 2 파일만 최소로 고치고 따로 커밋).

- [ ] **Step 1: 캡처** — `cdp_shot.mjs <이름> <경로쿼리> [desktop|mobile] [dark|light]` 로 찍고 `C:/Users/김승곤/Desktop/pa5_<이름>.png` 로 복사합니다.

| 이름 | 경로 | 확인 |
|---|---|---|
| pitcher | `/pages/player-analytics.html?id=65933` desktop light | 3칸, 높이 같음, 원형 그림·표, 2026 |
| pitcher_2019 | 같은 주소에서 연도 2019 를 고른 상태 | 그림이 2019 로 바뀜(공 1,694개). CDP `Runtime.evaluate` 로 select 값을 바꾸고 change 이벤트를 보낸 뒤 3초 기다려 캡처 |
| batter | `?id=76232` | 2칸 그대로, 무브먼트 없음 |
| futures | `?id=77263&mode=futures` | 2칸 그대로 |
| dark | `?id=65933` desktop dark | 원·고리·표 대비 |
| mobile | `?id=65933` mobile light | 위아래로 쌓임, 그림이 카드 폭에 맞음, 가로 넘침 없음 |

- [ ] **Step 2: 시험 다시 실행** — `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"` 26개 PASS.

- [ ] **Step 3: 보고** — PNG 이름·확인 결과·`git log origin/main..main --oneline` 을 보고서에 적습니다. push·배포는 하지 않습니다.
