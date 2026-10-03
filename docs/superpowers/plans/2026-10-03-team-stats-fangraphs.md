# 팀 통계 팬그래프 수준 개편 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bstats 팀 통계 페이지(`dashboard_js/pages/team-stats.html`)를 묶음 탭·고급 지표(wOBA·wRC+·FIP·지수)·팀 성적 탭·리그 평균 행·CSV·주소 저장을 갖춘 페이지로 바꿉니다.

**Architecture:** 계산(metrics)·칸 정의(columns)·데이터 받기(data)·표 그리기(table)·팀 성적 표(record)·조립(page)을 `dashboard_js/js/team-stats/` 의 여섯 파일로 나눕니다. 앞의 다섯 파일은 DOM 을 건드리지 않는 순수 함수라 Node 로 검증합니다. page.js 만 DOM 을 다루고, 화면은 헤드리스 Edge 캡처(PNG)로 확인합니다.

**Tech Stack:** 순수 JavaScript(빌드 도구 없음, `<script>` 태그), Node 24 내장 테스트(`node --test`), Python `http.server` 미리보기, 헤드리스 Edge 캡처.

**설계 문서:** `C:/Users/김승곤/Desktop/b_project/docs/superpowers/specs/2026-10-03-team-stats-fangraphs-design.md`

## Global Constraints

- 저장소: `C:/Users/김승곤/Desktop/b_project` (브랜치 `main`, 다른 세션과 폴더를 같이 씀).
- **고칠 수 있는 곳은 `dashboard_js/` 안뿐입니다.** `src/`, `crawler/`, `migration/`, `test/`, `tests/`, `data_collection/`, `park_factors/`, `wrangler.toml`, `package*.json`, `.github/` 는 읽기만 합니다.
- **git:** 브랜치를 바꾸지 않습니다. `git add -A`, `git add .`, `git commit -a`, `git stash`, `git reset`, `git restore`, `git checkout --` 를 쓰지 않습니다. 커밋 전에 `git status --short` 를 보고, 자기 파일만 `git add dashboard_js/<파일>` 로 고릅니다. 다른 변경(예: `src/`)이 보이면 옆 세션 것이니 그대로 둡니다.
- 커밋 메시지는 `feat(team-stats): 한국어 설명` 형식이고, 끝에 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` 를 붙입니다.
- **push·배포는 하지 않습니다.** evan 이 건마다 허락합니다.
- **D1 에 쓰지 않습니다.** 데이터 확인은 배포된 API(`https://kbo-api.bstats-baseball.workers.dev`)를 부르되, 같은 주소를 반복해서 부르지 않습니다. 시험 데이터는 `C:/tmp/bstats-team-stats-check/fixtures/` 에 이미 받아 두었습니다.
- 검증 스크립트는 저장소 밖 `C:/tmp/bstats-team-stats-check/tests/` 에 둡니다.
- 미리보기는 `127.0.0.2:8765` 로 띄웁니다. `localhost`·`127.0.0.1` 로 열면 `js/config.js` 가 API 를 `localhost:8000` 으로 돌려 데이터가 안 나옵니다.
- 캡처는 헤드리스 Edge(`--headless=new --screenshot`)로 하고, 호출마다 `--user-data-dir` 를 다르게 줍니다. 결과 PNG 는 바탕화면(`C:/Users/김승곤/Desktop/`)에 둡니다.
- 사용자에게 보이는 글은 `습니다/합니다` 정중체, 짧은 문장으로 씁니다. 이모지는 쓰지 않습니다.
- API 응답이 이상하면(빈 목록, `detail`·`error` 필드) 화면에서 가리지 말고 표 위 알림으로 보여 줍니다. 계산할 수 없는 값은 0 이 아니라 `null`(화면 '-')입니다.

## 파일 구조

| 파일 | 책임 | 의존 |
|---|---|---|
| `dashboard_js/js/team-stats/metrics.js` | 숫자 읽기, 팀 합산, 비율, wOBA·wRC+·OPS+, FIP·ERA-·FIP-, 순위표·피타고리안, 경기 결과 집계, 기간별 변환 | 없음 |
| `dashboard_js/js/team-stats/columns.js` | 탭별 칸 정의(이름·형식·설명·계산식·시작 연도·기간별 가능 여부·지수 방향), 묶음 목록, 값 형식 | 없음 |
| `dashboard_js/js/team-stats/data.js` | API 받기, 이상 응답 판정, sessionStorage | 없음 |
| `dashboard_js/js/team-stats/table.js` | 정렬, 표 HTML, 리그 평균 행, 지수 색, 설명 창 HTML, 지표 설명 목록, CSV | columns |
| `dashboard_js/js/team-stats/record.js` | 상대 전적·월별 승률 HTML | table(esc) |
| `dashboard_js/js/team-stats/page.js` | 상태·주소, 화면 조립, 이벤트 | 위 다섯 + components.js |
| `dashboard_js/pages/team-stats.html` | 뼈대 HTML·CSS, 스크립트 불러오기 | 위 여섯 |

모든 모듈은 같은 틀을 씁니다(브라우저 전역 `window.TeamStats.<이름>`, Node `module.exports`):

```js
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  // ...
  TS.metrics = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

검증 폴더(저장소 밖):

```
C:/tmp/bstats-team-stats-check/
  fixtures/   batters_2025.json pitchers_2025.json games_2025.json
              db_kbo_woba_weights_by_season.json db_self_park_factor.json
              db_team_stadium_by_season.json db_team_season_rank.json   (이미 있음)
  tests/      _load.js, *.test.js
  preview.py  미리보기 서버(Task 10)
  shot.sh     캡처 스크립트(Task 10)
```

테스트 실행: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`

---

### Task 1: 검증 틀과 계산 기초(숫자·이닝·타격 합산·타격 비율)

**Files:**
- Create: `C:/tmp/bstats-team-stats-check/tests/_load.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/metrics.basic.test.js`
- Create: `dashboard_js/js/team-stats/metrics.js`

**Interfaces:**
- Produces: `TeamStats.metrics` = `{ num(v)→number, div(a,b)→number|null, ipOuts(text)→int, BAT_SUM, BAT_KEYS, sumBatting(rows)→{team: totals}, battingRates(t)→{single,avg,obp,slg,ops,iso,babip,kpct,bbpct,bbk,goao} }`. 합계 키: `pa ab r h d2 d3 hr tb rbi bb ibb hbp so sf sh gdp multi xbh go ao gw`. 이후 Task 에서 같은 파일에 함수를 더합니다.

- [ ] **Step 1: 검증 틀 만들기**

`C:/tmp/bstats-team-stats-check/tests/_load.js`:

```js
// 저장소의 팀 통계 모듈과 시험 데이터를 불러옵니다.
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const REPO_JS = 'C:/Users/김승곤/Desktop/b_project/dashboard_js/js/team-stats';
const FIX = path.join(__dirname, '..', 'fixtures');

// 저장소 package.json 이 "type": "module" 이라, require 로 부르면 Node 가
// 이 파일들을 ES 모듈로 읽어 아무것도 내보내지 않습니다. 그래서 브라우저처럼
// 일반 스크립트로 실행하고, 전역 TeamStats 에 붙은 모듈을 꺼냅니다.
// 파일 이름을 .cjs 로 바꾸지 않습니다(브라우저가 .js 로 불러옵니다).
function load(name) {
  const file = path.join(REPO_JS, name + '.js');
  vm.runInThisContext(fs.readFileSync(file, 'utf8'), { filename: file });
  return globalThis.TeamStats[name];
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

module.exports = { load, fixture, refs, near };
```

- [ ] **Step 2: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.basic.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture, near } = require('./_load');
const M = load('metrics');

test('num: 문자열·빈값·글자를 숫자로', () => {
  assert.equal(M.num('12'), 12);
  assert.equal(M.num(''), 0);
  assert.equal(M.num(null), 0);
  assert.equal(M.num(undefined), 0);
  assert.equal(M.num('abc'), 0);
});

test('div: 분모가 0 이하이거나 숫자가 아니면 null', () => {
  assert.equal(M.div(1, 4), 0.25);
  assert.equal(M.div(1, 0), null);
  assert.equal(M.div(1, undefined), null);
  assert.equal(M.div(NaN, 3), null);
});

test('ipOuts: 이닝 글자를 아웃 수로(분수만 있는 이닝 포함)', () => {
  assert.equal(M.ipOuts('81 1/3'), 244);
  assert.equal(M.ipOuts('81 2/3'), 245);
  assert.equal(M.ipOuts('7'), 21);
  assert.equal(M.ipOuts('2/3'), 2);
  assert.equal(M.ipOuts('1/3'), 1);
  assert.equal(M.ipOuts(''), 0);
  assert.equal(M.ipOuts(null), 0);
});

test('sumBatting: 팀별로 더하고 single 칸은 안타(H)로 읽음', () => {
  const rows = [
    { player_team: 'A', plate_appearance: '10', at_bat: 8, single: 3, double: 1, triple: 0, home_run: 1, total_bases: 7, base_on_balls: 2, hit_by_pitch: 0, sacrifice_fly: 0, strikeout: 2, run: 1 },
    { player_team: 'A', plate_appearance: 5, at_bat: 5, single: 1, double: 0, triple: 0, home_run: 0, total_bases: 1, base_on_balls: 0, hit_by_pitch: 0, sacrifice_fly: 0, strikeout: 1, run: 0 },
    { player_team: '', plate_appearance: 99 },
  ];
  const t = M.sumBatting(rows);
  assert.deepEqual(Object.keys(t), ['A']);
  assert.equal(t.A.team, 'A');
  assert.equal(t.A.pa, 15);
  assert.equal(t.A.h, 4);
  assert.equal(t.A.tb, 8);
  assert.equal(t.A.rbi, 0);
});

test('battingRates: 성분에서 다시 계산', () => {
  const r = M.battingRates({ pa: 15, ab: 13, h: 4, d2: 1, d3: 0, hr: 1, tb: 8, bb: 2, hbp: 0, sf: 0, so: 3, go: 2, ao: 4 });
  assert.equal(r.single, 2);
  assert.ok(near(r.avg, 4 / 13));
  assert.ok(near(r.obp, 6 / 15));
  assert.ok(near(r.slg, 8 / 13));
  assert.ok(near(r.ops, 6 / 15 + 8 / 13));
  assert.ok(near(r.iso, 8 / 13 - 4 / 13));
  assert.ok(near(r.babip, 3 / 9));
  assert.ok(near(r.kpct, 20));
  assert.equal(r.goao, 0.5);
});

test('battingRates: 분모가 0 이면 null', () => {
  const z = { pa: 0, ab: 0, h: 0, d2: 0, d3: 0, hr: 0, tb: 0, bb: 0, hbp: 0, sf: 0, so: 0, go: 0, ao: 0 };
  const r = M.battingRates(z);
  assert.equal(r.avg, null);
  assert.equal(r.ops, null);
  assert.equal(r.kpct, null);
  assert.equal(r.goao, null);
});

// 검증 7(타격): 지금 페이지의 aggBatting 과 같은 값인지 봅니다.
function oldAggBatting(rows) {
  const n = v => (v === null || v === undefined || v === '') ? 0 : (+v || 0);
  const m = {};
  for (const r of rows) {
    const t = r.player_team; if (!t) continue;
    const a = m[t] || (m[t] = { team: t, ab: 0, h: 0, bb: 0, hbp: 0, sf: 0, tb: 0 });
    a.ab += n(r.at_bat); a.h += n(r.single); a.bb += n(r.base_on_balls);
    a.hbp += n(r.hit_by_pitch); a.sf += n(r.sacrifice_fly); a.tb += n(r.total_bases);
  }
  return Object.values(m).map(a => ({
    team: a.team,
    avg: a.ab ? a.h / a.ab : 0,
    obp: (a.ab + a.bb + a.hbp + a.sf) ? (a.h + a.bb + a.hbp) / (a.ab + a.bb + a.hbp + a.sf) : 0,
    slg: a.ab ? a.tb / a.ab : 0,
  }));
}

test('검증 7(타격): 2025 AVG·OBP·SLG 가 지금 페이지와 같음', () => {
  const b = fixture('batters_2025').batters;
  const cur = M.sumBatting(b);
  const old = oldAggBatting(b);
  assert.equal(old.length, 10);
  for (const o of old) {
    const r = M.battingRates(cur[o.team]);
    assert.ok(near(r.avg, o.avg, 1e-12), `${o.team} AVG`);
    assert.ok(near(r.obp, o.obp, 1e-12), `${o.team} OBP`);
    assert.ok(near(r.slg, o.slg, 1e-12), `${o.team} SLG`);
  }
});
```

- [ ] **Step 3: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.basic.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (metrics.js 가 아직 없음)

- [ ] **Step 4: metrics.js 기초 쓰기**

`dashboard_js/js/team-stats/metrics.js`:

```js
/*
 * 팀 통계 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.TeamStats.metrics 로, Node 검증 스크립트에서는
 * require 로 씁니다. 식의 근거는 docs/superpowers/specs/
 * 2026-10-03-team-stats-fangraphs-design.md 3장입니다.
 *
 * 원칙: 선수 비율을 평균 내지 않습니다. 팀 합계(성분)에서 다시 셉니다.
 * 계산할 수 없는 값은 0 이 아니라 null 입니다. 화면에서 '-' 가 됩니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  /** 서버가 숫자를 문자열로 줄 때가 있습니다. 비거나 못 읽으면 0 입니다. */
  function num(v) {
    if (v === null || v === undefined || v === '') return 0;
    const n = Number(v);
    return Number.isFinite(n) ? n : 0;
  }

  /** 나눗셈입니다. 분모가 0 이하이거나 결과가 숫자가 아니면 null 입니다. */
  function div(a, b) {
    const r = a / b;
    return b > 0 && Number.isFinite(r) ? r : null;
  }

  /** 객체 안의 숫자가 아닌 값(NaN·Infinity)을 null 로 바꿉니다. */
  function clean(o) {
    for (const k of Object.keys(o)) {
      if (typeof o[k] === 'number' && !Number.isFinite(o[k])) o[k] = null;
    }
    return o;
  }

  /**
   * 이닝 글자를 아웃 수로 바꿉니다. '81 1/3' → 244, '7' → 21.
   *
   * '2/3' 처럼 분수만 있는 이닝도 읽습니다. 예전 페이지는 이것을 0 으로
   * 읽어 2025 투수 4명의 이닝이 빠졌습니다.
   */
  function ipOuts(s) {
    const t = String(s === null || s === undefined ? '' : s).trim();
    const m = t.match(/^(?:(\d+))?\s*(?:([12])\/3)?$/);
    if (!m || (!m[1] && !m[2])) return 0;
    return (m[1] ? Number(m[1]) * 3 : 0) + (m[2] ? Number(m[2]) : 0);
  }

  // 공식 타자 기록 칸 → 팀 합계 키입니다.
  // `single` 칸의 실제 값은 안타(H)입니다(수집기가 KBO 의 H 를 넣습니다).
  const BAT_SUM = {
    pa: 'plate_appearance', ab: 'at_bat', r: 'run', h: 'single',
    d2: 'double', d3: 'triple', hr: 'home_run', tb: 'total_bases',
    rbi: 'run_batted_in', bb: 'base_on_balls', ibb: 'intentional_base_on_balls',
    hbp: 'hit_by_pitch', so: 'strikeout', sf: 'sacrifice_fly', sh: 'sacrifice_bunts',
    gdp: 'ground_into_double_play', multi: 'multi_hits', xbh: 'extra_base_hits',
    go: 'ground_outs', ao: 'air_outs', gw: 'gw_rbi',
  };
  const BAT_KEYS = Object.keys(BAT_SUM);

  /** 선수 행을 팀별로 더합니다. extra(a, r) 로 칸을 더 셀 수 있습니다. */
  function sumBy(rows, map, extra) {
    const out = {};
    for (const r of rows || []) {
      const team = r.player_team;
      if (!team) continue;
      const a = out[team] || (out[team] = { team: team });
      for (const k in map) a[k] = (a[k] || 0) + num(r[map[k]]);
      if (extra) extra(a, r);
    }
    return out;
  }

  function sumBatting(rows) {
    return sumBy(rows, BAT_SUM);
  }

  /** 타격 비율입니다. 모두 합계에서 다시 셉니다. */
  function battingRates(t) {
    const o = {
      single: t.h - t.d2 - t.d3 - t.hr,
      avg: div(t.h, t.ab),
      obp: div(t.h + t.bb + t.hbp, t.ab + t.bb + t.hbp + t.sf),
      slg: div(t.tb, t.ab),
      babip: div(t.h - t.hr, t.ab - t.so - t.hr + t.sf),
      kpct: div(t.so * 100, t.pa),
      bbpct: div(t.bb * 100, t.pa),
      bbk: div(t.bb, t.so),
      goao: div(t.go, t.ao),
    };
    o.ops = o.obp === null || o.slg === null ? null : o.obp + o.slg;
    o.iso = o.slg === null || o.avg === null ? null : o.slg - o.avg;
    return clean(o);
  }

  const api = {
    num, div, clean, ipOuts, BAT_SUM, BAT_KEYS, sumBy, sumBatting, battingRates,
  };
  TS.metrics = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 5: 테스트가 통과하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.basic.test.js`
Expected: PASS (7 tests)

- [ ] **Step 6: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/metrics.js
git commit -m "feat(team-stats): 팀 통계 계산 모듈 기초(합산·타격 비율·분수 이닝 읽기)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: 타격 고급 지표(wOBA·wRAA·wRC·wRC+·OPS+)와 검증 1·3

**Files:**
- Modify: `dashboard_js/js/team-stats/metrics.js` (함수 추가, `api` 에 등록)
- Create: `C:/tmp/bstats-team-stats-check/tests/metrics.batting.test.js`

**Interfaces:**
- Consumes: Task 1 의 `num, div, battingRates, sumBatting, BAT_KEYS`
- Produces:
  - `indexRefs(refs)` → `{ weights: {season: row}, pf: {'season|stadium': run_pf}, home: {'team|season': stadium}, pfOk: bool }`. `refs` = `{ weights: [], pf: [], stadium: [], rank: [] }` (각 `/db/table` 의 `rows`).
  - `pfHalf(ix, team, season)` → 2008 전은 `1`, 참조 표가 없으면 `null`, 그 외 `(run_pf + 1000) / 2000` (값이 없으면 run_pf=1000).
  - `wobaOf(t, w)` → number|null
  - `sumObjects(list, keys)` → 합계 객체
  - `battingTable(totals, season, ix, keys?)` → `{ rows: [팀 행], league: 리그 평균 행, ctx: { lgWoba, L, scale, lgObp, lgSlg, hasWeights } }`. 팀 행 = 합계 + 비율 + `woba wraa wrc wrcp opsp`. 리그 행은 `team:'리그 평균', isLeague:true`, 누적 숫자는 팀 평균, 비율은 리그 합으로, `wrcp`·`opsp` 는 100(계산할 팀이 없으면 null).

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.batting.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture, refs, near } = require('./_load');
const M = load('metrics');

const R = refs();
const ix = M.indexRefs(R);
const b = fixture('batters_2025').batters;

test('pfHalf: 2025 LG 는 잠실(run_pf 924) → 0.962', () => {
  assert.ok(near(M.pfHalf(ix, 'LG', 2025), (924 + 1000) / 2000));
});

test('pfHalf: 2007 은 보정 없음(1), 참조 표가 없으면 null', () => {
  const empty = M.indexRefs({});
  assert.equal(M.pfHalf(empty, 'LG', 2007), 1);
  assert.equal(M.pfHalf(empty, 'LG', 2025), null);
  assert.equal(M.pfHalf(ix, 'LG', 2007), 1);
});

test('pfHalf: 홈구장을 모르면 중립(1000) → 1', () => {
  assert.equal(M.pfHalf(ix, '없는팀', 2025), 1);
});

test('검증: 선수 wOBA 를 같은 식으로 재현(1e-5 안)', () => {
  const w = ix.weights[2025];
  let n = 0;
  for (const p of b) {
    if (p.woba === null || p.woba === undefined) continue;
    const t = Object.values(M.sumBatting([p]))[0];
    const mine = M.wobaOf(t, w);
    assert.ok(near(mine, Number(p.woba), 1e-5), `${p.player_name}: ${mine} vs ${p.woba}`);
    n++;
  }
  assert.ok(n >= 150, `wOBA 가 있는 선수가 ${n}명뿐입니다`);
});

test('검증 3: 리그 wOBA 가 서버가 쓴 값과 같음', () => {
  const v = M.battingTable(M.sumBatting(b), 2025, ix);
  const scale = Number(ix.weights[2025].wOBA_scale);
  const lgs = b
    .filter(p => p.woba !== null && p.woba !== undefined && p.wraa !== null && p.wraa !== undefined && Number(p.plate_appearance) > 0)
    .map(p => Number(p.woba) - Number(p.wraa) * scale / Number(p.plate_appearance));
  const server = lgs.reduce((a, x) => a + x, 0) / lgs.length;
  console.log('리그 wOBA 서버', server.toFixed(6), '화면', v.ctx.lgWoba.toFixed(6));
  assert.ok(near(server, v.ctx.lgWoba, 1e-5));
});

test('검증 1: 팀 wRC+ ≈ 선수 wRC+ 타석 가중 평균(PA 50 이상, ±0.5)', () => {
  const full = M.battingTable(M.sumBatting(b), 2025, ix);
  const { lgWoba, L, scale } = full.ctx;
  const w = ix.weights[2025];
  const by = {};
  for (const p of b) {
    if (p.wrc_plus === null || p.wrc_plus === undefined || Number(p.plate_appearance) < 50) continue;
    (by[p.player_team] = by[p.player_team] || []).push(p);
  }
  assert.equal(Object.keys(by).length, 10);
  for (const team of Object.keys(by)) {
    const ps = by[team];
    const t = Object.values(M.sumBatting(ps))[0];
    const woba = M.wobaOf(t, w);
    const wraa = (woba - lgWoba) / scale * t.pa;
    const pf = M.pfHalf(ix, team, 2025);
    const mine = (wraa / t.pa) / L * 100 + (2 - pf) * 100;
    const sumPa = ps.reduce((a, p) => a + Number(p.plate_appearance), 0);
    const theirs = ps.reduce((a, p) => a + Number(p.plate_appearance) * Number(p.wrc_plus), 0) / sumPa;
    console.log(team, '화면', mine.toFixed(2), '선수 가중', theirs.toFixed(2));
    assert.ok(Math.abs(mine - theirs) < 0.5, `${team}: ${mine} vs ${theirs}`);
  }
});

test('battingTable: 2025 팀 10개, 리그 행 지수 100, 누적은 팀 평균', () => {
  const v = M.battingTable(M.sumBatting(b), 2025, ix);
  assert.equal(v.rows.length, 10);
  assert.equal(v.league.isLeague, true);
  assert.equal(v.league.wrcp, 100);
  assert.equal(v.league.opsp, 100);
  const sumPa = v.rows.reduce((a, r) => a + r.pa, 0);
  assert.ok(near(v.league.pa, sumPa / 10));
  assert.ok(v.rows.every(r => typeof r.wrcp === 'number' && r.wrcp > 60 && r.wrcp < 140));
  const avgW = v.rows.reduce((a, r) => a + r.wrcp * r.pa, 0) / sumPa;
  console.log('팀 wRC+ 타석 가중 평균', avgW.toFixed(2));
});

test('battingTable: 2007 은 wOBA·wRC+ null, OPS+ 는 보정 없이', () => {
  const t = { A: { team: 'A', pa: 100, ab: 90, h: 27, d2: 5, d3: 1, hr: 3, tb: 43, bb: 8, hbp: 1, sf: 1, so: 15, r: 12 },
              B: { team: 'B', pa: 100, ab: 90, h: 22, d2: 4, d3: 0, hr: 2, tb: 32, bb: 7, hbp: 2, sf: 1, so: 20, r: 9 } };
  const v = M.battingTable(t, 2007, ix, ['pa', 'ab', 'h', 'd2', 'd3', 'hr', 'tb', 'bb', 'hbp', 'sf', 'so', 'r']);
  for (const r of v.rows) {
    assert.equal(r.woba, null);
    assert.equal(r.wrcp, null);
    assert.equal(typeof r.opsp, 'number');
  }
  assert.equal(v.league.wrcp, null);
  assert.equal(v.league.opsp, 100);
});

test('battingTable: 참조 표가 없으면 2025 도 wRC+·OPS+ null(0 이 아님)', () => {
  const v = M.battingTable(M.sumBatting(b), 2025, M.indexRefs({}));
  assert.ok(v.rows.every(r => r.wrcp === null && r.opsp === null && r.woba === null));
  assert.ok(v.rows.every(r => typeof r.avg === 'number'));
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.batting.test.js`
Expected: FAIL — `M.indexRefs is not a function`

