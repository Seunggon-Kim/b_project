# 테이블 계보 데이터(DB 세션 몫) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 수집 작업·표·API·화면의 계보를 코드와 손 파일에서 모아 `dashboard_js/data/table_lineage.json` 하나로 만들고, 계보가 낡으면 테스트가 실패하게 합니다.

**Architecture:** 코드에서 뽑을 수 있는 것(워크플로의 스크립트·실행 시각, API 의 SQL 표 이름, 화면의 API 주소)은 `scripts/lineage_extract.py` 의 순수 함수가 뽑습니다. 뽑기 어려운 "스크립트 → 표"와 원천은 손 파일 `database/lineage_writes.json` 에 적습니다. `scripts/build_lineage.py` 가 둘을 합쳐 정해진 모양의 JSON 을 씁니다. 화면(탭)은 화면 세션이 이 JSON 으로 만듭니다.

**Tech Stack:** Python 3.13(표준 라이브러리만), pytest. 저장소 `Seunggon-Kim/b_project`.

설계서: `docs/superpowers/specs/2026-10-04-table-lineage-design.md` (결과 JSON 모양·상태 점 규칙·테스트 6개의 근거).

## Global Constraints

- 저장소는 **공개**입니다. 비밀·IP·`~/.bstats/` 내용을 넣지 않습니다.
- push 는 evan 허락 뒤. 이 계획은 데이터 파일·스크립트·테스트만 만들고 화면을 바꾸지 않습니다(`dashboard_js/data/` 에 JSON 하나만 더함).
- 결과 JSON 은 같은 입력이면 같은 출력: 시각·커밋 해시를 넣지 않고, 배열은 정렬, `json.dumps(..., ensure_ascii=False, indent=1, sort_keys=True)` + 줄 끝 `\n`, LF.
- 표준 라이브러리만 씁니다(requirements 를 늘리지 않음).
- Python 테스트: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`(현재 511 통과). JS 테스트(`npm test`, 407)는 이 계획과 무관하지만 깨지면 안 됩니다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
- 사용자에게 보이는 한국어(JSON 의 설명·일정 문구)는 습니다체, 이모지 금지.
- 작업 위치: `git -C C:/Users/김승곤/Desktop/b_project worktree add C:/tmp/b_project_lin -b feat/table-lineage-data docs/table-lineage-spec` (설계서 커밋 473623a 위). Windows, Git Bash. `python` 명령은 없고 `py` 를 씁니다.

## 설계서에서 다듬은 점(이 계획이 정함)

- **실행 기록 키는 작업마다 다를 수 있습니다.** `roster_to_d1.py` 는 daily 에서 `roster`, roster.yml 에서 `roster_pm` 으로 남습니다. 그래서 손 파일과 결과 JSON 의 스크립트 항목은 `status_key`(글자) 대신 `status_keys`(작업 이름 → 키)를 씁니다. 결과의 `jobs[].steps[].status_key` 는 그 작업의 값으로 풀어 둡니다.
- **데이터 탐색 페이지는 모든 표를 읽습니다.** 그 페이지를 "표 → 화면" 선에 넣으면 선이 30개 늘어 그림이 무너집니다. 결과 JSON 의 그 페이지에 `"explorer": true` 를 두고 `edges` 에서 뺍니다. `/db/tables`·`/db/table/:name` 주소도 표마다의 `routes` 에서 뺍니다(모든 표를 읽는 주소라 정보가 없음).
- **다른 화면이 `/db/table/<이름>` 으로 특정 표를 읽는 경우**(팀 통계의 참조 표 4개)는 그 화면 소스 파일에 글자로 적힌 표 이름을 그 화면이 읽는 표로 봅니다.
- **페이지가 싣는 `js/api.js` 의 글자는 세지 않습니다.** 그 안의 주소 틀이 모두 잡혀 페이지마다 쓰지 않는 주소가 붙습니다. `api.js` 는 페이지가 실제로 부르는 `API.<메서드>` 로만 셉니다(Task 2 구현 중 발견).
- **`reads` 에는 계산에 들어가는 다른 표만 적습니다.** 팀 이름·ID 확인 같은 찾아보기와 자기가 쓰는 표는 빼고 `note` 에 적습니다(그림의 "계산 표" 화살표가 부풀지 않게). 표의 `kind` 는 원천에서 받는 스크립트가 하나라도 쓰면 `collected`, 원천 없이 다른 표만 읽어 계산하면 `derived` 입니다(Task 3 검토에서 정함).
- **외부를 넘기는 API**(실시간 순위·일정·퓨처스)는 손 파일 `live_route_files` 에 적고, 그 주소를 쓰는 화면에 `source:kbo_live → page:…` 선을 긋습니다.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `scripts/lineage_extract.py` | 코드에서 계보 재료를 뽑는 순수 함수(파일 읽기는 `root` 를 받아 함) |
| `scripts/build_lineage.py` | 손 파일 + 뽑은 재료 → 결과 dict, `main()` 이 JSON 파일을 씀 |
| `database/lineage_writes.json` | 손 파일: 원천, 스크립트별 sources/writes/reads/status_keys, 손 작업 표, 외부 API 파일 |
| `dashboard_js/data/table_lineage.json` | 생성물(커밋). 화면 세션이 읽음 |
| `tests/test_lineage_extract.py` | 뽑기 함수 단위 시험(가짜 입력) |
| `tests/test_lineage.py` | 실제 저장소를 대상으로 한 계보 검사(설계서 테스트 1~5) |

---

### Task 1: 워크플로·스키마 뽑기

**Files:**
- Create: `scripts/lineage_extract.py`
- Test: `tests/test_lineage_extract.py`

**Interfaces:**
- Produces: `cron_to_kst(cron: str) -> str`, `parse_workflow(text: str) -> {"cron_utc": str|None, "steps": [{"name": str|None, "script": str}]}`, `schema_tables(schema_sql: str) -> set[str]`, `job_keys(text: str) -> set[str]`

- [ ] **Step 1: 실패하는 테스트**

`tests/test_lineage_extract.py`:

```python
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lineage_extract as lx  # noqa: E402


def test_cron_to_kst():
    assert lx.cron_to_kst("33 18 * * *") == "매일 03:33"
    assert lx.cron_to_kst("7 7 * * *") == "매일 16:07"
    assert lx.cron_to_kst("47 20 * * 1") == "매주 화 05:47"
    assert lx.cron_to_kst("13 4 1 * *") == "매월 1일 13:13"
    assert lx.cron_to_kst("*/5 * * * *") == "*/5 * * * *"


