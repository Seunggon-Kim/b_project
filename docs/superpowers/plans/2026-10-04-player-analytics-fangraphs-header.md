# 선수 분석 머리 부분 개편 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 선수 분석 페이지의 헤더와 카드 줄(Quick Look·프로필)을 팬그래프 선수 페이지 모양으로 바꿉니다.

**Architecture:** 계산·표 HTML 은 새 순수 모듈 `js/player-analytics/quicklook.js`(전역 `PlayerAnalytics.quicklook`)에 둡니다. 합계·비율은 공용 `TeamStats.metrics`, 숫자 표시는 공용 `TeamStats.columns.fmt` 를 가져다 씁니다. 스타일은 새 `css/player-analytics.css` 의 새 클래스만 씁니다. 페이지는 마크업과 렌더 함수만 바꿉니다.

**Tech Stack:** 순수 HTML/CSS/JS(빌드 없음), Node `node:test`(저장소 밖 시험), 헤드리스 Edge 캡처.

설계: `docs/superpowers/specs/2026-10-04-player-analytics-fangraphs-header-design.md`

## Global Constraints

- 저장소: `C:/Users/김승곤/Desktop/b_project`, 브랜치 `main`. 화면 세션과 같은 폴더를 씁니다.
- 커밋은 자기 파일만 경로를 붙여서 합니다: `git commit -m "…" -- <파일들>`. `git add -A`·stash·reset·restore·브랜치 변경 금지.
- push·배포는 evan 허락 뒤에만 합니다. 이 계획에는 push 가 없습니다.
- 공용 `dashboard_js/js/stats/*.js`, `dashboard_js/css/stats.css`, `dashboard_js/css/style.css` 는 고치지 않습니다.
- API 주소를 바꾸지 않습니다(새 fetch 없음).
- `player-analytics?id=<선수 ID>`·`&mode=futures` 주소 동작을 그대로 둡니다.
- 미리보기 서버는 화면 세션의 `http://127.0.0.2:8765/` 를 씁니다. 새로 띄우지 않습니다. 꺼져 있으면 evan 에게 묻습니다.
- 사이트 CSS 변수: `--bg-card`, `--bg-secondary`, `--border-color`, `--text-primary`, `--text-secondary`, `--text-muted`, `--primary`. (`--card-bg` 는 정의되어 있지 않습니다. 쓰지 않습니다.)
- 시험 위치: `C:/tmp/bstats-player-analytics-check/tests`, 픽스처 `C:/tmp/bstats-player-analytics-check/fixtures/player_65933.json`(투수 구창모), `player_76232.json`(타자 양의지). 이미 받아 두었습니다.
- 시험 실행: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
- 저장소 `package.json` 이 `"type": "module"` 이라 모듈을 `require` 로 부르지 않고 `vm.runInThisContext` 로 실행합니다.

---

### Task 1: Quick Look 순수 모듈

**Files:**
- Create: `dashboard_js/js/player-analytics/quicklook.js`
- Test: `C:/tmp/bstats-player-analytics-check/tests/_load.js`, `C:/tmp/bstats-player-analytics-check/tests/quicklook.test.js`

**Interfaces:**
- Consumes: `TeamStats.metrics.{num, sumPitching, pitchingRates, sumBatting, battingRates}`, `TeamStats.columns.fmt(v, kind)` (kind: `int`·`ip`·`f1`·`f2`·`avg3`). 호출할 때 읽습니다(불러올 때 아님).
- Produces: `PlayerAnalytics.quicklook` =
  - `kindOf(player) → 'pit' | 'bat'` (`position === '투수'` 면 pit)
  - `pickSeasons(player, thisYear) → [y-2, y-1, y]`
  - `total(rows, kind) → 합계·비율 객체 | null`
  - `build(player, thisYear) → Model`
  - `buildFutures(seasons, kind) → Model | null` (kind: `'batter' | 'pitcher'`, 퓨처스 응답 `f.kind` 그대로)
  - `summary(columns, cells) → Model`
  - `tableHtml(model) → string`
  - `ageParts(birthday, today) → {years, months} | null`
  - `dobText(birthday) → 'YYYY.MM.DD' | null`
  - `Model = { head: string[], rows: string[][], career: boolean }` (각 줄 0번째가 라벨)

- [ ] **Step 1: 시험 로더 쓰기**

`C:/tmp/bstats-player-analytics-check/tests/_load.js`:

```js
// 저장소의 공용 통계 모듈과 Quick Look 모듈을 브라우저처럼 불러옵니다.
// 저장소 package.json 이 "type": "module" 이라 require 로는 못 부릅니다.
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const REPO_JS = 'C:/Users/김승곤/Desktop/b_project/dashboard_js/js';
const FIX = path.join(__dirname, '..', 'fixtures');

function run(rel) {
  const file = path.join(REPO_JS, rel);
  vm.runInThisContext(fs.readFileSync(file, 'utf8'), { filename: file });
}

run('stats/metrics.js');
run('stats/columns.js');
run('player-analytics/quicklook.js');

function fixture(name) {
  return JSON.parse(fs.readFileSync(path.join(FIX, name + '.json'), 'utf8'));
}

module.exports = { Q: globalThis.PlayerAnalytics.quicklook, fixture, REPO_JS };
```

- [ ] **Step 2: 실패하는 시험 쓰기**

