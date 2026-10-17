# 데이터 관리 B: 공개 페이지 묶음 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 공개 '데이터 관리' 페이지(`pages/data-ops.html`)와 그것이 읽는 Worker 주소 `GET /ops/storage`, 주간 작업의 빅쿼리 현황 기록, 모든 페이지 메뉴 링크, 계보 반영을 한 묶음으로 만듭니다.

**Architecture:** Worker 는 MySQL 만 읽습니다(표 크기 `information_schema`, 행 수 `meta_table_counts`, 빅쿼리 현황 `meta_bq_tables`). 화면은 그 응답과 기존 `/jobs/status`, 계보 파일, 새 손 파일 `source_history.json` 을 읽어 그립니다. 수집 상태·출처 멈춤 판정은 계보 화면의 `window.Lineage.model.jobStatus`·`sourceStopped` 를 고치지 않고 불러 씁니다. 계산(`dataops/model.js`)과 그리기(`dataops/view.js`)를 나눕니다.

**Tech Stack:** Cloudflare Workers(ES module, `node --test`), MySQL 8.4(Hyperdrive), 정적 HTML·바닐라 JS(UMD, `vm` 으로 시험), pytest, GitHub Actions.

설계: `docs/superpowers/specs/2026-10-18-data-ops-tab-design.md` (§4, §5, §7, §8).
미리보기 참고: `docs/superpowers/plans/assets/2026-10-18-data-ops/data_ops_mock_template.html`, `data_ops_mock_make.py`(실제 표·상태 + 예시 용량으로 그린 승인안. 화면 모양·툴팁 문구의 원본입니다).
선행: 계획 A(`2026-10-18-data-ops-a-cost-report-and-bq-snapshot.md`)의 Task 1·2(결과 JSON, `record_bq_snapshot.py`).

## Global Constraints

- **시작 조건:** evan 이 "KBO 약관 대응 세션(fix/kbo-tos-frontend 등)이 끝났다"고 확인한 뒤에만 시작합니다. 확인 전에는 이 계획의 어떤 파일도 main 쪽에 커밋하지 않습니다.
- 사용자에게 보이는 한국어는 `습니다/합니다/입니다` 체. 이모지 금지. 툴팁 첫 줄 굵게·둘째 보통·셋째부터 흐림. 키보드 초점으로도 열림.
- 색은 `dashboard_js/css/style.css` 의 토큰(`var(--…)`)만 씁니다(어두운 테마 대응). 좁은 화면(900px 이하) 타일·카드 2열, 출처·이력 1열.
- 공개 응답·화면에 넣지 않는 것: 프로젝트 ID, 데이터셋 이름, 인스턴스 이름, IP, Hyperdrive ID, 오류 원문(`meta_bq_tables.error`), 비용. 바깥 사이트 주소는 링크로 걸지 않습니다.
- koreabaseball.com·KBO 이미지 서버는 코드·시험·손 실행 어디서도 부르지 않습니다. 계보 파일의 `sources[].url` 은 화면에 쓰지 않습니다(사이트 이름만).
- 행 수 차이에 해석을 붙이지 않습니다. 비교 칸은 `같음`·`차이 ±N행`·`복사 실패`·`빅쿼리에 없음` 넷뿐입니다.
- 화면은 `api.js` 를 쓰지 않고 `window.KBO_API_BASE`(config.js)로 직접 `fetch` 합니다.
- `dashboard_js/js/lineage/*`, `pages/database-explorer.html` 의 메뉴 줄 말고는 고치지 않습니다(이 계획에서 그 페이지는 메뉴 링크 한 줄만 더함).
- 각 Task 는 자기 시험만 통과하면 됩니다. `tests/test_lineage.py` 는 계보를 다시 만드는 Task 6 에서 통과시킵니다(그 전에는 새 페이지·주소 때문에 실패하는 것이 정상).
- push·Worker 배포·Pages 배포·DB 쓰기(테이블 만들기)는 evan 허락 뒤. push 직전 `git log origin/main..HEAD --oneline` 을 다시 보여 주고 허락받은 sha 만 올립니다. Pages 배포 전 `git status --short dashboard_js` 를 보고 남의 변경이 있으면 알립니다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 작업 폴더

```bash
cd C:/Users/김승곤/Desktop/b_project
git fetch origin
git worktree add C:/tmp/b_project_opsB -b feat/data-ops-b origin/main
cd C:/tmp/b_project_opsB
git merge --no-ff feat/data-ops-a      # 계획 A 가 아직 main 에 없으면
git merge --no-ff docs/data-ops-spec   # 설계·계획 문서
```

## 파일 구조

| 파일 | 책임 |
|---|---|
| `migration/mysql/schema.sql` (수정) | `meta_bq_tables` 정의 |
| `.github/workflows/weekly.yml` (수정) | 복사에 `--result-json`, 새 단계 '빅쿼리 현황 기록', 요약 줄 |
| `src/lib/opsstorage.js` (새) | SQL 글자 + 응답 몸통 계산(순수) |
| `src/routes/ops.js` (새) | `GET /ops/storage` |
| `src/index.js` (수정) | 주소 등록 |
| `dashboard_js/js/dataops/model.js` (새) | 화면 계산(순수, UMD) |
| `dashboard_js/js/dataops/view.js` (새) | 그리기·툴팁·불러오기 |
| `dashboard_js/css/dataops.css` (새) | 화면 모양 |
| `dashboard_js/pages/data-ops.html` (새) | 페이지 |
| `dashboard_js/data/source_history.json` (새) | 수집 중단 이력(손 파일) |
| `dashboard_js/index.html`, `dashboard_js/pages/*.html` (수정) | 메뉴에 '데이터 관리' |
| `database/lineage_writes.json` (수정) | 새 스크립트·주소 설명 |
| `dashboard_js/data/table_lineage.json` (재생성) | `py scripts/build_lineage.py` |
| `test/opsstorage.test.js`, `test/dataops_model.test.js`, `tests/test_data_ops_wiring.py` (새) | |

---

### Task 1: `schema.sql` 과 주간 작업 연결

**Files:**
- Modify: `migration/mysql/schema.sql`(`meta_table_counts` 정의 바로 뒤), `.github/workflows/weekly.yml`(빅쿼리 복사 단계 약 153–158행, 그 뒤 기록 단계들, 요약 단계)
- Test: `tests/test_data_ops_wiring.py`

**Interfaces:**
- Consumes: `migration.mysql.record_bq_snapshot.DDL`, CLI `--result-json`.
- Produces: 주간 작업이 `$RUNNER_TEMP/bq_result.json` 을 만들고 `record_bq_snapshot` 을 부름.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```python
# tests/test_data_ops_wiring.py
"""데이터 관리 화면이 기대는 연결(스키마·주간 작업)을 봅니다."""
from pathlib import Path

import yaml

from migration.mysql import record_bq_snapshot as r

ROOT = Path(__file__).resolve().parents[1]


def weekly_steps():
    wf = yaml.safe_load((ROOT / ".github/workflows/weekly.yml").read_text(encoding="utf-8"))
    job = next(iter(wf["jobs"].values()))
    return job["steps"]


def test_schema_sql_에_현황_표가_설계와_같이_있습니다():
    schema = (ROOT / "migration/mysql/schema.sql").read_text(encoding="utf-8")
    assert r.DDL in schema


def test_빅쿼리_복사가_결과_파일을_남깁니다():
    step = next(s for s in weekly_steps() if s.get("id") == "bq_copy")
    assert '--result-json "$RUNNER_TEMP/bq_result.json"' in step["run"]


def test_현황_기록은_복사_뒤에_돌고_실패해도_판정을_바꾸지_않습니다():
    steps = weekly_steps()
    names = [s.get("name") for s in steps]
    i_copy = next(i for i, s in enumerate(steps) if s.get("id") == "bq_copy")
    i_rec = names.index("빅쿼리 현황 기록")
    rec = steps[i_rec]
    assert i_rec > i_copy
    assert rec.get("continue-on-error") is True
    assert rec.get("id") == "bq_snapshot"
    assert "always()" in rec["if"]
    assert "python -m migration.mysql.record_bq_snapshot" in rec["run"]
    assert '[ -f "$RUNNER_TEMP/bq_result.json" ]' in rec["run"]


def test_요약에_현황_기록_줄이_있습니다():
    summary = next(s for s in weekly_steps() if s.get("name") == "요약")
    assert "| 빅쿼리 현황 기록 | ${{ steps.bq_snapshot.outcome }} |" in summary["run"]
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_data_ops_wiring.py -q`
Expected: FAIL 4개

- [ ] **Step 3: 구현합니다**

`migration/mysql/schema.sql` 의 `meta_table_counts` 정의 다음 빈 줄 뒤에 `record_bq_snapshot.DDL` 과 글자 하나 다르지 않게 붙입니다.