- [ ] **Step 3: metrics.js 에 함수 추가**

`battingRates` 함수 바로 아래에 넣습니다:

```js
  /**
   * 참조 표를 찾기 쉬운 모양으로 바꿉니다.
   * refs = { weights, pf, stadium, rank } (각 /db/table 의 rows)
   */
  function indexRefs(refs) {
    refs = refs || {};
    const ix = { weights: {}, pf: {}, home: {}, pfOk: false };
    for (const r of refs.weights || []) ix.weights[num(r.season)] = r;
    for (const r of refs.pf || []) ix.pf[num(r.season) + '|' + r.stadium] = num(r.run_pf);
    for (const r of refs.stadium || []) ix.home[r.player_team + '|' + num(r.season)] = r.stadium;
    ix.pfOk = (refs.pf || []).length > 0 && (refs.stadium || []).length > 0;
    return ix;
  }

  /**
   * 반 구장 보정입니다. 선수 wRC+ 의 pf_half 와 같습니다.
   *   (홈구장 run_pf + 1000) / 2000
   * 2008 전은 파크팩터가 없어 1(보정 없음)입니다. 참조 표를 못 받았으면
   * null 입니다. 홈구장이나 값이 없으면 선수 wRC+ 계산기처럼 중립(1000)
   * 으로 봅니다(park_factors/build_wrc_plus.py).
   */
  function pfHalf(ix, team, season) {
    if (season < 2008) return 1;
    if (!ix || !ix.pfOk) return null;
    const st = ix.home[team + '|' + season];
    const run = st ? ix.pf[season + '|' + st] : 0;
    return ((run > 0 ? run : 1000) + 1000) / 2000;
  }

  /**
   * wOBA 입니다. 선수 wOBA 와 같은 식입니다(BB 는 고의4구 포함).
   *   (wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) / (AB + BB + SF + HBP)
   */
  function wobaOf(t, w) {
    if (!w) return null;
    const one = t.h - t.d2 - t.d3 - t.hr;
    const den = t.ab + t.bb + t.sf + t.hbp;
    if (!(den > 0)) return null;
    const v = (num(w.fg_wBB) * t.bb + num(w.fg_wHBP) * t.hbp + num(w.fg_w1B) * one
      + num(w.fg_w2B) * t.d2 + num(w.fg_w3B) * t.d3 + num(w.fg_wHR) * t.hr) / den;
    return Number.isFinite(v) ? v : null;
  }

  /** 여러 합계 객체를 keys 만 더합니다. */
  function sumObjects(list, keys) {
    const s = {};
    for (const k of keys) s[k] = 0;
    for (const o of list) for (const k of keys) s[k] += num(o[k]);
    return s;
  }

  /**
   * 타격 표입니다. totals 는 sumBatting 결과(또는 기간별 합계)입니다.
   * keys 는 합계 키 목록입니다(기간별은 응답에 있는 칸만).
   */
  function battingTable(totals, season, ix, keys) {
    keys = keys || BAT_KEYS;
    const teams = Object.values(totals || {});
    const lg = sumObjects(teams, keys);
    const lgR = battingRates(lg);
    const w = (ix && ix.weights[season]) || null;
    const lgWoba = wobaOf(lg, w);
    const L = div(lg.r, lg.pa);
    const scale = w ? num(w.wOBA_scale) : 0;

    const rows = teams.map(function (t) {
      const row = Object.assign({}, t, battingRates(t));
      const pf = pfHalf(ix, t.team, season);
      row.woba = wobaOf(t, w);
      row.wraa = null;
      row.wrc = null;
      row.wrcp = null;
      if (row.woba !== null && lgWoba !== null && scale > 0 && t.pa > 0) {
        row.wraa = (row.woba - lgWoba) / scale * t.pa;
        if (L !== null) {
          row.wrc = (row.wraa / t.pa + L) * t.pa;
          // 선수 wRC+ 와 같은 식: K + (2 - PF) * 100, K = (wRAA/PA) / L * 100
          if (pf !== null) row.wrcp = (row.wraa / t.pa) / L * 100 + (2 - pf) * 100;
        }
      }
      row.opsp = (row.obp !== null && row.slg !== null && lgR.obp > 0 && lgR.slg > 0 && pf)
        ? 100 * (row.obp / lgR.obp + row.slg / lgR.slg - 1) / pf
        : null;
      return row;
    });

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, lgR);
    league.single = lgR.single === null ? null : lgR.single / n;
    league.woba = lgWoba;
    league.wraa = lgWoba === null ? null : 0;
    league.wrc = lgWoba !== null && L !== null ? L * lg.pa / n : null;
    league.wrcp = rows.some(r => r.wrcp !== null) ? 100 : null;
    league.opsp = rows.some(r => r.opsp !== null) ? 100 : null;

    return {
      rows: rows,
      league: league,
      ctx: { lgWoba: lgWoba, L: L, scale: scale, lgObp: lgR.obp, lgSlg: lgR.slg, hasWeights: !!w },
    };
  }
```

`api` 객체를 이렇게 바꿉니다:

```js
  const api = {
    num, div, clean, ipOuts, BAT_SUM, BAT_KEYS, sumBy, sumBatting, battingRates,
    indexRefs, pfHalf, wobaOf, sumObjects, battingTable,
  };
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS. 콘솔에 팀별 `화면 / 선수 가중` wRC+ 와 리그 wOBA 가 찍힙니다. **검증 1·3 이 실패하면 고치지 말고 멈춰서 숫자를 evan 에게 보고합니다**(데이터 문제일 수 있습니다).

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/metrics.js
git commit -m "feat(team-stats): 팀 wOBA·wRC+·OPS+ 계산(선수 wRC+ 와 같은 식, 반 구장 보정)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 투구 지표(합산·비율·FIP·LOB%·ERA-·FIP-)와 검증 2·4·7

**Files:**
- Modify: `dashboard_js/js/team-stats/metrics.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/metrics.pitching.test.js`

**Interfaces:**
- Consumes: `num, div, clean, ipOuts, sumBy, sumObjects, pfHalf, indexRefs`
- Produces:
  - `PIT_SUM`, `PIT_KEYS` (합계 키: `h r er bb so hr w l sv hld hbp ibb cg sho qs bs tbf np d2 d3 wp bk gs gf svo gidp go ao sh sf outs`)
  - `sumPitching(rows)` → `{team: totals}` (`outs` 포함)
  - `pitchingRates(t)` → `{era, ra9, whip, k9, bb9, h9, hr9, kbb, kpct, bbpct, kbbpct, oavg, babip, lobpct, pip, goao}`
  - `fipCore(t)` → number|null
  - `pitchingTable(totals, season, ix, keys?)` → `{ rows, league, ctx: { lgEra, cfip } }`. 팀 행에 `fip ef erap fipp` 추가.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.pitching.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture, refs, near } = require('./_load');
const M = load('metrics');

const ix = M.indexRefs(refs());
const p = fixture('pitchers_2025').pitchers;

test('sumPitching: 이닝을 아웃으로 더함(분수만 있는 이닝 포함)', () => {
  const t = M.sumPitching([
    { player_team: 'A', innings_pitched: '5 1/3', hits: 4, earned_run: 2, sacrifice_bunts: 1 },
    { player_team: 'A', innings_pitched: '2/3', hits: 1, earned_run: 0, sacrifice_bunts: 0 },
  ]);
  assert.equal(t.A.outs, 18);
  assert.equal(t.A.h, 5);
  assert.equal(t.A.sh, 1);
});

test('pitchingRates: 식대로 계산', () => {
  const t = { outs: 27, er: 3, r: 4, h: 9, bb: 2, ibb: 0, hbp: 1, so: 8, hr: 1, tbf: 38, sh: 1, sf: 1, np: 140, go: 10, ao: 8 };
  const r = M.pitchingRates(t);
  assert.ok(near(r.era, 3));
  assert.ok(near(r.ra9, 4));
  assert.ok(near(r.whip, 11 / 9));
  assert.ok(near(r.oavg, 9 / 33));
  assert.ok(near(r.babip, 8 / 25));
  assert.ok(near(r.lobpct, 800 / 10.6));
  assert.ok(near(r.kpct, 800 / 38));
  assert.ok(near(r.kbbpct, 800 / 38 - 200 / 38));
  assert.ok(near(r.pip, 140 / 9));
});

test('pitchingRates: 응답에 없는 칸(undefined)은 null', () => {
  const r = M.pitchingRates({ outs: 27, h: 9, r: 4, bb: 2, so: 8, hr: 1 });
  assert.equal(r.era, null);
  assert.equal(r.kpct, null);
  assert.equal(r.lobpct, null);
  assert.ok(near(r.ra9, 4));
});

test('검증 2: 팀 FIP 의 이닝 가중 평균 = 리그 ERA', () => {
  const v = M.pitchingTable(M.sumPitching(p), 2025, ix);
  const outs = v.rows.reduce((a, r) => a + r.outs, 0);
  const wFip = v.rows.reduce((a, r) => a + r.fip * r.outs, 0) / outs;
  console.log('리그 ERA', v.ctx.lgEra.toFixed(4), '팀 FIP 가중 평균', wFip.toFixed(4), 'cFIP', v.ctx.cfip.toFixed(4));
  assert.ok(near(wFip, v.ctx.lgEra, 1e-9));
  assert.ok(near(v.league.fip, v.league.era, 1e-12));
  assert.equal(v.league.erap, 100);
  assert.equal(v.league.fipp, 100);
});

test('검증 4: 피안타율 식이 공식 피안타율과 맞음(BB 에 고의4구 포함 확인)', () => {
  let inc = 0, exc = 0, n = 0;
  for (const x of p) {
    const t = Object.values(M.sumPitching([x]))[0];
    const off = Number(x.batting_average);
    const den = t.tbf - t.bb - t.hbp - t.sh - t.sf;
    if (!(den > 0) || !Number.isFinite(off)) continue;
    n++;
    if ((t.h / den).toFixed(3) === off.toFixed(3)) inc++;
    const den2 = den - t.ibb;
    if (den2 > 0 && (t.h / den2).toFixed(3) === off.toFixed(3)) exc++;
  }
  console.log(`피안타율 일치: 고의4구 포함 식 ${inc}/${n}, 제외 식 ${exc}/${n}`);
  assert.ok(inc / n >= 0.95, `포함 식 일치율 ${inc}/${n}`);
  assert.ok(inc >= exc);
});

// 검증 7(투구): 지금 페이지와 ERA·WHIP 비교. 예전 이닝 읽기는 '2/3' 을 0 으로
// 읽으므로, 그 차이만큼만 다른지 봅니다.
function oldOuts(s) {
  s = String(s == null ? '' : s).trim();
  const m = s.match(/^(\d+)(?:\s+([12])\/3)?$/);
  return m ? (+m[1]) * 3 + (m[2] ? +m[2] : 0) : 0;
}

test('검증 7(투구): ERA·WHIP 식은 예전과 같고, 분수 이닝만큼만 다름', () => {
  const v = M.pitchingTable(M.sumPitching(p), 2025, ix);
  const old = {};
  for (const x of p) {
    const a = old[x.player_team] || (old[x.player_team] = { outs: 0, er: 0, h: 0, bb: 0 });
    a.outs += oldOuts(x.innings_pitched);
    a.er += M.num(x.earned_run); a.h += M.num(x.hits); a.bb += M.num(x.base_on_balls);
  }
  for (const r of v.rows) {
    const o = old[r.team];
    const sameOutsEra = r.er * 27 / o.outs;
    console.log(r.team, '아웃 차이', r.outs - o.outs, 'ERA 새', r.era.toFixed(3), '예전', sameOutsEra.toFixed(3));
    assert.ok(r.outs >= o.outs);
    assert.ok(near(r.era, r.er * 27 / r.outs, 1e-12));
    assert.ok(near(r.whip, (r.h + r.bb) * 3 / r.outs, 1e-12));
    if (r.outs === o.outs) assert.ok(near(r.era, sameOutsEra, 1e-12));
  }
});

test('pitchingTable: 2007 은 ERA- 보정 없음, 참조 표가 없으면 2025 ERA- null', () => {
  const t = { A: { team: 'A', outs: 300, er: 40, h: 100, bb: 30, ibb: 2, hbp: 5, so: 80, hr: 8 },
              B: { team: 'B', outs: 300, er: 50, h: 110, bb: 35, ibb: 1, hbp: 4, so: 70, hr: 12 } };
  const keys = ['outs', 'er', 'h', 'bb', 'ibb', 'hbp', 'so', 'hr'];
  const v = M.pitchingTable(t, 2007, ix, keys);
  const lgEra = 90 * 27 / 600;
  assert.ok(near(v.rows[0].erap, 100 * (40 * 27 / 300) / lgEra));
  const v2 = M.pitchingTable(t, 2025, M.indexRefs({}), keys);
  assert.equal(v2.rows[0].erap, null);
  assert.equal(typeof v2.rows[0].fip, 'number');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.pitching.test.js`
Expected: FAIL — `M.sumPitching is not a function`

- [ ] **Step 3: metrics.js 에 함수 추가**

`battingTable` 아래에 넣습니다:

```js
  // 공식 투수 기록 칸 → 팀 합계 키입니다. 이닝은 sumPitching 이 outs 로 셉니다.
  const PIT_SUM = {
    h: 'hits', r: 'run', er: 'earned_run', bb: 'base_on_balls', so: 'strikeout',
    hr: 'home_run', w: 'wins', l: 'losses', sv: 'save', hld: 'hold',
    hbp: 'hit_by_pitch', ibb: 'intentional_base_on_balls', cg: 'complete_game',
    sho: 'shutout', qs: 'quality_start', bs: 'blown_save', tbf: 'total_batters_faced',
    np: 'number_of_pitchers', d2: 'double', d3: 'triple', wp: 'wild_pitch', bk: 'balk',
    gs: 'games_started', gf: 'games_finished', svo: 'save_opportunity',
    gidp: 'ground_into_double_play', go: 'ground_outs', ao: 'air_outs',
    sh: 'sacrifice_bunts', sf: 'sacrifice_fly',
  };
  const PIT_KEYS = Object.keys(PIT_SUM).concat(['outs']);

  function sumPitching(rows) {
    return sumBy(rows, PIT_SUM, function (a, r) {
      a.outs = (a.outs || 0) + ipOuts(r.innings_pitched);
    });
  }

  /** 투구 비율입니다. 응답에 없는 칸이 있으면 그 지표는 null 입니다. */
  function pitchingRates(t) {
    const outs = t.outs;
    const per9 = function (x) { return div(x * 27, outs); };
    const o = {
      era: per9(t.er),
      ra9: per9(t.r),
      whip: div((t.h + t.bb) * 3, outs),
      k9: per9(t.so),
      bb9: per9(t.bb),
      h9: per9(t.h),
      hr9: per9(t.hr),
      kbb: div(t.so, t.bb),
      kpct: div(t.so * 100, t.tbf),
      bbpct: div(t.bb * 100, t.tbf),
      // 피안타율: 상대 타수 = TBF - BB - HBP - SH - SF (투수 기록의 BB 는 고의4구 포함)
      oavg: div(t.h, t.tbf - t.bb - t.hbp - t.sh - t.sf),
      babip: div(t.h - t.hr, t.tbf - t.bb - t.hbp - t.sh - t.so - t.hr),
      lobpct: div((t.h + t.bb + t.hbp - t.r) * 100, t.h + t.bb + t.hbp - 1.4 * t.hr),
      pip: div(t.np * 3, outs),
      goao: div(t.go, t.ao),
    };
    o.kbbpct = o.kpct === null || o.bbpct === null ? null : o.kpct - o.bbpct;
    return clean(o);
  }

  /** FIP 의 상수 앞부분입니다: (13·HR + 3·(BB − IBB + HBP) − 2·SO) / IP */
  function fipCore(t) {
    return div((13 * t.hr + 3 * (t.bb - t.ibb + t.hbp) - 2 * t.so) * 3, t.outs);
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
    const lgR = pitchingRates(lg);
    const lgCore = fipCore(lg);
    const cfip = lgR.era !== null && lgCore !== null ? lgR.era - lgCore : null;

    const rows = teams.map(function (t) {
      const row = Object.assign({}, t, pitchingRates(t));
      const core = fipCore(t);
      const pf = pfHalf(ix, t.team, season);
      row.fip = core !== null && cfip !== null ? core + cfip : null;
      row.ef = row.era !== null && row.fip !== null ? row.era - row.fip : null;
      row.erap = row.era !== null && lgR.era > 0 && pf !== null
        ? 100 * row.era * (2 - pf) / lgR.era : null;
      row.fipp = row.fip !== null && lgR.era > 0 && pf !== null
        ? 100 * row.fip * (2 - pf) / lgR.era : null;
      return row;
    });

    const n = teams.length || 1;
    const league = { team: '리그 평균', isLeague: true };
    for (const k of keys) league[k] = lg[k] / n;
    Object.assign(league, lgR);
    league.fip = cfip !== null ? lgR.era : null;
    league.ef = league.fip !== null ? 0 : null;
    league.erap = rows.some(r => r.erap !== null) ? 100 : null;
    league.fipp = rows.some(r => r.fipp !== null) ? 100 : null;

    return { rows: rows, league: league, ctx: { lgEra: lgR.era, cfip: cfip } };
  }
```