`C:/tmp/bstats-player-analytics-check/tests/quicklook.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { Q, fixture } = require('./_load');

const row = (m, label) => m.rows.find(r => r[0] === label);

test('pickSeasons: 현역은 올해, 은퇴는 마지막 시즌까지 3년', () => {
  assert.deepEqual(Q.pickSeasons({ is_active: 1, pitcher_seasons: [{ season: 2019 }] }, 2026), [2024, 2025, 2026]);
  assert.deepEqual(Q.pickSeasons({ is_active: 0, batter_seasons: [{ season: 2017 }, { season: 2019 }] }, 2026), [2017, 2018, 2019]);
  assert.deepEqual(Q.pickSeasons({ is_active: 0 }, 2026), [2024, 2025, 2026]);
});

test('kindOf: 투수만 pit', () => {
  assert.equal(Q.kindOf({ position: '투수' }), 'pit');
  assert.equal(Q.kindOf({ position: '포수' }), 'bat');
  assert.equal(Q.kindOf({}), 'bat');
});

test('build 투수(구창모): 머리·팀·리그·시즌 값', () => {
  const m = Q.build(fixture('player_65933'), 2026);
  assert.equal(m.career, true);
  assert.deepEqual(m.head, ['시즌', '2024', '2025', '2026', '통산']);
  assert.deepEqual(row(m, '팀'), ['팀', '-', 'NC', 'NC', '-']);
  assert.deepEqual(row(m, '리그'), ['리그', '-', '1군', '1군', '1군']);
  assert.deepEqual(m.rows.map(r => r[0]), ['팀', '리그', 'W', 'L', 'SV', 'HLD', 'G', 'GS', 'IP', 'K%', 'BB%', 'ERA', 'WHIP']);
  assert.deepEqual(row(m, 'IP'), ['IP', '-', '14 1/3', '151', '845 2/3']);
  assert.deepEqual(row(m, 'ERA'), ['ERA', '-', '2.51', '4.11', '3.74']);
  assert.deepEqual(row(m, 'WHIP'), ['WHIP', '-', '1.19', '1.33', '1.29']);
  assert.deepEqual(row(m, 'K%'), ['K%', '-', '30.5%', '19.0%', '23.0%']);
  assert.deepEqual(row(m, 'BB%'), ['BB%', '-', '5.1%', '6.9%', '8.1%']);
  assert.deepEqual(row(m, 'W'), ['W', '-', '1', '11', '59']);
  assert.deepEqual(row(m, 'HLD'), ['HLD', '-', '0', '0', '4']);
  assert.deepEqual(row(m, 'G'), ['G', '-', '4', '27', '205']);
  assert.deepEqual(row(m, 'GS'), ['GS', '-', '3', '27', '148']);
});

test('build 타자(양의지): 시즌·통산 비율은 합계에서 다시 셈', () => {
  const m = Q.build(fixture('player_76232'), 2026);
  assert.deepEqual(m.rows.map(r => r[0]), ['팀', '리그', 'G', 'PA', 'HR', 'R', 'RBI', 'BB%', 'K%', 'AVG', 'OBP', 'SLG', 'OPS']);
  assert.deepEqual(row(m, '팀'), ['팀', '두산', '두산', '두산', '-']);
  assert.deepEqual(row(m, 'AVG'), ['AVG', '.314', '.337', '.253', '.306']);
  assert.deepEqual(row(m, 'OBP'), ['OBP', '.379', '.406', '.359', '.388']);
  assert.deepEqual(row(m, 'SLG'), ['SLG', '.479', '.533', '.445', '.498']);
  assert.deepEqual(row(m, 'OPS'), ['OPS', '.858', '.939', '.805', '.887']);
  assert.deepEqual(row(m, 'BB%'), ['BB%', '8.2%', '9.7%', '11.0%', '9.8%']);
  assert.deepEqual(row(m, 'PA'), ['PA', '485', '517', '518', '7901']);
  assert.deepEqual(row(m, 'HR'), ['HR', '17', '20', '22', '304']);
  assert.deepEqual(row(m, 'G'), ['G', '119', '130', '130', '2093']);
});

test('build: 이적 시즌은 더하고 팀은 A/B', () => {
  const p = {
    position: '투수', is_active: 1,
    pitcher_seasons: [
      { season: 2026, player_team: 'LG', innings_pitched: '10 1/3', earned_run: 3, total_batters_faced: 40, strikeout: 8, base_on_balls: 2, hits: 9, games: 5, wins: 1 },
      { season: 2026, player_team: 'KT', innings_pitched: '5 2/3', earned_run: 1, total_batters_faced: 20, strikeout: 4, base_on_balls: 1, hits: 3, games: 3, wins: 0 },
    ],
  };
  const m = Q.build(p, 2026);
  assert.deepEqual(row(m, '팀'), ['팀', '-', '-', 'LG/KT', '-']);
  assert.deepEqual(row(m, 'IP'), ['IP', '-', '-', '16', '16']);
  assert.deepEqual(row(m, 'ERA'), ['ERA', '-', '-', '2.25', '2.25']);
  assert.deepEqual(row(m, 'K%'), ['K%', '-', '-', '20.0%', '20.0%']);
  assert.deepEqual(row(m, 'G'), ['G', '-', '-', '8', '8']);
});

test('build: 분모가 0 이면 비율은 -', () => {
  const p = { position: '투수', is_active: 1, pitcher_seasons: [{ season: 2026, player_team: 'SSG', innings_pitched: '0', total_batters_faced: 0, games: 1 }] };
  const m = Q.build(p, 2026);
  assert.deepEqual(row(m, 'ERA'), ['ERA', '-', '-', '-', '-']);
  assert.deepEqual(row(m, 'K%'), ['K%', '-', '-', '-', '-']);
  assert.deepEqual(row(m, 'G'), ['G', '-', '-', '1', '1']);
});

test('build: 기록이 전혀 없으면 통산까지 -', () => {
  const m = Q.build({ position: '내야수', is_active: 1, batter_seasons: [] }, 2026);
  assert.deepEqual(row(m, '리그'), ['리그', '-', '-', '-', '-']);
  assert.deepEqual(row(m, 'AVG'), ['AVG', '-', '-', '-', '-']);
});

test('buildFutures: 최근 3시즌을 오래된 순으로, 리그는 퓨처스, 빈 값은 -', () => {
  const seasons = [
    { season: 2026, team: '상무', W: 3, L: '', ERA: '2.10' },
    { season: 2025, team: '상무', W: 1, L: 2, ERA: '3.00' },
    { season: 2024, team: 'NC', W: 0, L: 0, ERA: '-' },
    { season: 2023, team: 'NC', W: 9, L: 9, ERA: '9.99' },
  ];
  const m = Q.buildFutures(seasons, 'pitcher');
  assert.equal(m.career, false);
  assert.deepEqual(m.head, ['시즌', '2024', '2025', '2026']);
  assert.deepEqual(row(m, '팀'), ['팀', 'NC', '상무', '상무']);
  assert.deepEqual(row(m, '리그'), ['리그', '퓨처스', '퓨처스', '퓨처스']);
  assert.deepEqual(row(m, 'L'), ['L', '0', '2', '-']);
  assert.deepEqual(m.rows.map(r => r[0]), ['팀', '리그', 'W', 'L', 'ERA', 'G', 'SV', 'HLD', 'IP', 'H', 'BB', 'SO']);
  assert.deepEqual(Q.buildFutures(seasons, 'batter').rows.map(r => r[0]),
    ['팀', '리그', 'G', 'PA', 'AB', 'R', 'H', 'HR', 'RBI', 'AVG', 'OBP', 'SLG']);
  assert.equal(Q.buildFutures([], 'batter'), null);
});

test('summary: 올 시즌 요약을 같은 모양으로', () => {
  const m = Q.summary(['G', 'AVG'], [12, '.301']);
  assert.deepEqual(m.head, ['시즌', '올해']);
  assert.deepEqual(m.rows, [['리그', '퓨처스'], ['G', '12'], ['AVG', '.301']]);
  assert.equal(m.career, false);
  assert.deepEqual(Q.summary(['G', 'HR'], [3]).rows[2], ['HR', '-']);
});

test('tableHtml: 라벨 칸·통산 칸 클래스, 글자 이스케이프', () => {
  const html = Q.tableHtml({ head: ['시즌', '2026', '통산'], rows: [['팀', 'A<B', '-']], career: true });
  assert.match(html, /^<div class="pa-ql-wrap"><table class="pa-ql">/);
  assert.match(html, /<th class="pa-ql-label">시즌<\/th><th>2026<\/th><th class="pa-ql-career">통산<\/th>/);
  assert.match(html, /<td class="pa-ql-label">팀<\/td><td>A&lt;B<\/td><td class="pa-ql-career">-<\/td>/);
  const noCareer = Q.tableHtml({ head: ['시즌', '2026'], rows: [['팀', 'NC']], career: false });
  assert.ok(!noCareer.includes('pa-ql-career'));
});

test('ageParts·dobText', () => {
  const today = new Date(2026, 9, 4); // 2026-10-04
  assert.deepEqual(Q.ageParts('19970217', today), { years: 29, months: 7 });
  assert.deepEqual(Q.ageParts(19871004, today), { years: 39, months: 0 });
  assert.deepEqual(Q.ageParts('19871005', today), { years: 38, months: 11 });
  assert.equal(Q.ageParts('', today), null);
  assert.equal(Q.ageParts(null, today), null);
  assert.equal(Q.ageParts('20301231', today), null);
  assert.equal(Q.dobText(19970217), '1997.02.17');
  assert.equal(Q.dobText('1997-02-17'), null);
  assert.equal(Q.dobText(undefined), null);
});
```