```sql
CREATE TABLE `meta_bq_tables` (
  `name` VARCHAR(64) NOT NULL,
  `bq_rows` BIGINT,
  `bq_bytes` BIGINT,
  `last_ok_at` DATETIME,
  `last_try_at` DATETIME NOT NULL,
  `status` VARCHAR(8) NOT NULL,
  `error` VARCHAR(300),
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
```

`.github/workflows/weekly.yml`:

```yaml
      - name: 빅쿼리 복사
        id: bq_copy
        if: ${{ !cancelled() && steps.push.outcome == 'success' }}
        continue-on-error: true
        timeout-minutes: 40
        run: python -m migration.mysql.sqlite_to_bigquery --db "$KBO_DB" --result-json "$RUNNER_TEMP/bq_result.json"
```

'빅쿼리 복사 기록' 단계 바로 뒤에 더합니다.

```yaml
      # 공개 '데이터 관리' 화면이 읽는 빅쿼리 현황(meta_bq_tables)을 남깁니다.
      # 실패해도 주간 판정은 바꾸지 않습니다(mysql_sink 실패 기록을 쓰지 않음).
      - name: 빅쿼리 현황 기록
        id: bq_snapshot
        if: always()
        continue-on-error: true
        run: |
          if [ -f "$RUNNER_TEMP/bq_result.json" ]; then
            python -m migration.mysql.record_bq_snapshot --result-json "$RUNNER_TEMP/bq_result.json"
          else
            echo "빅쿼리 복사 결과 파일이 없어 현황을 기록하지 않습니다."
          fi
```

'요약' 단계의 `빅쿼리 복사` 줄 바로 뒤에 더합니다.

```yaml
            echo "| 빅쿼리 현황 기록 | ${{ steps.bq_snapshot.outcome }} |"
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_data_ops_wiring.py tests/test_sqlite_to_bigquery.py tests/test_collect_workflows.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add migration/mysql/schema.sql .github/workflows/weekly.yml tests/test_data_ops_wiring.py
git commit -m "feat(weekly): 빅쿼리 복사 결과를 meta_bq_tables 에 기록(실패해도 주간 판정 그대로), schema.sql 에 표 정의

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Worker `GET /ops/storage`

**Files:**
- Create: `src/lib/opsstorage.js`, `src/routes/ops.js`
- Modify: `src/index.js`(`/jobs/status` 등록 줄 근처)
- Test: `test/opsstorage.test.js`

**Interfaces:**
- Produces:
  - `SIZE_SQL`, `COUNT_SQL`, `BQ_SQL` (문자열)
  - `storageBody({ sizes, counts, bq, tables, now }) -> object` — 설계 §4-3 의 모양. `sizes` 는 `[{name, data_bytes, index_bytes}]`, `counts` 는 `[{name, n, updated_kst}]`, `bq` 는 `[{name, bq_rows, bq_bytes, last_ok_at, last_try_at, status}]` 또는 `null`, `tables` 는 컬럼 사전의 `tables`(분류), `now` 는 `Date`.
  - 응답 `mysql.tables[]`: `{name, category, rows, rows_updated_at, data_bytes, index_bytes}`, MySQL 용량(데이터+인덱스) 큰 순, 같으면 이름순. `mysql.total_rows`, `mysql.total_bytes`.
  - 응답 `bigquery`: `null` 또는 `{last_copy_at, ok, fail, tables: [{name, rows, bytes, last_ok_at, last_try_at, status}]}`. `error` 칸은 없음.
  - `opsStorage(request, env)` 라우트.

시각 처리: SQL 에서 글자로 만들어 받습니다(드라이버의 DATETIME 해석에 기대지 않음). `meta_table_counts.updated_at` 은 UTC 로 적혀 있으므로 9시간 더해 KST, `meta_bq_tables` 는 이미 KST.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```js
// test/opsstorage.test.js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { storageBody, SIZE_SQL, COUNT_SQL, BQ_SQL } from '../src/lib/opsstorage.js';
import { cacheControlFor } from '../src/lib/cachepolicy.js';

const NOW = new Date(Date.UTC(2026, 9, 18, 12, 40));   // KST 21:40
const sizes = [
  { name: 'games', data_bytes: '3000000', index_bytes: 1000000 },
  { name: 'play_by_play', data_bytes: 1900000000, index_bytes: 600000000 },
  { name: 'teams', data_bytes: 16384, index_bytes: 0 },
];
const counts = [
  { name: 'games', n: 12688, updated_kst: '2026-10-18 00:05' },
  { name: 'play_by_play', n: 3991757, updated_kst: '2026-10-18 00:04' },
];
const tables = { games: { category: '수집 데이터' }, play_by_play: { category: '수집 데이터' } };
const bq = [
  { name: 'games', bq_rows: 12684, bq_bytes: 3100000, last_ok_at: '2026-10-13 11:27', last_try_at: '2026-10-13 11:27', status: 'ok', error: '숨김' },
  { name: 'play_by_play', bq_rows: 3990573, bq_bytes: 1540000000, last_ok_at: '2026-10-06 11:20', last_try_at: '2026-10-13 11:27', status: 'fail' },
];

test('MySQL 표는 용량 큰 순이고 행 수·분류·갱신 시각을 붙입니다', () => {
  const b = storageBody({ sizes, counts, bq, tables, now: NOW });
  assert.deepEqual(b.mysql.tables.map(t => t.name), ['play_by_play', 'games', 'teams']);
  assert.deepEqual(b.mysql.tables[1], {
    name: 'games', category: '수집 데이터', rows: 12688, rows_updated_at: '2026-10-18 00:05',
    data_bytes: 3000000, index_bytes: 1000000,
  });
  assert.equal(b.mysql.tables[2].rows, null);
  assert.equal(b.mysql.tables[2].category, '');
  assert.equal(b.mysql.total_rows, 12688 + 3991757);
  assert.equal(b.mysql.total_bytes, 3000000 + 1000000 + 1900000000 + 600000000 + 16384);
  assert.equal(b.generated_at, '2026-10-18 21:40');
});

test('빅쿼리 현황은 오류 원문을 내보내지 않습니다', () => {
  const b = storageBody({ sizes, counts, bq, tables, now: NOW });
  assert.equal(b.bigquery.ok, 1);
  assert.equal(b.bigquery.fail, 1);
  assert.equal(b.bigquery.last_copy_at, '2026-10-13 11:27');
  assert.deepEqual(b.bigquery.tables[0], {
    name: 'games', rows: 12684, bytes: 3100000,
    last_ok_at: '2026-10-13 11:27', last_try_at: '2026-10-13 11:27', status: 'ok',
  });
  assert.ok(!JSON.stringify(b).includes('숨김'));
});

test('빅쿼리 현황을 못 읽었으면 null 입니다', () => {
  const b = storageBody({ sizes, counts, bq: null, tables, now: NOW });
  assert.equal(b.bigquery, null);
});