WF = """
on:
  schedule:
    - cron: '33 18 * * *'
jobs:
  run:
    steps:
      - name: 의존성 설치
        run: python -m pip install -r requirements.txt
      - name: PBP 수집·적재
        id: pbp
        run: python data_collection/daily_pbp_to_d1.py
      # - name: 꺼 둔 단계
      #   run: python data_collection/old.py
      - name: 결과 기록
        run: |
          python data_collection/record_job_run.py --job pbp \\
            --status ok
          python data_collection/record_job_run.py --job games --status ok
      - name: D1·MySQL 대조
        run: python -m migration.mysql.reconcile --days 3
"""


def test_parse_workflow():
    w = lx.parse_workflow(WF)
    assert w["cron_utc"] == "33 18 * * *"
    assert w["steps"] == [
        {"name": "PBP 수집·적재", "script": "data_collection/daily_pbp_to_d1.py"},
        {"name": "결과 기록", "script": "data_collection/record_job_run.py"},
        {"name": "D1·MySQL 대조", "script": "migration/mysql/reconcile.py"},
    ]


def test_job_keys():
    assert lx.job_keys(WF) == {"pbp", "games"}


def test_schema_tables():
    sql = "CREATE TABLE `games` (\n  `a` INT\n);\nCREATE TABLE `meta_job_runs` (x INT);\n"
    assert lx.schema_tables(sql) == {"games", "meta_job_runs"}
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage_extract.py -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: No module named 'lineage_extract'`

- [ ] **Step 3: 구현**

`scripts/lineage_extract.py`:

```python
# -*- coding: utf-8 -*-
"""테이블 계보의 재료를 코드에서 뽑습니다.

설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md

뽑기 쉬운 것만 여기서 뽑습니다. 수집 스크립트가 어떤 표에 쓰는지는 SQL 을
조립해 만드는 곳이 많아 기계로 뽑으면 틀리기 쉽습니다. 그건 손 파일
(database/lineage_writes.json)에 적고, 테스트가 실제 코드와 맞는지 봅니다.
"""
import re

DOW = ["일", "월", "화", "수", "목", "금", "토"]

CRON = re.compile(r"cron:\s*'([^']+)'")
STEP = re.compile(r"^\s*-\s*name:\s*(.+?)\s*$")
PY_CALL = re.compile(r"\bpython3?\s+(?:-m\s+([A-Za-z_][\w.]*)|([A-Za-z0-9_./-]+\.py))")
JOB_KEY = re.compile(r"record_job_run\.py\s+--job\s+([a-z_]+)")
TABLE = re.compile(r"CREATE TABLE `([A-Za-z0-9_]+)`")


def cron_to_kst(cron):
    """UTC cron 다섯 칸을 한국 시각 문구로 바꿉니다. 모르는 꼴이면 원문 그대로입니다.

    한국은 UTC+9 이고 서머타임이 없습니다. 9시간을 더해 날을 넘기면 요일·날짜도
    하루 밉니다(weekly 의 월 20:47 UTC 는 한국 화 05:47).
    """
    parts = cron.split()
    if len(parts) != 5:
        return cron
    mi, hr, dom, mon, dow = parts
    if not (mi.isdigit() and hr.isdigit()) or mon != "*":
        return cron
    h = int(hr) + 9
    next_day = h >= 24
    hm = "%02d:%02d" % (h % 24, int(mi))
    if dom == "*" and dow == "*":
        return "매일 " + hm
    if dom == "*" and dow.isdigit():
        return "매주 %s %s" % (DOW[(int(dow) + (1 if next_day else 0)) % 7], hm)
    if dow == "*" and dom.isdigit():
        return "매월 %d일 %s" % (int(dom) + (1 if next_day else 0), hm)
    return cron


def parse_workflow(text):
    """워크플로 YAML 글자에서 실행 시각과 (단계 이름, 스크립트) 목록을 뽑습니다.

    `python 경로.py` 와 `python -m 모듈` 을 모두 스크립트로 봅니다(모듈은 경로로
    바꿈). `pip` 은 뺍니다. 주석 줄(#)은 건너뜁니다. 같은 (단계, 스크립트)는
    한 번만 넣습니다.
    """
    m = CRON.search(text)
    steps, seen, name = [], set(), None
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        s = STEP.match(line)
        if s:
            name = s.group(1).strip().strip("'\"")
            continue
        for mod, path in PY_CALL.findall(line):
            if mod == "pip":
                continue
            script = mod.replace(".", "/") + ".py" if mod else path
            if (name, script) not in seen:
                seen.add((name, script))
                steps.append({"name": name, "script": script})
    return {"cron_utc": m.group(1) if m else None, "steps": steps}


def job_keys(text):
    """워크플로가 `record_job_run.py --job <키>` 로 남기는 실행 기록 키입니다."""
    return set(JOB_KEY.findall(text))


def schema_tables(schema_sql):
    """MySQL 스키마(migration/mysql/schema.sql)의 표 이름입니다."""
    return set(TABLE.findall(schema_sql))
```

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage_extract.py -p no:cacheprovider -q`
Expected: 4 passed.

- [ ] **Step 5: 커밋**

```bash
git add scripts/lineage_extract.py tests/test_lineage_extract.py
git commit -m "feat(lineage): 워크플로·스키마에서 계보 재료 뽑기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: API·화면 뽑기

**Files:**
- Modify: `scripts/lineage_extract.py`(끝에 함수 추가)
- Modify: `tests/test_lineage_extract.py`(끝에 시험 추가)

**Interfaces:**
- Consumes: `schema_tables` (Task 1)
- Produces:
  - `route_files(index_js: str) -> dict[str, str]` (GET 경로 → `src/routes/<파일>.js`, 인라인 핸들러는 빠짐)
  - `sql_tables(js_text: str, known: set[str]) -> set[str]`
  - `route_patterns(index_js: str) -> list[str]` (모든 GET 경로, 인라인 포함)
  - `match_route(template_path: str, patterns: list[str]) -> str|None`
  - `api_methods(api_js: str) -> dict[str, str]` (`API.<메서드>` → 주소 틀)
  - `page_sources(page_path: Path, html: str) -> list[Path]` (페이지가 `<script src>` 로 싣는 로컬 JS 파일)
  - `source_routes(text: str, patterns: list[str], methods: dict[str, str]) -> set[str]`
  - `quoted_tables(text: str, known: set[str]) -> set[str]`
  - `page_title(html: str) -> str`

- [ ] **Step 1: 실패하는 테스트(파일 끝에 붙임)**

```python
INDEX_JS = """
import { json } from './lib/respond.js';
import { standings } from './routes/standings.js';
import {
  playersSearch, playerDetail as detail,
} from './routes/players.js';
router.add('GET', '/', () => json({ ok: 1 }));
router.add('GET', '/standings', standings);
router.add('GET', '/players/search', playersSearch);
router.add('GET', '/players/:id', detail);
router.add('POST', '/admin/purge-cache', purge);
"""