- [ ] **Step 3: 실패 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: FAIL — `quicklook.js` 가 없어 `ENOENT` 로 로더가 멈춥니다.

- [ ] **Step 4: 모듈 쓰기**

`dashboard_js/js/player-analytics/quicklook.js`:

```js
/*
 * 선수 분석 페이지의 Quick Look 표와 헤더 글자를 만드는 순수 함수입니다.
 * 화면(DOM)에는 손대지 않습니다.
 *
 * 합계·비율은 공용 TeamStats.metrics, 숫자 표시는 TeamStats.columns.fmt 를
 * 가져다 씁니다(호출할 때 읽으므로 불러오는 순서는 이 파일이 뒤면 됩니다).
 * 설계: docs/superpowers/specs/2026-10-04-player-analytics-fangraphs-header-design.md
 *
 * 원칙은 공용 모듈과 같습니다. 비율을 평균 내지 않고 합계에서 다시 셉니다.
 * 셀 수 없는 값은 '-' 입니다.
 */
(function (root) {
  'use strict';
  const PA = root.PlayerAnalytics = root.PlayerAnalytics || {};
  const TS = function () { return root.TeamStats; };

  // [라벨, 합계 키, 표시 형식]. 'pct' 는 소수 1자리 뒤에 % 를 붙입니다.
  const ROWS = {
    pit: [
      ['W', 'w', 'int'], ['L', 'l', 'int'], ['SV', 'sv', 'int'], ['HLD', 'hld', 'int'],
      ['G', 'g', 'int'], ['GS', 'gs', 'int'], ['IP', 'outs', 'ip'],
      ['K%', 'kpct', 'pct'], ['BB%', 'bbpct', 'pct'], ['ERA', 'era', 'f2'], ['WHIP', 'whip', 'f2'],
    ],
    bat: [
      ['G', 'g', 'int'], ['PA', 'pa', 'int'], ['HR', 'hr', 'int'], ['R', 'r', 'int'], ['RBI', 'rbi', 'int'],
      ['BB%', 'bbpct', 'pct'], ['K%', 'kpct', 'pct'],
      ['AVG', 'avg', 'avg3'], ['OBP', 'obp', 'avg3'], ['SLG', 'slg', 'avg3'], ['OPS', 'ops', 'avg3'],
    ],
  };

  // 퓨처스 Quick Look 줄입니다. 퓨처스 응답의 칸 이름 그대로입니다.
  // wOBA·wRC+ 는 2군에 타석 단위 자료가 없어 만들 수 없습니다.
  const FUT = {
    batter: ['G', 'PA', 'AB', 'R', 'H', 'HR', 'RBI', 'AVG', 'OBP', 'SLG'],
    pitcher: ['W', 'L', 'ERA', 'G', 'SV', 'HLD', 'IP', 'H', 'BB', 'SO'],
  };

  function kindOf(player) {
    return player && player.position === '투수' ? 'pit' : 'bat';
  }

  function seasonRows(player, kind) {
    return (kind === 'pit' ? player.pitcher_seasons : player.batter_seasons) || [];
  }

  /** 최근 3시즌입니다. 현역은 올해 기준, 은퇴는 마지막 활동 시즌 기준입니다. */
  function pickSeasons(player, thisYear) {
    const ys = [].concat(player.pitcher_seasons || [], player.batter_seasons || [])
      .map(function (s) { return s.season; })
      .filter(function (y) { return typeof y === 'number'; });
    const last = ys.length ? Math.max.apply(null, ys) : thisYear;
    const a = player.is_active ? thisYear : last;
    return [a - 2, a - 1, a];
  }

  /**
   * 행 여러 개를 한 덩어리로 더하고 비율을 다시 셉니다. 행이 없으면 null.
   * 공용 합계 함수는 player_team 별로 묶으므로 팀을 같은 값으로 바꾼 사본을
   * 넘깁니다. 출장 경기(games)는 공용 합계 키에 없어 따로 더합니다.
   */
  function total(rows, kind) {
    if (!rows || !rows.length) return null;
    const M = TS().metrics;
    const flat = rows.map(function (r) { return Object.assign({}, r, { player_team: '_' }); });
    const t = (kind === 'pit' ? M.sumPitching(flat) : M.sumBatting(flat))._;
    t.g = rows.reduce(function (s, r) { return s + M.num(r.games); }, 0);
    return Object.assign(t, kind === 'pit' ? M.pitchingRates(t) : M.battingRates(t));
  }

  function teamsOf(rows) {
    const out = [];
    rows.forEach(function (r) {
      if (r.player_team && out.indexOf(r.player_team) === -1) out.push(r.player_team);
    });
    return out.length ? out.join('/') : '-';
  }

  function cell(v, kind) {
    const fmt = TS().columns.fmt;
    if (kind === 'pct') {
      const s = fmt(v, 'f1');
      return s === '-' ? s : s + '%';
    }
    return fmt(v, kind);
  }

  /** 1군 Quick Look 입니다. 칸은 최근 3시즌 + 통산입니다. */
  function build(player, thisYear) {
    const kind = kindOf(player);
    const all = seasonRows(player, kind);
    const cols = pickSeasons(player, thisYear).map(function (y) {
      const rs = all.filter(function (s) { return s.season === y; });
      return { head: String(y), team: rs.length ? teamsOf(rs) : '-', level: rs.length ? '1군' : '-', t: total(rs, kind) };
    });
    cols.push({ head: '통산', team: '-', level: all.length ? '1군' : '-', t: total(all, kind) });
    const rows = [
      ['팀'].concat(cols.map(function (c) { return c.team; })),
      ['리그'].concat(cols.map(function (c) { return c.level; })),
    ];
    ROWS[kind].forEach(function (d) {
      rows.push([d[0]].concat(cols.map(function (c) { return c.t ? cell(c.t[d[1]], d[2]) : '-'; })));
    });
    return { head: ['시즌'].concat(cols.map(function (c) { return c.head; })), rows: rows, career: true };
  }

  function text(x) {
    return x === null || x === undefined || x === '' ? '-' : String(x);
  }

  /** 퓨처스 Quick Look 입니다. 응답은 최신 시즌이 앞이고, 통산 칸은 없습니다. */
  function buildFutures(seasons, kind) {
    const use = (seasons || []).slice(0, 3).reverse();
    if (!use.length) return null;
    const metrics = FUT[kind] || FUT.batter;
    const rows = [
      ['팀'].concat(use.map(function (s) { return text(s.team); })),
      ['리그'].concat(use.map(function () { return '퓨처스'; })),
    ];
    metrics.forEach(function (m) {
      rows.push([m].concat(use.map(function (s) { return text(s[m]); })));
    });
    return { head: ['시즌'].concat(use.map(function (s) { return String(s.season); })), rows: rows, career: false };
  }

  /** 연도별 기록이 없는 퓨처스 선수의 올 시즌 요약입니다. */
  function summary(columns, cells) {
    const rows = [['리그', '퓨처스']];
    (columns || []).forEach(function (c, i) { rows.push([c, text(cells && cells[i])]); });
    return { head: ['시즌', '올해'], rows: rows, career: false };
  }

  function esc(s) {
    return String(s).replace(/[&<>"]/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c];
    });
  }

  /** Model 을 촘촘한 세로 표 HTML 로 바꿉니다. 첫 칸은 라벨, 통산 칸은 강조입니다. */
  function tableHtml(m) {
    const last = m.head.length - 1;
    const one = function (x, i, tag) {
      const cls = i === 0 ? 'pa-ql-label' : (m.career && i === last ? 'pa-ql-career' : '');
      return '<' + tag + (cls ? ' class="' + cls + '"' : '') + '>' + esc(x) + '</' + tag + '>';
    };
    return '<div class="pa-ql-wrap"><table class="pa-ql"><thead><tr>'
      + m.head.map(function (x, i) { return one(x, i, 'th'); }).join('')
      + '</tr></thead><tbody>'
      + m.rows.map(function (r) {
        return '<tr>' + r.map(function (x, i) { return one(x, i, 'td'); }).join('') + '</tr>';
      }).join('')
      + '</tbody></table></div>';
  }

  /** 만 나이(년·개월)입니다. 생일은 YYYYMMDD. 못 읽거나 미래면 null. */
  function ageParts(birthday, today) {
    const s = String(birthday === null || birthday === undefined ? '' : birthday);
    if (!/^\d{8}$/.test(s)) return null;
    const y = Number(s.slice(0, 4)), mo = Number(s.slice(4, 6)), d = Number(s.slice(6, 8));
    let months = (today.getFullYear() - y) * 12 + (today.getMonth() + 1 - mo);
    if (today.getDate() < d) months--;
    if (months < 0) return null;
    return { years: Math.floor(months / 12), months: months % 12 };
  }

  /** 생년월일 글자(YYYY.MM.DD)입니다. YYYYMMDD 가 아니면 null. */
  function dobText(birthday) {
    const s = String(birthday === null || birthday === undefined ? '' : birthday);
    return /^\d{8}$/.test(s) ? s.slice(0, 4) + '.' + s.slice(4, 6) + '.' + s.slice(6, 8) : null;
  }

  const api = { ROWS, FUT, kindOf, pickSeasons, total, build, buildFutures, summary, tableHtml, ageParts, dobText };
  PA.quicklook = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 5: 통과 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 11개 모두 PASS. 반올림 경계로 한 자리가 다르면 Python 이 아니라 JS `toFixed` 결과가 기준입니다. 이때는 원천 합계를 손으로 다시 셈해 확인한 뒤 기대값을 고치고, 고친 이유를 보고서에 적습니다.

- [ ] **Step 6: 커밋**

```bash
cd "C:/Users/김승곤/Desktop/b_project"
git add dashboard_js/js/player-analytics/quicklook.js
git commit -m "feat(player-analytics): Quick Look 표·나이 계산 순수 모듈" -- dashboard_js/js/player-analytics/quicklook.js
```

---

### Task 2: 헤더·카드 화면 연결

**Files:**
- Create: `dashboard_js/css/player-analytics.css`
- Modify: `dashboard_js/pages/player-analytics.html` (머리 22행 근처, 마크업 82~97행, `renderHeaderBar` 429~481행, 퓨처스 표 함수 594~629행, `loadFuturesPlayer` 664~703행, `loadPlayerInfo` 772~893행, 스크립트 175~176행)
- Test: `C:/tmp/bstats-player-analytics-check/tests/page-html.test.js`

**Interfaces:**
- Consumes: Task 1 의 `PlayerAnalytics.quicklook.{build, buildFutures, summary, tableHtml, ageParts, dobText}`. 페이지 전역 `formatThrowBat`, `formatMoney`, `isForeignPlayer`, `firstTeamBadge`, `createLoadingSpinner`, `createErrorMessage`, `createTable`(components.js·페이지 안).
- Produces: 화면. 요소 id `player-header-bar`, `player-card`, `player-stats` 는 그대로 남습니다(로딩 스피너·테마 코드가 씁니다).

- [ ] **Step 1: 실패하는 구조 시험 쓰기**

`C:/tmp/bstats-player-analytics-check/tests/page-html.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { REPO_JS } = require('./_load');