test('SQL 은 meta_ 표를 빼고 시각을 글자로 받습니다', () => {
  assert.match(SIZE_SQL, /information_schema\.tables/);
  assert.match(SIZE_SQL, /NOT LIKE 'meta\\_%'/);
  assert.match(SIZE_SQL, /table_type = 'BASE TABLE'/);
  assert.match(COUNT_SQL, /DATE_ADD\(updated_at, INTERVAL 9 HOUR\)/);
  assert.match(BQ_SQL, /DATE_FORMAT\(last_try_at/);
  assert.ok(!/\berror\b/.test(BQ_SQL));
});

test('주소가 등록돼 있고 엣지에 한 시간 캐시합니다', () => {
  const index = readFileSync('src/index.js', 'utf8');
  assert.match(index, /router\.add\('GET', '\/ops\/storage', opsStorage\)/);
  assert.match(cacheControlFor('/ops/storage'), /s-maxage=3600,/);
});
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `node --test test/opsstorage.test.js`
Expected: FAIL (`Cannot find module '../src/lib/opsstorage.js'`)

- [ ] **Step 3: 구현합니다**

```js
// src/lib/opsstorage.js
// 공개 '데이터 관리' 화면의 저장소 현황(GET /ops/storage)입니다.
//
// 세 가지를 읽습니다. 표 크기(information_schema, MySQL 추정치라 하루 단위로
// 갱신), 행 수(meta_table_counts, 적재 때 맞춘 값), 빅쿼리 사본 현황(meta_bq_tables,
// 주간 복사가 record_bq_snapshot.py 로 남김). Worker 에는 GCP 자격이 없어
// 빅쿼리를 직접 읽지 않습니다. 오류 원문(meta_bq_tables.error)은 프로젝트 이름이나
// 경로가 섞일 수 있어 내보내지 않습니다.
// 설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §4-3

export const SIZE_SQL =
  'SELECT table_name AS name, data_length AS data_bytes, index_length AS index_bytes '
  + 'FROM information_schema.tables WHERE table_schema = DATABASE() '
  + "AND table_type = 'BASE TABLE' AND table_name NOT LIKE 'meta\\_%'";  // lib/schema.js 와 같은 글자

// updated_at 은 UTC 로 적혀 있습니다(mysql_sink.refresh_count).
export const COUNT_SQL =
  "SELECT name, n, DATE_FORMAT(DATE_ADD(updated_at, INTERVAL 9 HOUR), '%Y-%m-%d %H:%i') AS updated_kst "
  + 'FROM meta_table_counts';

// 시각은 KST 로 적혀 있습니다(record_bq_snapshot.py).
export const BQ_SQL =
  'SELECT name, bq_rows, bq_bytes, '
  + "DATE_FORMAT(last_ok_at, '%Y-%m-%d %H:%i') AS last_ok_at, "
  + "DATE_FORMAT(last_try_at, '%Y-%m-%d %H:%i') AS last_try_at, status "
  + 'FROM meta_bq_tables';

function num(v) {
  if (v === null || v === undefined || v === '') return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function kstText(d) {
  const k = new Date(d.getTime() + 9 * 3600 * 1000);
  const p = (x) => String(x).padStart(2, '0');
  return `${k.getUTCFullYear()}-${p(k.getUTCMonth() + 1)}-${p(k.getUTCDate())} `
    + `${p(k.getUTCHours())}:${p(k.getUTCMinutes())}`;
}

export function storageBody({ sizes, counts, bq, tables, now }) {
  const cnt = new Map((counts || []).map(r => [r.name, r]));
  const my = (sizes || []).map((r) => {
    const c = cnt.get(r.name);
    return {
      name: r.name,
      category: ((tables || {})[r.name] || {}).category || '',
      rows: c ? num(c.n) : null,
      rows_updated_at: c ? (c.updated_kst || null) : null,
      data_bytes: num(r.data_bytes) || 0,
      index_bytes: num(r.index_bytes) || 0,
    };
  });
  my.sort((a, b) => (b.data_bytes + b.index_bytes) - (a.data_bytes + a.index_bytes)
    || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0));

  let bigquery = null;
  if (bq) {
    const list = bq.map(r => ({
      name: r.name, rows: num(r.bq_rows), bytes: num(r.bq_bytes),
      last_ok_at: r.last_ok_at || null, last_try_at: r.last_try_at || null, status: r.status,
    }));
    const tries = list.map(t => t.last_try_at).filter(Boolean).sort();
    bigquery = {
      last_copy_at: tries.length ? tries[tries.length - 1] : null,
      ok: list.filter(t => t.status === 'ok').length,
      fail: list.filter(t => t.status !== 'ok').length,
      tables: list,
    };
  }
  return {
    generated_at: kstText(now),
    mysql: {
      tables: my,
      total_rows: my.reduce((s, t) => s + (t.rows || 0), 0),
      total_bytes: my.reduce((s, t) => s + t.data_bytes + t.index_bytes, 0),
    },
    bigquery,
  };
}
```

```js
// src/routes/ops.js
// GET /ops/storage — 공개 '데이터 관리' 화면의 저장소 현황입니다.
// 계산은 lib/opsstorage.js 에 있습니다(이 파일은 컬럼 사전 JSON 을 import 해서
// node:test 가 직접 읽지 못합니다).

import { json, dbError } from '../lib/respond.js';
import { columnDict } from '../lib/coldict.js';
import { storageBody, SIZE_SQL, COUNT_SQL, BQ_SQL } from '../lib/opsstorage.js';

export async function opsStorage(request, env) {
  const db = env.MYSQL;
  let sizes;
  let counts;
  try {
    sizes = (await db.prepare(SIZE_SQL).all()).results || [];
    counts = (await db.prepare(COUNT_SQL).all()).results || [];
  } catch (err) {
    return dbError(err);
  }
  // 표가 아직 없거나(첫 주간 실행 전) 읽기에 실패해도 MySQL 부분은 보여 줍니다.
  let bq = null;
  try {
    bq = (await db.prepare(BQ_SQL).all()).results || [];
  } catch {
    bq = null;
  }
  return json(storageBody({ sizes, counts, bq, tables: columnDict().tables || {}, now: new Date() }));
}
```

`src/index.js`: 다른 라우트 import 들 옆에 `import { opsStorage } from './routes/ops.js';`, `router.add('GET', '/jobs/status', jobsStatus);` 다음 줄에 `router.add('GET', '/ops/storage', opsStorage);`. 캐시 정책은 기본값(엣지 1시간·브라우저 1분)이 설계 §4-3 의 1시간과 같으므로 `cachepolicy.js` 는 고치지 않습니다(시험이 확인).

- [ ] **Step 4: 시험을 돌립니다**

Run: `node --test test/opsstorage.test.js` 그리고 `npm test`
Expected: 새 시험 PASS, 기존 시험 그대로

- [ ] **Step 5: 커밋합니다**

```bash
git add src/lib/opsstorage.js src/routes/ops.js src/index.js test/opsstorage.test.js
git commit -m "feat(api): GET /ops/storage — MySQL 표 크기·행 수와 빅쿼리 사본 현황(오류 원문 제외)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 화면 계산 `dataops/model.js`

**Files:**
- Create: `dashboard_js/js/dataops/model.js`
- Test: `test/dataops_model.test.js`

**Interfaces:**
- Consumes: `/ops/storage` 응답(Task 2), 계보 파일, `/jobs/status` 의 `details`, `window.Lineage.model.jobStatus(lin, job, details, nowMs)`·`sourceStopped(lin, id)`(인자로 받음).
- Produces (`window.DataOps.model`):
  - `FOLD = 10`
  - `fmtBytes(n) -> string` — `2.48 GB`·`7.5 MB`·`18 KB`
  - `compare(myTable, bqTable|undefined, hasBq) -> {kind: 'same'|'diff'|'fail'|'missing'|'unknown', diff}`
  - `storageRows(storage) -> [{name, category, rows, bytes, data_bytes, index_bytes, rows_updated_at, bq, cmp}]`(응답 순서 유지)
  - `splitFold(rows, n=FOLD) -> {top, rest}`
  - `storageSummary(storage, rows) -> {totalRows, totalBytes, tableCount, same, bqBytes, lastCopyAt}`
  - `hostName(url) -> 'KBO 공식 사이트'|'네이버 스포츠'|'바깥 사이트'`
  - `sourceCards(lin, sourceStopped) -> [{id, name, host, stopped, scripts: [파일 이름]}]`
  - `jobCards(lin, details, nowMs, jobStatus) -> [{id, schedule, stopped, state, items}]`
  - `jobCounts(cards) -> {ok, run, warn, stopped}` — 멈춘 작업의 단계는 `stopped` 에만 셈, `run` = 멈추지 않은 작업의 단계 수, `warn` = 그중 정상이 아닌 수.
  - `historyEvents(hist) -> [...]` — 날짜 내림차순, 같은 날은 파일 순서.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```js
// test/dataops_model.test.js
// 화면 스크립트(UMD)를 vm 으로 불러 시험합니다. dashboard_js/*.js 는 script 태그용이라
// import 할 수 없습니다(package.json 의 type=module 과 무관).
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

function load(...files) {
  const ctx = {};
  ctx.window = ctx;
  vm.createContext(ctx);
  for (const f of files) vm.runInContext(readFileSync(f, 'utf8'), ctx, { filename: f });
  return ctx;
}
const ctx = load('dashboard_js/js/lineage/model.js', 'dashboard_js/js/dataops/model.js');
const M = ctx.DataOps.model;
const L = ctx.Lineage.model;

test('용량 글자', () => {
  assert.equal(M.fmtBytes(2480000000), '2.48 GB');
  assert.equal(M.fmtBytes(7500000), '7.5 MB');
  assert.equal(M.fmtBytes(18000), '18 KB');
  assert.equal(M.fmtBytes(null), '-');
});

test('비교 칸은 네 가지와 정보 없음뿐입니다', () => {
  const my = { name: 'games', rows: 12688 };
  assert.deepEqual({ ...M.compare(my, { rows: 12688, status: 'ok' }, true) }, { kind: 'same', diff: 0 });
  assert.deepEqual({ ...M.compare(my, { rows: 12684, status: 'ok' }, true) }, { kind: 'diff', diff: 4 });
  assert.equal(M.compare(my, { rows: 12000, status: 'fail' }, true).kind, 'fail');
  assert.equal(M.compare(my, undefined, true).kind, 'missing');
  assert.equal(M.compare(my, undefined, false).kind, 'unknown');
});

const STORAGE = {
  mysql: {
    tables: Array.from({ length: 12 }, (_, i) => ({
      name: 't' + String(i).padStart(2, '0'), category: '', rows: 10, rows_updated_at: null,
      data_bytes: 1000 - i, index_bytes: 0,
    })),
    total_rows: 120, total_bytes: 11934,
  },
  bigquery: { last_copy_at: '2026-10-13 11:27', ok: 2, fail: 0,
    tables: [{ name: 't00', rows: 10, bytes: 500, status: 'ok' }, { name: 't01', rows: 9, bytes: 400, status: 'ok' }] },
};

test('저장소 줄과 접기', () => {
  const rows = M.storageRows(STORAGE);
  assert.equal(rows[0].cmp.kind, 'same');
  assert.equal(rows[1].cmp.kind, 'diff');
  assert.equal(rows[2].cmp.kind, 'missing');
  const { top, rest } = M.splitFold(rows);
  assert.equal(top.length, 10);
  assert.equal(rest.length, 2);
  const s = M.storageSummary(STORAGE, rows);
  assert.deepEqual({ ...s }, { totalRows: 120, totalBytes: 11934, tableCount: 12, same: 1,
    bqBytes: 900, lastCopyAt: '2026-10-13 11:27' });
});

test('빅쿼리 정보가 없으면 비교는 정보 없음입니다', () => {
  const rows = M.storageRows({ ...STORAGE, bigquery: null });
  assert.ok(rows.every(r => r.cmp.kind === 'unknown'));
  assert.equal(M.storageSummary({ ...STORAGE, bigquery: null }, rows).lastCopyAt, null);
});

const LIN = {
  sources: [
    { id: 'kbo_record', name: 'KBO 기록실', url: 'https://www.koreabaseball.com/Record/' },
    { id: 'naver_relay', name: '네이버 문자중계', url: 'https://sports.naver.com/kbaseball/' },
    { id: 'kbo_live', name: '네이버 실시간', url: 'https://m.sports.naver.com/kbaseball/' },
  ],
  scripts: [
    { path: 'data_collection/a.py', sources: ['kbo_record'], stopped: true },
    { path: 'data_collection/b.py', sources: ['kbo_record', 'naver_relay'], stopped: true },
    { path: 'data_collection/c.py', sources: ['naver_relay'], stopped: false },
  ],
  jobs: [
    { id: 'daily', schedule_kst: '매일 03:33', stale_hours: 36, stopped: false,
      steps: [{ name: 'PBP', status_key: 'pbp' }, { name: '기록', status_key: null }, { name: 'games', status_key: 'games' }] },
    { id: 'roster', schedule_kst: '멈춤', stale_hours: 36, stopped: true,
      steps: [{ name: '명단', status_key: 'roster_pm' }] },
  ],
};

test('출처 카드: 쓰는 스크립트가 모두 멈췄을 때만 수집 중단', () => {
  const cards = M.sourceCards(LIN, L.sourceStopped);
  assert.deepEqual(cards.map(c => [c.id, c.host, c.stopped, c.scripts.length]), [
    ['kbo_record', 'KBO 공식 사이트', true, 2],
    ['naver_relay', '네이버 스포츠', false, 2],
    ['kbo_live', '네이버 스포츠', false, 0],
  ]);
  assert.deepEqual([...cards[0].scripts], ['a.py', 'b.py']);
  assert.ok(!JSON.stringify(cards).includes('koreabaseball'));
});

test('작업 카드와 셈', () => {
  const now = Date.UTC(2026, 9, 17, 16, 0);   // KST 10-18 01:00
  const details = {
    pbp: { last_run_at: '2026-10-17 23:59', status: 'ok' },
    games: { last_run_at: '2026-10-15 23:59', status: 'ok' },
    roster_pm: { last_run_at: '2026-10-17 22:41', status: 'ok' },
  };
  const cards = M.jobCards(LIN, details, now, L.jobStatus);
  assert.deepEqual(cards.map(c => [c.id, c.state, c.items.length]), [['daily', 'stale', 2], ['roster', 'stopped', 1]]);
  assert.deepEqual({ ...M.jobCounts(cards) }, { ok: 1, run: 2, warn: 1, stopped: 1 });
});

test('이력은 최근 날짜부터, 같은 날은 파일 순서', () => {
  const ev = M.historyEvents({ events: [
    { date: '2026-10-14', what: 'a' }, { date: '2026-10-18', what: 'b' }, { date: '2026-10-18', what: 'c' },
  ] });
  assert.deepEqual(ev.map(e => e.what), ['b', 'c', 'a']);
  assert.deepEqual([...M.historyEvents(null)], []);
});
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `node --test test/dataops_model.test.js`
Expected: FAIL (`ENOENT … dataops/model.js`)

- [ ] **Step 3: 구현합니다**

```js
/*
 * 데이터 관리 화면 계산입니다. 화면(DOM)에는 손대지 않습니다.
 *
 * 브라우저에서는 window.DataOps.model, 시험(test/dataops_model.test.js)에서는 vm 으로
 * 불러 씁니다. 수집 상태와 출처 멈춤 판정은 계보 화면의 함수(window.Lineage.model 의
 * jobStatus·sourceStopped)를 인자로 받아 씁니다. 같은 규칙을 두 번 쓰지 않으려는 것입니다.
 * 설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §5
 */
(function (root) {
  'use strict';
  const D = root.DataOps = root.DataOps || {};
  const FOLD = 10;

  function fmtBytes(n) {
    if (n === null || n === undefined || !Number.isFinite(Number(n))) return '-';
    const v = Number(n);
    if (v >= 1e9) return (v / 1e9).toFixed(2) + ' GB';
    if (v >= 1e6) return (v / 1e6).toFixed(1) + ' MB';
    return Math.round(v / 1e3) + ' KB';
  }

  /** MySQL 행 수와 빅쿼리 사본을 견줍니다. 해석은 붙이지 않습니다. */
  function compare(my, bq, hasBq) {
    if (!hasBq) return { kind: 'unknown', diff: null };
    if (!bq) return { kind: 'missing', diff: null };
    if (bq.status !== 'ok') return { kind: 'fail', diff: null };
    const diff = (my.rows || 0) - (bq.rows || 0);
    return diff === 0 ? { kind: 'same', diff: 0 } : { kind: 'diff', diff: diff };
  }

  function storageRows(storage) {
    const hasBq = !!(storage && storage.bigquery);
    const bq = new Map(((hasBq && storage.bigquery.tables) || []).map(t => [t.name, t]));
    return ((storage && storage.mysql && storage.mysql.tables) || []).map(function (t) {
      const b = bq.get(t.name);
      return Object.assign({}, t, {
        bytes: (t.data_bytes || 0) + (t.index_bytes || 0),
        bq: b || null,
        cmp: compare(t, b, hasBq),
      });
    });
  }

  function splitFold(rows, n) {
    const k = n === undefined ? FOLD : n;
    return { top: rows.slice(0, k), rest: rows.slice(k) };
  }

  function storageSummary(storage, rows) {
    const bq = storage && storage.bigquery;
    return {
      totalRows: storage.mysql.total_rows,
      totalBytes: storage.mysql.total_bytes,
      tableCount: rows.length,
      same: rows.filter(r => r.cmp.kind === 'same').length,
      bqBytes: bq ? bq.tables.reduce((s, t) => s + (t.bytes || 0), 0) : null,
      lastCopyAt: bq ? bq.last_copy_at : null,
    };
  }

  /** 바깥 사이트 주소는 화면에 쓰지 않고 이름만 씁니다. */
  function hostName(url) {
    const u = String(url || '');
    if (/naver\.com/.test(u)) return '네이버 스포츠';
    if (/koreabaseball\.com/.test(u)) return 'KBO 공식 사이트';
    return '바깥 사이트';
  }

  function sourceCards(lin, sourceStopped) {
    return ((lin && lin.sources) || []).map(function (s) {
      const scripts = ((lin.scripts) || []).filter(x => (x.sources || []).includes(s.id))
        .map(x => String(x.path).split('/').pop()).sort();
      return { id: s.id, name: s.name, host: hostName(s.url), stopped: !!sourceStopped(lin, s.id), scripts: scripts };
    });
  }

  function jobCards(lin, details, nowMs, jobStatus) {
    return ((lin && lin.jobs) || []).map(function (j) {
      const st = jobStatus(lin, j, details, nowMs);
      return { id: j.id, schedule: j.schedule_kst, stopped: !!j.stopped, staleHours: j.stale_hours,
        state: st.state, items: st.items };
    });
  }

  function jobCounts(cards) {
    const out = { ok: 0, run: 0, warn: 0, stopped: 0 };
    cards.forEach(function (c) {
      c.items.forEach(function (it) {
        if (c.stopped) { out.stopped += 1; return; }
        out.run += 1;
        if (it.state === 'ok') out.ok += 1; else out.warn += 1;
      });
    });
    return out;
  }

  function historyEvents(hist) {
    const ev = ((hist && hist.events) || []).map((e, i) => ({ e: e, i: i }));
    ev.sort((a, b) => (a.e.date < b.e.date ? 1 : a.e.date > b.e.date ? -1 : a.i - b.i));
    return ev.map(x => x.e);
  }

  const api = { FOLD, fmtBytes, compare, storageRows, splitFold, storageSummary, hostName,
    sourceCards, jobCards, jobCounts, historyEvents };
  D.model = api;
  if (typeof module === 'object' && module.exports) module.exports = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `node --test test/dataops_model.test.js`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add dashboard_js/js/dataops/model.js test/dataops_model.test.js
git commit -m "feat(data-ops): 화면 계산(저장소 비교·접기·출처·작업 상태·이력), 계보 판정 함수 재사용

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 페이지·그리기·모양·이력 파일

**Files:**
- Create: `dashboard_js/pages/data-ops.html`, `dashboard_js/js/dataops/view.js`, `dashboard_js/css/dataops.css`, `dashboard_js/data/source_history.json`
- Test: `tests/test_data_ops_wiring.py`(더함)

**Interfaces:**
- Consumes: Task 3 의 `window.DataOps.model`, `window.Lineage.model`, `window.KBO_API_BASE`.
- Produces: 페이지가 부르는 주소 글자 `'/ops/storage'`, `'/jobs/status'`(계보가 이 글자로 페이지↔주소를 잇습니다).

- [ ] **Step 1: 실패하는 시험을 더합니다**

`tests/test_data_ops_wiring.py` 끝에 더합니다.

```python
import json
import re


def test_이력_파일_모양():
    data = json.loads((ROOT / "dashboard_js/data/source_history.json").read_text(encoding="utf-8"))
    lin = json.loads((ROOT / "dashboard_js/data/table_lineage.json").read_text(encoding="utf-8"))
    ids = {s["id"] for s in lin["sources"]}
    assert data["events"]
    for e in data["events"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", e["date"])
        assert e["kind"] in {"중단", "대체", "재개", "알림"}
        assert set(e.get("sources", [])) <= ids
        assert e["what"] and e["reason"]


def test_페이지는_KBO_주소를_싣지_않고_api_js_를_쓰지_않습니다():
    page = (ROOT / "dashboard_js/pages/data-ops.html").read_text(encoding="utf-8")
    view = (ROOT / "dashboard_js/js/dataops/view.js").read_text(encoding="utf-8")
    hist = (ROOT / "dashboard_js/data/source_history.json").read_text(encoding="utf-8")
    for text in (page, view, hist):
        assert "koreabaseball" not in text
    assert "js/api.js" not in page
    for src in ("../js/config.js", "../js/lineage/model.js", "../js/dataops/model.js", "../js/dataops/view.js"):
        assert src in page
    assert "'/ops/storage'" in view and "'/jobs/status'" in view
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_data_ops_wiring.py -q`
Expected: 새 시험 2개 FAIL(파일 없음)

- [ ] **Step 3: 이력 파일을 씁니다**

날짜는 쓰기 전에 커밋 기록으로 확인합니다: `git log -1 --format=%ad --date=short f91bfc4`(수집 중단), `git log -1 --format=%ad --date=short 4707d4c`(/standings 대체), `git log -1 --format=%ad --date=short 90a2370`(화면 내림). 아래 날짜가 다르면 커밋 날짜로 고칩니다.

```json
{
  "events": [
    { "date": "2026-10-18", "kind": "대체", "sources": ["kbo_record"],
      "what": "팀 순위",
      "detail": "팀 순위를 KBO 기록실 대신 네이버 스포츠에서 읽도록 바꿨습니다.",
      "reason": "KBO 이용약관 제14조" },
    { "date": "2026-10-18", "kind": "중단", "sources": ["kbo_futures", "kbo_register"],
      "what": "퓨처스·1군 등록 명단 화면",
      "detail": "네이버에 같은 자료가 없어 화면을 내렸습니다. 대체하지 않습니다.",
      "reason": "KBO 이용약관 제14조" },
    { "date": "2026-10-17", "kind": "중단",
      "sources": ["kbo_record", "kbo_futures", "kbo_register", "kbo_player_search", "kbo_player_detail"],
      "what": "KBO 공식 사이트 수집 전부",
      "detail": "공식 기록·팀 순위·퓨처스·등록 명단·새 선수 단계와 roster·monthly 예약 실행을 멈췄습니다.",
      "reason": "KBO 이용약관 제14조(자동 수집·재배포 금지)" },
    { "date": "2026-10-14", "kind": "알림", "sources": [],
      "what": "KBO 이용약관 개정 시행",
      "detail": "크롤러·스크래퍼 등 자동 수집과 재배포·2차 가공을 금지하는 조항이 시행됐습니다.",
      "reason": "2026-09-15 공고" }
  ]
}
```

- [ ] **Step 4: 모양 파일을 씁니다**

`dashboard_js/css/dataops.css` 는 미리보기 틀(`docs/superpowers/plans/assets/2026-10-18-data-ops/data_ops_mock_template.html`)의 `<style>` 안 내용을 그대로 옮기되, 아래만 바꿉니다.
- `.mockbar` 규칙을 지웁니다.
- `.tip` 의 배경 `#0f172a`·글자 `#f8fafc`·흐림 `#cbd5e1` 은 그대로 둡니다(툴팁은 두 테마 모두 어두운 바탕).
- `.chip.diff`(`#dbeafe`/`#1d4ed8`), `.chip.bad`(`#fee2e2`/`#b91c1c`), `.chip.ok`(`#d1fae5`/`#047857`), `.chip.none`(`#f1f5f9`/`#475569`) 아래에 어두운 테마 규칙을 더합니다.

```css
[data-theme="dark"] .chip.diff{background:rgba(59,130,246,.18);color:#93c5fd}
[data-theme="dark"] .chip.bad{background:rgba(239,68,68,.18);color:#fca5a5}
[data-theme="dark"] .chip.ok{background:rgba(16,185,129,.18);color:#6ee7b7}
[data-theme="dark"] .chip.none{background:var(--bg-tertiary);color:var(--text-muted)}
.ops-msg{color:var(--text-muted);font-size:.85rem;padding:12px 0}
```

(테마 속성 이름은 `js/theme-toggle.js` 에서 확인합니다. `data-theme` 이 아니면 그 이름으로 바꿉니다.)

- [ ] **Step 5: 그리기 `view.js` 를 씁니다**

```js
/*
 * 데이터 관리 화면 그리기입니다. 계산은 dataops/model.js 에 있습니다.
 * 네 가지를 따로 불러오고, 하나가 실패해도 나머지는 그립니다(설계 §5).
 *   /ops/storage, /jobs/status (Worker), ../data/table_lineage.json, ../data/source_history.json
 * api.js 는 쓰지 않습니다. 툴팁 모양은 bstats 공용(첫 줄 굵게, 둘째 보통, 셋째부터 흐림).
 */
(function () {
  'use strict';
  const M = window.DataOps.model;
  const L = window.Lineage.model;
  const API = window.KBO_API_BASE;
  const STATE = { ok: ['정상', 'ok'], stale: ['오래됨', 'warn'], fail: ['실패', 'bad'], none: ['기록 없음', 'none'] };

  function esc(s) {
    return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  }
  function tip() { return ' tabindex="0" data-tip="' + esc(Array.from(arguments).join('\n')) + '"'; }
  function num(n) { return n === null || n === undefined ? '-' : Number(n).toLocaleString('ko-KR'); }
  function $(id) { return document.getElementById(id); }
  function getJson(url) { return fetch(url).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); }); }
  function fail(id, what) { $(id).innerHTML = '<p class="ops-msg">' + esc(what) + '을(를) 불러오지 못했습니다.</p>'; }

  // ---- 저장소 ----
  function cmpChip(c) {
    if (c.kind === 'same') return '<span class="chip same">같음</span>';
    if (c.kind === 'diff') return '<span class="chip diff">차이 ' + (c.diff > 0 ? '+' : '') + num(c.diff) + '행</span>';
    if (c.kind === 'fail') return '<span class="chip bad">복사 실패</span>';
    if (c.kind === 'missing') return '<span class="chip none">빅쿼리에 없음</span>';
    return '<span class="chip none">정보 없음</span>';
  }
  function storageRow(r, maxBytes, folded) {
    const t = tip(r.name,
      (r.category || '분류 없음') + ' · MySQL ' + num(r.rows) + '행 · 빅쿼리 ' + (r.bq ? num(r.bq.rows) + '행' : '-'),
      'MySQL 용량 ' + M.fmtBytes(r.bytes) + ' = 데이터 ' + M.fmtBytes(r.data_bytes) + ' + 인덱스 ' + M.fmtBytes(r.index_bytes),
      '행 수 갱신 ' + (r.rows_updated_at || '-') + ' · 빅쿼리 마지막 성공 ' + ((r.bq && r.bq.last_ok_at) || '-'),
      '차이 = MySQL 행 수 − 빅쿼리 행 수. 빅쿼리는 주 1회 사본이라 그 사이 들어온 행만큼 차이가 납니다.');
    const w = Math.max(r.bytes / (maxBytes || 1) * 100, 0.6).toFixed(1);
    return '<tr' + t + (folded ? ' class="fold"' : '') + '><th scope="row"><code>' + esc(r.name) + '</code></th>'
      + '<td class="cat">' + esc(r.category || '-') + '</td><td>' + num(r.rows) + '</td>'
      + '<td class="szc"><span class="sz">' + M.fmtBytes(r.bytes) + '</span><span class="szbar"><span style="width:' + w + '%"></span></span></td>'
      + '<td>' + (r.bq ? num(r.bq.rows) : '-') + '</td><td>' + (r.bq ? M.fmtBytes(r.bq.bytes) : '-') + '</td>'
      + '<td>' + cmpChip(r.cmp) + '</td></tr>';
  }
  function renderStorage(storage) {
    const rows = M.storageRows(storage);
    const s = M.storageSummary(storage, rows);
    const maxBytes = rows.length ? rows[0].bytes : 1;
    const parts = M.splitFold(rows);
    $('ops-st-body').innerHTML = parts.top.map(r => storageRow(r, maxBytes, false)).join('')
      + parts.rest.map(r => storageRow(r, maxBytes, true)).join('');
    $('ops-st-total').innerHTML = '<th scope="row">합계</th><td></td><td>' + num(s.totalRows) + '</td><td>'
      + M.fmtBytes(s.totalBytes) + '</td><td></td><td>' + (s.bqBytes === null ? '-' : M.fmtBytes(s.bqBytes)) + '</td><td></td>';
    $('ops-st-sub').textContent = 'MySQL 용량이 큰 표부터 ' + parts.top.length + '개 · 합계는 전체 ' + rows.length
      + '개 기준 · 빅쿼리 마지막 복사 ' + (s.lastCopyAt || '정보 없음');
    const btn = $('ops-st-fold');
    if (parts.rest.length) {
      btn.hidden = false;
      const label = () => ($('ops-st').classList.contains('open') ? '용량 큰 ' + parts.top.length + '개만 보기' : '나머지 ' + parts.rest.length + '개 표 보기');
      btn.textContent = label();
      btn.onclick = () => { $('ops-st').classList.toggle('open'); btn.textContent = label(); };
    }
    $('ops-t-my').innerHTML = num(s.totalRows) + '<small>행</small>';
    $('ops-t-my-f').textContent = '표 ' + s.tableCount + '개 · 용량 약 ' + M.fmtBytes(s.totalBytes);
    if (storage.bigquery) {
      $('ops-t-bq').innerHTML = s.same + '<small>/ ' + s.tableCount + ' 표 같음</small>';
      $('ops-t-bq-f').textContent = '마지막 복사 ' + (s.lastCopyAt || '-') + ' · 용량 약 ' + M.fmtBytes(s.bqBytes);
    } else {
      $('ops-t-bq').innerHTML = '-';
      $('ops-t-bq-f').textContent = '빅쿼리 정보 없음';
    }
  }

  // ---- 수집 작업 ----
  function renderJobs(lin, details) {
    const cards = M.jobCards(lin, details, Date.now(), L.jobStatus);
    $('ops-jobs').innerHTML = cards.map(function (c) {
      const lis = c.items.map(function (it) {
        const st = c.stopped ? ['멈춤', 'stop'] : (STATE[it.state] || STATE.none);
        const t = tip(it.step + ' · ' + it.key, st[0] + ' · 마지막 실행 ' + (it.at || '-'),
          it.note ? '메모: ' + it.note : '',
          c.stopped ? L.stoppedReason(lin) : '오래됨 기준: 마지막 실행 뒤 ' + c.staleHours + '시간이 지나면 오래됨으로 봅니다.');
        return '<li' + t + '><span class="dot ' + st[1] + '"></span><span class="sn">' + esc(it.step)
          + '</span><span class="sw">' + esc(it.at ? it.at.slice(5) : '-') + '</span></li>';
      }).join('');
      return '<div class="job' + (c.stopped ? ' stopped' : '') + '"><div class="jh"><b>' + esc(c.id) + '</b>'
        + (c.stopped ? '<span class="chip stop">예약 멈춤</span>' : '') + '<span class="js">' + esc(c.schedule) + '</span></div>'
        + '<ul>' + lis + '</ul></div>';
    }).join('');
    const n = M.jobCounts(cards);
    $('ops-t-job').innerHTML = n.ok + '<small>/ ' + n.run + ' 정상</small>';
    $('ops-t-job-f').textContent = '확인 필요 ' + n.warn + ' · 예약 멈춤 ' + n.stopped;
  }

  // ---- 출처·이력 ----
  function renderSources(lin) {
    const cards = M.sourceCards(lin, L.sourceStopped);
    const off = cards.filter(c => c.stopped).length;
    $('ops-src').innerHTML = cards.map(function (c) {
      const t = tip(c.name, (c.stopped ? '수집 중단' : '사용 중') + ' · ' + c.host,
        '이 출처를 쓰는 수집 스크립트: ' + (c.scripts.join(', ') || '없음(API 가 그때그때 읽음)'),
        "상태 규칙: 이 출처를 쓰는 수집 스크립트가 모두 멈췄으면 '수집 중단'입니다(계보 파일 기준).");
      return '<div class="src' + (c.stopped ? ' off' : '') + '"' + t + '><div class="sh"><b>' + esc(c.name) + '</b>'
        + (c.stopped ? '<span class="chip stop">수집 중단</span>' : '<span class="chip ok">사용 중</span>')
        + '</div><div class="sm">' + esc(c.host) + ' · 스크립트 ' + c.scripts.length + '개</div></div>';
    }).join('');
    $('ops-src-sub').textContent = '사용 중 ' + (cards.length - off) + ' · 수집 중단 ' + off;
    $('ops-t-src').innerHTML = (cards.length - off) + '<small>사용 중</small>';
    $('ops-t-src-f').textContent = '수집 중단 ' + off;
  }
  function renderHistory(hist) {
    const KIND = { '중단': 'bad', '대체': 'ok', '재개': 'ok', '알림': 'none' };
    $('ops-hist').innerHTML = M.historyEvents(hist).map(e =>
      '<li><span class="hd">' + esc(e.date) + '</span><span class="chip ' + (KIND[e.kind] || 'none') + '">' + esc(e.kind)
      + '</span><div class="hb"><b>' + esc(e.what) + '</b><p>' + esc(e.detail || '') + '</p><p class="why">이유: '
      + esc(e.reason) + '</p></div></li>').join('');
  }

  // ---- 툴팁 ----
  function renderTip(text) {
    return text.split('\n').filter(Boolean).map((l, i) =>
      '<div class="' + (i === 0 ? 'l1' : i === 1 ? 'l2' : 'lx') + '">' + esc(l) + '</div>').join('');
  }
  let cur = null;
  function hide() { if (cur) { cur.remove(); cur = null; } }
  function show(el) {
    hide();
    const t = document.createElement('div');
    t.className = 'tip';
    t.setAttribute('role', 'tooltip');
    t.innerHTML = renderTip(el.getAttribute('data-tip'));
    document.body.appendChild(t);
    const r = el.getBoundingClientRect();
    const x = Math.max(8, Math.min(r.left + r.width / 2 - t.offsetWidth / 2, innerWidth - t.offsetWidth - 8));
    let y = r.top - t.offsetHeight - 8;
    if (y < 8) y = r.bottom + 8;
    t.style.left = x + 'px';
    t.style.top = y + 'px';
    cur = t;
  }
  document.addEventListener('mouseover', e => { const el = e.target.closest('[data-tip]'); if (el) show(el); else hide(); });
  document.addEventListener('focusin', e => { const el = e.target.closest('[data-tip]'); if (el) show(el); });
  document.addEventListener('focusout', hide);
  document.addEventListener('keydown', e => { if (e.key === 'Escape') hide(); });
  addEventListener('scroll', hide, true);

  // ---- 불러오기 ----
  const lin = getJson('../data/table_lineage.json');
  getJson(API + '/ops/storage').then(renderStorage).catch(() => {
    fail('ops-st-msg', '저장소 현황');
    $('ops-t-my').textContent = '-';
    $('ops-t-bq').textContent = '-';
  });
  Promise.all([lin, getJson(API + '/jobs/status')])
    .then(([l, js]) => renderJobs(l, js.details || {}))
    .catch(() => fail('ops-jobs', '수집 작업 상태'));
  lin.then(renderSources).catch(() => fail('ops-src', '출처'));
  getJson('../data/source_history.json').then(renderHistory).catch(() => fail('ops-hist', '수집 중단 이력'));
})();
```

`'/ops/storage'`·`'/jobs/status'` 를 따옴표 글자로 둔 이유: 계보 추출기(`lineage_extract.source_routes`)가 따옴표로 시작하는 경로 글자를 주소로 읽습니다. `API + '/ops/storage'` 꼴을 바꾸지 마십시오.

- [ ] **Step 6: 페이지를 씁니다**

`dashboard_js/pages/data-ops.html` — 머리(`<head>`)는 `pages/team-stats.html` 의 `<head>` 를 복사하고 아래만 바꿉니다: `<title>데이터 관리 - Bstats</title>`, `<meta name="description" content="Bstats 데이터 저장소·수집 상태·출처">`, 그 페이지 전용 CSS·JS 줄은 지우고 `<link rel="stylesheet" href="../css/dataops.css">` 를 더합니다(`config.js`·`theme-toggle.js`·`nav.js` 는 남김). 몸통:

```html
<body>
    <header class="header">
        <div class="header-content">
            <a href="../" class="logo">
                <img src="../assets/favicon/diamond.svg" alt="" class="logo-icon" width="26" height="26">
                <span>Bstats</span>
            </a>
            <nav class="nav">
                <a href="../" class="nav-link">홈</a>
                <a href="team-stats" class="nav-link">팀 통계</a>
                <a href="player-stats" class="nav-link">선수 통계</a>
                <a href="player-analytics" class="nav-link">선수 분석</a>
                <a href="article" class="nav-link">아티클</a>
                <a href="factor-stats" class="nav-link">요인 통계</a>
                <a href="database-explorer" class="nav-link">데이터 탐색</a>
                <a href="data-ops" class="nav-link active">데이터 관리</a>
            </nav>
        </div>
    </header>

    <main class="container">
        <div class="ops-head">
            <h1>데이터 관리</h1>
            <p>이 사이트의 데이터가 어디에 얼마나 있는지, 언제 들어왔는지, 어디서 오는지 보여 줍니다.</p>
        </div>

        <div class="ops-sum">
            <div class="ops-tile"><div class="k">MySQL 전체 <span class="info" tabindex="0" data-tip="MySQL 전체
사이트가 실제로 읽는 원본 데이터베이스입니다. 표마다 행 수와 용량을 더했습니다.
행 수는 적재할 때마다 맞춰 두는 값이고, 용량은 데이터+인덱스의 추정치로 하루 단위로 갱신됩니다.">i</span></div><div class="v" id="ops-t-my">…</div><div class="f" id="ops-t-my-f"></div></div>
            <div class="ops-tile"><div class="k">빅쿼리 사본 <span class="info" tabindex="0" data-tip="빅쿼리 사본
분석용으로 매주 MySQL 표를 통째로 복사해 둔 사본입니다. 사이트는 이 사본을 읽지 않습니다.
마지막 복사 시각과, 행 수가 MySQL 과 같은 표 수를 보여 줍니다.">i</span></div><div class="v" id="ops-t-bq">…</div><div class="f" id="ops-t-bq-f"></div></div>
            <div class="ops-tile"><div class="k">수집 작업 <span class="info" tabindex="0" data-tip="수집 작업
예약 실행 중인 수집 단계 가운데 정상인 단계의 수입니다.
정상 = 마지막 실행이 성공했고 작업마다 정한 시간 안에 다시 돌았습니다.
예약을 멈춘 작업의 단계는 따로 셉니다.">i</span></div><div class="v" id="ops-t-job">…</div><div class="f" id="ops-t-job-f"></div></div>
            <div class="ops-tile"><div class="k">출처 <span class="info" tabindex="0" data-tip="출처
데이터를 가져오는 바깥 사이트입니다.
수집 중단 = 그 출처를 쓰는 수집 스크립트가 모두 멈춘 경우입니다.">i</span></div><div class="v" id="ops-t-src">…</div><div class="f" id="ops-t-src-f"></div></div>
        </div>

        <section class="ops-sec">
            <h2>저장소 현황 <span class="info" tabindex="0" data-tip="저장소 현황
표마다 MySQL(원본)과 빅쿼리(주간 사본)의 행 수·용량을 나란히 봅니다. 줄에 마우스를 올리면 자세한 값이 나옵니다.
차이 = MySQL 행 수 − 빅쿼리 행 수. 빅쿼리는 주 1회 사본이라 그 사이 들어온 행만큼 차이가 납니다. 해석은 붙이지 않고 숫자만 보여 줍니다.
MySQL 용량은 데이터+인덱스의 추정치입니다.">i</span></h2>
            <p class="sub" id="ops-st-sub"></p>
            <div id="ops-st-msg"></div>
            <div class="st-wrap">
                <table class="st" id="ops-st">
                    <thead>
                        <tr><th></th><th></th><th class="grp my" colspan="2">MySQL (원본)</th><th class="grp bq" colspan="2">빅쿼리 (주간 사본)</th><th></th></tr>
                        <tr><th>표</th><th>분류</th><th>행 수</th><th>용량<span class="info" tabindex="0" data-tip="MySQL 용량
데이터 + 인덱스 크기입니다. MySQL 이 알려 주는 추정치이고 하루 단위로 갱신됩니다.
막대 길이는 가장 큰 표를 100으로 둔 비율입니다.">i</span></th><th>행 수</th><th>용량<span class="info" tabindex="0" data-tip="빅쿼리 용량
마지막으로 복사에 성공했을 때 빅쿼리가 알려 준 표 크기입니다.
인덱스가 없어 MySQL 보다 작게 나옵니다.">i</span></th><th>비교<span class="info" tabindex="0" data-tip="비교
같음: 두 행 수가 같습니다.
차이 N행: MySQL 행 수 − 빅쿼리 행 수입니다.
복사 실패: 지난 복사에서 이 표가 실패했습니다. 빅쿼리에는 그 전 사본이 남아 있습니다.
빅쿼리에 없음: 아직 한 번도 복사되지 않은 새 표입니다.">i</span></th></tr>
                    </thead>
                    <tbody id="ops-st-body"></tbody>
                    <tfoot><tr id="ops-st-total"></tr></tfoot>
                </table>
            </div>
            <button class="foldbtn" type="button" id="ops-st-fold" hidden></button>
            <div class="legend"><span><span class="chip same">같음</span> 두 행 수가 같음</span><span><span class="chip diff">차이</span> MySQL − 빅쿼리</span><span><span class="chip bad">복사 실패</span> 지난 복사 실패</span><span><span class="chip none">빅쿼리에 없음</span> 아직 복사 전</span></div>
        </section>

        <section class="ops-sec">
            <h2>수집 작업 상태 <span class="info" tabindex="0" data-tip="수집 작업 상태
예약 작업과 그 안의 기록 단계입니다. 점 색: 초록 정상, 노랑 오래됨, 빨강 실패, 회색 기록 없음, 점선 예약 멈춤.
오래됨 = 마지막 실행 뒤 작업마다 정한 시간이 지났습니다. 날짜는 KST 입니다.">i</span></h2>
            <p class="sub">단계에 마우스를 올리면 마지막 실행 시각과 메모가 나옵니다.</p>
            <div class="jobs" id="ops-jobs"></div>
            <a class="more" href="database-explorer">자세한 수집 일정은 데이터 탐색에서 봅니다 &rarr;</a>
        </section>

        <div class="two">
            <section class="ops-sec">
                <h2>출처 <span class="info" tabindex="0" data-tip="출처
데이터를 가져오는 바깥 사이트 목록입니다(계보 파일 기준).
수집 중단 = 그 출처를 쓰는 수집 스크립트가 모두 멈춘 경우입니다.
바깥 사이트 주소는 링크로 걸지 않습니다.">i</span></h2>
                <p class="sub" id="ops-src-sub"></p>
                <div class="srcs" id="ops-src"></div>
            </section>
            <section class="ops-sec">
                <h2>수집 중단 이력 <span class="info" tabindex="0" data-tip="수집 중단 이력
출처를 멈추거나 바꾼 일을 최근 것부터 적은 기록입니다.
중단: 수집을 멈췄습니다. 대체: 다른 출처로 바꿨습니다. 알림: 바깥 사정이 바뀌었습니다.">i</span></h2>
                <p class="sub">최근 것부터</p>
                <ul class="tl" id="ops-hist"></ul>
            </section>
        </div>
    </main>

    <script src="../js/lineage/model.js"></script>
    <script src="../js/dataops/model.js"></script>
    <script src="../js/dataops/view.js"></script>
</body>
</html>
```

(`<head>` 에 `<script src="../js/config.js"></script>` 가 있어야 `window.KBO_API_BASE` 가 정해집니다.)

- [ ] **Step 7: 시험을 돌립니다**

Run: `py -m pytest tests/test_data_ops_wiring.py -q` 그리고 `node --test test/dataops_model.test.js`
Expected: 전부 PASS

- [ ] **Step 8: 로컬에서 눈으로 봅니다**

```bash
py -m http.server 8765 --bind 127.0.0.2 --directory dashboard_js
```

`http://127.0.0.2:8765/pages/data-ops` 를 헤드리스 Edge 로 캡처합니다(1300×2000, 밝은 테마 하나·어두운 테마 하나). Worker 에 `/ops/storage` 가 아직 배포되지 않았으므로 저장소 칸은 '불러오지 못했습니다'가 정상입니다(실패 처리 확인). 나머지 세 칸은 실제 값으로 그려져야 합니다. 캡처는 `바탕화면/bstats_미리보기/data_ops/impl/` 에 두고 Read 로 열어 확인합니다. 서버는 끕니다.

- [ ] **Step 9: 커밋합니다**

```bash
git add dashboard_js/pages/data-ops.html dashboard_js/js/dataops/view.js dashboard_js/css/dataops.css dashboard_js/data/source_history.json tests/test_data_ops_wiring.py
git commit -m "feat(data-ops): 데이터 관리 페이지(저장소·수집 상태·출처·중단 이력, 부분별 실패 처리·툴팁)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 모든 페이지 메뉴에 '데이터 관리'

**Files:**
- Modify: `dashboard_js/index.html:43`, `dashboard_js/pages/{article,database-explorer,factor-stats,player-analytics,player-stats,team-record,team-stats}.html` 의 '데이터 탐색' 메뉴 줄 바로 뒤
- Test: `tests/test_data_ops_wiring.py`(더함)

- [ ] **Step 1: 실패하는 시험을 더합니다**

```python
NAV_PAGES = ["index.html"] + ["pages/%s.html" % p for p in (
    "article", "database-explorer", "factor-stats", "player-analytics",
    "player-stats", "team-record", "team-stats", "data-ops")]


def test_모든_페이지_메뉴에_데이터_관리가_데이터_탐색_뒤에_있습니다():
    for rel in NAV_PAGES:
        html = (ROOT / "dashboard_js" / rel).read_text(encoding="utf-8")
        nav = html[html.index('<nav class="nav">'):html.index("</nav>")]
        links = re.findall(r'href="([^"]+)" class="nav-link[^"]*">([^<]+)<', nav)
        names = [n for _, n in links]
        assert names[-2:] == ["데이터 탐색", "데이터 관리"], rel
        href = dict((n, h) for h, n in links)["데이터 관리"]
        assert href == ("pages/data-ops" if rel == "index.html" else "data-ops"), rel
```

- [ ] **Step 2: 실패를 봅니다**

Run: `py -m pytest tests/test_data_ops_wiring.py -q -k 메뉴`
Expected: FAIL (`index.html`)

- [ ] **Step 3: 고칩니다**

`index.html` 의 `<a href="pages/database-explorer" class="nav-link">데이터 탐색</a>` 다음 줄에 같은 들여쓰기로
`<a href="pages/data-ops" class="nav-link">데이터 관리</a>` 를 넣습니다.
나머지 7개 페이지는 `<a href="database-explorer" class="nav-link…">데이터 탐색</a>` 다음 줄에
`<a href="data-ops" class="nav-link">데이터 관리</a>` 를 넣습니다(database-explorer.html 은 이 한 줄만 고칩니다).
좁은 화면 햄버거 메뉴(`js/nav.js`)는 `.nav` 안 링크를 그대로 쓰므로 따로 고칠 것이 없습니다.

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_data_ops_wiring.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add dashboard_js/index.html dashboard_js/pages/*.html tests/test_data_ops_wiring.py
git commit -m "feat(nav): 모든 페이지 메뉴에 '데이터 관리'(데이터 탐색 오른쪽)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 계보 반영과 전체 시험

**Files:**
- Modify: `database/lineage_writes.json`
- Regenerate: `dashboard_js/data/table_lineage.json`

- [ ] **Step 1: 손 파일에 더합니다**

`database/lineage_writes.json` 의 `scripts` 에(키 이름 순서를 지키는 파일이면 그 자리에):

```json
"migration/mysql/record_bq_snapshot.py": {
  "sources": [], "writes": [], "reads": [],
  "note": "빅쿼리 사본 현황(meta_bq_tables)을 씁니다. meta_ 표는 계보에 그리지 않습니다.",
  "desc": "주간 빅쿼리 복사가 남긴 결과 파일을 읽어 표마다 빅쿼리 행 수·용량·마지막 성공 시각을 MySQL meta_bq_tables 에 씁니다. 공개 데이터 관리 화면이 이 값을 읽습니다. 실패해도 주간 작업 판정은 바꾸지 않습니다."
}
```

`routes_without_tables` 에:

```json
"/ops/storage": "표 크기(information_schema)와 meta_table_counts·meta_bq_tables 를 읽습니다. meta_ 표는 계보에 그리지 않습니다."
```

- [ ] **Step 2: 계보를 다시 만듭니다**

Run: `py scripts/build_lineage.py`
Expected: `dashboard_js/data/table_lineage.json` 이 바뀜. `git diff --stat` 로 `pages` 에 `pages/data-ops.html`(routes `/jobs/status`·`/ops/storage`), `routes` 에 `/ops/storage`, `scripts` 에 `record_bq_snapshot.py`, `tables` 에 `meta_bq_tables`(kind meta) 가 생겼는지 봅니다. 그 밖의 줄이 바뀌었으면 멈추고 까닭을 evan 에게 알립니다(다른 세션의 변경일 수 있음).

- [ ] **Step 3: 계보 시험**

Run: `py -m pytest tests/test_lineage.py -q`
Expected: 전부 PASS. 실패하면 메시지가 가리키는 손 파일 칸(예: `no_status_ok`, `job_keys_without_tables`)을 고치고 Step 2 부터 다시. 고친 내용과 까닭을 커밋 메시지에 적습니다.

- [ ] **Step 4: 전체 시험**

Run: `py -m pytest tests -q` 그리고 `npm test`
Expected: 전부 PASS(브랜치 시작 때 이미 실패하던 시험이 있으면 이름을 적고 evan 에게 알립니다).

- [ ] **Step 5: 커밋합니다**

```bash
git add database/lineage_writes.json dashboard_js/data/table_lineage.json
git commit -m "chore(lineage): 데이터 관리 화면·/ops/storage·record_bq_snapshot·meta_bq_tables 반영

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: 검토, evan 실행 단계, 배포

**Files:** 없음

- [ ] **Step 1: 코드 검토**

superpowers:requesting-code-review 로 `origin/main..HEAD` 전체를 검토받고, 지적을 반영해 커밋합니다.

- [ ] **Step 2: evan 에게 할 일을 순서대로 알리고 허락을 받습니다** (각 단계는 evan 의 명시 허락 뒤)

1. **MySQL 에 표 만들기(evan 직접, root):** 프록시를 띄운 뒤 `migration/mysql/record_bq_snapshot.py` 의 `DDL` 을 실행합니다. 확인: `SHOW CREATE TABLE meta_bq_tables;`. Worker 의 읽기 계정(`bstats_api`)은 `bstats.*` SELECT 라 따로 권한을 줄 필요가 없습니다. 수집 계정(`bstats_loader`)은 INSERT·UPDATE·DELETE 가 있어 그대로 씁니다. 각 계정 권한은 `SHOW GRANTS FOR …` 로 확인합니다.
2. **push:** 같은 명령 줄에서 `git log origin/main..HEAD --oneline` 을 다시 보여 주고, 허락받은 마지막 sha 로 `git push origin <sha>:main`.
3. **Worker 배포(evan 직접):** `npx wrangler@4 deploy`. 배포 전 지금 운영 버전 ID 를 `~/.bstats/notes/kbo-api-rollback-version.txt` 에 적습니다. 확인: `curl -s <API>/ops/storage | py -m json.tool | head -40` — `bigquery` 는 첫 주간 실행 전이라 `[]`(빈 목록) 이거나 표가 없으면 `null`.
4. **Pages 배포:** `git status --short dashboard_js` 와 `git log origin/main..main` 을 보고 남의 변경이 없을 때 `npx --yes wrangler@4 pages deploy dashboard_js --project-name bstats --branch main`.
5. **첫 빅쿼리 현황 채우기(선택):** 다음 주간 예약 실행(화 05:47 KST)을 기다리거나, evan 이 weekly 를 손으로 실행. 실행 뒤 요약 표의 '빅쿼리 현황 기록' 이 success 인지, `/ops/storage` 의 `bigquery.tables` 가 채워졌는지 봅니다(엣지 캐시 1시간).

- [ ] **Step 3: 운영 화면 확인**

`https://bstats.pages.dev/pages/data-ops` 를 헤드리스 Edge 로 밝은·어두운 테마 캡처해 `바탕화면/bstats_미리보기/data_ops/live/` 에 두고 evan 에게 경로를 알립니다.