def test_route_files_and_patterns():
    assert lx.route_files(INDEX_JS) == {
        "/standings": "src/routes/standings.js",
        "/players/search": "src/routes/players.js",
        "/players/:id": "src/routes/players.js",
    }
    assert lx.route_patterns(INDEX_JS) == ["/", "/standings", "/players/search", "/players/:id"]


def test_sql_tables():
    js = """
      const a = await db.prepare('SELECT * FROM players WHERE x = ?');
      const b = `SELECT g.a FROM games g JOIN \\`teams\\` t ON 1
                 LEFT JOIN "kbo_roster" r ON 1 WHERE a IN (SELECT 1 FROM nope)`;
      import { x } from './y.js';  // from comments are lower-case and ignored
    """
    assert lx.sql_tables(js, {"players", "games", "teams", "kbo_roster"}) == {
        "players", "games", "teams", "kbo_roster"}


def test_match_route():
    pats = ["/players/search", "/players/:id", "/players/:id/arsenal", "/db/table/:name"]
    assert lx.match_route("/players/${playerId}/arsenal", pats) == "/players/:id/arsenal"
    assert lx.match_route("/players/search", pats) == "/players/search"
    assert lx.match_route("/players/${id}", pats) == "/players/:id"
    assert lx.match_route("/db/table/${name}", pats) == "/db/table/:name"
    assert lx.match_route("/nowhere", pats) is None
    assert lx.match_route("/players/", pats) is None


API_JS = """
class API {
    static async getGames(season = 2025, limit = 50) {
        const response = await fetch(`${API_BASE_URL}/games?season=${season}&limit=${limit}`);
    }
    static async getPitchArsenal(playerId) {
        const response = await fetch(`${API_BASE_URL}/players/${playerId}/arsenal`);
    }
}
"""


def test_api_methods():
    assert lx.api_methods(API_JS) == {
        "getGames": "/games", "getPitchArsenal": "/players/${playerId}/arsenal"}


def test_source_routes_and_tables():
    pats = ["/games", "/players/:id/arsenal", "/db/table/:name", "/stats/seasons"]
    methods = lx.api_methods(API_JS)
    page = """
      const g = await API.getGames(2025);
      const r = await getJson(`${base}/db/table/${name}?limit=500`);
      const s = await getJson(`${base}/stats/seasons`);
      const refs = ['kbo_woba_weights_by_season', "stadium_dim", 'not_a_table'];
      const other = `${dir}/file.txt`;
    """
    assert lx.source_routes(page, pats, methods) == {"/games", "/db/table/:name", "/stats/seasons"}
    assert lx.quoted_tables(page, {"kbo_woba_weights_by_season", "stadium_dim"}) == {
        "kbo_woba_weights_by_season", "stadium_dim"}


def test_page_sources_and_title(tmp_path):
    (tmp_path / "js").mkdir()
    (tmp_path / "pages").mkdir()
    (tmp_path / "js" / "api.js").write_text("x", encoding="utf-8")
    html = ('<title> 팀 통계 | bstats </title>'
            '<script src="../js/api.js"></script>'
            '<script src="https://cdn.example/x.js"></script>'
            '<script src="../js/missing.js"></script>')
    page = tmp_path / "pages" / "team-stats.html"
    # Windows 임시 폴더는 짧은 이름(8.3)·한글 사용자 폴더 때문에 경로 표기가 갈릴 수
    # 있어 양쪽을 resolve() 로 맞춰 비교합니다.
    assert [p.resolve() for p in lx.page_sources(page, html)] == [(tmp_path / "js" / "api.js").resolve()]
    assert lx.page_title(html) == "팀 통계 | bstats"
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage_extract.py -p no:cacheprovider -q`
Expected: 새 시험들이 `AttributeError: module 'lineage_extract' has no attribute ...` 로 FAIL.

- [ ] **Step 3: 구현(파일 끝에 붙임)**

```python
IMPORT = re.compile(r"import\s*\{([^}]*)\}\s*from\s*'\./routes/([\w-]+)\.js'", re.S)
ADD = re.compile(r"router\.add\(\s*'GET'\s*,\s*'([^']+)'\s*,\s*([A-Za-z_]\w*)?")
SQL_TABLE = re.compile(r"\b(?:FROM|JOIN)\s+[`\"\\]*([A-Za-z_]\w*)")
TEMPLATE = re.compile(r"`\$\{[A-Za-z_][\w.]*\}(/[^`?'\"\s]*)")
API_CALL = re.compile(r"\bAPI\.([A-Za-z_]\w*)\(")
METHOD = re.compile(r"static\s+async\s+([A-Za-z_]\w*)\s*\(")
SCRIPT_SRC = re.compile(r"<script[^>]+src=\"([^\"]+)\"")
QUOTED = re.compile(r"['\"]([a-z][a-z0-9_]*)['\"]")
TITLE = re.compile(r"<title>\s*(.*?)\s*</title>", re.S)
VAR = re.compile(r"\$\{[^}]*\}")


def route_files(index_js):
    """GET 경로 → 그 핸들러가 있는 라우트 파일입니다. 인라인 핸들러는 뺍니다."""
    owner = {}
    for names, mod in IMPORT.findall(index_js):
        for n in names.split(","):
            n = n.strip().split(" as ")[-1].strip()
            if n:
                owner[n] = "src/routes/%s.js" % mod
    return {path: owner[h] for path, h in ADD.findall(index_js) if h in owner}