`api` 에 `PIT_SUM, PIT_KEYS, sumPitching, pitchingRates, fipCore, pitchingTable` 를 더합니다.

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS. 콘솔에 피안타율 일치 수와 팀별 아웃 차이(분수 이닝 버그 고친 몫)가 찍힙니다. 검증 4 가 실패하면(고의4구 제외 식이 더 잘 맞으면) 멈추고 evan 에게 숫자를 보고합니다. 그때는 FIP 식의 `BB − IBB` 를 다시 봐야 합니다.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/metrics.js
git commit -m "feat(team-stats): 팀 투구 지표(FIP·LOB%·ERA-·FIP-·정확한 피안타율) 계산" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 팀 성적(순위표·득실·피타고리안·경기 결과 집계)과 검증 5·6

**Files:**
- Modify: `dashboard_js/js/team-stats/metrics.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/metrics.record.test.js`

**Interfaces:**
- Consumes: `num, div, sumBatting, sumPitching, battingTable, pitchingTable, indexRefs`
- Produces:
  - `rankFor(rankRows, season)` → `{team: { team, rank, league, g, w, l, d, pct, gb }}` (`gb` 는 순위표 문자열을 숫자로, 비면 null)
  - `pythag(r, ra)` → number|null (지수 1.83)
  - `gameSplits(games, start?, end?)` → `{team: { team, g, w, l, d, r, ra, home:{w,l,d}, away:{w,l,d}, onerun:{w,l,d}, month:{4|5|..: {w,l,d}}, vs:{opp:{w,l,d}} }}` (정규시즌만, start·end 는 YYYYMMDD 숫자, 3·4월은 키 4)
  - `recordTable(rank, batTotals, pitTotals, splits|null)` → `[{ team, rank, league, g, w, l, d, pct, gb, r, ra, diff, pyth, expw, luck, home, away, onerun }]`
  - `recordFromGames(splits)` → 같은 모양(승차는 승률 1위 기준 계산)
  - `rankFromStandings(teams)` → `rankFor` 와 같은 모양. `teams` = `/standings` 응답의 `teams`(값이 문자열). **올해만 씁니다.** 저장된 순위표(`team_season_rank`)의 2026 이 8월 말 값(111~119경기)에 멈춰 있기 때문입니다(2026-10-03 확인, 실시간은 136~140경기).
  - `seasonView({ batters, pitchers, refs, season, rank? })` → `{ season, ix, bat, pit, rank, batTotals, pitTotals, unmatched: [팀 이름] }`. `rank` 를 넘기면 순위표 대신 그것을 씁니다. `bat`·`pit` 는 battingTable·pitchingTable 결과이고 팀 행의 `g` 는 순위표 경기 수입니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.record.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture, refs, near } = require('./_load');
const M = load('metrics');

const R = refs();
const games = fixture('games_2025').games;

test('rankFor: 2025 LG 85-56-3, 승률 85/141, 승차 0', () => {
  const k = M.rankFor(R.rank, 2025);
  assert.equal(Object.keys(k).length, 10);
  assert.equal(k.LG.w, 85);
  assert.equal(k.LG.l, 56);
  assert.equal(k.LG.d, 3);
  assert.ok(near(k.LG.pct, 85 / 141));
  assert.equal(k.LG.gb, 0);
  assert.equal(k['한화'].gb, 1.5);
});

test('rankFor: 1999 은 드림·매직 두 리그 8팀', () => {
  const k = M.rankFor(R.rank, 1999);
  assert.equal(Object.keys(k).length, 8);
  assert.deepEqual([...new Set(Object.values(k).map(x => x.league))].sort(), ['드림리그', '매직리그']);
});

test('pythag', () => {
  assert.equal(M.pythag(100, 100), 0.5);
  assert.equal(M.pythag(0, 5), null);
  assert.ok(near(M.pythag(788, 598), Math.pow(788, 1.83) / (Math.pow(788, 1.83) + Math.pow(598, 1.83))));
});

test('gameSplits: 홈·원정·1점차·월별·상대 전적·득실, 포스트시즌 제외', () => {
  const g = [
    { game_type: '정규시즌', game_date: 20250405, home_team_id: 'A', away_team_id: 'B', home_score: 3, away_score: 2 },
    { game_type: '정규시즌', game_date: 20250510, home_team_id: 'B', away_team_id: 'A', home_score: 5, away_score: 1 },
    { game_type: '정규시즌', game_date: 20250511, home_team_id: 'B', away_team_id: 'A', home_score: 4, away_score: 4 },
    { game_type: '포스트시즌', game_date: 20251020, home_team_id: 'A', away_team_id: 'B', home_score: 9, away_score: 0 },
  ];
  const s = M.gameSplits(g);
  assert.deepEqual([s.A.w, s.A.l, s.A.d, s.A.g], [1, 1, 1, 3]);
  assert.deepEqual(s.A.home, { w: 1, l: 0, d: 0 });
  assert.deepEqual(s.A.away, { w: 0, l: 1, d: 1 });
  assert.deepEqual(s.A.onerun, { w: 1, l: 0, d: 0 });
  assert.deepEqual(s.A.month[4], { w: 1, l: 0, d: 0 });
  assert.deepEqual(s.A.month[5], { w: 0, l: 1, d: 1 });
  assert.deepEqual(s.A.vs.B, { w: 1, l: 1, d: 1 });
  assert.equal(s.A.r, 8);
  assert.equal(s.A.ra, 11);
  const only5 = M.gameSplits(g, 20250501, 20250531);
  assert.equal(only5.A.g, 2);
});

test('recordFromGames: 승차는 승률 1위 기준', () => {
  const s = {
    A: { team: 'A', g: 10, w: 7, l: 3, d: 0, r: 50, ra: 30, home: {}, away: {}, onerun: {} },
    B: { team: 'B', g: 10, w: 4, l: 6, d: 0, r: 30, ra: 50, home: {}, away: {}, onerun: {} },
  };
  const rows = M.recordFromGames(s);
  const a = rows.find(r => r.team === 'A'), b = rows.find(r => r.team === 'B');
  assert.equal(a.gb, 0);
  assert.equal(b.gb, 3);
  assert.equal(a.diff, 20);
  assert.ok(near(a.luck, 7 - M.pythag(50, 30) * 10));
});

test('seasonView 2025: 팀 g 는 순위표 경기 수, 이름이 다 맞음', () => {
  const v = M.seasonView({ batters: fixture('batters_2025').batters, pitchers: fixture('pitchers_2025').pitchers, refs: R, season: 2025 });
  assert.deepEqual(v.unmatched, []);
  assert.ok(v.bat.rows.every(r => r.g === 144));
  assert.equal(v.bat.league.g, 144);
  const rec = M.recordTable(v.rank, v.batTotals, v.pitTotals, M.gameSplits(games));
  assert.equal(rec.length, 10);
  const lg = rec.find(r => r.team === 'LG');
  assert.equal(lg.r, v.batTotals.LG.r);
  assert.equal(lg.ra, v.pitTotals.LG.r);
  assert.ok(near(lg.luck, lg.w - lg.expw));
  assert.ok(lg.home && typeof lg.home.w === 'number');
});

test('rankFromStandings: 실시간 순위를 같은 모양으로(문자열 → 숫자)', () => {
  const k = M.rankFromStandings(fixture('standings_now').teams);
  assert.equal(Object.keys(k).length, 10);
  assert.equal(typeof k.KT.w, 'number');
  assert.equal(typeof k.KT.g, 'number');
  assert.ok(near(k.KT.pct, k.KT.w / (k.KT.w + k.KT.l)));
  assert.equal(k.KT.gb, 0);
  assert.equal(k.KT.league, '단일');
});

test('seasonView: rank 를 넘기면 순위표 대신 그것을 씀', () => {
  const rank = { LG: { team: 'LG', g: 99, w: 1, l: 1, d: 0, pct: 0.5, gb: 0, rank: 1, league: '단일' } };
  const v = M.seasonView({ batters: fixture('batters_2025').batters, pitchers: fixture('pitchers_2025').pitchers, refs: R, season: 2025, rank: rank });
  assert.equal(v.bat.rows.find(r => r.team === 'LG').g, 99);
  assert.equal(v.rank, rank);
});

test('검증 5: 2025 순위표 승패 ↔ 경기 결과로 센 승패', () => {
  const k = M.rankFor(R.rank, 2025);
  const s = M.gameSplits(games);
  const diffs = [];
  for (const t of Object.keys(k)) {
    const a = k[t], b = s[t];
    const d = Math.abs(a.w - b.w) + Math.abs(a.l - b.l) + Math.abs(a.d - b.d);
    if (d) diffs.push(`${t}: 순위표 ${a.w}-${a.l}-${a.d}, 경기 결과 ${b.w}-${b.l}-${b.d}`);
    assert.ok(d <= 2, `${t} 차이가 큽니다`);
  }
  console.log(diffs.length ? '차이:\n' + diffs.join('\n') : '모두 같음');
});