const html = fs.readFileSync(path.join(REPO_JS, '..', 'pages', 'player-analytics.html'), 'utf8');

test('스크립트 순서: 공용 통계 → quicklook → 인라인', () => {
  const srcs = [...html.matchAll(/<script src="([^"]+)"/g)].map(m => m[1]);
  assert.deepEqual(srcs, [
    '../js/config.js', '../js/theme-toggle.js', '../js/nav.js',
    '../js/api.js', '../js/components.js',
    '../js/stats/metrics.js', '../js/stats/columns.js', '../js/player-analytics/quicklook.js',
  ]);
  assert.ok(html.indexOf('player-analytics/quicklook.js') < html.indexOf('<script>\n'), '인라인 스크립트보다 먼저');
});

test('CSS: style.css 바로 뒤에 player-analytics.css', () => {
  assert.match(html, /href="\.\.\/css\/style\.css">\r?\n    <link rel="stylesheet" href="\.\.\/css\/player-analytics\.css">/);
});

test('카드 줄: Quick Look 이 먼저, 프로필이 다음, id 유지', () => {
  const ql = html.indexOf('class="pa-card pa-card--ql"');
  const prof = html.indexOf('class="pa-card pa-card--profile"');
  assert.ok(ql > 0 && prof > ql);
  assert.match(html, /<div class="pa-card-body" id="player-stats"><\/div>/);
  assert.match(html, /<div class="pa-card-body" id="player-card"><\/div>/);
  assert.match(html, /id="player-header-bar" class="player-header-bar pa-hdr fade-in"/);
});