def route_patterns(index_js):
    """등록된 GET 경로 전부(등록 순서)입니다."""
    return [path for path, _ in ADD.findall(index_js)]


def sql_tables(js_text, known):
    """SQL 글자의 FROM·JOIN 뒤 표 이름 가운데 실제 표만 돌려줍니다.

    대문자 FROM·JOIN 만 봅니다. JS 의 `import … from` 과 주석의 소문자 from 을
    피하려는 것입니다. 이 저장소의 SQL 은 키워드를 대문자로 씁니다.
    """
    return {t for t in SQL_TABLE.findall(js_text) if t in known}


def match_route(template_path, patterns):
    """`/players/${id}/arsenal` 같은 화면 쪽 주소 틀을 라우트 패턴에 맞춥니다."""
    path = VAR.sub(":v", template_path).rstrip("/")
    segs = path.split("/")
    for p in patterns:
        ps = p.rstrip("/").split("/")
        if len(ps) != len(segs):
            continue
        if all(a == b or (b.startswith(":") and a) for a, b in zip(segs, ps)):
            if all(not (a == ":v" and not b.startswith(":")) for a, b in zip(segs, ps)):
                return p
    return None


def api_methods(api_js):
    """api.js 의 `static async <이름>(` 마다 그 몸통에서 처음 부르는 주소 틀입니다."""
    out = {}
    starts = [(m.group(1), m.start()) for m in METHOD.finditer(api_js)]
    for i, (name, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else len(api_js)
        t = TEMPLATE.search(api_js, start, end)
        if t:
            out[name] = t.group(1)
    return out


def page_sources(page_path, html):
    """페이지가 `<script src>` 로 싣는 로컬 JS 파일(있는 것만, 순서대로)입니다."""
    out = []
    for src in SCRIPT_SRC.findall(html):
        if "://" in src:
            continue
        f = (page_path.parent / src).resolve()
        if f.exists():
            out.append(f)
    return out


def source_routes(text, patterns, methods):
    """소스 글자가 부르는 라우트 패턴들입니다(주소 틀 + API.<메서드> 호출)."""
    found = set()
    for tpl in TEMPLATE.findall(text):
        r = match_route(tpl, patterns)
        if r:
            found.add(r)
    for name in API_CALL.findall(text):
        if name in methods:
            r = match_route(methods[name], patterns)
            if r:
                found.add(r)
    return found


def quoted_tables(text, known):
    """따옴표로 적힌 실제 표 이름들입니다(`/db/table/<이름>` 으로 읽는 화면용)."""
    return {t for t in QUOTED.findall(text) if t in known}


def page_title(html):
    m = TITLE.search(html)
    return m.group(1).strip() if m else ""
```

`match_route` 규칙: 화면 쪽의 변수 칸(`${…}` → `:v`)은 패턴의 변수 칸(`:id`)에만 맞고, 글자 칸은 같은 글자에만 맞습니다. `/players/` 처럼 끝이 비면 `/players` 로 보고, 그런 패턴이 없으면 `None` 입니다.

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage_extract.py -p no:cacheprovider -q`
Expected: 10 passed. 실패하면 함수를 고치되 시험의 기대값은 바꾸지 않습니다(기대값이 틀렸다고 판단되면 보고서에 근거와 함께 적고 멈춥니다).

- [ ] **Step 5: 실제 저장소로 확인(커밋하지 않음)**

```bash
PYTHONUTF8=1 py - <<'EOF'
import sys; from pathlib import Path
sys.path.insert(0, "scripts"); import lineage_extract as lx
R = Path(".")
known = lx.schema_tables((R/"migration/mysql/schema.sql").read_text(encoding="utf-8"))
idx = (R/"src/index.js").read_text(encoding="utf-8")
pats = lx.route_patterns(idx); files = lx.route_files(idx)
print(len(pats), "routes;", len(files), "with files")
for f in sorted(set(files.values())):
    print(f, sorted(lx.sql_tables((R/f).read_text(encoding="utf-8"), known)))
methods = lx.api_methods((R/"dashboard_js/js/api.js").read_text(encoding="utf-8"))
print("api methods", len(methods))
for p in [R/"dashboard_js/index.html", *sorted((R/"dashboard_js/pages").glob("*.html"))]:
    html = p.read_text(encoding="utf-8")
    text = html + "".join(f.read_text(encoding="utf-8") for f in lx.page_sources(p.resolve(), html))
    print(p.name, sorted(lx.source_routes(text, pats, methods)))
EOF
```

표가 하나도 안 나오는 라우트 파일(외부를 넘기는 standings·schedule·futures 등 제외)이 있거나, 화면이 API 를 하나도 안 부르는 것으로 나오면(사이트맵 같은 정적 페이지 제외) 원인을 찾아 함수를 고치고 시험을 더합니다. 출력을 보고서에 붙입니다.

- [ ] **Step 6: 커밋**

```bash
git add scripts/lineage_extract.py tests/test_lineage_extract.py
git commit -m "feat(lineage): API 의 SQL 표와 화면의 API 주소 뽑기

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 손 파일과 계보 검사

**Files:**
- Create: `database/lineage_writes.json`
- Create: `tests/test_lineage.py`

**Interfaces:**
- Consumes: `parse_workflow`, `job_keys`, `schema_tables` (Task 1)
- Produces: 손 파일 모양(Task 4 가 읽음)

```json
{
  "sources": { "<id>": { "name": "<한국어 이름>", "url": "<https://…>" } },
  "scripts": {
    "<저장소 상대 경로>": {
      "sources": ["<source id>"],
      "writes": ["<표>"],
      "reads": ["<표>"],
      "status_keys": { "<daily|roster|weekly|monthly>": "<meta_job_runs.job>" },
      "note": "<선택: 한 줄 설명>"
    }
  },
  "manual_tables": { "<표>": "<왜 손으로 채우는지 한 줄>" },
  "live_route_files": ["src/routes/standings.js"]
}
```

- [ ] **Step 1: 실패하는 테스트**

`tests/test_lineage.py`:

```python
# -*- coding: utf-8 -*-
"""계보 손 파일이 실제 코드와 맞는지 봅니다(설계서 테스트 1~4).

새 워크플로 단계를 더하고 계보를 잊거나, 어떤 작업도 쓰지 않는 표가 생기면
여기서 실패합니다. 2026-10-03 팀 순위표가 한 번 채운 뒤 한 달 넘게 멈춰 있던
일을 다시 놓치지 않으려는 것입니다.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import lineage_extract as lx  # noqa: E402

WORKFLOWS = ["daily", "roster", "weekly", "monthly"]
HAND = json.loads((ROOT / "database" / "lineage_writes.json").read_text(encoding="utf-8"))
KNOWN = lx.schema_tables((ROOT / "migration" / "mysql" / "schema.sql").read_text(encoding="utf-8"))


def wf_text(name):
    return (ROOT / ".github" / "workflows" / (name + ".yml")).read_text(encoding="utf-8")


def test_워크플로가_부르는_스크립트가_손_파일에_다_있습니다():
    missing = []
    for w in WORKFLOWS:
        for s in lx.parse_workflow(wf_text(w))["steps"]:
            if s["script"] not in HAND["scripts"]:
                missing.append("%s: %s" % (w, s["script"]))
    assert not missing, "database/lineage_writes.json 에 없는 스크립트: %s" % missing


def test_손_파일의_표_이름이_실제_표입니다():
    bad = set()
    for path, s in HAND["scripts"].items():
        bad |= {t for t in s.get("writes", []) + s.get("reads", []) if t not in KNOWN}
    bad |= {t for t in HAND.get("manual_tables", {}) if t not in KNOWN}
    assert not bad, "schema.sql 에 없는 표: %s" % sorted(bad)


def test_어떤_작업도_쓰지_않는_표가_없습니다():
    written = set()
    for s in HAND["scripts"].values():
        written |= set(s.get("writes", []))
    orphans = sorted(t for t in KNOWN
                     if not t.startswith("meta_")
                     and t not in written and t not in HAND.get("manual_tables", {}))
    assert not orphans, (
        "쓰는 스크립트도 손 작업 설명도 없는 표: %s\n"
        "수집 작업이 쓰면 scripts 의 writes 에, 손으로 채운 표면 manual_tables 에 이유와 함께 적으십시오."
        % orphans)


def test_실행_기록_키가_워크플로에_있습니다():
    keys = set()
    for w in WORKFLOWS:
        keys |= lx.job_keys(wf_text(w))
    bad = sorted({k for s in HAND["scripts"].values() for k in s.get("status_keys", {}).values()} - keys)
    assert not bad, "record_job_run.py --job 에 없는 키: %s" % bad


def test_원천_id_와_외부_API_파일이_있습니다():
    ids = set(HAND["sources"])
    bad = sorted({sid for s in HAND["scripts"].values() for sid in s.get("sources", [])} - ids)
    assert not bad, "sources 에 정의되지 않은 원천: %s" % bad
    for f in HAND.get("live_route_files", []):
        assert (ROOT / f).exists(), f
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage.py -p no:cacheprovider -q`
Expected: `FileNotFoundError: … lineage_writes.json`

- [ ] **Step 3: 손 파일 쓰기 — 스크립트마다 코드를 읽고 확인**

아래 초안에서 시작하되, **항목마다 그 스크립트를 열어 실제로 쓰는 표(INSERT·UPSERT·`build_upserts("표", …)`·`sink.upsert("표", …)`·`refresh_count("표")`)와 읽는 표를 확인**하고 고칩니다. 확인 방법 예: `grep -nE "INSERT|upsert|build_upserts|build_inserts|refresh_count|CREATE TABLE|FROM " <스크립트>`. 원천 URL 은 스크립트 안의 주소에서 가져옵니다(없으면 사이트 첫 화면 주소). 초안과 다르게 고친 항목은 보고서에 근거(파일:줄)와 함께 적습니다.

- 표를 직접 쓰지 않는 거들기 스크립트는 `"writes": []` 와 `note` 를 둡니다: `record_job_run.py`(실행 기록, meta 표), `migration/mysql/reconcile.py`(대조), `migration/mysql/mysql_to_sqlite.py`(계산용 내려받기), `migration/d1_to_sqlite.py`, `migration/sqlite_to_d1.py`(계산 결과 올리기), `migration/export_csv.py`, `park_factors/truncated.py`(계산용 임시 표만 만듦), `data_collection/official_stats_http.py`(CSV 만 받음, 적재는 csv_to_d1).
- weekly 계산 스크립트는 로컬 SQLite 에서 계산하고 `sqlite_to_d1.py` 가 올립니다. 계보에서는 **계산한 스크립트가 그 표를 쓴다**고 적습니다(`migration/sqlite_to_d1.py` 의 `DERIVED_TABLES` 와 맞는지 확인).
- monthly 의 `player_info_scraper.py`·`heal_player_photos.py` 도 같은 방식입니다(로컬 SQLite 에서 `players` 를 고치고 `sqlite_to_d1.py` 가 올림 — 실제로 그런지 확인).

초안:

```json
{
  "sources": {
    "naver_relay": { "name": "네이버 문자중계", "url": "https://sports.naver.com/kbaseball/" },
    "kbo_record": { "name": "KBO 기록실", "url": "https://www.koreabaseball.com/Record/" },
    "kbo_roster": { "name": "KBO 1군 등록 현황", "url": "https://www.koreabaseball.com/Player/Register.aspx" },
    "kbo_player_search": { "name": "KBO 선수 검색", "url": "https://www.koreabaseball.com/Player/Search.aspx" },
    "kbo_futures": { "name": "KBO 퓨처스리그", "url": "https://www.koreabaseball.com/Futures/" },
    "kbo_live": { "name": "KBO 실시간(순위·일정)", "url": "https://www.koreabaseball.com/" }
  },
  "scripts": {
    "data_collection/daily_pbp_to_d1.py": { "sources": ["naver_relay"], "writes": ["play_by_play"], "reads": [], "status_keys": { "daily": "pbp" } },
    "data_collection/daily_games_to_d1.py": { "sources": [], "writes": ["games"], "reads": ["play_by_play"], "status_keys": { "daily": "games" }, "note": "그날 문자중계에서 경기 결과를 만듭니다." },
    "data_collection/futures_to_d1.py": { "sources": ["kbo_futures"], "writes": ["futures_games"], "reads": [], "status_keys": { "daily": "futures" } },
    "data_collection/team_ranks.py": { "sources": ["kbo_record"], "writes": ["team_season_rank"], "reads": [], "status_keys": { "daily": "team_ranks" } },
    "data_collection/official_stats_http.py": { "sources": ["kbo_record"], "writes": [], "reads": [], "note": "공식 기록을 CSV 로 받습니다. 표에는 csv_to_d1.py 가 넣습니다." },
    "data_collection/csv_to_d1.py": { "sources": [], "writes": ["kbo_official_batter_stats", "kbo_official_pitcher_stats"], "reads": [], "status_keys": { "daily": "official_stats" } },
    "data_collection/roster_to_d1.py": { "sources": ["kbo_roster"], "writes": ["kbo_roster", "kbo_roster_moves"], "reads": [], "status_keys": { "daily": "roster", "roster": "roster_pm" } },
    "data_collection/sync_players_from_roster.py": { "sources": [], "writes": ["players"], "reads": ["kbo_roster"], "note": "명단의 소속·등번호를 players 에 반영합니다." },
    "data_collection/add_new_players.py": { "sources": ["kbo_player_search"], "writes": ["players"], "reads": ["kbo_roster"], "status_keys": { "daily": "add_new_players", "roster": "add_new_players" } },
    "data_collection/futures_records.py": { "sources": ["kbo_futures"], "writes": ["futures_season_stats"], "reads": [] },
    "data_collection/player_info_scraper.py": { "sources": ["kbo_player_search"], "writes": ["players"], "reads": [], "status_keys": { "monthly": "player_info" } },
    "data_collection/heal_player_photos.py": { "sources": [], "writes": ["players"], "reads": [], "note": "선수 사진 주소를 고칩니다." },
    "data_collection/record_job_run.py": { "sources": [], "writes": [], "reads": [], "note": "작업 실행 기록(meta_job_runs)만 남깁니다." },
    "migration/mysql/reconcile.py": { "sources": [], "writes": [], "reads": [], "status_keys": { "daily": "reconcile" }, "note": "D1 과 MySQL 을 견줍니다." },
    "migration/mysql/mysql_to_sqlite.py": { "sources": [], "writes": [], "reads": [], "note": "주간 계산용으로 MySQL 을 내려받습니다." },
    "migration/d1_to_sqlite.py": { "sources": [], "writes": [], "reads": [], "note": "월간 작업용으로 D1 을 내려받습니다." },
    "migration/sqlite_to_d1.py": { "sources": [], "writes": [], "reads": [], "note": "계산 결과 표를 D1·MySQL 에 올립니다." },
    "migration/export_csv.py": { "sources": [], "writes": [], "reads": [], "note": "전체 내려받기 CSV 를 만듭니다." },
    "park_factors/truncated.py": { "sources": [], "writes": [], "reads": ["games", "play_by_play"], "note": "중간에 끊긴 경기를 가려 계산에서 뺍니다(계산용 임시 표)." },
    "park_factors/compute_self_park_factors.py": { "sources": [], "writes": ["self_park_factor"], "reads": ["play_by_play", "games"], "status_keys": { "weekly": "park_factors" } },
    "park_factors/build_woba_weights.py": { "sources": [], "writes": ["kbo_woba_weights_by_season"], "reads": ["play_by_play"], "status_keys": { "weekly": "park_factors" } },
    "park_factors/build_wrc_plus.py": { "sources": [], "writes": ["wrc_plus_comparison", "weighted_pf_by_batter_season"], "reads": ["play_by_play", "self_park_factor", "kbo_woba_weights_by_season"], "status_keys": { "weekly": "park_factors" } },
    "park_factors/build_re24_run_values.py": { "sources": [], "writes": ["re24_matrix_by_season", "kbo_run_values_by_season"], "reads": ["play_by_play"], "status_keys": { "weekly": "park_factors" } }
  },
  "manual_tables": {
    "franchises": "구단 계보표입니다. migration/build_franchises.py 로 한 번 만들었습니다.",
    "team_seasons": "시즌별 팀 표기명입니다. 손으로 관리합니다.",
    "teams": "팀 목록입니다. 손으로 관리합니다.",
    "futures_teams": "퓨처스 팀 목록입니다. 손으로 관리합니다.",
    "stadium_dim": "구장 정보입니다. 손으로 관리합니다.",
    "team_stadium_by_season": "시즌별 홈구장입니다. 손으로 관리합니다.",
    "team_logos": "팀 로고 이미지입니다. 손으로 넣었습니다.",
    "statiz_park_factor": "STATIZ 파크팩터 참고값입니다. 한 번 받아 두었습니다.",
    "statiz_yearly_constants": "STATIZ 연도별 상수 참고값입니다. 한 번 받아 두었습니다.",
    "korean_series_champion": "한국시리즈 우승 기록입니다. 손으로 관리합니다.",
    "game_team_stats": "경기별 팀 기록입니다. 예전 적재 뒤 갱신하는 작업이 없습니다."
  },
  "live_route_files": [
    "src/routes/standings.js", "src/routes/schedule.js", "src/routes/futures.js",
    "src/routes/futuresplayer.js", "src/routes/futuresrecord.js"
  ]
}
```

`manual_tables` 의 설명은 확인한 사실로 바꿉니다(예: 어떤 스크립트로 처음 채웠는지 `git log --format=%s -- <스크립트>` 나 `grep -rn "<표>" migration data_collection` 으로 찾음). `team_season_rank` 의 1982~2025 는 한 번 받은 값이지만 daily 가 올 시즌을 쓰므로 `writes` 쪽에 둡니다. `live_route_files` 는 `src/routes/` 에서 외부 사이트를 `fetch` 하는 파일을 확인해 맞춥니다(DB 도 읽는 파일이면 그대로 두어도 됨 — 표는 SQL 에서 따로 잡힘).

- [ ] **Step 4: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage.py -p no:cacheprovider -q`
Expected: 5 passed. 실패하면 손 파일을 사실에 맞게 고칩니다(테스트를 느슨하게 바꾸지 않습니다).

- [ ] **Step 5: 커밋**

```bash
git add database/lineage_writes.json tests/test_lineage.py
git commit -m "feat(lineage): 스크립트→표 손 파일과 계보 검사(고아 표·빠진 스크립트·기록 키)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: 결과 JSON 만들기

**Files:**
- Create: `scripts/build_lineage.py`
- Create: `dashboard_js/data/table_lineage.json`(생성물)
- Modify: `tests/test_lineage.py`(끝에 시험 추가)

**Interfaces:**
- Consumes: Task 1·2 의 함수 전부, Task 3 의 손 파일
- Produces: `build(root: Path) -> dict`(설계서 3절 모양 + 이 계획의 다듬은 점), `main()`(결과 파일을 씀), `STALE_HOURS`

- [ ] **Step 1: 실패하는 테스트(파일 끝에 붙임)**

```python
import build_lineage as bl  # noqa: E402

OUT = ROOT / "dashboard_js" / "data" / "table_lineage.json"


def test_결과_파일이_지금_코드로_만든_것과_같습니다():
    want = bl.build(ROOT)
    got = json.loads(OUT.read_text(encoding="utf-8"))
    assert got == want, "py scripts/build_lineage.py 로 다시 만드십시오."


def test_결과_모양():
    d = bl.build(ROOT)
    assert d["version"] == 1
    assert [j["id"] for j in d["jobs"]] == ["daily", "monthly", "roster", "weekly"]
    daily = next(j for j in d["jobs"] if j["id"] == "daily")
    assert daily["schedule_kst"] == "매일 03:33" and daily["stale_hours"] == 36
    tr = next(t for t in d["tables"] if t["name"] == "team_season_rank")
    assert tr["kind"] == "collected" and tr["written_by"] == ["data_collection/team_ranks.py"]
    for name in ("games", "players", "play_by_play"):
        assert next(t for t in d["tables"] if t["name"] == name)["kind"] == "collected", name
    wrc = next(t for t in d["tables"] if t["name"] == "wrc_plus_comparison")
    assert wrc["kind"] == "derived" and "play_by_play" in wrc["derived_from"]
    assert {"from": "job:daily", "to": "table:team_season_rank"} in d["edges"]
    assert {"from": "table:play_by_play", "to": "table:wrc_plus_comparison"} in d["edges"]
    # api.js 를 싣기만 하고 부르지 않는 주소가 페이지에 붙지 않습니다.
    stats = next(p for p in d["pages"] if p["path"] == "pages/player-stats.html")
    assert "/db/tables" not in stats["routes"] and "/jobs/status" not in stats["routes"]
    explorer = next(p for p in d["pages"] if p["path"] == "pages/database-explorer.html")
    assert explorer["explorer"] is True
    assert not any(e["to"] == "page:pages/database-explorer.html" for e in d["edges"])
    assert all(t["kind"] == "meta" for t in d["tables"] if t["name"].startswith("meta_"))
    assert not any(e["to"].startswith("table:meta_") or e["from"].startswith("table:meta_")
                   for e in d["edges"])
    # 정렬·결정성
    assert d["edges"] == sorted(d["edges"], key=lambda e: (e["from"], e["to"]))
    assert bl.build(ROOT) == d
```

- [ ] **Step 2: 실패 확인**

Run: `PYTHONUTF8=1 py -m pytest tests/test_lineage.py -p no:cacheprovider -q`
Expected: `ModuleNotFoundError: No module named 'build_lineage'`

- [ ] **Step 3: 구현**

`scripts/build_lineage.py`:

```python
# -*- coding: utf-8 -*-
"""테이블 계보 JSON 을 만듭니다.

    py scripts/build_lineage.py

손 파일(database/lineage_writes.json)과 코드에서 뽑은 재료를 합쳐
dashboard_js/data/table_lineage.json 을 씁니다. 데이터 탐색 페이지의
"테이블 계보" 탭이 이 파일을 읽습니다.

작업·표·API·화면을 바꾸면 손 파일을 고치고 이 스크립트를 다시 돌립니다.
잊으면 tests/test_lineage.py 가 실패합니다.
설계: docs/superpowers/specs/2026-10-04-table-lineage-design.md
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import lineage_extract as lx  # noqa: E402

ROOT = HERE.parent
WORKFLOWS = ["daily", "roster", "weekly", "monthly"]
STALE_HOURS = {"daily": 36, "roster": 36, "weekly": 8 * 24, "monthly": 35 * 24}
EXPLORER_PAGE = "pages/database-explorer.html"
ALL_TABLE_ROUTE_FILES = {"src/routes/dbexplorer.js"}
OUT = ROOT / "dashboard_js" / "data" / "table_lineage.json"


def _read(root, rel):
    return (root / rel).read_text(encoding="utf-8")


def _pages(root):
    base = root / "dashboard_js"
    return [base / "index.html", *sorted((base / "pages").glob("*.html"))]


def build(root=ROOT):
    root = Path(root)
    hand = json.loads(_read(root, "database/lineage_writes.json"))
    known = lx.schema_tables(_read(root, "migration/mysql/schema.sql"))
    coldict = json.loads(_read(root, "database/column_descriptions.json")).get("tables", {})
    visible = {t for t in known if not t.startswith("meta_")}

    # 작업 → 스크립트
    jobs, script_jobs = [], {}
    for w in WORKFLOWS:
        wf = lx.parse_workflow(_read(root, ".github/workflows/%s.yml" % w))
        steps = []
        for s in wf["steps"]:
            keys = hand["scripts"].get(s["script"], {}).get("status_keys", {})
            steps.append({"name": s["name"], "script": s["script"], "status_key": keys.get(w)})
            script_jobs.setdefault(s["script"], set()).add(w)
        jobs.append({
            "id": w, "workflow": w + ".yml", "cron_utc": wf["cron_utc"],
            "schedule_kst": lx.cron_to_kst(wf["cron_utc"]) if wf["cron_utc"] else None,
            "stale_hours": STALE_HOURS[w], "steps": steps,
        })

    scripts = []
    for path in sorted(hand["scripts"]):
        s = hand["scripts"][path]
        scripts.append({
            "path": path, "jobs": sorted(script_jobs.get(path, [])),
            "sources": sorted(s.get("sources", [])), "writes": sorted(s.get("writes", [])),
            "reads": sorted(s.get("reads", [])), "status_keys": s.get("status_keys", {}),
            "note": s.get("note"),
        })

    # API 주소 → 표
    index_js = _read(root, "src/index.js")
    patterns = lx.route_patterns(index_js)
    files = lx.route_files(index_js)
    live_files = set(hand.get("live_route_files", []))
    route_tables, all_routes, live_routes = {}, set(), set()
    for path, f in files.items():
        if f in ALL_TABLE_ROUTE_FILES:
            all_routes.add(path)
            route_tables[path] = set(visible)
        else:
            route_tables[path] = lx.sql_tables(_read(root, f), visible)
        if f in live_files:
            live_routes.add(path)

    # 화면 → API 주소, 화면이 /db/table/<이름> 으로 읽는 표
    methods = lx.api_methods(_read(root, "dashboard_js/js/api.js"))
    api_js = (root / "dashboard_js" / "js" / "api.js").resolve()
    pages, page_routes, page_db = [], {}, {}
    for p in _pages(root):
        html = p.read_text(encoding="utf-8")
        # api.js 글자는 넣지 않습니다. 그 안의 주소 틀이 모두 잡혀, api.js 를
        # 싣는 페이지마다 쓰지도 않는 주소 20여 개가 붙습니다. api.js 는
        # 페이지가 실제로 부르는 API.<메서드> 로만 셉니다.
        text = html + "".join(f.read_text(encoding="utf-8")
                              for f in lx.page_sources(p.resolve(), html)
                              if f.resolve() != api_js)
        rel = p.relative_to(root / "dashboard_js").as_posix()
        routes = lx.source_routes(text, patterns, methods)
        page_routes[rel] = routes
        if "/db/table/:name" in routes and rel != EXPLORER_PAGE:
            page_db[rel] = lx.quoted_tables(text, visible)
        pages.append({"path": rel, "title": lx.page_title(html), "routes": sorted(routes),
                      "explorer": rel == EXPLORER_PAGE})

    routes = []
    for path in sorted(route_tables):
        routes.append({
            "path": path, "file": files[path], "tables": sorted(route_tables[path]),
            "reads_all_tables": path in all_routes, "live": path in live_routes,
            "pages": sorted(p for p, rs in page_routes.items() if path in rs),
        })

    # 표
    tables = []
    for t in sorted(known):
        writers = sorted(p for p, s in hand["scripts"].items() if t in s.get("writes", []))
        derived = sorted({r for p in writers for r in hand["scripts"][p].get("reads", [])} - {t})
        t_routes = sorted(r["path"] for r in routes
                          if t in r["tables"] and not r["reads_all_tables"])
        t_pages = {p for r in routes if r["path"] in t_routes for p in r["pages"]}
        t_pages |= {p for p, ts in page_db.items() if t in ts}
        t_pages.discard(EXPLORER_PAGE)
        # 원천에서 받아 오는 스크립트가 하나라도 쓰면 "받아 온 표"입니다. players 는
        # 명단(kbo_roster)에서 소속을 고치기도 하지만 기본은 KBO 선수 페이지에서
        # 받습니다. 원천 없이 다른 표만 읽어 계산하는 표가 "계산 표"입니다.
        collects = any(hand["scripts"][p].get("sources") for p in writers)
        if t.startswith("meta_"):
            kind = "meta"
        elif not writers and t in hand.get("manual_tables", {}):
            kind = "manual"
        elif derived and not collects:
            kind = "derived"
        else:
            kind = "collected"
        meta = coldict.get(t, {})
        tables.append({
            "name": t, "kind": kind, "category": meta.get("category"),
            "desc": meta.get("table_desc"),
            "written_by": writers, "derived_from": derived, "routes": t_routes,
            "pages": sorted(t_pages), "manual_note": hand.get("manual_tables", {}).get(t),
        })

    # 그림의 선(4칸)
    edges = set()
    by_path = {s["path"]: s for s in scripts}
    for j in jobs:
        for step in j["steps"]:
            s = by_path.get(step["script"], {})
            for src in s.get("sources", []):
                edges.add(("source:" + src, "job:" + j["id"]))
            for t in s.get("writes", []):
                if not t.startswith("meta_"):
                    edges.add(("job:" + j["id"], "table:" + t))
    for t in tables:
        if t["kind"] == "meta":
            continue
        for src in t["derived_from"]:
            if not src.startswith("meta_"):
                edges.add(("table:" + src, "table:" + t["name"]))
        for p in t["pages"]:
            edges.add(("table:" + t["name"], "page:" + p))
    for r in routes:
        if r["live"]:
            for p in r["pages"]:
                if p != EXPLORER_PAGE:
                    edges.add(("source:kbo_live", "page:" + p))

    sources = [{"id": k, "name": v["name"], "url": v.get("url")}
               for k, v in sorted(hand["sources"].items())]
    return {
        "version": 1,
        "sources": sources,
        "jobs": sorted(jobs, key=lambda j: j["id"]),
        "scripts": scripts,
        "tables": tables,
        "routes": routes,
        "pages": sorted(pages, key=lambda p: p["path"]),
        "edges": [{"from": a, "to": b} for a, b in sorted(edges)],
    }


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True) + "\n"


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(dumps(build(ROOT)), encoding="utf-8", newline="\n")
    print("썼습니다: %s" % OUT.relative_to(ROOT).as_posix())
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 결과 파일 만들기**