test('검증 6: 팀 득점 합(공식) ↔ 경기 점수 합', () => {
  const v = M.seasonView({ batters: fixture('batters_2025').batters, pitchers: fixture('pitchers_2025').pitchers, refs: R, season: 2025 });
  const s = M.gameSplits(games);
  let off = 0, gm = 0;
  for (const t of Object.keys(s)) {
    const a = v.batTotals[t].r, b = s[t].r;
    off += a; gm += b;
    console.log(t, '공식 득점 합', a, '경기 점수 합', b, '차이', a - b);
  }
  console.log('리그 합', off, gm);
  assert.ok(Math.abs(off - gm) / gm < 0.01);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.record.test.js`
Expected: FAIL — `M.rankFor is not a function`

- [ ] **Step 3: metrics.js 에 함수 추가**

`pitchingTable` 아래에 넣습니다:

```js
  /**
   * 그 시즌의 공식 순위표입니다. 팀-시즌 한 줄씩입니다(1982~1988 도 시즌
   * 합계). 1999·2000 은 드림·매직 양대 리그라 승차는 리그 안 값입니다.
   */
  function rankFor(rankRows, season) {
    const out = {};
    for (const r of rankRows || []) {
      if (num(r.season) !== season) continue;
      const w = num(r.wins), l = num(r.losses), d = num(r.draws);
      out[r.team_name] = {
        team: r.team_name,
        rank: num(r.rank),
        league: r.league || '단일',
        g: num(r.games),
        w: w, l: l, d: d,
        pct: div(w, w + l),
        gb: r.gb === null || r.gb === undefined || r.gb === '' ? null : num(r.gb),
      };
    }
    return out;
  }

  /**
   * 실시간 순위(/standings)를 rankFor 와 같은 모양으로 바꿉니다. 올해만
   * 씁니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다(2026 은 8월
   * 말 값에 멈춰 있었습니다).
   */
  function rankFromStandings(teams) {
    const out = {};
    for (const t of teams || []) {
      if (!t || !t.team) continue;
      const w = num(t.wins), l = num(t.losses), d = num(t.draws);
      out[t.team] = {
        team: t.team,
        rank: num(t.rank),
        league: '단일',
        g: num(t.games),
        w: w, l: l, d: d,
        pct: div(w, w + l),
        gb: t.gb === null || t.gb === undefined || t.gb === '' ? null : num(t.gb),
      };
    }
    return out;
  }

  /** 피타고리안 기대 승률입니다. R^1.83 / (R^1.83 + RA^1.83) */
  function pythag(r, ra) {
    if (!(r > 0) || !(ra > 0)) return null;
    const a = Math.pow(r, 1.83), b = Math.pow(ra, 1.83);
    return a / (a + b);
  }

  function emptyWL() { return { w: 0, l: 0, d: 0 }; }
  function addWL(o, my, opp) {
    if (my > opp) o.w++;
    else if (my < opp) o.l++;
    else o.d++;
  }

  /**
   * 경기 결과로 팀별 승패·득실·홈/원정·1점차·월별·상대 전적을 셉니다.
   * 정규시즌만 셉니다. 점수가 같으면 무승부입니다.
   * start·end 는 YYYYMMDD 숫자이고, 없으면 전체입니다.
   * 월은 3·4월을 묶어 키 4 로 둡니다.
   */
  function gameSplits(games, start, end) {
    const out = {};
    function get(t) {
      return out[t] || (out[t] = {
        team: t, g: 0, w: 0, l: 0, d: 0, r: 0, ra: 0,
        home: emptyWL(), away: emptyWL(), onerun: emptyWL(), month: {}, vs: {},
      });
    }
    for (const x of games || []) {
      if (x.game_type !== '정규시즌') continue;
      const day = num(x.game_date);
      if (start && day < start) continue;
      if (end && day > end) continue;
      if (x.home_score === null || x.home_score === undefined
        || x.away_score === null || x.away_score === undefined) continue;
      const hs = num(x.home_score), as = num(x.away_score);
      const month = Math.floor(day / 100) % 100;
      const mk = month <= 4 ? 4 : month;
      const sides = [
        [x.home_team_id, hs, as, 'home', x.away_team_id],
        [x.away_team_id, as, hs, 'away', x.home_team_id],
      ];
      for (const s of sides) {
        const a = get(s[0]), my = s[1], opp = s[2];
        a.g++;
        a.r += my;
        a.ra += opp;
        addWL(a, my, opp);
        addWL(a[s[3]], my, opp);
        if (Math.abs(my - opp) === 1) addWL(a.onerun, my, opp);
        addWL(a.month[mk] || (a.month[mk] = emptyWL()), my, opp);
        addWL(a.vs[s[4]] || (a.vs[s[4]] = emptyWL()), my, opp);
      }
    }
    return out;
  }

  /** 시즌 팀 성적 표입니다. 승패는 순위표, 득실은 공식 기록 합입니다. */
  function recordTable(rank, batTotals, pitTotals, splits) {
    return Object.keys(rank).map(function (team) {
      const k = rank[team];
      const b = batTotals && batTotals[team], p = pitTotals && pitTotals[team];
      const r = b ? b.r : null, ra = p ? p.r : null;
      const py = pythag(r, ra);
      const s = splits && splits[team];
      const expw = py === null ? null : py * (k.w + k.l);
      return Object.assign({}, k, {
        r: r, ra: ra,
        diff: r !== null && ra !== null ? r - ra : null,
        pyth: py,
        expw: expw,
        luck: expw === null ? null : k.w - expw,
        home: s ? s.home : null,
        away: s ? s.away : null,
        onerun: s ? s.onerun : null,
      });
    });
  }

  /** 기간별 팀 성적 표입니다. 모두 경기 결과에서 셉니다. */
  function recordFromGames(splits) {
    const rows = Object.values(splits || {}).map(function (s) {
      const py = pythag(s.r, s.ra);
      const expw = py === null ? null : py * (s.w + s.l);
      return {
        team: s.team, g: s.g, w: s.w, l: s.l, d: s.d,
        pct: div(s.w, s.w + s.l), gb: null,
        r: s.r, ra: s.ra, diff: s.r - s.ra,
        pyth: py, expw: expw, luck: expw === null ? null : s.w - expw,
        home: s.home, away: s.away, onerun: s.onerun,
      };
    });
    const top = rows.slice().sort((a, b) => (b.pct || 0) - (a.pct || 0))[0];
    rows.forEach(function (r) {
      r.gb = top ? ((top.w - r.w) + (r.l - top.l)) / 2 : null;
    });
    return rows;
  }

  /** 시즌 보기 전체입니다. 팀 행의 g 는 순위표 경기 수로 바꿉니다. */
  function seasonView(input) {
    const season = num(input.season);
    const ix = indexRefs(input.refs);
    const batTotals = sumBatting(input.batters);
    const pitTotals = sumPitching(input.pitchers);
    const rank = input.rank || rankFor(input.refs && input.refs.rank, season);
    const bat = battingTable(batTotals, season, ix);
    const pit = pitchingTable(pitTotals, season, ix);
    [bat, pit].forEach(function (tbl) {
      tbl.rows.forEach(function (r) { r.g = rank[r.team] ? rank[r.team].g : null; });
      const gs = tbl.rows.map(r => r.g).filter(v => v !== null);
      tbl.league.g = gs.length ? gs.reduce((a, b) => a + b, 0) / gs.length : null;
    });
    const names = Object.keys(rank);
    const unmatched = names.length
      ? names.filter(t => !batTotals[t]).concat(Object.keys(batTotals).filter(t => !rank[t]))
      : [];
    return { season, ix, bat, pit, rank, batTotals, pitTotals, unmatched };
  }
```

`api` 에 `rankFor, rankFromStandings, pythag, gameSplits, recordTable, recordFromGames, seasonView` 를 더합니다.

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS. 검증 5 의 차이 목록과 검증 6 의 팀별 득점 차이가 콘솔에 찍힙니다(2025 정규시즌 경기 결과는 719경기라 한 경기쯤 차이가 날 수 있습니다). 검증 5 가 실패하면 멈추고 차이 목록을 evan 에게 보고합니다.

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/metrics.js
git commit -m "feat(team-stats): 팀 성적 계산(순위표·피타고리안·홈원정·1점차·월별·상대 전적)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 기간별(경기 기록) 변환

**Files:**
- Modify: `dashboard_js/js/team-stats/metrics.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/metrics.range.test.js`

**Interfaces:**
- Consumes: `battingTable, pitchingTable, num, div`
- Produces:
  - `RANGE_BAT`, `RANGE_PIT` (내부 키 → `/stats/team_range` 칸 이름)
  - `rangeTotals(list, map)` → `{team: totals}` (응답에 있는 칸만)
  - `rangeBattingTable(resp, season, ix)` → battingTable 결과 모양
  - `rangePitchingTable(resp, season, ix)` → pitchingTable 결과 모양(`oavg` 는 응답의 H ÷ AB_against)
  - `resp` = `/stats/team_range` 응답 `{ batting: [{team,G,PA,AB,R,H,2B,3B,HR,BB,HBP,SO,SH,SF,TB,...}], pitching: [{team,G,IP_outs,H,R,BB,SO,HR,AB_against,...}], games, date_min, date_max, note }`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/metrics.range.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, refs, near } = require('./_load');
const M = load('metrics');

const ix = M.indexRefs(refs());
const resp = {
  batting: [
    { team: 'LG', G: 12, PA: 470, AB: 410, R: 60, H: 115, '2B': 22, '3B': 3, HR: 10, BB: 45, HBP: 6, SO: 80, SH: 4, SF: 5, TB: 173 },
    { team: '두산', G: 12, PA: 450, AB: 400, R: 48, H: 100, '2B': 18, '3B': 1, HR: 8, BB: 38, HBP: 5, SO: 90, SH: 3, SF: 4, TB: 144 },
  ],
  pitching: [
    { team: 'LG', G: 12, IP_outs: 324, H: 100, R: 48, BB: 38, SO: 90, HR: 8, AB_against: 400 },
    { team: '두산', G: 12, IP_outs: 321, H: 115, R: 60, BB: 45, SO: 80, HR: 10, AB_against: 410 },
  ],
  games: 12, date_min: 20250917, date_max: 20250930,
};

test('rangeBattingTable: 비율·wOBA·wRC+ 계산, 없는 칸은 키가 없음', () => {
  const v = M.rangeBattingTable(resp, 2025, ix);
  const lg = v.rows.find(r => r.team === 'LG');
  assert.ok(near(lg.avg, 115 / 410));
  assert.equal(lg.g, 12);
  assert.equal(typeof lg.woba, 'number');
  assert.equal(typeof lg.wrcp, 'number');
  assert.equal('rbi' in lg, false);
  assert.equal(v.league.wrcp, 100);
  assert.ok(near(v.ctx.L, 108 / 920));
});

test('rangePitchingTable: ERA·FIP 는 null, RA/9·피안타율은 계산', () => {
  const v = M.rangePitchingTable(resp, 2025, ix);
  const lg = v.rows.find(r => r.team === 'LG');
  assert.equal(lg.era, null);
  assert.equal(lg.fip, null);
  assert.equal(lg.erap, null);
  assert.ok(near(lg.ra9, 48 * 27 / 324));
  assert.ok(near(lg.oavg, 100 / 400));
  assert.ok(near(v.league.oavg, 215 / 810));
});

test('빈 응답이면 빈 표', () => {
  const v = M.rangeBattingTable({ batting: [], pitching: [] }, 2025, ix);
  assert.equal(v.rows.length, 0);
  const p = M.rangePitchingTable(null, 2025, ix);
  assert.equal(p.rows.length, 0);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/metrics.range.test.js`
Expected: FAIL — `M.rangeBattingTable is not a function`

- [ ] **Step 3: metrics.js 에 함수 추가**

`seasonView` 아래에 넣습니다:

```js
  // /stats/team_range 칸 → 내부 키입니다. 응답에 없는 칸(RBI·ER 등)은 넣지
  // 않습니다. 그래야 그 지표가 0 이 아니라 null 이 됩니다.
  const RANGE_BAT = {
    g: 'G', pa: 'PA', ab: 'AB', r: 'R', h: 'H', d2: '2B', d3: '3B', hr: 'HR',
    bb: 'BB', hbp: 'HBP', so: 'SO', sh: 'SH', sf: 'SF', tb: 'TB',
  };
  const RANGE_PIT = { g: 'G', outs: 'IP_outs', h: 'H', r: 'R', bb: 'BB', so: 'SO', hr: 'HR' };

  function rangeTotals(list, map) {
    const out = {};
    for (const x of list || []) {
      if (!x || !x.team) continue;
      const a = { team: x.team };
      for (const k in map) a[k] = num(x[map[k]]);
      out[x.team] = a;
    }
    return out;
  }

  /** 기간별 타격 표입니다. 리그 기준값은 같은 기간 리그 합입니다. */
  function rangeBattingTable(resp, season, ix) {
    return battingTable(rangeTotals(resp && resp.batting, RANGE_BAT), season, ix, Object.keys(RANGE_BAT));
  }

  /** 기간별 투구 표입니다. 피안타율은 응답의 AB_against 로 셉니다. */
  function rangePitchingTable(resp, season, ix) {
    const list = (resp && resp.pitching) || [];
    const tbl = pitchingTable(rangeTotals(list, RANGE_PIT), season, ix, Object.keys(RANGE_PIT));
    const by = {};
    let H = 0, AB = 0;
    for (const x of list) {
      by[x.team] = x;
      H += num(x.H);
      AB += num(x.AB_against);
    }
    tbl.rows.forEach(function (r) {
      const x = by[r.team];
      r.oavg = x ? div(num(x.H), num(x.AB_against)) : null;
    });
    tbl.league.oavg = div(H, AB);
    return tbl;
  }
```

`api` 에 `RANGE_BAT, RANGE_PIT, rangeTotals, rangeBattingTable, rangePitchingTable` 를 더합니다.

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS (모든 metrics 테스트)

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/metrics.js
git commit -m "feat(team-stats): 기간별(경기 기록) 팀 타격·투구 표 변환" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 1차 보고(사람 확인 지점)**

Task 2~4 콘솔 출력(검증 1·3·4·5·6·7 숫자)을 모아 evan 에게 짧게 보고합니다. 화면은 아직 그대로라 PNG 는 없습니다.

---

### Task 6: 칸 정의(columns.js)

**Files:**
- Create: `dashboard_js/js/team-stats/columns.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/columns.test.js`

**Interfaces:**
- Produces: `TeamStats.columns` = `{ BAT, PIT, REC, ORDER: {bat: [키], pit: [키]}, GROUPS: {bat: {dash, std, adv}, pit: {dash, std, adv}}, REC_KEYS: [키], def(tab, key) → {key, label, kind, desc, formula?, since?, range, index?, better?} | null, fmt(value, kind) → string }`
  - `tab` 은 `'bat' | 'pit' | 'rec'`.
  - `kind`: `int avg3 f1 f2 ip idx signed0 signed1 wl gb`.
  - `index`: `'high'`(높을수록 좋음) 또는 `'low'`(낮을수록 좋음). 지수 칸(wRC+·OPS+·ERA-·FIP-)에만 있습니다.
  - `better: 'low'` 이면 처음 정렬이 오름차순입니다.
  - `range: true` 이면 기간별에서도 계산됩니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/columns.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const C = load('columns');

test('묶음·팀 성적의 모든 키에 정의가 있음', () => {
  for (const tab of ['bat', 'pit']) {
    for (const g of ['dash', 'std', 'adv']) {
      for (const k of C.GROUPS[tab][g]) assert.ok(C.def(tab, k), `${tab}.${g}.${k}`);
    }
  }
  for (const k of C.REC_KEYS) assert.ok(C.def('rec', k), `rec.${k}`);
});

test('묶음 칸 목록이 설계와 같음', () => {
  assert.deepEqual(C.GROUPS.bat.dash, ['g', 'pa', 'hr', 'r', 'rbi', 'bbpct', 'kpct', 'iso', 'babip', 'avg', 'obp', 'slg', 'woba', 'wrcp']);
  assert.deepEqual(C.GROUPS.pit.dash, ['w', 'l', 'sv', 'g', 'gs', 'outs', 'k9', 'bb9', 'hr9', 'babip', 'lobpct', 'era', 'fip']);
  assert.deepEqual(C.REC_KEYS, ['g', 'w', 'l', 'd', 'pct', 'gb', 'r', 'ra', 'diff', 'pyth', 'expw', 'luck', 'home', 'away', 'onerun']);
});

test('모든 정의에 이름·형식·설명이 있음', () => {
  for (const tab of ['bat', 'pit', 'rec']) {
    for (const k of (tab === 'rec' ? C.REC_KEYS : C.ORDER[tab])) {
      const d = C.def(tab, k);
      assert.ok(d.label && d.kind && d.desc, `${tab}.${k}`);
      assert.ok(!/다\.$/.test(d.desc) || /니다\.$/.test(d.desc), `${tab}.${k} 설명은 정중체`);
    }
  }
});

test('지수 칸 방향', () => {
  assert.equal(C.def('bat', 'wrcp').index, 'high');
  assert.equal(C.def('bat', 'opsp').index, 'high');
  assert.equal(C.def('pit', 'erap').index, 'low');
  assert.equal(C.def('pit', 'fipp').index, 'low');
  assert.equal(C.def('bat', 'avg').index, undefined);
});

test('기간별 가능 여부', () => {
  assert.equal(C.def('bat', 'rbi').range, false);
  assert.equal(C.def('bat', 'wrcp').range, true);
  assert.equal(C.def('pit', 'era').range, false);
  assert.equal(C.def('pit', 'ra9').range, true);
});

test('fmt', () => {
  assert.equal(C.fmt(null, 'avg3'), '-');
  assert.equal(C.fmt(NaN, 'f1'), '-');
  assert.equal(C.fmt(0.2781, 'avg3'), '.278');
  assert.equal(C.fmt(1.2346, 'avg3'), '1.235');
  assert.equal(C.fmt(-0.0123, 'avg3'), '-.012');
  assert.equal(C.fmt(5481.3, 'int'), '5481');
  assert.equal(C.fmt(3871, 'ip'), '1290 1/3');
  assert.equal(C.fmt(3870, 'ip'), '1290');
  assert.equal(C.fmt(111.6, 'idx'), '112');
  assert.equal(C.fmt(190, 'signed0'), '+190');
  assert.equal(C.fmt(-5, 'signed0'), '-5');
  assert.equal(C.fmt(0, 'signed0'), '0');
  assert.equal(C.fmt(2, 'signed1'), '+2.0');
  assert.equal(C.fmt(-0.04, 'signed1'), '0.0');
  assert.equal(C.fmt({ w: 45, l: 26, d: 1 }, 'wl'), '45-26-1');
  assert.equal(C.fmt({ w: 20, l: 15, d: 0 }, 'wl'), '20-15');
  assert.equal(C.fmt(0, 'gb'), '-');
  assert.equal(C.fmt(1.5, 'gb'), '1.5');
  assert.equal(C.fmt(13, 'gb'), '13');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/columns.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (columns.js 가 아직 없음)

- [ ] **Step 3: columns.js 쓰기**

`dashboard_js/js/team-stats/columns.js`:

```js
/*
 * 팀 통계 표의 칸 정의입니다. 이름·형식·설명·계산식·시작 연도·기간별
 * 가능 여부를 한 곳에 둡니다. 화면(DOM)에는 손대지 않습니다.
 *
 *   kind   값 형식(fmt 참고)
 *   range  기간별(경기 기록)에서도 계산되면 true
 *   index  지수 칸(리그 평균 100). 'high' 는 높을수록, 'low' 는 낮을수록 좋음
 *   better 'low' 면 처음 정렬이 오름차순
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const PF_NOTE = '구장 보정 = (홈구장 득점 파크팩터 + 1000) ÷ 2000';

  const BAT = {
    g: { label: 'G', kind: 'int', range: true, desc: '팀이 치른 경기 수입니다. 시즌은 공식 순위표, 기간별은 경기 기록에서 셉니다.' },
    pa: { label: 'PA', kind: 'int', range: true, desc: '타석입니다.' },
    ab: { label: 'AB', kind: 'int', range: true, desc: '타수입니다.' },
    h: { label: 'H', kind: 'int', range: true, desc: '안타입니다.' },
    single: { label: '1B', kind: 'int', range: true, desc: '단타입니다.', formula: 'H − 2B − 3B − HR' },
    d2: { label: '2B', kind: 'int', range: true, desc: '2루타입니다.' },
    d3: { label: '3B', kind: 'int', range: true, desc: '3루타입니다.' },
    hr: { label: 'HR', kind: 'int', range: true, desc: '홈런입니다.' },
    r: { label: 'R', kind: 'int', range: true, desc: '득점입니다.' },
    rbi: { label: 'RBI', kind: 'int', range: false, desc: '타점입니다.' },
    bb: { label: 'BB', kind: 'int', range: true, desc: '볼넷입니다. 고의4구를 포함합니다.' },
    ibb: { label: 'IBB', kind: 'int', range: false, desc: '고의4구입니다.' },
    so: { label: 'SO', kind: 'int', range: true, better: 'low', desc: '삼진입니다.' },
    hbp: { label: 'HBP', kind: 'int', range: true, desc: '몸에 맞는 공입니다.' },
    sf: { label: 'SF', kind: 'int', range: true, desc: '희생플라이입니다.' },
    sh: { label: 'SH', kind: 'int', range: true, desc: '희생번트입니다.' },
    gdp: { label: 'GDP', kind: 'int', range: false, better: 'low', desc: '병살타입니다.' },
    tb: { label: 'TB', kind: 'int', range: true, desc: '루타입니다.' },
    xbh: { label: 'XBH', kind: 'int', range: false, desc: '장타(2루타·3루타·홈런)입니다.' },
    multi: { label: '멀티히트', kind: 'int', range: false, desc: '한 경기에 안타 두 개 이상을 친 횟수의 합입니다.' },
    gw: { label: 'GW RBI', kind: 'int', range: false, desc: '결승타점입니다.' },
    go: { label: 'GO', kind: 'int', range: false, desc: '땅볼 아웃입니다.' },
    ao: { label: 'AO', kind: 'int', range: false, desc: '뜬공 아웃입니다.' },
    goao: { label: 'GO/AO', kind: 'f2', range: false, desc: '뜬공 아웃 하나당 땅볼 아웃입니다.', formula: 'GO ÷ AO' },
    avg: { label: 'AVG', kind: 'avg3', range: true, desc: '타율입니다.', formula: 'H ÷ AB' },
    obp: { label: 'OBP', kind: 'avg3', range: true, desc: '출루율입니다.', formula: '(H + BB + HBP) ÷ (AB + BB + HBP + SF)' },
    slg: { label: 'SLG', kind: 'avg3', range: true, desc: '장타율입니다.', formula: 'TB ÷ AB' },
    ops: { label: 'OPS', kind: 'avg3', range: true, desc: '출루율과 장타율의 합입니다.', formula: 'OBP + SLG' },
    iso: { label: 'ISO', kind: 'avg3', range: true, desc: '순수 장타력입니다.', formula: 'SLG − AVG' },
    babip: { label: 'BABIP', kind: 'avg3', range: true, desc: '인플레이 타구의 타율입니다. 삼진·홈런을 뺀 타구만 셉니다.', formula: '(H − HR) ÷ (AB − SO − HR + SF)' },
    kpct: { label: 'K%', kind: 'f1', range: true, better: 'low', desc: '타석 대비 삼진 비율입니다.', formula: 'SO ÷ PA × 100' },
    bbpct: { label: 'BB%', kind: 'f1', range: true, desc: '타석 대비 볼넷 비율입니다.', formula: 'BB ÷ PA × 100' },
    bbk: { label: 'BB/K', kind: 'f2', range: true, desc: '삼진 하나당 볼넷입니다.', formula: 'BB ÷ SO' },
    woba: { label: 'wOBA', kind: 'avg3', range: true, since: 2008, desc: '타격 결과마다 득점 가치를 달리 매긴 출루율입니다. 가중치는 KBO 경기 기록으로 시즌마다 구합니다.', formula: '(wBB·BB + wHBP·HBP + w1B·1B + w2B·2B + w3B·3B + wHR·HR) ÷ (AB + BB + SF + HBP)' },
    wraa: { label: 'wRAA', kind: 'f1', range: true, since: 2008, desc: '리그 평균 타선보다 더 만든 득점입니다. 0이 평균입니다.', formula: '(wOBA − 리그 wOBA) ÷ wOBA 척도 × PA' },
    wrc: { label: 'wRC', kind: 'int', range: true, since: 2008, desc: 'wOBA로 잰 팀 득점 생산량입니다.', formula: '(wRAA ÷ PA + 리그 득점/PA) × PA' },
    wrcp: { label: 'wRC+', kind: 'idx', range: true, since: 2008, index: 'high', desc: '타석당 득점 생산을 리그 평균 100에 맞춘 값입니다. 110이면 평균보다 10% 더 만듭니다. 홈구장 영향을 반만 덜어 냅니다(선수 wRC+와 같은 방식).', formula: '(wRAA ÷ PA) ÷ 리그 득점/PA × 100 + (2 − 구장 보정) × 100. ' + PF_NOTE },
    opsp: { label: 'OPS+', kind: 'idx', range: true, index: 'high', desc: 'OPS를 리그 평균 100에 맞춘 값입니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다. 그 전은 파크팩터가 없어 보정하지 않습니다.', formula: '100 × (OBP ÷ 리그 OBP + SLG ÷ 리그 SLG − 1) ÷ 구장 보정. ' + PF_NOTE },
  };

  const PIT = {
    w: { label: 'W', kind: 'int', range: false, desc: '승리입니다.' },
    l: { label: 'L', kind: 'int', range: false, better: 'low', desc: '패배입니다.' },
    sv: { label: 'SV', kind: 'int', range: false, desc: '세이브입니다.' },
    hld: { label: 'HLD', kind: 'int', range: false, desc: '홀드입니다.' },
    bs: { label: 'BS', kind: 'int', range: false, better: 'low', desc: '블론 세이브입니다.' },
    svo: { label: 'SVO', kind: 'int', range: false, desc: '세이브 기회입니다.' },
    g: { label: 'G', kind: 'int', range: true, desc: '팀이 치른 경기 수입니다. 시즌은 공식 순위표, 기간별은 경기 기록에서 셉니다.' },
    gs: { label: 'GS', kind: 'int', range: false, desc: '선발 등판 수입니다.' },
    gf: { label: 'GF', kind: 'int', range: false, desc: '경기를 마무리한 횟수입니다.' },
    cg: { label: 'CG', kind: 'int', range: false, desc: '완투입니다.' },
    sho: { label: 'SHO', kind: 'int', range: false, desc: '완봉입니다.' },
    qs: { label: 'QS', kind: 'int', range: false, desc: '선발이 6이닝 이상 던지고 자책점 3점 이하로 막은 경기입니다.' },
    outs: { label: 'IP', kind: 'ip', range: true, desc: '던진 이닝입니다.' },
    tbf: { label: 'TBF', kind: 'int', range: false, desc: '상대한 타자 수입니다.' },
    np: { label: 'NP', kind: 'int', range: false, desc: '던진 공의 수입니다.' },
    h: { label: 'H', kind: 'int', range: true, better: 'low', desc: '내준 안타입니다.' },
    d2: { label: '2B', kind: 'int', range: false, better: 'low', desc: '내준 2루타입니다.' },
    d3: { label: '3B', kind: 'int', range: false, better: 'low', desc: '내준 3루타입니다.' },
    hr: { label: 'HR', kind: 'int', range: true, better: 'low', desc: '내준 홈런입니다.' },
    r: { label: 'R', kind: 'int', range: true, better: 'low', desc: '실점입니다.' },
    er: { label: 'ER', kind: 'int', range: false, better: 'low', desc: '자책점입니다.' },
    bb: { label: 'BB', kind: 'int', range: true, better: 'low', desc: '내준 볼넷입니다. 고의4구를 포함합니다.' },
    ibb: { label: 'IBB', kind: 'int', range: false, desc: '고의4구입니다.' },
    hbp: { label: 'HBP', kind: 'int', range: false, better: 'low', desc: '몸에 맞는 공입니다.' },
    so: { label: 'SO', kind: 'int', range: true, desc: '탈삼진입니다.' },
    wp: { label: 'WP', kind: 'int', range: false, better: 'low', desc: '폭투입니다.' },
    bk: { label: 'BK', kind: 'int', range: false, better: 'low', desc: '보크입니다.' },
    gidp: { label: 'GIDP', kind: 'int', range: false, desc: '유도한 병살입니다.' },
    go: { label: 'GO', kind: 'int', range: false, desc: '유도한 땅볼 아웃입니다.' },
    ao: { label: 'AO', kind: 'int', range: false, desc: '유도한 뜬공 아웃입니다.' },
    goao: { label: 'GO/AO', kind: 'f2', range: false, desc: '뜬공 아웃 하나당 땅볼 아웃입니다.', formula: 'GO ÷ AO' },
    era: { label: 'ERA', kind: 'f2', range: false, better: 'low', desc: '9이닝당 자책점입니다.', formula: 'ER × 9 ÷ IP' },
    ra9: { label: 'RA/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 실점입니다. 기간별은 자책점이 없어 ERA 대신 씁니다.', formula: 'R × 9 ÷ IP' },
    whip: { label: 'WHIP', kind: 'f2', range: true, better: 'low', desc: '이닝당 내준 안타와 볼넷입니다.', formula: '(H + BB) ÷ IP' },
    k9: { label: 'K/9', kind: 'f2', range: true, desc: '9이닝당 탈삼진입니다.', formula: 'SO × 9 ÷ IP' },
    bb9: { label: 'BB/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 볼넷입니다.', formula: 'BB × 9 ÷ IP' },
    h9: { label: 'H/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 피안타입니다.', formula: 'H × 9 ÷ IP' },
    hr9: { label: 'HR/9', kind: 'f2', range: true, better: 'low', desc: '9이닝당 피홈런입니다.', formula: 'HR × 9 ÷ IP' },
    kbb: { label: 'K/BB', kind: 'f2', range: true, desc: '볼넷 하나당 탈삼진입니다.', formula: 'SO ÷ BB' },
    kpct: { label: 'K%', kind: 'f1', range: false, desc: '상대 타자 대비 탈삼진 비율입니다.', formula: 'SO ÷ TBF × 100' },
    bbpct: { label: 'BB%', kind: 'f1', range: false, better: 'low', desc: '상대 타자 대비 볼넷 비율입니다.', formula: 'BB ÷ TBF × 100' },
    kbbpct: { label: 'K−BB%', kind: 'f1', range: false, desc: '탈삼진 비율에서 볼넷 비율을 뺀 값입니다.', formula: 'K% − BB%' },
    oavg: { label: 'AVG', kind: 'avg3', range: true, better: 'low', desc: '피안타율입니다.', formula: 'H ÷ (TBF − BB − HBP − SH − SF)' },
    babip: { label: 'BABIP', kind: 'avg3', range: false, better: 'low', desc: '인플레이 타구의 피안타율입니다.', formula: '(H − HR) ÷ (TBF − BB − HBP − SH − SO − HR)' },
    lobpct: { label: 'LOB%', kind: 'f1', range: false, desc: '잔루 처리율입니다. 내보낸 주자를 실점 없이 남긴 비율입니다.', formula: '(H + BB + HBP − R) ÷ (H + BB + HBP − 1.4 × HR) × 100' },
    pip: { label: 'P/IP', kind: 'f1', range: false, better: 'low', desc: '1이닝당 투구 수입니다.', formula: 'NP ÷ IP' },
    fip: { label: 'FIP', kind: 'f2', range: false, better: 'low', desc: '수비와 상관없는 홈런·볼넷·몸에 맞는 공·삼진만으로 매긴 평균자책점입니다. 리그 평균이 리그 ERA와 같도록 상수를 맞춥니다.', formula: '(13·HR + 3·(BB − IBB + HBP) − 2·SO) ÷ IP + 상수. 상수 = 리그 ERA − (13·리그 HR + 3·(리그 BB − 리그 IBB + 리그 HBP) − 2·리그 SO) ÷ 리그 IP' },
    ef: { label: 'E−F', kind: 'f2', range: false, desc: 'ERA에서 FIP를 뺀 값입니다. 양수면 수비나 운 때문에 실점이 더 났을 수 있습니다.', formula: 'ERA − FIP' },
    erap: { label: 'ERA-', kind: 'idx', range: false, index: 'low', better: 'low', desc: 'ERA를 리그 평균 100에 맞춘 값입니다. 낮을수록 좋습니다. 90이면 평균보다 10% 덜 내줍니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다.', formula: '100 × ERA × (2 − 구장 보정) ÷ 리그 ERA. ' + PF_NOTE },
    fipp: { label: 'FIP-', kind: 'idx', range: false, index: 'low', better: 'low', desc: 'FIP를 리그 평균 100에 맞춘 값입니다. 낮을수록 좋습니다. 2008년부터 홈구장 영향을 반만 덜어 냅니다.', formula: '100 × FIP × (2 − 구장 보정) ÷ 리그 FIP. ' + PF_NOTE },
  };

  const REC = {
    g: { label: 'G', kind: 'int', range: true, desc: '치른 경기 수입니다.' },
    w: { label: 'W', kind: 'int', range: true, desc: '승리입니다.' },
    l: { label: 'L', kind: 'int', range: true, better: 'low', desc: '패배입니다.' },
    d: { label: 'D', kind: 'int', range: true, desc: '무승부입니다.' },
    pct: { label: '승률', kind: 'avg3', range: true, desc: '승률입니다. 무승부는 뺍니다.', formula: 'W ÷ (W + L)' },
    gb: { label: '승차', kind: 'gb', range: true, better: 'low', desc: '1위와의 승차입니다. 시즌은 공식 순위표 값이고, 1999·2000년은 리그 안에서 잰 값입니다.', formula: '((1위 W − W) + (L − 1위 L)) ÷ 2' },
    r: { label: 'R', kind: 'int', range: true, desc: '팀 득점입니다. 시즌은 공식 타자 기록 합, 기간별은 경기 점수 합입니다.' },
    ra: { label: 'RA', kind: 'int', range: true, better: 'low', desc: '팀 실점입니다. 시즌은 공식 투수 기록 합, 기간별은 경기 점수 합입니다.' },
    diff: { label: '득실차', kind: 'signed0', range: true, desc: '득점에서 실점을 뺀 값입니다.', formula: 'R − RA' },
    pyth: { label: '피타고리안', kind: 'avg3', range: true, desc: '득점과 실점만으로 계산한 기대 승률입니다.', formula: 'R^1.83 ÷ (R^1.83 + RA^1.83)' },
    expw: { label: '기대 승', kind: 'f1', range: true, desc: '피타고리안 승률로 본 기대 승수입니다.', formula: '피타고리안 × (W + L)' },
    luck: { label: '승수 차', kind: 'signed1', range: true, desc: '실제 승수에서 기대 승수를 뺀 값입니다. 양수면 득실에 비해 많이 이겼습니다.', formula: 'W − 기대 승' },
    home: { label: '홈', kind: 'wl', range: true, since: 2008, desc: '홈 경기 승-패(-무)입니다.' },
    away: { label: '원정', kind: 'wl', range: true, since: 2008, desc: '원정 경기 승-패(-무)입니다.' },
    onerun: { label: '1점차', kind: 'wl', range: true, since: 2008, desc: '1점 차로 끝난 경기의 승-패입니다.' },
  };

  const GROUPS = {
    bat: {
      dash: ['g', 'pa', 'hr', 'r', 'rbi', 'bbpct', 'kpct', 'iso', 'babip', 'avg', 'obp', 'slg', 'woba', 'wrcp'],
      std: ['g', 'pa', 'ab', 'h', 'single', 'd2', 'd3', 'hr', 'r', 'rbi', 'bb', 'ibb', 'so', 'hbp', 'sf', 'sh', 'gdp', 'avg'],
      adv: ['pa', 'bbpct', 'kpct', 'bbk', 'avg', 'obp', 'slg', 'ops', 'iso', 'babip', 'woba', 'wraa', 'wrc', 'wrcp', 'opsp'],
    },
    pit: {
      dash: ['w', 'l', 'sv', 'g', 'gs', 'outs', 'k9', 'bb9', 'hr9', 'babip', 'lobpct', 'era', 'fip'],
      std: ['w', 'l', 'era', 'g', 'gs', 'cg', 'sho', 'sv', 'hld', 'bs', 'outs', 'tbf', 'h', 'r', 'er', 'hr', 'bb', 'ibb', 'hbp', 'wp', 'bk', 'so'],
      adv: ['k9', 'bb9', 'kbb', 'hr9', 'kpct', 'bbpct', 'kbbpct', 'oavg', 'whip', 'babip', 'lobpct', 'erap', 'fipp', 'fip', 'ef'],
    },
  };
  const REC_KEYS = Object.keys(REC);
  const ORDER = { bat: Object.keys(BAT), pit: Object.keys(PIT) };
  const TABLES = { bat: BAT, pit: PIT, rec: REC };

  /** 칸 정의를 key 를 붙여 돌려줍니다. 없으면 null. */
  function def(tab, key) {
    const t = TABLES[tab];
    const d = t && Object.prototype.hasOwnProperty.call(t, key) ? t[key] : null;
    return d ? Object.assign({ key: key }, d) : null;
  }

  /** 값을 화면 글자로 바꿉니다. 없거나 숫자가 아니면 '-'. */
  function fmt(v, kind) {
    if (v === null || v === undefined) return '-';
    if (kind === 'wl') {
      if (typeof v !== 'object') return '-';
      return v.d ? `${v.w}-${v.l}-${v.d}` : `${v.w}-${v.l}`;
    }
    const n = Number(v);
    if (!Number.isFinite(n)) return '-';
    switch (kind) {
      case 'avg3': return n.toFixed(3).replace(/^(-?)0\./, '$1.');
      case 'f1': return n.toFixed(1);
      case 'f2': return n.toFixed(2);
      case 'idx': return String(Math.round(n));
      case 'ip': {
        const o = Math.round(n), w = Math.floor(o / 3), r = o % 3;
        return r ? `${w} ${r}/3` : String(w);
      }
      case 'signed0': {
        const s = Math.round(n);
        return s > 0 ? '+' + s : String(s === 0 ? 0 : s);
      }
      case 'signed1': {
        const s = n.toFixed(1);
        if (s === '-0.0' || s === '0.0') return '0.0';
        return n > 0 ? '+' + s : s;
      }
      case 'gb':
        if (n === 0) return '-';
        return Number.isInteger(n) ? String(n) : n.toFixed(1);
      case 'int':
      default:
        return String(Math.round(n));
    }
  }

  const api = { BAT, PIT, REC, ORDER, GROUPS, REC_KEYS, def, fmt };
  TS.columns = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/columns.js
git commit -m "feat(team-stats): 탭·묶음별 칸 정의와 지표 설명·계산식" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 데이터 받기(data.js)

**Files:**
- Create: `dashboard_js/js/team-stats/data.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/data.test.js`

**Interfaces:**
- Produces: `TeamStats.data` = `{ badReason(json, listKey) → string|null, getJson(url, listKey, fetchImpl?) → Promise<{ok, data?, error?}>, loadRefs(base, opts?) → Promise<{weights, pf, stadium, rank, errors}>, loadSeason(base, season, opts?) → Promise<{batters, pitchers, errors}>, loadGames(base, season, opts?) → Promise<{games, errors}>, loadRange(base, start, end, opts?) → Promise<{data, errors}>, loadStandings(base, opts?) → Promise<{teams, errors}>, loadSeasons(base, opts?) → Promise<number[]> }`
  - `opts` = `{ fetch, store }` (테스트용. 브라우저에서는 비워 둡니다)
  - `errors` = `[{ what: '파크팩터', error: 'D1_ERROR: …' }]`
  - 실패한 응답은 sessionStorage 에 넣지 않습니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/data.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const D = load('data');

function fakeStore() {
  const m = new Map();
  return { getItem: k => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), _m: m };
}
function fakeFetch(map) {
  const calls = [];
  const f = async url => {
    calls.push(url);
    for (const key of Object.keys(map)) {
      if (url.includes(key)) {
        const r = map[key];
        return { ok: r.status === undefined || r.status < 400, status: r.status || 200, json: async () => r.body };
      }
    }
    return { ok: false, status: 404, json: async () => ({}) };
  };
  f.calls = calls;
  return f;
}

test('badReason', () => {
  assert.equal(D.badReason({ rows: [1] }, 'rows'), null);
  assert.match(D.badReason({ detail: 'D1_ERROR: x' }, 'rows'), /D1_ERROR/);
  assert.match(D.badReason({ error: 'boom' }), /boom/);
  assert.match(D.badReason({ rows: [] }, 'rows'), /비어/);
  assert.match(D.badReason({}, 'rows'), /없습니다/);
  assert.match(D.badReason(null), /비어/);
  assert.equal(D.badReason({ batting: [] }), null);
});

test('getJson: HTTP 오류·detail·예외', async () => {
  const f = fakeFetch({ '/a': { status: 500, body: {} }, '/b': { body: { detail: 'D1_ERROR: export' } }, '/c': { body: { rows: [1] } } });
  assert.deepEqual(await D.getJson('x/a', 'rows', f), { ok: false, error: 'HTTP 500' });
  const b = await D.getJson('x/b', 'rows', f);
  assert.equal(b.ok, false);
  assert.match(b.error, /export/);
  assert.equal((await D.getJson('x/c', 'rows', f)).ok, true);
  const thrown = await D.getJson('x/c', 'rows', async () => { throw new Error('net down'); });
  assert.equal(thrown.ok, false);
  assert.match(thrown.error, /net down/);
});

test('loadRefs: 성공한 표만 저장하고, 실패는 이름과 이유를 남김', async () => {
  const store = fakeStore();
  const f = fakeFetch({
    kbo_woba_weights_by_season: { body: { rows: [{ season: 2025 }] } },
    self_park_factor: { body: { detail: 'D1_ERROR: Currently processing a long-running export.' } },
    team_stadium_by_season: { body: { rows: [{ player_team: 'LG' }] } },
    team_season_rank: { body: { rows: [{ team_name: 'LG' }] } },
  });
  const r = await D.loadRefs('B', { fetch: f, store });
  assert.equal(r.weights.length, 1);
  assert.deepEqual(r.pf, []);
  assert.equal(r.errors.length, 1);
  assert.equal(r.errors[0].what, '파크팩터');
  assert.match(r.errors[0].error, /export/);
  assert.ok(f.calls.includes('B/db/table/self_park_factor?limit=500'));
  assert.equal(store.getItem('ts_ref_self_park_factor_v1'), null);
  assert.ok(store.getItem('ts_ref_kbo_woba_weights_by_season_v1'));
  const f2 = fakeFetch({});
  const r2 = await D.loadRefs('B', { fetch: f2, store });
  assert.equal(r2.weights.length, 1);
  assert.ok(!f2.calls.some(u => u.includes('kbo_woba_weights_by_season')));
  assert.ok(f2.calls.some(u => u.includes('self_park_factor')));
});

test('loadSeason: 지금 페이지와 같은 주소, 실패는 errors 로', async () => {
  const f = fakeFetch({ '/stats/batters': { body: { batters: [{ a: 1 }] } }, '/stats/pitchers': { body: { pitchers: [] } } });
  const r = await D.loadSeason('B', 2025, { fetch: f });
  assert.ok(f.calls.includes('B/stats/batters?season=2025&limit=2000&min_pa=0'));
  assert.ok(f.calls.includes('B/stats/pitchers?season=2025&limit=2000&min_ip=0'));
  assert.equal(r.batters.length, 1);
  assert.equal(r.errors.length, 1);
  assert.equal(r.errors[0].what, '투수 기록');
});

test('loadGames·loadRange 주소', async () => {
  const f = fakeFetch({ '/games': { body: { games: [{ g: 1 }] } }, '/stats/team_range': { body: { batting: [], pitching: [], games: 0 } } });
  const g = await D.loadGames('B', 2025, { fetch: f });
  assert.equal(g.games.length, 1);
  assert.ok(f.calls.includes('B/games?season=2025&limit=1000'));
  const r = await D.loadRange('B', '2025-09-17', '2025-09-30', { fetch: f });
  assert.deepEqual(r.errors, []);
  assert.equal(r.data.games, 0);
  assert.ok(f.calls.includes('B/stats/team_range?start=2025-09-17&end=2025-09-30'));
});

test('loadStandings: 200 이어도 error 필드면 실패로', async () => {
  const f = fakeFetch({ '/standings': { body: { teams: [], error: 'KBO 응답 없음' } } });
  const r = await D.loadStandings('B', { fetch: f });
  assert.deepEqual(r.teams, []);
  assert.equal(r.errors[0].what, '실시간 순위');
  assert.match(r.errors[0].error, /KBO/);
  const ok = await D.loadStandings('B', { fetch: fakeFetch({ '/standings': { body: { teams: [{ team: 'KT' }] } } }) });
  assert.equal(ok.teams.length, 1);
  assert.deepEqual(ok.errors, []);
});

test('loadSeasons: 내림차순, 실패하면 올해~1982', async () => {
  const store = fakeStore();
  const ok = await D.loadSeasons('B', { fetch: fakeFetch({ '/stats/seasons': { body: { seasons: [2025, 2026, 1982] } } }), store });
  assert.deepEqual(ok, [2026, 2025, 1982]);
  const bad = await D.loadSeasons('B', { fetch: fakeFetch({}), store: fakeStore() });
  assert.equal(bad[bad.length - 1], 1982);
  assert.ok(bad[0] >= 2026);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/data.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (data.js 가 아직 없음)

- [ ] **Step 3: data.js 쓰기**

`dashboard_js/js/team-stats/data.js`:

```js
/*
 * 팀 통계 데이터 받기입니다.
 *
 * 응답이 이상하면(HTTP 오류, detail·error 필드, 빈 목록) 가리지 않고
 * errors 에 이유를 담아 돌려줍니다. 화면은 그것을 표 위에 알립니다.
 * 실패한 응답은 sessionStorage 에 넣지 않습니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  /** 응답이 이상하면 이유, 괜찮으면 null 입니다. listKey 가 있으면 그 목록이 비어도 이상입니다. */
  function badReason(json, listKey) {
    if (json === null || json === undefined || typeof json !== 'object') return '응답이 비어 있습니다';
    if (json.detail) return String(json.detail);
    if (json.error) return String(json.error);
    if (listKey) {
      const v = json[listKey];
      if (!Array.isArray(v)) return `${listKey} 목록이 없습니다`;
      if (!v.length) return `${listKey} 목록이 비어 있습니다`;
    }
    return null;
  }

  async function getJson(url, listKey, fetchImpl) {
    const f = fetchImpl || root.fetch.bind(root);
    try {
      const res = await f(url);
      if (!res.ok) return { ok: false, error: `HTTP ${res.status}` };
      const json = await res.json();
      const why = badReason(json, listKey);
      return why ? { ok: false, error: why } : { ok: true, data: json };
    } catch (e) {
      return { ok: false, error: String((e && e.message) || e) };
    }
  }

  function storeOf(opts) {
    if (opts && opts.store) return opts.store;
    try { return root.sessionStorage || null; } catch (e) { return null; }
  }
  function cacheGet(key, opts) {
    try {
      const s = storeOf(opts);
      const v = s ? s.getItem(key) : null;
      return v ? JSON.parse(v) : null;
    } catch (e) { return null; }
  }
  function cacheSet(key, val, opts) {
    try {
      const s = storeOf(opts);
      if (s) s.setItem(key, JSON.stringify(val));
    } catch (e) { /* 저장 공간이 없으면 넘어갑니다 */ }
  }

  // 시즌과 상관없는 참조 표입니다. 데이터 탐색 주소(/db/table)로 받습니다.
  // 팀 통계용 전용 주소가 생기면 여기만 바꿉니다(설계 문서 10장).
  const REF_TABLES = {
    weights: 'kbo_woba_weights_by_season',
    pf: 'self_park_factor',
    stadium: 'team_stadium_by_season',
    rank: 'team_season_rank',
  };
  const REF_LABEL = { weights: 'wOBA 가중치', pf: '파크팩터', stadium: '팀 홈구장', rank: '순위표' };

  async function loadRefs(base, opts) {
    opts = opts || {};
    const out = { errors: [] };
    await Promise.all(Object.keys(REF_TABLES).map(async function (k) {
      const name = REF_TABLES[k];
      const key = `ts_ref_${name}_v1`;
      const hit = cacheGet(key, opts);
      if (Array.isArray(hit) && hit.length) { out[k] = hit; return; }
      const r = await getJson(`${base}/db/table/${name}?limit=500`, 'rows', opts.fetch);
      if (r.ok) {
        out[k] = r.data.rows;
        cacheSet(key, r.data.rows, opts);
      } else {
        out[k] = [];
        out.errors.push({ what: REF_LABEL[k], error: r.error });
      }
    }));
    return out;
  }

  // 주소는 지금 페이지(API.getBatterStats(season, 2000, 0, ''))와 같게 둡니다.
  // 같은 주소라야 엣지 캐시를 같이 씁니다.
  async function loadSeason(base, season, opts) {
    opts = opts || {};
    const res = await Promise.all([
      getJson(`${base}/stats/batters?season=${season}&limit=2000&min_pa=0`, 'batters', opts.fetch),
      getJson(`${base}/stats/pitchers?season=${season}&limit=2000&min_ip=0`, 'pitchers', opts.fetch),
    ]);
    const b = res[0], p = res[1];
    const errors = [];
    if (!b.ok) errors.push({ what: '타자 기록', error: b.error });
    if (!p.ok) errors.push({ what: '투수 기록', error: p.error });
    return { batters: b.ok ? b.data.batters : [], pitchers: p.ok ? p.data.pitchers : [], errors: errors };
  }

  async function loadGames(base, season, opts) {
    const r = await getJson(`${base}/games?season=${season}&limit=1000`, 'games', (opts || {}).fetch);
    return { games: r.ok ? r.data.games : [], errors: r.ok ? [] : [{ what: '경기 결과', error: r.error }] };
  }

  // 기간에 경기가 없으면 빈 목록이 정상이라 listKey 를 주지 않습니다.
  async function loadRange(base, start, end, opts) {
    const url = `${base}/stats/team_range?start=${encodeURIComponent(start)}&end=${encodeURIComponent(end)}`;
    const r = await getJson(url, null, (opts || {}).fetch);
    return { data: r.ok ? r.data : null, errors: r.ok ? [] : [{ what: '기간별 기록', error: r.error }] };
  }

  /**
   * 실시간 순위(올해)입니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있어
   * 올해는 이것을 씁니다. 이 주소는 실패해도 200 과 error 필드를 줍니다.
   */
  async function loadStandings(base, opts) {
    const r = await getJson(`${base}/standings`, 'teams', (opts || {}).fetch);
    return { teams: r.ok ? r.data.teams : [], errors: r.ok ? [] : [{ what: '실시간 순위', error: r.error }] };
  }

  /** 공식 기록이 있는 시즌(내림차순)입니다. 실패하면 올해~1982 입니다. */
  async function loadSeasons(base, opts) {
    opts = opts || {};
    const KEY = 'teamstats_seasons_v2';
    const desc = list => list.map(Number).filter(Number.isFinite).sort((a, b) => b - a);
    const hit = cacheGet(KEY, opts);
    if (Array.isArray(hit) && hit.length) return desc(hit);
    const r = await getJson(`${base}/stats/seasons`, 'seasons', opts.fetch);
    if (r.ok) {
      cacheSet(KEY, r.data.seasons, opts);
      return desc(r.data.seasons);
    }
    const list = [];
    for (let y = new Date().getFullYear(); y >= 1982; y--) list.push(y);
    return list;
  }

  const api = { badReason, getJson, loadRefs, loadSeason, loadGames, loadRange, loadStandings, loadSeasons };
  TS.data = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/data.js
git commit -m "feat(team-stats): 데이터 받기와 이상 응답 판정(실패는 저장하지 않음)" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: 표 그리기(table.js)

**Files:**
- Create: `dashboard_js/js/team-stats/table.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/table.test.js`

**Interfaces:**
- Consumes: `TeamStats.columns.fmt`
- Produces: `TeamStats.table` = `{ esc(s), indexClass(v, dir) → '' | 'ts-up1..3' | 'ts-down1..3', sortRows(rows, key, dir, kind) → 새 배열, renderTable(opt) → HTML, toCsv(opt) → 문자열, tipHtml(def) → HTML, glossaryHtml(defs) → HTML }`
  - `opt` = `{ cols: [def], rows: [팀 행], league: 행|null, sort: {key, dir}, teamHref?: fn(team)→주소|null, highlight?: 팀 이름, rank?: bool(기본 true) }`
  - 표에는 `#`·`팀` 칸이 앞에 붙습니다. 머리글은 `<th class="sortable" data-key="키"><span class="ts-term" data-col="키">이름</span></th>` 입니다.
  - 리그 평균 행은 정렬과 상관없이 맨 아래(`tr.ts-league`)입니다.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/table.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
const C = load('columns');
const T = load('table');

const cols = [C.def('bat', 'avg'), C.def('bat', 'wrcp'), C.def('rec', 'home')];
const rows = [
  { team: 'A', avg: 0.250, wrcp: 112, home: { w: 10, l: 5, d: 0 } },
  { team: 'B<x>', avg: 0.280, wrcp: null, home: { w: 6, l: 9, d: 1 } },
  { team: 'C', avg: 0.260, wrcp: 85, home: null },
];
const league = { team: '리그 평균', isLeague: true, avg: 0.263, wrcp: 100, home: null };

test('indexClass: 리그 평균에서 떨어진 정도', () => {
  assert.equal(T.indexClass(112, 'high'), 'ts-up3');
  assert.equal(T.indexClass(106, 'high'), 'ts-up2');
  assert.equal(T.indexClass(103, 'high'), 'ts-up1');
  assert.equal(T.indexClass(101, 'high'), '');
  assert.equal(T.indexClass(98, 'high'), 'ts-down1');
  assert.equal(T.indexClass(85, 'high'), 'ts-down3');
  assert.equal(T.indexClass(85, 'low'), 'ts-up3');
  assert.equal(T.indexClass(null, 'high'), '');
});

test('sortRows: 값이 없으면 방향과 상관없이 맨 아래', () => {
  assert.deepEqual(T.sortRows(rows, 'wrcp', 'desc', 'idx').map(r => r.team), ['A', 'C', 'B<x>']);
  assert.deepEqual(T.sortRows(rows, 'wrcp', 'asc', 'idx').map(r => r.team), ['C', 'A', 'B<x>']);
  assert.deepEqual(T.sortRows(rows, 'home', 'desc', 'wl').map(r => r.team), ['A', 'B<x>', 'C']);
  assert.notEqual(T.sortRows(rows, 'avg', 'desc', 'avg3'), rows);
});

test('renderTable: 머리글·정렬 표시·리그 행 맨 아래·색·이스케이프', () => {
  const h = T.renderTable({ cols, rows, league, sort: { key: 'avg', dir: 'asc' }, teamHref: t => (t === 'A' ? 'team-record?id=A' : null) });
  assert.match(h, /<th class="sortable sorted" data-key="avg"><span class="ts-term" data-col="avg">AVG<\/span><span class="sort-ind">▲<\/span><\/th>/);
  assert.ok(h.indexOf('>A<') < h.indexOf('ts-league'));
  assert.ok(h.lastIndexOf('<tr') === h.indexOf('<tr class="ts-league">'));
  assert.match(h, /B&lt;x&gt;/);
  assert.match(h, /<td class="ts-up3">112<\/td>/);
  assert.match(h, /href="team-record\?id=A"/);
  assert.match(h, /<td>-<\/td>/);
  assert.match(h, /10-5/);
  assert.match(h, /6-9-1/);
  assert.ok(!/ts-up|ts-down/.test(h.slice(h.indexOf('ts-league'))));
});

test('renderTable: rank:false 면 # 칸이 없음, highlight 행 강조', () => {
  const h = T.renderTable({ cols, rows, league: null, sort: { key: 'avg', dir: 'desc' }, rank: false, highlight: 'C' });
  assert.ok(!h.includes('ts-rank'));
  assert.match(h, /<tr class="ts-hl">/);
});

test('toCsv: BOM·머리글·화면 글자 그대로·리그 행·따옴표', () => {
  const csv = T.toCsv({ cols, rows: [{ team: 'A,1', avg: 0.25, wrcp: 112, home: { w: 1, l: 2, d: 0 } }], league, sort: { key: 'avg', dir: 'desc' } });
  assert.ok(csv.startsWith('\uFEFF#,팀,AVG,wRC+,홈\r\n'));
  assert.match(csv, /1,"A,1",\.250,112,1-2\r\n/);
  assert.match(csv, /,리그 평균,\.263,100,-\r\n$/);
});

test('tipHtml·glossaryHtml', () => {
  const tip = T.tipHtml(C.def('bat', 'wrcp'));
  assert.match(tip, /<b>wRC\+<\/b>/);
  assert.match(tip, /계산식:/);
  assert.match(tip, /2008년부터/);
  const g = T.glossaryHtml([C.def('bat', 'avg')]);
  assert.match(g, /<dt>AVG<\/dt>/);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/table.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (table.js 가 아직 없음)

- [ ] **Step 3: table.js 쓰기**

`dashboard_js/js/team-stats/table.js`:

```js
/*
 * 팀 통계 표 그리기입니다. HTML 문자열을 만들 뿐 DOM 에 붙이지는 않습니다
 * (붙이는 일은 page.js). columns.js 가 먼저 로드되어야 합니다.
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
    const d = (v - 100) * (dir === 'low' ? -1 : 1);
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

  function rowHtml(r, rank, opt, isLeague) {
    const showRank = opt.rank !== false;
    const href = !isLeague && opt.teamHref ? opt.teamHref(r.team) : null;
    const name = isLeague ? '리그 평균' : r.team;
    const tcell = href ? `<a class="player-link" href="${esc(href)}">${esc(name)}</a>` : esc(name);
    const cls = isLeague ? ' class="ts-league"' : (opt.highlight && opt.highlight === r.team ? ' class="ts-hl"' : '');
    let h = `<tr${cls}>`;
    if (showRank) h += `<td class="ts-rank">${rank}</td>`;
    h += `<td class="ts-team">${tcell}</td>`;
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

  /** 표 HTML 입니다. 리그 평균 행은 정렬과 상관없이 맨 아래입니다. */
  function renderTable(opt) {
    const showRank = opt.rank !== false;
    let h = '<div class="table-container ts-wrap"><table class="table ts-table"><thead><tr>';
    if (showRank) h += '<th class="ts-rank">#</th>';
    h += '<th class="ts-team">팀</th>';
    for (const c of opt.cols) {
      const on = opt.sort && opt.sort.key === c.key;
      const ind = on ? `<span class="sort-ind">${opt.sort.dir === 'asc' ? '▲' : '▼'}</span>` : '';
      h += `<th class="sortable${on ? ' sorted' : ''}" data-key="${esc(c.key)}">`
        + `<span class="ts-term" data-col="${esc(c.key)}">${esc(c.label)}</span>${ind}</th>`;
    }
    h += '</tr></thead><tbody>';
    sorted(opt).forEach(function (r, i) { h += rowHtml(r, i + 1, opt, false); });
    if (opt.league) h += rowHtml(opt.league, '', opt, true);
    return h + '</tbody></table></div>';
  }

  function csvCell(s) {
    s = String(s);
    return /[",\r\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s;
  }

  /** 지금 보이는 표 그대로의 CSV 입니다. 엑셀용 BOM 을 붙입니다. */
  function toCsv(opt) {
    const lines = [['#', '팀'].concat(opt.cols.map(c => c.label))];
    sorted(opt).forEach(function (r, i) {
      lines.push([i + 1, r.team].concat(opt.cols.map(c => C().fmt(r[c.key], c.kind))));
    });
    if (opt.league) lines.push(['', '리그 평균'].concat(opt.cols.map(c => C().fmt(opt.league[c.key], c.kind))));
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

  /** 표 아래 '지표 설명' 목록입니다. */
  function glossaryHtml(defs) {
    return defs.filter(Boolean).map(function (d) {
      let dd = esc(d.desc);
      if (d.formula) dd += ` 계산식: ${esc(d.formula)}`;
      if (d.since) dd += ` ${d.since}년부터 있습니다.`;
      return `<dt>${esc(d.label)}</dt><dd>${dd}</dd>`;
    }).join('');
  }

  const api = { esc, indexClass, sortRows, renderTable, toCsv, tipHtml, glossaryHtml };
  TS.table = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/table.js
git commit -m "feat(team-stats): 정렬 표·리그 평균 행·지수 색·설명 창·CSV" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: 상대 전적·월별 승률(record.js)

**Files:**
- Create: `dashboard_js/js/team-stats/record.js`
- Create: `C:/tmp/bstats-team-stats-check/tests/record.test.js`

**Interfaces:**
- Consumes: `TeamStats.table.esc`, `TeamStats.columns.fmt`, `metrics.gameSplits` 결과 모양
- Produces: `TeamStats.record` = `{ h2hHtml(splits, order, highlight) → HTML, monthlyHtml(splits, order, highlight) → HTML, noGamesHtml(season) → HTML }`
  - `order` = 팀 이름 배열(승률 순). 가로 줄 팀이 세로 칸 팀을 상대로 거둔 승-패(-무), 맨 오른쪽 합계.

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/record.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load, fixture } = require('./_load');
const M = load('metrics');
load('columns');
load('table');
const Rec = load('record');

const s = {
  A: { team: 'A', vs: { B: { w: 9, l: 7, d: 0 } }, month: { 4: { w: 5, l: 3, d: 0 }, 5: { w: 4, l: 4, d: 1 } } },
  B: { team: 'B', vs: { A: { w: 7, l: 9, d: 0 } }, month: { 4: { w: 3, l: 5, d: 0 } } },
};

test('h2hHtml: 자기 칸·승패 색·합계·강조', () => {
  const h = Rec.h2hHtml(s, ['A', 'B'], 'B');
  assert.match(h, /ts-h2h/);
  assert.match(h, /<td class="ts-self">·<\/td>/);
  assert.match(h, /<td class="ts-win">9-7<\/td>/);
  assert.match(h, /<td class="ts-loss">7-9<\/td>/);
  assert.match(h, /<td class="ts-total">9-7-0<\/td>/);
  assert.match(h, /<tr class="ts-hl"><td class="ts-team">B<\/td>/);
});

test('monthlyHtml: 3·4월 묶음, 없는 달은 -', () => {
  const h = Rec.monthlyHtml(s, ['A', 'B'], '');
  assert.match(h, /<th>3·4월<\/th><th>5월<\/th>/);
  assert.match(h, /\.625/);
  assert.match(h, /<td>-<\/td>/);
});

test('noGamesHtml', () => {
  assert.match(Rec.noGamesHtml(1985), /2008년부터/);
});

test('2025 실데이터로 10×10 표', () => {
  const sp = M.gameSplits(fixture('games_2025').games);
  const order = Object.keys(sp);
  const h = Rec.h2hHtml(sp, order, '');
  assert.equal((h.match(/ts-self/g) || []).length, 10);
  assert.equal((h.match(/ts-total/g) || []).length, 10);
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/record.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (record.js 가 아직 없음)

- [ ] **Step 3: record.js 쓰기**

`dashboard_js/js/team-stats/record.js`:

```js
/*
 * 팀 성적 탭의 상대 전적·월별 승률 표입니다. HTML 문자열만 만듭니다.
 * table.js·columns.js 가 먼저 로드되어야 합니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};
  function esc(s) { return TS.table.esc(s); }
  function wl(v) { return v.d ? `${v.w}-${v.l}-${v.d}` : `${v.w}-${v.l}`; }

  /** 상대 전적입니다. 가로 줄 팀이 세로 칸 팀을 상대로 거둔 승-패(-무). */
  function h2hHtml(splits, order, highlight) {
    let h = '<div class="table-container ts-wrap"><table class="table ts-table ts-h2h"><thead><tr><th class="ts-team">팀</th>';
    order.forEach(function (t) { h += `<th>${esc(t)}</th>`; });
    h += '<th>합계</th></tr></thead><tbody>';
    order.forEach(function (t) {
      const s = splits[t];
      let W = 0, L = 0, D = 0;
      h += `<tr${highlight && highlight === t ? ' class="ts-hl"' : ''}><td class="ts-team">${esc(t)}</td>`;
      order.forEach(function (o) {
        if (o === t) { h += '<td class="ts-self">·</td>'; return; }
        const v = s && s.vs && s.vs[o];
        if (!v) { h += '<td>-</td>'; return; }
        W += v.w; L += v.l; D += v.d;
        const c = v.w > v.l ? 'ts-win' : v.w < v.l ? 'ts-loss' : '';
        h += `<td${c ? ` class="${c}"` : ''}>${wl(v)}</td>`;
      });
      h += `<td class="ts-total">${W}-${L}-${D}</td></tr>`;
    });
    return h + '</tbody></table></div>';
  }

  /** 월별 승률입니다. 3·4월은 묶습니다(키 4). */
  function monthlyHtml(splits, order, highlight) {
    const months = [...new Set(order.flatMap(t => Object.keys((splits[t] && splits[t].month) || {}).map(Number)))]
      .sort((a, b) => a - b);
    let h = '<div class="table-container ts-wrap"><table class="table ts-table ts-month"><thead><tr><th class="ts-team">팀</th>';
    months.forEach(function (m) { h += `<th>${m === 4 ? '3·4월' : m + '월'}</th>`; });
    h += '</tr></thead><tbody>';
    order.forEach(function (t) {
      const mm = (splits[t] && splits[t].month) || {};
      h += `<tr${highlight && highlight === t ? ' class="ts-hl"' : ''}><td class="ts-team">${esc(t)}</td>`;
      months.forEach(function (m) {
        const v = mm[m];
        const pct = v && v.w + v.l > 0 ? v.w / (v.w + v.l) : null;
        h += `<td>${esc(TS.columns.fmt(pct, 'avg3'))}</td>`;
      });
      h += '</tr>';
    });
    return h + '</tbody></table></div>';
  }

  function noGamesHtml(season) {
    return `<p class="text-muted ts-sub">${esc(season)}년은 경기별 결과가 없어 볼 수 없습니다. 경기 결과는 2008년부터 있습니다.</p>`;
  }

  const api = { h2hHtml, monthlyHtml, noGamesHtml };
  TS.record = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 5: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/record.js
git commit -m "feat(team-stats): 상대 전적·월별 승률 표" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: 페이지 조립(page.js + team-stats.html)과 첫 화면 캡처

**Files:**
- Create: `dashboard_js/js/team-stats/page.js`
- Modify: `dashboard_js/pages/team-stats.html` (전체 교체: `<head>` 의 폰트·파비콘·스크립트는 그대로, `<style>`·`<main>`·아래 스크립트를 바꿈)
- Create: `C:/tmp/bstats-team-stats-check/tests/page.test.js`
- Create: `C:/tmp/bstats-team-stats-check/preview.py`
- Create: `C:/tmp/bstats-team-stats-check/shot.sh`

**Interfaces:**
- Consumes: 위 다섯 모듈, `components.js` 의 `createLoadingSpinner`, `createEmptyState`, `createErrorMessage`, `teamRecordHref`, `window.KBO_API_BASE`
- Produces: `TeamStats.page` = `{ parseState(search) → state, toSearch(state) → '?…', visibleKeys(tab, group, mode, season, custom) → [키], defaultSort(tab, keys) → {key, dir}, pickSort(state, keys) → {key, dir}, csvName(state, mode) → 파일 이름 }`
  - `state` = `{ tab: 'bat'|'pit'|'rec', group: 'dash'|'std'|'adv'|'custom', season: number|null, team: string, start: 'YYYY-MM-DD'|'', end: 'YYYY-MM-DD'|'', sort: 키|'', dir: 'asc'|'desc'|'', cols: [키] }`

- [ ] **Step 1: 실패하는 테스트 쓰기**

`C:/tmp/bstats-team-stats-check/tests/page.test.js`:

```js
const test = require('node:test');
const assert = require('node:assert/strict');
const { load } = require('./_load');
load('columns');
const P = load('page');

test('parseState: 기본값과 잘못된 값 거르기', () => {
  const s = P.parseState('');
  assert.deepEqual(s, { tab: 'bat', group: 'dash', season: null, team: '', start: '', end: '', sort: '', dir: '', cols: [] });
  const t = P.parseState('?tab=pit&group=adv&season=2025&team=%EB%91%90%EC%82%B0&start=2025-09-17&end=2025-09-30&sort=fip&dir=asc&cols=k9,x;y,era');
  assert.equal(t.tab, 'pit');
  assert.equal(t.group, 'adv');
  assert.equal(t.season, 2025);
  assert.equal(t.team, '두산');
  assert.equal(t.start, '2025-09-17');
  assert.equal(t.sort, 'fip');
  assert.equal(t.dir, 'asc');
  assert.deepEqual(t.cols, ['k9', 'era']);
  const bad = P.parseState('?tab=zzz&group=foo&season=20x5&start=2025/09/17&sort=<b>');
  assert.equal(bad.tab, 'bat');
  assert.equal(bad.group, 'dash');
  assert.equal(bad.season, null);
  assert.equal(bad.start, '');
  assert.equal(bad.sort, '');
});

test('toSearch ↔ parseState 왕복', () => {
  const s = { tab: 'bat', group: 'custom', season: 2025, team: 'LG', start: '', end: '', sort: 'wrcp', dir: 'desc', cols: ['pa', 'wrcp'] };
  assert.equal(P.toSearch(s), '?tab=bat&group=custom&season=2025&team=LG&sort=wrcp&dir=desc&cols=pa%2Cwrcp');
  assert.deepEqual(P.parseState(P.toSearch(s)), s);
  const r = { tab: 'rec', group: 'dash', season: 2025, team: '', start: '2025-09-01', end: '2025-09-30', sort: '', dir: '', cols: [] };
  assert.equal(P.toSearch(r), '?tab=rec&season=2025&start=2025-09-01&end=2025-09-30');
});

test('visibleKeys: 2007 이전 대시보드는 wRC+ 뒤에 OPS+', () => {
  const k = P.visibleKeys('bat', 'dash', 'season', 1985, null);
  assert.equal(k[k.indexOf('wrcp') + 1], 'opsp');
  assert.ok(!P.visibleKeys('bat', 'dash', 'season', 2025, null).includes('opsp'));
});

test('visibleKeys: 기간별 투구는 ERA 대신 RA/9, 안 되는 칸은 숨김', () => {
  const k = P.visibleKeys('pit', 'dash', 'range', 2025, null);
  assert.ok(k.includes('ra9'));
  assert.ok(!k.includes('era'));
  assert.ok(!k.includes('w'));
  assert.ok(!k.includes('fip'));
  const b = P.visibleKeys('bat', 'dash', 'range', 2025, null);
  assert.ok(!b.includes('rbi'));
  assert.ok(b.includes('wrcp'));
});

test('visibleKeys: 사용자 지정·모르는 키 거르기·팀 성적', () => {
  assert.deepEqual(P.visibleKeys('bat', 'custom', 'season', 2025, ['pa', 'nope', 'wrcp']), ['pa', 'wrcp']);
  assert.equal(P.visibleKeys('bat', 'custom', 'season', 2025, null)[0], 'g');
  assert.equal(P.visibleKeys('rec', 'dash', 'season', 2025, null).length, 15);
});

test('defaultSort·pickSort', () => {
  assert.deepEqual(P.defaultSort('bat', ['avg', 'wrcp']), { key: 'wrcp', dir: 'desc' });
  assert.deepEqual(P.defaultSort('bat', ['avg', 'opsp']), { key: 'opsp', dir: 'desc' });
  assert.deepEqual(P.defaultSort('pit', ['fip', 'era']), { key: 'era', dir: 'asc' });
  assert.deepEqual(P.defaultSort('pit', ['ra9', 'whip']), { key: 'ra9', dir: 'asc' });
  assert.deepEqual(P.defaultSort('rec', ['w', 'pct']), { key: 'pct', dir: 'desc' });
  assert.deepEqual(P.pickSort({ tab: 'bat', sort: 'hr', dir: 'asc' }, ['hr', 'wrcp']), { key: 'hr', dir: 'asc' });
  assert.deepEqual(P.pickSort({ tab: 'bat', sort: 'era', dir: 'asc' }, ['hr', 'wrcp']), { key: 'wrcp', dir: 'desc' });
});

test('csvName', () => {
  assert.equal(P.csvName({ tab: 'bat', group: 'dash', season: 2025, start: '', end: '' }, 'season'), 'bstats_team_batting_dash_2025.csv');
  assert.equal(P.csvName({ tab: 'rec', group: 'dash', season: 2025, start: '2025-09-01', end: '2025-09-30' }, 'range'), 'bstats_team_record_2025-09-01_2025-09-30.csv');
});
```

- [ ] **Step 2: 테스트가 실패하는지 확인**

Run: `node --test C:/tmp/bstats-team-stats-check/tests/page.test.js`
Expected: FAIL — `ENOENT: no such file or directory` (page.js 가 아직 없음)

- [ ] **Step 3: page.js 쓰기**

`dashboard_js/js/team-stats/page.js`:

```js
/*
 * 팀 통계 페이지 조립입니다. 상태(탭·묶음·시즌·팀·기간·정렬·칸)와 주소,
 * 화면 그리기, 이벤트를 맡습니다.
 *
 * 계산은 metrics.js, 칸 정의는 columns.js, 데이터는 data.js, 표는
 * table.js, 상대 전적·월별은 record.js 가 합니다. 위쪽 순수 함수는 Node
 * 로 검증하고, 아래 화면 부분은 브라우저에서만 돕니다.
 */
(function (root) {
  'use strict';
  const TS = root.TeamStats = root.TeamStats || {};

  const TABS = ['bat', 'pit', 'rec'];
  const GROUP_KEYS = ['dash', 'std', 'adv', 'custom'];
  const PBP_MIN = 2008;

  const okKey = k => /^[a-z0-9]+$/.test(k || '');
  const okDate = d => /^\d{4}-\d{2}-\d{2}$/.test(d || '');

  /** 주소의 ?… 를 상태로 읽습니다. 잘못된 값은 기본값으로 둡니다. */
  function parseState(search) {
    const p = new URLSearchParams(search || '');
    const g = k => p.get(k) || '';
    return {
      tab: TABS.includes(g('tab')) ? g('tab') : 'bat',
      group: GROUP_KEYS.includes(g('group')) ? g('group') : 'dash',
      season: /^\d{4}$/.test(g('season')) ? Number(g('season')) : null,
      team: g('team'),
      start: okDate(g('start')) ? g('start') : '',
      end: okDate(g('end')) ? g('end') : '',
      sort: okKey(g('sort')) ? g('sort') : '',
      dir: g('dir') === 'asc' || g('dir') === 'desc' ? g('dir') : '',
      cols: g('cols').split(',').filter(okKey),
    };
  }

  /** 상태를 주소의 ?… 로 씁니다. */
  function toSearch(s) {
    const p = new URLSearchParams();
    p.set('tab', s.tab);
    if (s.tab !== 'rec') p.set('group', s.group);
    if (s.season) p.set('season', String(s.season));
    if (s.team) p.set('team', s.team);
    if (s.start && s.end) { p.set('start', s.start); p.set('end', s.end); }
    if (s.sort) { p.set('sort', s.sort); p.set('dir', s.dir || 'desc'); }
    if (s.tab !== 'rec' && s.group === 'custom' && s.cols && s.cols.length) p.set('cols', s.cols.join(','));
    return '?' + p.toString();
  }

  /** 지금 보일 칸입니다. */
  function visibleKeys(tab, group, mode, season, custom) {
    const C = TS.columns;
    let keys;
    if (tab === 'rec') keys = C.REC_KEYS.slice();
    else if (group === 'custom') keys = (custom && custom.length ? custom : C.GROUPS[tab].dash).slice();
    else keys = C.GROUPS[tab][group].slice();
    // 2007 이전은 wRC+ 가 비므로 대시보드에 OPS+ 를 붙입니다.
    if (tab === 'bat' && group === 'dash' && season < PBP_MIN && !keys.includes('opsp')) {
      const i = keys.indexOf('wrcp');
      keys.splice(i < 0 ? keys.length : i + 1, 0, 'opsp');
    }
    if (mode === 'range' && tab !== 'rec') {
      keys = keys.map(k => (tab === 'pit' && k === 'era' ? 'ra9' : k));
      keys = keys.filter((k, i) => keys.indexOf(k) === i);
      keys = keys.filter(k => { const d = C.def(tab, k); return d && d.range; });
    }
    return keys.filter(k => C.def(tab, k));
  }

  const SORT_PREF = {
    bat: [['wrcp', 'desc'], ['opsp', 'desc'], ['avg', 'desc'], ['ops', 'desc']],
    pit: [['era', 'asc'], ['ra9', 'asc'], ['fip', 'asc'], ['whip', 'asc']],
    rec: [['pct', 'desc']],
  };

  function defaultSort(tab, keys) {
    for (const [k, d] of SORT_PREF[tab]) if (keys.includes(k)) return { key: k, dir: d };
    return { key: keys[0], dir: 'desc' };
  }

  function pickSort(st, keys) {
    if (st.sort && keys.includes(st.sort)) return { key: st.sort, dir: st.dir || 'desc' };
    return defaultSort(st.tab, keys);
  }

  function csvName(st, mode) {
    const what = { bat: 'batting', pit: 'pitching', rec: 'record' }[st.tab];
    const when = mode === 'range' ? `${st.start}_${st.end}` : String(st.season);
    return ['bstats', 'team', what, st.tab === 'rec' ? '' : st.group, when].filter(Boolean).join('_') + '.csv';
  }

  // ===== 화면(브라우저에서만) =====

  const SEASON_CAVEAT = '출처: KBO 공식 선수 기록을 팀별로 합산해 계산합니다. 비율 지표는 성분에서 다시 계산합니다. 시즌 중 트레이드된 선수는 그 시즌 기록 전체가 한 팀으로 잡혀 팀 합산이 조금 어긋날 수 있습니다. 진행 중인 시즌은 최신 일일 갱신 기준이라 KBO 실시간과 1~2경기 차이가 날 수 있습니다.';
  const OLD_CAVEAT = ' 2007년 이전은 파크팩터가 없어 OPS+·ERA-·FIP-를 구장 보정 없이 계산했고, wOBA·wRC+는 2008년부터 있습니다.';
  const RANGE_CAVEAT = '선택한 기간 안에 끝난 경기의 경기 기록(PBP)을 집계합니다. 시즌 누적과 산출 방식이 달라 수치가 다를 수 있습니다.';
  const REC_CAVEAT = '승패는 공식 순위표, 득점·실점은 공식 선수 기록 합계입니다. 홈·원정·1점차·월별·상대 전적은 정규시즌 경기 결과에서 셉니다(2008년부터).';
  const REC_RANGE_CAVEAT = '선택한 기간의 정규시즌 경기 결과로 승패·득실을 셉니다.';
  const LEAGUE2_CAVEAT = ' 1999·2000년은 드림·매직 양대 리그라 승차는 리그 안에서 잰 값입니다.';
  const LIVE_CAVEAT = ' 올해 승패와 경기 수는 KBO 실시간 순위입니다.';

  const S = {
    st: null, seasons: [], refs: { errors: [] },
    season: {}, games: {}, range: {}, standings: null,
    custom: { bat: null, pit: null }, panelOpen: false,
    seq: 0, last: null, pbpMax: new Date().getFullYear(),
  };

  function $(id) { return document.getElementById(id); }
  function mode() { return S.st.start && S.st.end ? 'range' : 'season'; }
  function ymd(d) { return Number(String(d).replace(/-/g, '')); }
  function fmtDate(dt) {
    const z = n => String(n).padStart(2, '0');
    return `${dt.getFullYear()}-${z(dt.getMonth() + 1)}-${z(dt.getDate())}`;
  }
  function fmtYmd(n) {
    const s = String(n === null || n === undefined ? '' : n);
    return s.length === 8 ? `${s.slice(0, 4)}-${s.slice(4, 6)}-${s.slice(6, 8)}` : s;
  }
  function teamHref(t) {
    return typeof root.teamRecordHref === 'function' ? root.teamRecordHref(t, '') : null;
  }
  function keysNow() {
    return visibleKeys(S.st.tab, S.st.group, mode(), S.st.season, S.custom[S.st.tab]);
  }

  function writeUrl(replace) {
    const st = S.st;
    st.cols = st.tab !== 'rec' && st.group === 'custom' ? (S.custom[st.tab] || []) : [];
    const url = location.pathname + toSearch(st);
    if (replace) history.replaceState(null, '', url);
    else history.pushState(null, '', url);
  }

  /** 상태를 받은 시즌 목록에 맞춥니다. */
  function normalize() {
    const st = S.st;
    if (!st.season || !S.seasons.includes(st.season)) st.season = S.seasons[0];
    if (mode() === 'range') {
      const y = String(st.season);
      const ok = st.season >= PBP_MIN && st.start.slice(0, 4) === y && st.end.slice(0, 4) === y;
      if (!ok) { st.start = ''; st.end = ''; }
      else if (st.start > st.end) { const t = st.start; st.start = st.end; st.end = t; }
    }
    if (st.group === 'custom' && st.cols.length) S.custom[st.tab] = st.cols.slice();
  }

  /** 기간 입력을 고른 시즌에 묶습니다. 경기 기록이 없는 시즌이면 막습니다. */
  function syncRange() {
    const y = S.st.season;
    const a = $('range-start'), b = $('range-end'), go = $('range-go'), note = $('range-note');
    const has = y >= PBP_MIN && y <= S.pbpMax;
    [a, b, go].forEach(el => { el.disabled = !has; });
    go.title = has ? '' : '이 시즌은 경기 기록이 없습니다';
    $('range-clear').hidden = mode() !== 'range';
    if (!has) {
      a.value = '';
      b.value = '';
      note.textContent = `${y} 시즌은 경기 기록이 없어 기간별로 볼 수 없습니다 (경기 기록은 ${PBP_MIN}년부터입니다)`;
      return;
    }
    a.min = b.min = `${y}-01-01`;
    a.max = b.max = `${y}-12-31`;
    if (mode() === 'range') { a.value = S.st.start; b.value = S.st.end; return; }
    // 기본 두 주입니다. 올해면 오늘까지, 지난 시즌이면 9월 말까지입니다.
    const now = new Date();
    const end = y === now.getFullYear() ? now : new Date(y, 8, 30);
    a.value = fmtDate(new Date(end.getTime() - 13 * 86400000));
    b.value = fmtDate(end);
    note.textContent = '';
  }

  /** 지금 화면에 필요한 데이터를 받습니다. 받은 것은 기억하고, 실패한 것은 다시 받습니다. */
  async function ensureData() {
    const st = S.st, y = st.season, D = TS.data, base = root.KBO_API_BASE;
    const need = { season: false, games: false, range: false };
    if (mode() === 'range') {
      if (st.tab === 'rec') need.games = true; else need.range = true;
    } else {
      need.season = true;
      if (st.tab === 'rec' && y >= PBP_MIN) need.games = true;
    }
    const stale = x => !x || x.errors.length > 0;
    const jobs = [];
    if (need.season && stale(S.season[y])) jobs.push(D.loadSeason(base, y).then(r => { S.season[y] = r; }));
    if (need.games && stale(S.games[y])) jobs.push(D.loadGames(base, y).then(r => { S.games[y] = r; }));
    const rk = st.start + '|' + st.end;
    if (need.range && stale(S.range[rk])) jobs.push(D.loadRange(base, st.start, st.end).then(r => { S.range[rk] = r; }));
    // 올해(가장 최근 시즌)는 승패·경기 수를 실시간 순위로 받습니다.
    if (need.season && y === S.pbpMax && stale(S.standings)) jobs.push(D.loadStandings(base).then(r => { S.standings = r; }));
    await Promise.all(jobs);
  }

  /**
   * 올해면 실시간 순위, 아니면 null(저장된 순위표를 씀)입니다.
   * 실시간 순위를 못 받으면 알림을 남기고 저장된 순위표로 돌아갑니다.
   */
  function liveRank(alerts) {
    if (S.st.season !== S.pbpMax || !S.standings) return null;
    if (S.standings.errors.length || !S.standings.teams.length) {
      errAlerts(alerts, S.standings.errors);
      alerts.push({ kind: 'warn', text: '실시간 순위를 받지 못해 저장된 순위표를 씁니다. 저장된 순위표는 시즌 중 갱신이 늦을 수 있습니다.' });
      return null;
    }
    return TS.metrics.rankFromStandings(S.standings.teams);
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

  function titleText() {
    const st = S.st;
    const what = st.tab === 'bat' ? '팀 타격' : st.tab === 'pit' ? '팀 투구' : '승패와 득실';
    if (mode() === 'range') return `${what} (기간별)`;
    return `${what} (${st.season} 시즌${st.tab === 'rec' ? '' : ' 누적'})`;
  }

  function fillTeams(names) {
    const el = $('team-select');
    const list = [...new Set(names.filter(Boolean))].sort((a, b) => a.localeCompare(b, 'ko'));
    if (S.st.team && !list.includes(S.st.team)) S.st.team = '';
    el.innerHTML = '<option value="">전체</option>'
      + list.map(t => `<option value="${TS.table.esc(t)}">${TS.table.esc(t)}</option>`).join('');
    el.value = S.st.team;
  }

  function fillSeasons() {
    const el = $('season-select');
    el.innerHTML = S.seasons.map(y => `<option value="${y}">${y}</option>`).join('');
    el.value = String(S.st.season);
  }

  function syncTabs() {
    const st = S.st;
    document.querySelectorAll('#ts-tabs [data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === st.tab));
    document.querySelectorAll('#ts-groups [data-group]').forEach(b => b.classList.toggle('active', b.dataset.group === st.group));
    $('ts-groups').hidden = st.tab === 'rec';
    $('ts-rec-extra').hidden = st.tab !== 'rec';
    $('col-panel').classList.toggle('hidden', !(st.tab !== 'rec' && st.group === 'custom' && S.panelOpen));
  }

  function syncRecordLink() {
    const a = $('team-record-link');
    const t = S.st.team;
    const href = t ? teamHref(t) : null;
    a.href = href ? `${href}&name=${encodeURIComponent(t)}` : 'team-record';
    a.textContent = t ? `${t} 기록실` : '기록실';
  }

  function renderColPanel() {
    const tab = S.st.tab;
    if (tab === 'rec') return;
    const C = TS.columns, esc = TS.table.esc;
    const on = new Set(S.custom[tab] || C.GROUPS[tab].dash);
    const defs = C.ORDER[tab].map(k => C.def(tab, k));
    const isRange = mode() === 'range';
    $('col-list').innerHTML = defs.map(function (d) {
      const na = isRange && !d.range;
      const cls = [on.has(d.key) ? '' : 'off', na ? 'na' : ''].filter(Boolean).join(' ');
      return `<label class="${cls}" title="${esc(d.desc)}"><input type="checkbox" data-col="${d.key}"`
        + `${on.has(d.key) ? ' checked' : ''}${na ? ' disabled' : ''}>${esc(d.label)}</label>`;
    }).join('');
    $('col-count').textContent = `${on.size}개 / ${defs.length}개`;
  }

  /** 받은 데이터로 지금 탭을 그립니다. 서버를 부르지 않습니다. */
  function render() {
    const st = S.st, C = TS.columns, M = TS.metrics, T = TS.table, R = TS.record;
    const y = st.season, m = mode();
    const alerts = [];
    errAlerts(alerts, S.refs.errors);
    syncTabs();
    $('ts-title').textContent = titleText();

    const keys = keysNow();
    const cols = keys.map(k => C.def(st.tab, k));
    let rows = [], league = null, splits = null, caveat = '';

    if (st.tab === 'rec') {
      if (m === 'range') {
        const g = S.games[y];
        errAlerts(alerts, g.errors);
        splits = M.gameSplits(g.games, ymd(st.start), ymd(st.end));
        rows = M.recordFromGames(splits);
        const n = rows.reduce((a, r) => a + r.g, 0) / 2;
        $('range-note').textContent = n ? `반영: ${st.start} ~ ${st.end}, ${n}경기` : '해당 기간 경기 없음';
        caveat = REC_RANGE_CAVEAT;
      } else {
        const sd = S.season[y];
        errAlerts(alerts, sd.errors);
        const live = liveRank(alerts);
        const v = M.seasonView({ batters: sd.batters, pitchers: sd.pitchers, refs: S.refs, season: y, rank: live || undefined });
        if (y >= PBP_MIN) {
          const g = S.games[y];
          errAlerts(alerts, g.errors);
          if (g.games.length) splits = M.gameSplits(g.games);
        }
        rows = M.recordTable(v.rank, v.batTotals, v.pitTotals, splits);
        if (!rows.length && !S.refs.errors.length) alerts.push({ kind: 'warn', text: `순위표에 ${y} 시즌이 없습니다.` });
        caveat = REC_CAVEAT + (y === 1999 || y === 2000 ? LEAGUE2_CAVEAT : '') + (live ? LIVE_CAVEAT : '');
      }
    } else if (m === 'range') {
      const rr = S.range[st.start + '|' + st.end];
      errAlerts(alerts, rr.errors);
      const ix = M.indexRefs(S.refs);
      const tbl = st.tab === 'bat' ? M.rangeBattingTable(rr.data, y, ix) : M.rangePitchingTable(rr.data, y, ix);
      rows = tbl.rows;
      league = rows.length ? tbl.league : null;
      alerts.push({ kind: 'info', text: '기간별은 경기 기록으로 세서 RBI·ERA·FIP 등은 없습니다. 계산할 수 없는 칸은 숨겼습니다.' });
      const d = rr.data || {};
      $('range-note').textContent = d.games ? `반영: ${fmtYmd(d.date_min)} ~ ${fmtYmd(d.date_max)}, ${d.games}경기` : '해당 기간 경기 없음';
      caveat = d.note || RANGE_CAVEAT;
    } else {
      const sd = S.season[y];
      errAlerts(alerts, sd.errors);
      const live = liveRank(alerts);
      const v = M.seasonView({ batters: sd.batters, pitchers: sd.pitchers, refs: S.refs, season: y, rank: live || undefined });
      if (v.unmatched.length) {
        alerts.push({ kind: 'warn', text: `순위표와 선수 기록의 팀 이름이 맞지 않습니다: ${v.unmatched.join(', ')}. 이 팀의 경기 수는 '-'로 둡니다.` });
      }
      const tbl = st.tab === 'bat' ? v.bat : v.pit;
      rows = tbl.rows;
      league = rows.length ? tbl.league : null;
      caveat = SEASON_CAVEAT + (y < PBP_MIN ? OLD_CAVEAT : '') + (live ? LIVE_CAVEAT : '');
    }

    fillTeams(rows.map(r => r.team));
    const shown = st.team ? rows.filter(r => r.team === st.team) : rows;
    const sort = pickSort(st, keys);
    S.last = { cols: cols, rows: shown, league: league, sort: sort };
    $('ts-table').innerHTML = shown.length
      ? T.renderTable({ cols: cols, rows: shown, league: league, sort: sort, teamHref: teamHref })
      : createEmptyState(m === 'range' ? '해당 기간 기록이 없습니다.' : '해당 시즌 기록이 없습니다.');

    if (st.tab === 'rec') {
      const order = rows.slice().sort((a, b) => (b.pct || 0) - (a.pct || 0)).map(r => r.team);
      $('ts-h2h').innerHTML = splits ? R.h2hHtml(splits, order, st.team) : R.noGamesHtml(y);
      $('ts-monthly').innerHTML = splits ? R.monthlyHtml(splits, order, st.team) : R.noGamesHtml(y);
    }
    $('ts-glossary-list').innerHTML = T.glossaryHtml(cols);
    $('caveat-note').textContent = caveat;
    renderAlerts(alerts);
    syncRecordLink();
    if (!$('col-panel').classList.contains('hidden')) renderColPanel();
  }

  /** 주소를 쓰고, 필요한 데이터를 받은 뒤 그립니다. 늦게 온 이전 응답은 버립니다. */
  async function refresh(opt) {
    opt = opt || {};
    const seq = ++S.seq;
    if (!opt.noUrl) writeUrl(opt.replace);
    $('ts-table').innerHTML = createLoadingSpinner();
    await ensureData();
    if (seq !== S.seq) return;
    render();
  }

  function downloadCsv() {
    if (!S.last) return;
    const csv = TS.table.toCsv(S.last);
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv;charset=utf-8' }));
    const a = document.createElement('a');
    a.href = url;
    a.download = csvName(S.st, mode());
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
    document.addEventListener('mouseover', function (e) {
      const el = e.target.closest && e.target.closest('.ts-term[data-col]');
      if (!el) return;
      const d = TS.columns.def(S.st.tab, el.dataset.col);
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
      if (box && e.target.closest && e.target.closest('.ts-term[data-col]')) box.style.display = 'none';
    });
  }

  function bind() {
    $('ts-tabs').addEventListener('click', function (e) {
      const b = e.target.closest('[data-tab]');
      if (!b || b.dataset.tab === S.st.tab) return;
      S.st.tab = b.dataset.tab;
      S.st.sort = '';
      S.st.dir = '';
      refresh();
    });
    $('ts-groups').addEventListener('click', function (e) {
      const b = e.target.closest('[data-group]');
      if (!b) return;
      const g = b.dataset.group;
      if (g === 'custom') S.panelOpen = S.st.group === 'custom' ? !S.panelOpen : true;
      if (g !== S.st.group) { S.st.group = g; S.st.sort = ''; S.st.dir = ''; }
      render();
      writeUrl();
    });
    $('season-select').addEventListener('change', function (e) {
      S.st.season = Number(e.target.value);
      S.st.start = '';
      S.st.end = '';
      syncRange();
      refresh();
    });
    $('team-select').addEventListener('change', function (e) {
      S.st.team = e.target.value;
      render();
      writeUrl();
    });
    $('range-go').addEventListener('click', function () {
      const a = $('range-start').value, b = $('range-end').value;
      if (!a || !b) return;
      S.st.start = a <= b ? a : b;
      S.st.end = a <= b ? b : a;
      S.st.sort = '';
      S.st.dir = '';
      syncRange();
      refresh();
    });
    $('range-clear').addEventListener('click', function () {
      S.st.start = '';
      S.st.end = '';
      syncRange();
      refresh();
    });
    $('csv-btn').addEventListener('click', downloadCsv);
    $('link-btn').addEventListener('click', copyLink);
    $('ts-table').addEventListener('click', function (e) {
      const th = e.target.closest('th.sortable');
      if (!th) return;
      const k = th.dataset.key;
      const cur = pickSort(S.st, keysNow());
      if (cur.key === k) S.st.dir = cur.dir === 'asc' ? 'desc' : 'asc';
      else {
        const d = TS.columns.def(S.st.tab, k);
        S.st.dir = d && d.better === 'low' ? 'asc' : 'desc';
      }
      S.st.sort = k;
      render();
      writeUrl(true);
    });
    $('col-list').addEventListener('change', function (e) {
      const k = e.target.getAttribute('data-col');
      if (!k) return;
      const tab = S.st.tab;
      const on = new Set(S.custom[tab] || TS.columns.GROUPS[tab].dash);
      if (e.target.checked) on.add(k); else on.delete(k);
      S.custom[tab] = TS.columns.ORDER[tab].filter(x => on.has(x));
      render();
      writeUrl(true);
    });
    document.querySelectorAll('[data-col-preset]').forEach(function (b) {
      b.addEventListener('click', function () {
        const tab = S.st.tab;
        S.custom[tab] = b.dataset.colPreset === 'all' ? TS.columns.ORDER[tab].slice() : TS.columns.GROUPS[tab].dash.slice();
        render();
        writeUrl(true);
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
      syncRange();
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
      S.seasons = got[0];
      S.refs = got[1];
      S.pbpMax = S.seasons[0];
      normalize();
      if (S.st.group === 'custom') S.panelOpen = true;
      fillSeasons();
      syncRange();
      bind();
      await refresh({ replace: true });
    } catch (e) {
      console.error(e);
      $('ts-table').innerHTML = createErrorMessage('팀 기록을 불러오는데 실패했습니다.');
    }
  }

  const api = { parseState, toSearch, visibleKeys, defaultSort, pickSort, csvName };
  TS.page = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
  if (typeof document !== 'undefined' && document.getElementById('ts-table')) {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 테스트가 통과하는지 확인**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 5: team-stats.html 교체**

`dashboard_js/pages/team-stats.html` 전체를 아래로 바꿉니다(헤더·nav 는 지금과 같습니다):

```html
<!DOCTYPE html>
<html lang="ko">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>팀 통계 - Bstats</title>
    <meta name="description" content="KBO 팀별 타격·투구·팀 성적 (시즌 누적·기간별, wOBA·wRC+·FIP·상대 전적)">

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
    <style>
        [hidden] { display: none !important; }
        .tabbtn { background: transparent; color: inherit; border: 1px solid #94a3b8; border-radius: 8px; padding: 0.4rem 0.9rem; cursor: pointer; font-size: 0.9rem; font-weight: 600; white-space: nowrap; flex-shrink: 0; font-family: inherit; }
        .tabbtn.active { background: #3b82f6; color: #fff; border-color: #3b82f6; }
        .tabbtn:hover { border-color: #3b82f6; }
        .tabbtn:disabled { opacity: 0.45; cursor: not-allowed; }
        a.tabbtn { text-decoration: none; display: inline-flex; align-items: center; }
        /* factor-stats(.fs-tab)와 같은 밑줄형 탭 */
        .fs-tabs { display: flex; justify-content: center; gap: 0.5rem; border-bottom: 2px solid var(--border-color); margin-bottom: 1rem; flex-wrap: wrap; }
        .fs-tab { background: none; border: none; padding: 0.7rem 1.4rem; font-size: 1rem; font-weight: 600; font-family: inherit; color: var(--text-secondary); cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; }
        .fs-tab:hover { color: var(--primary); }
        .fs-tab.active { color: var(--primary); border-bottom-color: var(--primary); }
        /* 묶음 버튼(사각형, CSV 버튼과 같은 모양) */
        .ts-groups { display: flex; gap: 0.4rem; flex-wrap: wrap; margin: 0 0 0.9rem; }
        /* 고르개 줄 */
        .ctrl-bar { display: flex; align-items: center; gap: 0.7rem 1.5rem; flex-wrap: wrap; padding: 0.75rem 1rem !important; }
        .ctrl-card { padding: 0 !important; margin-bottom: 1rem !important; }
        .ctrl-card:hover, .ts-card:hover { transform: none; }
        .ctrl-group { display: flex; align-items: center; gap: 0.6rem; flex-wrap: nowrap; flex-shrink: 0; }
        .ctrl-group label { white-space: nowrap; flex-shrink: 0; margin: 0; }
        .ctrl-group .tabbtn { height: 37px; box-sizing: border-box; }
        .ctrl-right { margin-left: auto; }
        .ctrl-divider { align-self: stretch; width: 1px; min-height: 1.8rem; background: var(--border-color); }
        .ctrl-note { flex-basis: 100%; font-size: 0.85rem; }
        .ctrl-note:empty { display: none; }
        @media (max-width: 640px) { .ctrl-divider { display: none; } .ctrl-group { flex-wrap: wrap; } .ctrl-right { margin-left: 0; } }
        /* 사용자 지정 칸 고르개 */
        .col-panel { flex-basis: 100%; border-top: 1px solid var(--border-color); margin-top: 0.5rem; padding-top: 0.75rem; }
        .col-panel.hidden { display: none; }
        .col-panel-head { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.6rem; }
        .col-panel-btns { margin-left: auto; display: flex; gap: 0.35rem; }
        .col-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 0.35rem 0.9rem; }
        .col-list label { display: flex; align-items: center; gap: 0.35rem; font-size: 0.85rem; cursor: pointer; margin: 0; }
        .col-list label.off { color: var(--text-muted); }
        .col-list label.na { opacity: 0.45; cursor: not-allowed; }
        /* 알림 */
        .ts-alerts:empty { display: none; }
        .ts-alerts { margin-bottom: 0.8rem; }
        .ts-alert { border-left: 3px solid var(--warning); background: rgba(245, 158, 11, 0.08); padding: 0.45rem 0.7rem; font-size: 0.85rem; margin-bottom: 0.4rem; border-radius: 6px; color: var(--text-secondary); }
        .ts-alert-info { border-left-color: var(--primary); background: rgba(59, 130, 246, 0.07); }
        /* 표: 촘촘한 간격, 순위·팀 열 고정 */
        .ts-wrap { max-height: none; }
        .ts-table th, .ts-table td { padding: 0.42rem 0.55rem; font-size: 0.82rem; text-align: right; }
        .ts-table th.ts-rank, .ts-table td.ts-rank { position: sticky; left: 0; z-index: 3; width: 2.6rem; min-width: 2.6rem; max-width: 2.6rem; text-align: left; background: var(--bg-secondary); border-right: none; }
        .ts-table th.ts-team, .ts-table td.ts-team { position: sticky; left: 2.6rem; z-index: 3; text-align: left; background: var(--bg-secondary); border-right: 1px solid var(--border-color); font-weight: 600; }
        .ts-table thead th { z-index: 4; }
        .ts-table thead th.ts-rank, .ts-table thead th.ts-team { z-index: 6; background: var(--bg-tertiary); }
        .ts-h2h .ts-team, .ts-month .ts-team { left: 0; }
        .ts-table th.sortable { cursor: pointer; user-select: none; white-space: nowrap; }
        .ts-table th.sortable:hover { color: #3b82f6; }
        .ts-table th.sorted { color: #3b82f6; }
        .sort-ind { font-size: 0.72em; margin-left: 3px; vertical-align: middle; }
        .ts-term { text-decoration: underline dotted var(--text-muted); text-underline-offset: 3px; cursor: help; }
        .ts-league td { background: var(--bg-tertiary); font-weight: 700; border-top: 2px solid var(--border-color); }
        .ts-hl td { background-color: rgba(245, 158, 11, 0.12); }
        /* 지수 칸 색(리그 평균 100 대비) */
        .ts-up1 { background: rgba(59, 130, 246, 0.14); }
        .ts-up2 { background: rgba(59, 130, 246, 0.26); }
        .ts-up3 { background: rgba(59, 130, 246, 0.40); }
        .ts-down1 { background: rgba(239, 68, 68, 0.13); }
        .ts-down2 { background: rgba(239, 68, 68, 0.24); }
        .ts-down3 { background: rgba(239, 68, 68, 0.38); }
        .ts-pos { color: #2563eb; }
        .ts-neg { color: #dc2626; }
        [data-theme="dark"] .ts-pos { color: #60a5fa; }
        [data-theme="dark"] .ts-neg { color: #f87171; }
        /* 상대 전적 */
        .ts-h2h td, .ts-h2h th { text-align: center; }
        .ts-win { background: rgba(59, 130, 246, 0.15); }
        .ts-loss { background: rgba(239, 68, 68, 0.13); }
        .ts-self { color: var(--text-muted); }
        .ts-total { font-weight: 700; border-left: 2px solid var(--border-color); }
        .ts-sub { font-size: 0.82rem; margin: 0 0 0.6rem; }
        /* 지표 설명 */
        .ts-glossary { padding: 0.8rem 1rem !important; }
        .ts-glossary summary { cursor: pointer; font-weight: 600; }
        .ts-glossary dl { margin: 0.6rem 0 0; display: grid; grid-template-columns: max-content 1fr; gap: 0.3rem 0.9rem; font-size: 0.82rem; }
        .ts-glossary dt { font-weight: 700; }
        .ts-glossary dd { margin: 0; color: var(--text-secondary); }
        /* 머리글 설명 창 */
        .tip-box { position: fixed; z-index: 9999; display: none; max-width: 300px; background: var(--bg-secondary); color: var(--text-primary); border: 1px solid var(--border-color); border-radius: 8px; padding: 0.5rem 0.7rem; font-size: 0.82rem; font-family: inherit; line-height: 1.45; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.12); pointer-events: none; white-space: normal; }
        .tip-box b { display: block; margin-bottom: 2px; }
        .tip-box .f { display: block; margin-top: 4px; color: var(--text-muted); }
    </style>
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
                <a href="team-stats" class="nav-link active">팀 통계</a>
                <a href="player-stats" class="nav-link">선수 통계</a>
                <a href="player-analytics" class="nav-link">선수 분석</a>
                <a href="article" class="nav-link">아티클</a>
                <a href="factor-stats" class="nav-link">요인 통계</a>
                <a href="database-explorer" class="nav-link">데이터 탐색</a>
            </nav>
        </div>
    </header>

    <main class="container">
        <h1 class="fade-in">팀 통계</h1>
        <p class="text-secondary mb-3">KBO 팀별 기록입니다. 묶음 탭으로 지표 묶음을 바꿉니다. <span class="ts-term">점선 밑줄</span>이 있는 지표에 마우스를 올리면 뜻과 계산식이 나오고, 누르면 정렬됩니다.</p>

        <div class="fs-tabs" id="ts-tabs">
            <button type="button" class="fs-tab active" data-tab="bat">타격</button>
            <button type="button" class="fs-tab" data-tab="pit">투구</button>
            <button type="button" class="fs-tab" data-tab="rec">팀 성적</button>
        </div>

        <div class="ts-groups" id="ts-groups">
            <button type="button" class="tabbtn active" data-group="dash">대시보드</button>
            <button type="button" class="tabbtn" data-group="std">표준</button>
            <button type="button" class="tabbtn" data-group="adv">고급</button>
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
                <div class="ctrl-divider" aria-hidden="true"></div>
                <div class="ctrl-group">
                    <label for="range-start"><strong>기간</strong></label>
                    <input type="date" id="range-start" class="input" style="max-width:185px;">
                    <span class="text-muted">~</span>
                    <input type="date" id="range-end" class="input" style="max-width:185px;">
                    <button type="button" id="range-go" class="tabbtn active">조회</button>
                    <button type="button" id="range-clear" class="tabbtn" hidden>시즌 전체</button>
                </div>
                <div class="ctrl-group ctrl-right">
                    <button type="button" id="csv-btn" class="tabbtn">CSV</button>
                    <button type="button" id="link-btn" class="tabbtn">링크 복사</button>
                    <a id="team-record-link" class="tabbtn" href="team-record">기록실</a>
                </div>
                <span class="text-muted ctrl-note" id="range-note"></span>
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
                    <h3 class="card-title" id="ts-title">팀 타격</h3>
                </div>
                <div class="card-body">
                    <div id="ts-table"></div>
                </div>
            </div>

            <div id="ts-rec-extra" hidden>
                <div class="card ts-card mt-3">
                    <div class="card-header">
                        <h3 class="card-title">상대 전적</h3>
                    </div>
                    <div class="card-body">
                        <p class="text-muted ts-sub">가로 줄 팀이 세로 칸 팀을 상대로 거둔 승-패(-무)입니다. 이긴 쪽이 많으면 옅은 파랑, 진 쪽이 많으면 옅은 빨강입니다.</p>
                        <div id="ts-h2h"></div>
                    </div>
                </div>
                <div class="card ts-card mt-3">
                    <div class="card-header">
                        <h3 class="card-title">월별 승률</h3>
                    </div>
                    <div class="card-body">
                        <div id="ts-monthly"></div>
                    </div>
                </div>
            </div>

            <details class="card ts-glossary mt-3">
                <summary>지표 설명</summary>
                <dl id="ts-glossary-list"></dl>
            </details>

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
    <script src="../js/team-stats/metrics.js"></script>
    <script src="../js/team-stats/columns.js"></script>
    <script src="../js/team-stats/data.js"></script>
    <script src="../js/team-stats/table.js"></script>
    <script src="../js/team-stats/record.js"></script>
    <script src="../js/team-stats/page.js"></script>
</body>

</html>
```

- [ ] **Step 6: 미리보기 서버와 캡처 스크립트 만들기**

`C:/tmp/bstats-team-stats-check/preview.py` (읽기 전용, GET 만 받음. `/__theme/<light|dark>?to=<경로>` 는 테마를 저장하고 그 경로로 보냅니다):

```python
import functools
import http.server
from urllib.parse import parse_qs, urlparse

ROOT = r'C:\Users\김승곤\Desktop\b_project\dashboard_js'


class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        u = urlparse(self.path)
        if u.path.startswith('/__theme/'):
            theme = u.path.rsplit('/', 1)[-1]
            if theme not in ('light', 'dark'):
                theme = 'light'
            to = parse_qs(u.query).get('to', ['/'])[0]
            if not to.startswith('/'):
                to = '/'
            body = ("<script>localStorage.setItem('kbo-theme-v2','%s');location.replace(%r);</script>" % (theme, to)).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


if __name__ == '__main__':
    http.server.ThreadingHTTPServer(('127.0.0.2', 8765), functools.partial(Handler, directory=ROOT)).serve_forever()
```

`C:/tmp/bstats-team-stats-check/shot.sh`:

```bash
#!/usr/bin/env bash
# 사용: shot.sh <이름> <경로와 쿼리> [폭] [높이]
# 결과: 바탕화면 bstats_ts_<이름>.png
EDGE="/c/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"
[ -f "$EDGE" ] || EDGE="/c/Program Files/Microsoft/Edge/Application/msedge.exe"
UD="C:/tmp/bstats-team-stats-check/edge_ud/$1_$(date +%s%N)"
OUT="C:/Users/김승곤/Desktop/bstats_ts_$1.png"
"$EDGE" --headless=new --disable-gpu --hide-scrollbars --user-data-dir="$UD" \
  --window-size="${3:-1400},${4:-1800}" --virtual-time-budget=20000 \
  --screenshot="$OUT" "http://127.0.0.2:8765$2" 2>&1 | grep -i written
```

- [ ] **Step 7: 미리보기를 띄우고 캡처하기**

미리보기 서버를 백그라운드로 띄웁니다(이미 떠 있으면 건너뜀):

Run (background): `py C:/tmp/bstats-team-stats-check/preview.py`

캡처합니다(같은 주소를 반복해서 찍지 않습니다):

```bash
S=C:/tmp/bstats-team-stats-check/shot.sh
bash $S bat_dash "/pages/team-stats.html?tab=bat&group=dash&season=2025"
bash $S bat_adv "/pages/team-stats.html?tab=bat&group=adv&season=2025"
bash $S pit_dash "/pages/team-stats.html?tab=pit&group=dash&season=2025"
bash $S pit_adv "/pages/team-stats.html?tab=pit&group=adv&season=2025"
bash $S rec "/pages/team-stats.html?tab=rec&season=2025" 1400 2600
bash $S custom "/pages/team-stats.html?tab=bat&group=custom&season=2025&cols=pa,hr,woba,wrcp"
```

Expected: 바탕화면에 PNG 6개. 각 PNG 를 Read 로 열어 확인합니다:
- 탭 3개, 묶음 버튼 4개(사각형), 고르개 줄 오른쪽에 CSV·링크 복사·기록실
- 표 맨 아래 리그 평균 행, wRC+(또는 ERA-·FIP-) 칸만 색
- 머리글 점선 밑줄, 숫자 자리 맞음, 순위·팀 열이 왼쪽에 붙음
- 팀 성적: 승패 표, 상대 전적 10×10(합계 열), 월별 승률
- 알림 줄에 오류가 없음(있으면 그 문구를 그대로 보고)
- 브라우저 콘솔 오류는 캡처로 안 보이므로, 이상하면 `--enable-logging=stderr --v=0` 을 붙여 다시 찍어 `Uncaught` 를 찾습니다.

- [ ] **Step 8: 커밋**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
git add dashboard_js/js/team-stats/page.js dashboard_js/pages/team-stats.html
git commit -m "feat(team-stats): 묶음 탭·팀 성적 탭·리그 평균·설명 창·CSV·주소 저장으로 팀 통계 개편" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 9: 2차 보고(사람 확인 지점)**

PNG 6개 경로와 눈에 띈 점을 evan 에게 보고하고, 고칠 점을 받습니다.

---

### Task 11: 경계 상황 확인(옛 시즌·기간별·팀 고르기·휴대폰·다크 모드)

**Files:**
- Modify (필요할 때만): `dashboard_js/pages/team-stats.html`, `dashboard_js/js/team-stats/*.js`

**Interfaces:**
- Consumes: Task 10 의 화면, `preview.py`, `shot.sh`

- [ ] **Step 1: 경계 화면 캡처**

```bash
S=C:/tmp/bstats-team-stats-check/shot.sh
bash $S old_bat "/pages/team-stats.html?tab=bat&group=dash&season=1985"
bash $S old_rec "/pages/team-stats.html?tab=rec&season=1985" 1400 2200
bash $S y1999_rec "/pages/team-stats.html?tab=rec&season=1999" 1400 2400
bash $S range_bat "/pages/team-stats.html?tab=bat&group=dash&season=2025&start=2025-09-17&end=2025-09-30"
bash $S range_pit "/pages/team-stats.html?tab=pit&group=dash&season=2025&start=2025-09-17&end=2025-09-30"
bash $S range_rec "/pages/team-stats.html?tab=rec&season=2025&start=2025-09-17&end=2025-09-30" 1400 2400
bash $S live_rec "/pages/team-stats.html?tab=rec&season=2026" 1400 2600
bash $S team_lg "/pages/team-stats.html?tab=bat&group=dash&season=2025&team=LG"
bash $S team_lg_rec "/pages/team-stats.html?tab=rec&season=2025&team=LG" 1400 2600
bash $S mobile "/pages/team-stats.html?tab=bat&group=dash&season=2025" 390 1600
bash $S dark_bat "/__theme/dark?to=/pages/team-stats.html%3Ftab%3Dbat%26group%3Ddash%26season%3D2025"
bash $S dark_rec "/__theme/dark?to=/pages/team-stats.html%3Ftab%3Drec%26season%3D2025" 1400 2600
```

`range_*` 는 `/stats/team_range` 를 같은 기간으로 한 번만 부릅니다(엣지 1시간 캐시). 다른 기간으로 반복하지 않습니다.

- [ ] **Step 2: 기대 결과와 대조**

각 PNG 를 Read 로 열어 확인합니다:
- `old_bat`: wOBA·wRC+ 칸 '-', wRC+ 뒤에 OPS+ 칸, OPS+ 높은 순, 아래 안내에 "2007년 이전은 … 구장 보정 없이" 문구, 기간 입력이 막히고 "1985 시즌은 경기 기록이 없어" 문구
- `old_rec`: 홈·원정·1점차 '-', 상대 전적·월별 자리에 "2008년부터" 안내
- `y1999_rec`: 8팀, 안내에 양대 리그 승차 문구
- `range_bat`: 알림 줄 "기간별은 경기 기록으로 세서…", RBI 칸 없음, wRC+ 있음, "반영: … 경기" 문구, '시즌 전체' 버튼 보임
- `range_pit`: ERA 대신 RA/9, W·L·FIP 칸 없음
- `range_rec`: 기간 승패·상대 전적
- `live_rec`: 2026 승패가 실시간 순위(팀당 136경기 이상)이고, 안내에 "올해 승패와 경기 수는 KBO 실시간 순위입니다" 문구
- `team_lg`: LG 한 줄 + 리그 평균 행, 기록실 버튼 "LG 기록실"
- `team_lg_rec`: 상대 전적·월별에서 LG 줄 강조
- `mobile`: 표가 옆으로 넘치되 순위·팀 열 고정, 고르개가 줄바꿈, 가로 스크롤이 페이지 전체로 번지지 않음
- `dark_*`: 글자·지수 색·리그 평균 행이 읽힘

어긋나는 것이 있으면 원인을 찾아 고치고(`superpowers:systematic-debugging`), 관련 테스트를 더한 뒤 다시 찍습니다.

- [ ] **Step 3: 전체 테스트**

Run: `node --test "C:/tmp/bstats-team-stats-check/tests/*.test.js"`
Expected: PASS

- [ ] **Step 4: 커밋(고친 것이 있을 때만)**

```bash
cd C:/Users/김승곤/Desktop/b_project
git status --short
# 고친 파일만 하나씩 이름을 적어 add 합니다(예: dashboard_js/pages/team-stats.html).
git add dashboard_js/pages/team-stats.html
git commit -m "fix(team-stats): 경계 화면에서 찾은 문제 수정" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

커밋 본문에 무엇을 왜 고쳤는지 한두 줄로 적습니다.

- [ ] **Step 5: 최종 보고(사람 확인 지점)**

evan 에게 보고합니다:
- PNG 경로 목록과 확인 결과
- 검증 1~7 숫자 요약(Task 2~4 콘솔 출력)
- `git log origin/main..main --oneline` 결과(옆 세션 커밋이 섞여 있는지)
- push·배포는 하지 않고 허락을 기다린다는 것. 배포 명령은 `npx --yes wrangler@4 pages deploy dashboard_js --project-name bstats --branch main` 이고, 배포 직전 `git status dashboard_js` 로 내 변경만 있는지 확인합니다.