test('옛 표 코드가 빠지고 새 함수를 씀', () => {
  for (const gone of ['futuresSeasonTable', 'FUT_SEASON_METRICS', 'verticalTable(', '시즌별 성적', '상세 프로필', 'header-bar-info-group']) {
    assert.ok(!html.includes(gone), gone);
  }
  for (const used of ['quicklook.build(', 'quicklook.buildFutures(', 'quicklook.summary(', 'quicklook.tableHtml(', 'quicklook.ageParts(', 'pa-hdr-name', 'profileHtml(']) {
    assert.ok(html.includes(used), used);
  }
});
```

- [ ] **Step 2: 실패 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: page-html 4개 FAIL, quicklook 11개 PASS.

- [ ] **Step 3: CSS 파일 쓰기**

`dashboard_js/css/player-analytics.css`:

```css
/*
 * 선수 분석 머리 부분(헤더·Quick Look·프로필)입니다. 팬그래프 선수 페이지 모양을 따릅니다.
 * 설계: docs/superpowers/specs/2026-10-04-player-analytics-fangraphs-header-design.md
 *
 * style.css 의 옛 .header-bar-*·.player-card·.stats-card 규칙은 건드리지 않습니다.
 * 이 파일은 새 클래스(pa-hdr-*, pa-card*, pa-ql*, pa-prof*)만 씁니다.
 */