Run: `PYTHONUTF8=1 py scripts/build_lineage.py`
Expected: `썼습니다: dashboard_js/data/table_lineage.json`

만든 파일을 열어 눈으로 확인합니다(보고서에 요약을 적음): 작업 4개·실행 시각 문구, `kind` 별 표 수, 표마다 `pages` 가 비어 있지 않은지(비어 있으면 그 표를 읽는 화면이 정말 없는지 확인), `edges` 수. 어떤 표의 `pages` 가 비었고 실제로 화면이 쓰는 표라면 뽑기 함수의 빈틈이므로 Task 2 함수를 고치고 시험을 더합니다.

- [ ] **Step 5: 통과 확인**

Run: `PYTHONUTF8=1 py -m pytest tests -p no:cacheprovider -q`
Expected: 전부 통과(511 + 새 시험).

- [ ] **Step 6: 커밋**

```bash
git add scripts/build_lineage.py dashboard_js/data/table_lineage.json tests/test_lineage.py
git commit -m "feat(lineage): 계보 JSON(dashboard_js/data/table_lineage.json)과 재생성 검사

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

## 끝난 뒤(컨트롤러)

- 화면 세션에 결과 JSON 경로와 모양(설계서 3절 + 이 계획의 다듬은 점: `status_keys`, `explorer`, `reads_all_tables`, `live`)을 보냅니다.
- evan 허락을 받아 main 에 push 합니다(데이터 파일·스크립트·테스트만, 화면 변화 없음).