/* ---------- 헤더 ---------- */
.player-header-bar.pa-hdr { align-items: stretch; min-height: 0; padding: 0; }
.pa-hdr-photo { flex-shrink: 0; width: 84px; min-height: 96px; overflow: hidden; }
.pa-hdr-photo img { width: 100%; height: 100%; object-fit: cover; display: block; }
.pa-hdr-info { flex: 1 1 auto; min-width: 0; padding: 0.75rem 1.1rem; display: flex; flex-direction: column; justify-content: center; gap: 0.2rem; }
.pa-hdr-top { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.2rem 0.6rem; }
.pa-hdr-name { font-size: 1.6rem; font-weight: 700; line-height: 1.2; color: var(--text-primary); }
.pa-hdr-num { font-size: 1rem; font-weight: 600; color: var(--text-muted); }
.pa-hdr-team { font-size: 1rem; color: var(--text-secondary); display: inline-flex; align-items: center; }
.pa-hdr-data { display: flex; flex-wrap: wrap; gap: 0.1rem 1.25rem; font-size: 0.92rem; color: var(--text-primary); }
.pa-hdr-dob { font-size: 0.85rem; color: var(--text-secondary); }
.pa-hdr-pos { flex-shrink: 0; align-self: center; margin: 0 1.25rem; padding: 0.4rem 0.9rem; font-size: 1rem; font-weight: 800; color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; white-space: nowrap; }
.theme-applied .pa-hdr-name { color: #fff !important; }
.theme-applied .pa-hdr-num,
.theme-applied .pa-hdr-team,
.theme-applied .pa-hdr-data { color: rgba(255, 255, 255, 0.85) !important; }
.theme-applied .pa-hdr-dob { color: rgba(255, 255, 255, 0.7) !important; }
.theme-applied .pa-hdr-pos { color: #fff !important; background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.25); }
@media (max-width: 640px) {
    .pa-hdr-photo { width: 64px; min-height: 84px; }
    .pa-hdr-info { padding: 0.6rem 0.75rem; }
    .pa-hdr-name { font-size: 1.3rem; }
    .pa-hdr-data { font-size: 0.85rem; gap: 0.1rem 0.8rem; }
    .pa-hdr-pos { margin: 0 0.6rem; padding: 0.3rem 0.55rem; font-size: 0.85rem; }
}

/* ---------- 카드(팬그래프 module card) ---------- */
.pa-card { background: var(--bg-card); border: 1px solid var(--border-color); border-radius: 8px; overflow: hidden; display: flex; flex-direction: column; min-width: 0; }
.pa-card--ql { grid-column: span 2; }
.pa-card-tabs { display: flex; border-bottom: 1px solid var(--border-color); background: var(--bg-secondary); }
.pa-card-tab { padding: 0.55rem 1rem; font-size: 0.9rem; font-weight: 700; color: var(--primary); border-bottom: 2px solid var(--primary); margin-bottom: -1px; }
.pa-card-body { flex: 1 1 auto; padding: 0.5rem 0.75rem 0.75rem; overflow-x: auto; }
/* style.css 의 #player-card { height: 100%; overflow: hidden } 을 이 카드 안에서만 풉니다. */
#player-card.pa-card-body { height: auto; overflow: visible; }
@media (max-width: 1024px) {
    .pa-card--ql, .pa-card--profile { grid-column: 1 / -1; }
}

/* ---------- Quick Look 표 ---------- */
.pa-ql-wrap { overflow-x: auto; }
.pa-ql { width: 100%; border-collapse: collapse; font-size: 0.85rem; font-variant-numeric: tabular-nums; }
.pa-ql th, .pa-ql td { padding: 0.3rem 0.6rem; text-align: right; border-bottom: 1px solid var(--border-color); white-space: nowrap; color: var(--text-primary); }
.pa-ql thead th { font-weight: 700; border-bottom: 2px solid var(--border-color); }
.pa-ql .pa-ql-label { text-align: left; font-weight: 600; color: var(--text-secondary); }
.pa-ql .pa-ql-career { font-weight: 700; background: rgba(59, 130, 246, 0.08); }
.pa-ql tbody tr:last-child td { border-bottom: 0; }
.pa-card-body .futures-stat-head { margin-bottom: 0.4rem; }

/* ---------- 프로필 ---------- */
.pa-prof { margin: 0; }
.pa-prof-row { display: grid; grid-template-columns: 7.5rem minmax(0, 1fr); gap: 0.5rem; padding: 0.45rem 0.1rem; border-bottom: 1px solid var(--border-color); font-size: 0.88rem; }
.pa-prof-row:last-child { border-bottom: 0; }
.pa-prof dt { color: var(--text-secondary); font-weight: 600; }
.pa-prof dd { margin: 0; color: var(--text-primary); overflow-wrap: anywhere; }
```

- [ ] **Step 4: 머리에 CSS·스크립트 넣기**

`pages/player-analytics.html` 22행 바로 아래:

```html
    <link rel="stylesheet" href="../css/style.css">
    <link rel="stylesheet" href="../css/player-analytics.css">
```

175~176행(`api.js`, `components.js`) 아래:

```html
    <script src="../js/api.js"></script>
    <script src="../js/components.js"></script>
    <script src="../js/stats/metrics.js"></script>
    <script src="../js/stats/columns.js"></script>
    <script src="../js/player-analytics/quicklook.js"></script>
```

- [ ] **Step 5: 마크업 바꾸기**

82~84행 헤더 여는 태그를 `<div id="player-header-bar" class="player-header-bar pa-hdr fade-in">` 로 바꿉니다.

86~97행(주석 두 줄, `#player-card`, `.stats-card`)을 아래로 바꿉니다. `player-details-grid` 여는 줄과 그 아래 퓨처스·Standard 블록은 그대로 둡니다.

```html
            <!-- 팬그래프 선수 페이지의 카드 줄입니다. 왼쪽 Quick Look(2칸),
                 오른쪽 프로필(1칸). 뉴스 카드는 수집을 안 해서 없습니다. -->
            <div class="player-details-grid fade-in">
                <div class="pa-card pa-card--ql">
                    <div class="pa-card-tabs"><span class="pa-card-tab">Quick Look</span></div>
                    <div class="pa-card-body" id="player-stats"></div>
                </div>

                <div class="pa-card pa-card--profile">
                    <div class="pa-card-tabs"><span class="pa-card-tab">프로필</span></div>
                    <div class="pa-card-body" id="player-card"></div>
                </div>
```

- [ ] **Step 6: 헤더 함수 바꾸기**

`renderHeaderBar` 의 사진 변수 계산(`PHOTO_PLACEHOLDER`~`backNum`)은 그대로 두고, 나이 계산 블록(`// 정확한 나이 계산` 부터 그 `if` 끝까지)과 `return` 템플릿 전체를 아래로 바꿉니다. 함수 위 주석(1군·퓨처스가 같은 함수)은 그대로 둡니다.

```js
            const Q = window.PlayerAnalytics.quicklook;
            const age = Q.ageParts(player.birthday, new Date());
            const dob = Q.dobText(player.birthday);
            const team = (player.is_active && (player.team_name || player.team_id))
                ? (player.team_name || player.team_id) : '-';

            // 팬그래프 헤더 모양입니다. 이름·팀 / 나이·투타·키몸무게 / 생년월일.
            // 포지션만 오른쪽 끝입니다.
            return `
                    <div class="pa-hdr-photo">
                        <img src="${imageUrl}" alt="${player.player_name}" data-local="${localImg}"
                             onerror="var l=this.getAttribute('data-local'); if(l && this.src.indexOf('player_photos')===-1){this.src=l;} else {this.onerror=null; this.src='${PHOTO_PLACEHOLDER}';}">
                    </div>
                    <div class="pa-hdr-info">
                        <div class="pa-hdr-top">
                            <div class="pa-hdr-name">${player.player_name}</div>
                            ${player.is_active ? '<span class="pa-hdr-num">No.' + backNum + '</span>' : ''}
                            <span class="pa-hdr-team">${team}${firstTeamBadge(player)}</span>
                        </div>
                        <div class="pa-hdr-data">
                            <span>나이: ${age ? age.years + '세' : '-'}</span>
                            <span>투타: ${formatThrowBat(player.throw, player.bat)}</span>
                            <span>${player.height ? player.height + 'cm' : '-'} / ${player.weight ? player.weight + 'kg' : '-'}</span>
                        </div>
                        ${dob ? `<div class="pa-hdr-dob">생년월일: ${dob}${age ? ` (만 ${age.years}세 ${age.months}개월)` : ''}</div>` : ''}
                    </div>
                    <div class="pa-hdr-pos">${player.position || '-'}</div>
                `;
```

- [ ] **Step 7: 프로필 도우미 넣고 퓨처스 옛 표 함수 빼기**

594~629행(`verticalTable` 주석·함수, `FUT_SEASON_METRICS` 주석·상수, `futuresSeasonTable` 주석·함수)을 지우고 그 자리에 넣습니다:

```js
        /** 프로필 카드 본문입니다. items = [[라벨, 값], ...] */
        function profileHtml(items) {
            return '<dl class="pa-prof">' + items.map(([k, v]) =>
                `<div class="pa-prof-row"><dt>${k}</dt><dd>${v}</dd></div>`).join('') + '</dl>';
        }
```

- [ ] **Step 8: 퓨처스 화면 연결**

`loadFuturesPlayer` 안 `cardDiv.innerHTML = \`…상세 프로필…\`;` 블록을 바꿉니다:

```js
            cardDiv.innerHTML = profileHtml([
                ['연봉', formatMoney(player.salary, 'KRW')],
                ['지명순위', f.draft || '-'],
                ['출신교', f.career || '-'],
            ]);
```

이어지는 `let html = …` 부터 `statsDiv.innerHTML = html;` 까지를 바꿉니다:

```js
            // 연도별 기록이 있으면 최근 3시즌, 없으면 올 시즌 요약입니다.
            const Q = window.PlayerAnalytics.quicklook;
            const seasons = f.seasons || [];
            const season = f.season || { columns: [], cells: [] };
            const model = seasons.length ? Q.buildFutures(seasons, f.kind)
                : (season.cells.length ? Q.summary(season.columns, season.cells) : null);
            let html = '<div class="futures-stat-head">'
                + '<span class="futures-badge">퓨처스(2군)</span>'
                + '<span class="futures-note">'
                + (seasons.length ? '2010년부터의 기록입니다.' : '올 시즌 기록입니다.')
                + '</span></div>';
            html += model ? Q.tableHtml(model) : '<p class="text-muted mt-2">퓨처스 기록이 없습니다.</p>';
            statsDiv.innerHTML = html;
```

- [ ] **Step 9: 1군 화면 연결**

`loadPlayerInfo` 안 `cardDiv.innerHTML = \`…상세 프로필…\`;` 블록을 바꿉니다:

```js
                const money = (v) => formatMoney(v, isForeign ? 'USD' : 'KRW');
                const draft = (player.draft_year || '')
                    + (player.draft_year && player.draft_order ? ' / ' : '')
                    + (player.draft_order || '');
                cardDiv.innerHTML = profileHtml([
                    ['연봉', money(player.salary)],
                    ['입단 계약금', money(player.signing_bonus)],
                    ['입단년도 / 지명순위', draft || '-'],
                    ['경력', player.career || '-'],
                ]);
```

`// Stats Table` 주석부터 타자 `else { … statsDiv.innerHTML = createTable(headers, rows); }` 닫는 괄호까지(최근 3시즌 계산·투수/타자 전치 표 전부)를 바꿉니다. `isPitcher` 는 아래 Standard 표가 쓰므로 남깁니다:

```js
                // Quick Look: 최근 3시즌 + 통산. 계산은 quicklook.js 입니다.
                const isPitcher = player.position === '투수';
                const Q = window.PlayerAnalytics.quicklook;
                statsDiv.innerHTML = Q.tableHtml(Q.build(player, new Date().getFullYear()));
```

- [ ] **Step 10: 시험 통과 확인**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 15개 모두 PASS.

`grep -n "formatIP\|createTable" dashboard_js/pages/player-analytics.html` 로 남은 사용처를 확인합니다. `formatIP` 는 지운 투수 표에서만 쓰였으므로 나오지 않아야 합니다(components.js 정의는 남김). `createTable` 은 최근 경기·Standard·Advanced 에 남아 있어야 합니다.

- [ ] **Step 11: 브라우저 콘솔 오류 확인**

미리보기 `http://127.0.0.2:8765/pages/player-analytics.html?id=65933` 를 헤드리스로 열어 DOM 을 덤프하고 `pa-ql`·`pa-hdr-name` 이 있는지 봅니다(서버를 새로 띄우지 않음):

```powershell
$edge = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
$a = @('--headless=new','--no-sandbox','--disable-gpu','--virtual-time-budget=10000','--user-data-dir=C:/tmp/bstats-player-analytics-check/ud_dom1','--dump-dom','http://127.0.0.2:8765/pages/player-analytics.html?id=65933')
Start-Process -FilePath $edge -ArgumentList $a -Wait -NoNewWindow -RedirectStandardOutput C:\tmp\bstats-player-analytics-check\dom_65933.html -RedirectStandardError C:\tmp\bstats-player-analytics-check\dom_65933.err
Select-String -Path C:\tmp\bstats-player-analytics-check\dom_65933.html -Pattern 'pa-ql-career','pa-hdr-name','845 2/3' | Select-Object -First 5
```

Expected: 세 패턴 모두 나옵니다.

- [ ] **Step 12: 커밋**

```bash
cd "C:/Users/김승곤/Desktop/b_project"
git add dashboard_js/css/player-analytics.css dashboard_js/pages/player-analytics.html
git commit -m "feat(player-analytics): 헤더·Quick Look·프로필을 팬그래프 모양으로" -- dashboard_js/css/player-analytics.css dashboard_js/pages/player-analytics.html
```

---

### Task 3: 화면 확인(PNG)과 마무리

**Files:**
- 고치는 파일 없음(확인에서 문제가 나오면 Task 2 파일만 고치고 따로 커밋)

- [ ] **Step 1: 캡처**

헤드리스 Edge 로 아래를 1789×1400 으로 캡처합니다. 호출마다 다른 `--user-data-dir`, `Start-Process -Wait -NoNewWindow`, `--virtual-time-budget=10000`. 출력은 `C:/tmp/bstats-player-analytics-check/shots/` 에 둔 뒤 바탕화면(`C:/Users/김승곤/Desktop/`)에 `pa_<이름>.png` 로 복사합니다.

| 이름 | 주소 |
|---|---|
| pitcher | `pages/player-analytics.html?id=65933` |
| batter | `pages/player-analytics.html?id=76232` |
| futures | `pages/player-analytics.html?id=65933&mode=futures` |
| retired | 은퇴 선수 1명(`is_active` 0). 검색창에 이름을 넣어 찾지 말고, 픽스처가 없으면 `/players/<id>` 를 한 번만 불러 확인 |
| dark | pitcher 와 같은 주소. 다크 모드는 `theme-toggle.js` 가 읽는 저장 키를 확인해 `--user-data-dir` 프로필에 넣거나, 확인용 사본 HTML 에 `data-theme="dark"` 를 넣어 캡처 |
| mobile | pitcher 와 같은 주소, 휴대폰 크기. `C:/tmp/bstats-team-stats-check/mobile_shot.mjs` 방식(CDP 기기 흉내)을 씁니다. 헤드리스 창 크기만 줄이면 휴대폰 화면이 안 나옵니다 |

- [ ] **Step 2: 눈으로 확인할 것**

- 헤더: 이름·등번호·팀·1군 배지가 한 줄, 나이·투타·키몸무게 한 줄, 생년월일(만 나이) 한 줄, 포지션 오른쪽 끝. 팀 색 배경에서 글자가 흰색 계열로 읽힘.
- Quick Look 이 왼쪽 2/3, 프로필이 오른쪽 1/3. 두 카드 높이 같음. 빈 칸이 크게 남지 않음.
- 통산 칸 강조, 숫자 오른쪽 정렬, IP `14 1/3` 형식.
- 퓨처스: 리그 줄 `퓨처스`, 통산 칸 없음, 안내 문구가 카드 안.
- 은퇴: 소속 `-`, 등번호 없음, 중립색.
- 다크 모드: 카드 배경·글자 대비 정상.
- 휴대폰: 헤더 글자가 겹치지 않고, 카드가 위아래로 쌓이며, 가로 넘침이 없음(표는 카드 안에서만 가로 스크롤).
- 아래 Standard·Advanced·구종 카드가 전과 같음.

- [ ] **Step 3: 전체 시험 다시 실행**

Run: `node --test "C:/tmp/bstats-player-analytics-check/tests/*.test.js"`
Expected: 15개 PASS.

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: 기존 시험이 그대로 PASS(공용 파일을 안 고쳤다는 확인).

- [ ] **Step 4: evan 에게 보고**

바탕화면 PNG 이름과 `git log origin/main..main --oneline` 을 보여 줍니다. push·배포는 허락을 받은 뒤 따로 합니다(push 전 `git pull --rebase`).
