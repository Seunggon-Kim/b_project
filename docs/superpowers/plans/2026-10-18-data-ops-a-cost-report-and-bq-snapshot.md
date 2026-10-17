# 데이터 관리 A: 비공개 비용 보고서와 빅쿼리 스냅샷 스크립트 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 계보 결과를 바꾸지 않는 부분을 먼저 만듭니다. evan PC 에서 손으로 돌리는 비용 보고서와, 주간 빅쿼리 복사 결과를 MySQL `meta_bq_tables` 에 남길 준비(복사 결과 JSON + 기록 스크립트)입니다.

**Architecture:** 비용 보고서는 `scripts/ops/` 아래 네 모듈입니다. 결제 집계(`cost_billing.py`), Cloudflare 집계(`cost_cloudflare.py`), HTML·SVG 그리기(`cost_render.py`), 실행(`cost_report.py`)으로 나눕니다. 셋은 순수 함수라 가짜 응답으로 시험합니다. 빅쿼리 쪽은 기존 `sqlite_to_bigquery.py` 에 `--result-json` 선택 인자를 더하고, 새 `record_bq_snapshot.py` 가 그 JSON 을 `meta_bq_tables` 에 씁니다. 워크플로 연결과 `schema.sql` 반영은 계획 B 입니다.

**Tech Stack:** Python 3.13, pytest, google-cloud-bigquery, requests(또는 urllib), PyMySQL(기존 `mysql_sink.mirror`), 헤드리스 Edge(PNG).

설계: `docs/superpowers/specs/2026-10-18-data-ops-tab-design.md` (§4-1, §4-2, §6, §7, §8).
미리보기 참고: `docs/superpowers/plans/assets/2026-10-18-data-ops/cost_report_mock_template.html`, `cost_report_mock_make.py`(예시 데이터로 그린 3차안. 화면 모양·툴팁 문구의 원본입니다).

## Global Constraints

- 사용자에게 보이는 한국어는 `습니다/합니다/입니다` 체. 이모지 금지. 툴팁 첫 줄 굵게·둘째 보통·셋째부터 흐림.
- koreabaseball.com·KBO 이미지 서버는 코드·시험·손 실행 어디서도 부르지 않습니다.
- 비밀값(토큰·결제 계정 ID)은 코드·시험·커밋에 넣지 않습니다. `~/.bstats/` 파일에서 읽습니다.
- `gcloud auth application-default login` 은 쓰지 않습니다. gcloud 는 매번 `--configuration=bstats`.
- 이 계획의 어떤 커밋도 `dashboard_js/data/table_lineage.json`·`scripts/build_lineage.py`·`database/lineage_writes.json`·`dashboard_js/pages/database-explorer.html`·`.github/workflows/*`·`migration/mysql/schema.sql` 을 고치지 않습니다.
- 끝에 `py -m pytest tests/test_lineage.py -q` 가 그대로 통과해야 합니다(계보 결과가 바뀌지 않았다는 증거).
- 같은 main 을 여러 세션이 씁니다. 작업은 worktree 브랜치에서 하고 push·병합은 evan 허락 뒤에만. push 직전 `git log origin/main..HEAD --oneline` 을 다시 보여 주고 허락받은 sha 만 올립니다.
- DB 쓰기(테이블 만들기 포함)·GCP 설정 변경·배포는 evan 허락 뒤. 이 계획은 MySQL 에 쓰지 않습니다(기록 스크립트는 가짜 연결로만 시험).
- 비용 보고서 출력 폴더: `바탕화면/bstats_비용보고/<YYYY-MM-DD>/`. 바탕화면 바로 아래에 파일을 두지 않습니다.
- 커밋 메시지 끝: `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`

## 작업 폴더

```bash
cd C:/Users/김승곤/Desktop/b_project
git fetch origin
git worktree add C:/tmp/b_project_opsA -b feat/data-ops-a origin/main
cd C:/tmp/b_project_opsA
```

설계·계획 커밋(`docs/data-ops-spec` 브랜치)은 계획 B 와 함께 병합합니다. 이 브랜치는 코드만 담습니다.

## 파일 구조

| 파일 | 책임 |
|---|---|
| `migration/mysql/sqlite_to_bigquery.py` (수정) | 표마다 빅쿼리 용량도 받고, `--result-json` 으로 결과를 파일에 씀, `meta_bq_tables` 는 복사하지 않음 |
| `migration/mysql/record_bq_snapshot.py` (새) | 결과 JSON → `meta_bq_tables` 쓸 행 계산(순수) + MySQL 쓰기 |
| `scripts/ops/__init__.py` (새, 빈 파일) | 패키지 |
| `scripts/ops/cost_billing.py` (새) | 결제 내보내기 질의 글자 + 행 → 보고서 숫자(순수) |
| `scripts/ops/cost_cloudflare.py` (새) | GraphQL 질의 글자 + 응답 → 일별 값(순수) |
| `scripts/ops/cost_render.py` (새) | 숫자 → HTML(인라인 SVG, 툴팁) |
| `scripts/ops/cost_report_template.html` (새) | 보고서 틀(미리보기 3차안에서 목업 띠·#demo 만 뺀 것) |
| `scripts/ops/cost_report.py` (새) | 실행: 입력 파일 읽기, 질의, 그리기, PNG |
| `tests/test_sqlite_to_bigquery.py` (수정) | 결과 JSON·용량·제외 시험 |
| `tests/test_record_bq_snapshot.py` (새) | |
| `tests/test_cost_billing.py`, `tests/test_cost_cloudflare.py`, `tests/test_cost_render.py`, `tests/test_cost_report.py` (새) | |

---

### Task 1: 빅쿼리 복사 결과 JSON 과 용량

**Files:**
- Modify: `migration/mysql/sqlite_to_bigquery.py` (`Result` 정의 약 136행, `plan()` 약 379행, `load_table()` 약 490행, `copy_tables()` 약 510행, `main()` 약 610행)
- Test: `tests/test_sqlite_to_bigquery.py`

**Interfaces:**
- Produces:
  - `Result = namedtuple("Result", "table source rows seconds error bytes", defaults=(None,))` — `bytes` 는 빅쿼리 표 `num_bytes`(int) 또는 실패·dry-run 이면 `None`.
  - `load_table(...) -> tuple[int, int]` — `(num_rows, num_bytes)`.
  - `SNAPSHOT_TABLE = "meta_bq_tables"` — `plan()` 이 이 표를 복사 목록에서 뺍니다(건너뜀 까닭 "빅쿼리 현황 표라 복사하지 않습니다").
  - `write_result_json(path, results, tried_at, mysql_tables) -> None` — `tried_at` 은 aware datetime, `mysql_tables` 는 MySQL 표 이름들(`specs` dict 를 그대로 넘겨도 됨). 파일 모양:
    `{"tried_at": "YYYY-MM-DD HH:MM", "tables": [{"name", "source", "rows", "bytes", "error"}], "mysql_tables": [표 이름…]}`
    `mysql_tables` 는 MySQL 에 있는 표 전부(복사 제외한 `meta_bq_tables` 포함)입니다. 기록 스크립트가 "MySQL 에 없는 표 줄 지우기"에 씁니다.
  - CLI: `--result-json PATH` (dry-run 이면 쓰지 않음).

- [ ] **Step 1: 실패하는 시험을 씁니다**

`tests/test_sqlite_to_bigquery.py` 의 `FakeTable` 과 `FakeClient.get_table` 을 용량을 주게 바꾸고 시험을 더합니다.

```python
class FakeTable:
    def __init__(self, num_rows, num_bytes=None):
        self.num_rows = num_rows
        self.num_bytes = num_rows * 100 if num_bytes is None else num_bytes
        self.description = None
```

(`FakeClient.get_table` 은 그대로 `FakeTable(self.loaded[table_id] + self.rows_delta)` 를 돌려줍니다.)

파일 끝에 더합니다.

```python
def test_복사_결과에_빅쿼리_용량을_담습니다(tmp_path):
    sq, specs, my = two_table_db(tmp_path)
    res = m.copy_tables(sq, my, specs, ALL3, FakeClient(), tmp_path)
    assert [(r.table, r.rows, r.bytes) for r in res] == [
        ("mixed", 5, 500), ("players", 3, 300), ("teams", 2, 200)]


def test_실패한_표는_용량이_없습니다(tmp_path):
    sq, specs, my = two_table_db(tmp_path)
    res = m.copy_tables(sq, my, specs, ALL3, FakeClient(fail={"mixed"}), tmp_path)
    assert res[0].error and res[0].bytes is None


def test_빅쿼리_현황_표는_복사하지_않습니다():
    specs = {"teams": [], m.SNAPSHOT_TABLE: []}
    copy, skipped = m.plan(specs, set())
    assert copy == [("teams", "mysql")]
    assert skipped == [(m.SNAPSHOT_TABLE, "빅쿼리 현황 표라 복사하지 않습니다")]


def test_main_은_결과_JSON_을_씁니다(tmp_path, monkeypatch):
    out = tmp_path / "bq_result.json"
    code, _, _ = run_main(tmp_path, monkeypatch, FakeClient(fail={"teams"}),
                          ["--result-json", str(out)])
    assert code == 1
    data = json.loads(out.read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", data["tried_at"])
    assert sorted(data["mysql_tables"]) == ["mixed", "players", "teams"]
    by = {t["name"]: t for t in data["tables"]}
    assert by["players"] == {"name": "players", "source": "mysql", "rows": 3,
                             "bytes": 300, "error": None}
    assert by["teams"]["error"] and by["teams"]["bytes"] is None


def test_dry_run_은_결과_JSON_을_쓰지_않습니다(tmp_path, monkeypatch):
    out = tmp_path / "bq_result.json"
    run_main(tmp_path, monkeypatch, FakeClient(), ["--dry-run", "--result-json", str(out)])
    assert not out.exists()
```

파일 맨 위 import 에 `import json` 을 더합니다.

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_sqlite_to_bigquery.py -q -k "용량 or 현황 or JSON"`
Expected: FAIL (`Result` 에 `bytes` 없음, `SNAPSHOT_TABLE` 없음, `--result-json` 모르는 인자)

- [ ] **Step 3: 구현합니다**

`Result` 를 바꿉니다.

```python
# bytes 는 뒤에 더한 칸이라 기본값을 둡니다(칸 5개로 만드는 기존 코드·시험이 그대로 돕니다).
Result = namedtuple("Result", "table source rows seconds error bytes", defaults=(None,))

# 빅쿼리 현황을 적는 MySQL 표입니다(record_bq_snapshot.py 가 씀). 복사하면
# 지난주 스냅샷이 다시 빅쿼리로 가므로 뺍니다.
SNAPSHOT_TABLE = "meta_bq_tables"
```

`plan()` 의 반복문 첫 줄에 더합니다.

```python
    for t in names:
        if t == SNAPSHOT_TABLE:
            skipped.append((t, "빅쿼리 현황 표라 복사하지 않습니다"))
        elif t not in specs:
```

(이어지는 `elif t in local and …` / `else` 는 그대로.)

`load_table()` 의 마지막 줄을 바꾸고 독스트링을 고칩니다.

```python
def load_table(client, table_id, path, schema, description):
    """Parquet 파일 하나를 표 하나로 올립니다(통째로 바꿈). 올린 뒤 빅쿼리 (행 수, 용량)입니다."""
    ...
    return t.num_rows, t.num_bytes
```

`copy_tables()` 안에서 `rows, error = None, None` 을 `rows, error, nbytes = None, None, None` 으로, 적재 부분을

```python
                got, nbytes = load_table(client, "%s.%s" % (dataset, t), path, bq_schema(cols),
                                         table_description(t, cols, now))
                if got != rows:
                    nbytes = None
                    raise RuntimeError(...)  # 기존 문장 그대로
```

으로, `results.append(Result(t, source, rows, secs, error))` 를 `results.append(Result(t, source, rows, secs, error, None if error else nbytes))` 로 바꿉니다.

`summary_note` 위에 더합니다.

```python
def write_result_json(path, results, tried_at, mysql_tables):
    """복사 결과를 record_bq_snapshot.py 가 읽을 파일로 씁니다."""
    data = {
        "tried_at": tried_at.astimezone(KST).strftime("%Y-%m-%d %H:%M"),
        "tables": [{"name": r.table, "source": r.source,
                    "rows": None if r.error else r.rows,
                    "bytes": r.bytes, "error": r.error} for r in results],
        "mysql_tables": sorted(mysql_tables),
    }
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
```

맨 위 import 에 `import json` 을 더합니다(`json` 이 이미 없다면).

`main()` 의 인자에 더합니다.

```python
    ap.add_argument("--result-json", default=None,
                    help="표마다 결과를 이 JSON 파일에 씁니다(record_bq_snapshot.py 가 읽음)")
```

`main()` 에서 `t0 = time.time()` 다음 줄에 `tried_at = datetime.datetime.now(KST)` 를 두고, `note = summary_note(results)` 바로 앞에 더합니다.

```python
    if args.result_json and not args.dry_run:
        write_result_json(args.result_json, results, tried_at, specs)
```

(`specs` 는 MySQL 표 이름 → 열 목록 dict 이라 `sorted(specs)` 가 표 이름입니다. `specs` 는 `my` 를 닫은 뒤에도 남는 지역 변수입니다.)

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_sqlite_to_bigquery.py -q`
Expected: 전부 PASS (기존 시험 포함. `FakeTable` 기본 용량 = 행 × 100)

- [ ] **Step 5: 커밋합니다**

```bash
git add migration/mysql/sqlite_to_bigquery.py tests/test_sqlite_to_bigquery.py
git commit -m "feat(bq-copy): 표마다 빅쿼리 용량과 결과 JSON(--result-json), meta_bq_tables 는 복사하지 않음

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `record_bq_snapshot.py` — 결과 JSON 을 `meta_bq_tables` 에

**Files:**
- Create: `migration/mysql/record_bq_snapshot.py`
- Test: `tests/test_record_bq_snapshot.py`

**Interfaces:**
- Consumes: Task 1 의 결과 JSON 모양.
- Produces:
  - `DDL: str` — 설계 §4-1 의 `CREATE TABLE` 글자 그대로(계획 B 가 `schema.sql` 과 같은지 시험).
  - `load_result(path) -> dict` — 없거나 깨졌거나 모양이 틀리면 `ValueError`.
  - `plan_rows(result, existing) -> tuple[list[dict], list[str]]` — `existing` 은 `{name: 지금 줄 dict}`. 돌려주는 값은 (쓸 줄 목록, 지울 이름 목록).
  - `write(sink, rows, deletes) -> None` — `sink.execute` 로 씀(UPSERT + DELETE). `sink` 는 `execute·query` 가 있는 것(`Db` 또는 시험의 가짜).
  - `class Db(con)` — pymysql 연결 감싸개. `mysql_sink.mirror` 는 쓰지 않습니다(실패가 주간 작업을 빨갛게 만들지 않게).
  - CLI: `python -m migration.mysql.record_bq_snapshot --result-json PATH`

규칙(설계 §4-1):
- 성공한 표: `bq_rows=rows, bq_bytes=bytes, last_ok_at=tried_at, last_try_at=tried_at, status='ok', error=NULL`.
- 실패한 표: 지금 줄의 `bq_rows·bq_bytes·last_ok_at` 를 그대로 두고 `last_try_at=tried_at, status='fail', error=앞 300자`. 지금 줄이 없으면 그 셋은 NULL.
- `mysql_tables` 에 없는 이름의 지금 줄은 지웁니다. `meta_bq_tables` 자신은 줄을 만들지 않습니다(복사하지 않는 표).
- 결과 JSON 의 `tables` 에 없지만 `mysql_tables` 에 있는 표(예: `--tables` 로 일부만 복사)는 건드리지 않습니다.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```python
# tests/test_record_bq_snapshot.py
import json

import pytest

from migration.mysql import record_bq_snapshot as r

T = "2026-10-20 06:10"


def result(tables, mysql_tables=None):
    return {"tried_at": T, "tables": tables,
            "mysql_tables": mysql_tables or [t["name"] for t in tables]}


def ok(name, rows=10, nbytes=1000):
    return {"name": name, "source": "mysql", "rows": rows, "bytes": nbytes, "error": None}


def bad(name, msg="적재 실패"):
    return {"name": name, "source": "mysql", "rows": None, "bytes": None, "error": msg}


def test_성공한_표는_새_값으로_덮습니다():
    rows, dels = r.plan_rows(result([ok("games", 12, 3400)]), {})
    assert rows == [{"name": "games", "bq_rows": 12, "bq_bytes": 3400, "last_ok_at": T,
                     "last_try_at": T, "status": "ok", "error": None}]
    assert dels == []


def test_실패한_표는_지난_성공_값을_남깁니다():
    before = {"games": {"name": "games", "bq_rows": 11, "bq_bytes": 3300,
                        "last_ok_at": "2026-10-13 06:00", "last_try_at": "2026-10-13 06:00",
                        "status": "ok", "error": None}}
    rows, _ = r.plan_rows(result([bad("games", "x" * 400)]), before)
    assert rows[0]["bq_rows"] == 11 and rows[0]["bq_bytes"] == 3300
    assert rows[0]["last_ok_at"] == "2026-10-13 06:00"
    assert rows[0]["last_try_at"] == T and rows[0]["status"] == "fail"
    assert len(rows[0]["error"]) == 300


def test_처음부터_실패한_표는_성공_값이_비어_있습니다():
    rows, _ = r.plan_rows(result([bad("games")]), {})
    assert rows[0]["bq_rows"] is None and rows[0]["last_ok_at"] is None


def test_MySQL_에_없는_표의_줄은_지웁니다():
    before = {"old": {"name": "old"}, "games": {"name": "games"}}
    _, dels = r.plan_rows(result([ok("games")], ["games", "meta_bq_tables"]), before)
    assert dels == ["old"]


def test_이번에_복사하지_않은_표는_건드리지_않습니다():
    before = {"teams": {"name": "teams", "bq_rows": 10}}
    rows, dels = r.plan_rows(result([ok("games")], ["games", "teams"]), before)
    assert [x["name"] for x in rows] == ["games"] and dels == []


def test_현황_표_자신은_줄을_만들지_않습니다():
    rows, _ = r.plan_rows(result([ok("meta_bq_tables")]), {})
    assert rows == []


@pytest.mark.parametrize("text", ["", "{", '{"tables": []}', '{"tried_at": "x", "tables": [], "mysql_tables": []}'])
def test_결과_파일이_틀리면_멈춥니다(tmp_path, text):
    p = tmp_path / "res.json"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        r.load_result(p)


def test_결과_파일이_없으면_멈춥니다(tmp_path):
    with pytest.raises(ValueError):
        r.load_result(tmp_path / "none.json")


class FakeSink:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return 1


def test_쓰기는_UPSERT_와_DELETE_입니다():
    s = FakeSink()
    rows, _ = r.plan_rows(result([ok("games")]), {})
    r.write(s, rows, ["old"])
    assert s.sql[0][0].startswith("INSERT INTO `meta_bq_tables`")
    assert "ON DUPLICATE KEY UPDATE" in s.sql[0][0]
    assert s.sql[0][1] == ["games", 10, 1000, T, T, "ok", None]
    assert s.sql[1] == ("DELETE FROM `meta_bq_tables` WHERE `name` IN (%s)", ["old"])


class BoomCursor:
    description = [("name",)]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if sql.startswith("INSERT"):
            raise RuntimeError("쓰기 실패(가짜)")

    def fetchall(self):
        return []


class BoomCon:
    def __init__(self):
        self.log = []

    def cursor(self):
        return BoomCursor()

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def test_쓰기가_실패해도_주간_작업의_실패_기록을_남기지_않습니다(tmp_path, monkeypatch):
    from migration.mysql import conn as myconn
    con = BoomCon()
    monkeypatch.setattr(myconn, "connect", lambda: con)
    fail_log = tmp_path / "fail.jsonl"
    monkeypatch.setenv("BSTATS_MYSQL_FAIL_LOG", str(fail_log))
    res = tmp_path / "res.json"
    res.write_text(json.dumps(result([ok("games")])), encoding="utf-8")
    assert r.main(["--result-json", str(res)]) == 1
    assert con.log == ["rollback", "close"] and not fail_log.exists()


def test_결과_파일이_없으면_연결하지_않고_1(tmp_path, monkeypatch):
    from migration.mysql import conn as myconn
    monkeypatch.setattr(myconn, "connect", lambda: (_ for _ in ()).throw(AssertionError("연결하면 안 됨")))
    assert r.main(["--result-json", str(tmp_path / "none.json")]) == 1


def test_DDL_은_설계서와_같은_열입니다():
    for col in ("`name` VARCHAR(64) NOT NULL", "`bq_rows` BIGINT", "`bq_bytes` BIGINT",
                "`last_ok_at` DATETIME", "`last_try_at` DATETIME NOT NULL",
                "`status` VARCHAR(8) NOT NULL", "`error` VARCHAR(300)", "PRIMARY KEY (`name`)"):
        assert col in r.DDL
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_record_bq_snapshot.py -q`
Expected: FAIL (`ModuleNotFoundError: migration.mysql.record_bq_snapshot`)

- [ ] **Step 3: 구현합니다**

```python
# -*- coding: utf-8 -*-
"""주간 빅쿼리 복사 결과를 MySQL meta_bq_tables 에 남깁니다.

공개 '데이터 관리' 화면이 GET /ops/storage 로 이 표를 읽습니다. Worker 에는 GCP
자격이 없어서 빅쿼리를 직접 읽지 못하므로, 복사한 쪽이 결과를 MySQL 에 적어
둡니다(설계 docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §4).

- 성공한 표는 행 수·용량·시각을 새 값으로 덮습니다.
- 실패한 표는 지난 성공 값을 남기고 상태·시도 시각·오류만 바꿉니다. 빅쿼리에는
  그 전 사본이 그대로 있기 때문입니다.
- MySQL 에 없는 표의 줄은 지웁니다.

결과 파일이 없거나 깨졌으면 아무것도 쓰지 않고 0 이 아닌 값으로 끝납니다.

    python -m migration.mysql.record_bq_snapshot --result-json bq_result.json
"""
import argparse
import json
import sys
from pathlib import Path

TABLE = "meta_bq_tables"
ERROR_MAX = 300
COLS = ["name", "bq_rows", "bq_bytes", "last_ok_at", "last_try_at", "status", "error"]

DDL = """CREATE TABLE `meta_bq_tables` (
  `name` VARCHAR(64) NOT NULL,
  `bq_rows` BIGINT,
  `bq_bytes` BIGINT,
  `last_ok_at` DATETIME,
  `last_try_at` DATETIME NOT NULL,
  `status` VARCHAR(8) NOT NULL,
  `error` VARCHAR(300),
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;"""


def load_result(path):
    """결과 JSON 입니다. 없거나 깨졌거나 모양이 틀리면 ValueError."""
    p = Path(path)
    if not p.is_file():
        raise ValueError("결과 파일이 없습니다: %s" % p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError("결과 파일을 읽지 못했습니다: %s" % e) from None
    if not isinstance(data, dict) or not all(k in data for k in ("tried_at", "tables", "mysql_tables")):
        raise ValueError("결과 파일 모양이 다릅니다")
    if not data["tables"] or not data["mysql_tables"]:
        raise ValueError("결과 파일에 표가 없습니다")
    return data


def plan_rows(result, existing):
    """(쓸 줄, 지울 이름)입니다. existing 은 {표 이름: 지금 줄}."""
    t = result["tried_at"]
    rows = []
    for item in result["tables"]:
        name = item["name"]
        if name == TABLE:
            continue
        if item.get("error"):
            old = existing.get(name) or {}
            rows.append({"name": name, "bq_rows": old.get("bq_rows"), "bq_bytes": old.get("bq_bytes"),
                         "last_ok_at": old.get("last_ok_at"), "last_try_at": t, "status": "fail",
                         "error": str(item["error"])[:ERROR_MAX]})
        else:
            rows.append({"name": name, "bq_rows": item["rows"], "bq_bytes": item["bytes"],
                         "last_ok_at": t, "last_try_at": t, "status": "ok", "error": None})
    alive = set(result["mysql_tables"])
    deletes = sorted(n for n in existing if n not in alive)
    return rows, deletes


def write(sink, rows, deletes):
    """한 트랜잭션 안의 sink(mysql_sink.Sink)로 씁니다."""
    q = lambda c: "`%s`" % c  # noqa: E731
    head = "INSERT INTO `%s` (%s) VALUES (%s)" % (
        TABLE, ", ".join(q(c) for c in COLS), ", ".join(["%s"] * len(COLS)))
    tail = " AS new ON DUPLICATE KEY UPDATE " + ", ".join(
        "%s=new.%s" % (q(c), q(c)) for c in COLS if c != "name")
    for row in rows:
        sink.execute(head + tail, [row[c] for c in COLS])
    if deletes:
        sink.execute("DELETE FROM `%s` WHERE `name` IN (%s)" % (TABLE, ", ".join(["%s"] * len(deletes))),
                     list(deletes))


class Db:
    """pymysql 연결에 execute·query 두 가지만 붙입니다(mysql_sink.Sink 와 같은 이름)."""

    def __init__(self, con):
        self.con = con

    def execute(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]


def read_existing(sink):
    out = {}
    for r in sink.query("SELECT %s FROM `%s`" % (", ".join("`%s`" % c for c in COLS), TABLE)):
        for k in ("last_ok_at", "last_try_at"):
            if r.get(k) is not None and not isinstance(r[k], str):
                r[k] = r[k].strftime("%Y-%m-%d %H:%M")
        out[r["name"]] = r
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="빅쿼리 복사 결과를 meta_bq_tables 에 씁니다")
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args(argv)
    try:
        result = load_result(args.result_json)
    except ValueError as e:
        print("빅쿼리 현황 기록 안 함: %s" % e)
        return 1

    # mysql_sink.mirror 는 실패하면 실패 기록 파일에 남기고, 주간 작업의 "MySQL 적재
    # 실패 확인"이 그 파일을 보고 작업을 빨갛게 끝냅니다. 이 기록이 실패해도 주간
    # 판정은 바꾸지 않기로 했으므로(설계 §4-2) 직접 연결합니다.
    from migration.mysql import conn as myconn
    con = myconn.connect()
    try:
        db = Db(con)
        rows, deletes = plan_rows(result, read_existing(db))
        write(db, rows, deletes)
        con.commit()
    except Exception as e:  # noqa: BLE001
        con.rollback()
        print("빅쿼리 현황 기록 실패: %s" % ("%s: %s" % (type(e).__name__, e))[:300])
        return 1
    finally:
        con.close()
    print("빅쿼리 현황 기록: %d개 표, 지운 줄 %d개" % (len(rows), len(deletes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_record_bq_snapshot.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add migration/mysql/record_bq_snapshot.py tests/test_record_bq_snapshot.py
git commit -m "feat(bq-copy): 복사 결과를 meta_bq_tables 에 남기는 record_bq_snapshot.py(아직 워크플로가 부르지 않음)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: 결제 집계 `cost_billing.py`

**Files:**
- Create: `scripts/ops/__init__.py` (빈 파일), `scripts/ops/cost_billing.py`
- Test: `tests/test_cost_billing.py`

**Interfaces:**
- Produces:
  - `billing_sql(table: str) -> str` — `@start`(DATE) 매개변수를 쓰는 질의. 열: `month, service, sku, day, currency, net`.
  - `FIXED_SKU_PATTERNS: list[str]` — 고정비 SKU 정규식(대소문자 무시).
  - `is_fixed(sku: str) -> bool`
  - `service_group(service: str) -> str` — `"Cloud SQL" | "BigQuery" | "Cloud Monitoring" | "기타"`.
  - `summarize(rows: list[dict], month: str, today: date, budget: int) -> dict` — 키:
    - `month`, `days_elapsed`(int), `days_in_month`(int)
    - `total`(이번 달 순액), `avg_per_day`, `forecast`, `budget`, `ratio_pct`, `forecast_ratio_pct`
    - `months`: `[{"month", "Cloud SQL", "BigQuery", "Cloud Monitoring", "기타", "total", "partial"}]` 오래된 달부터
    - `sql_skus`: `[{"sku", "amount", "kind": "고정"|"변동", "share_pct"}]` 이번 달 Cloud SQL, 금액 큰 순
    - `daily`: 최근 30일(오늘 포함) `[{"day": "YYYY-MM-DD", "fixed", "백업·PITR 로그", "네트워크", "BigQuery", "기타", "partial": bool}]`
    - `fixed_per_day`(지난 29일 평균 고정비, 반올림 정수), `var_median`(지난 29일 변동비 중앙값)
    - `unknown_sql_skus`: 고정 목록에 없고 백업·네트워크로도 안 나뉜 Cloud SQL SKU 이름(주의 칸에 적음)
    - `currencies`: 행에 나온 통화 집합(원 말고 다른 것이 있으면 주의 칸)

일별 변동비 항목 나누기(데이터로 분명히 정해지는 규칙만):
- Cloud SQL 이고 `is_fixed` → `fixed`
- Cloud SQL 이고 SKU 에 `backup` 또는 `log`(대소문자 무시) → `백업·PITR 로그`
- 서비스 무관 SKU 에 `egress` 또는 `network`(대소문자 무시) → `네트워크`
- 서비스가 BigQuery → `BigQuery`
- 나머지 → `기타` (Cloud SQL 인데 여기로 온 SKU 는 `unknown_sql_skus` 에도 넣음)

- [ ] **Step 1: 실패하는 시험을 씁니다**

`tests/` 는 패키지가 아니라서 시험끼리 나눠 쓰는 예시 데이터는 같은 폴더 모듈로 둡니다
(pytest 가 시험 파일 폴더를 import 경로에 넣습니다).

```python
# tests/ops_cost_fixtures.py
"""비용 보고서 시험이 함께 쓰는 예시 데이터입니다(실제 결제·사용량 아님)."""
import datetime as dt

SQL = "Cloud SQL"
INST = "Cloud SQL for MySQL: Zonal - Micro instance in Seoul"
DISK = "Cloud SQL for MySQL: Zonal - Standard storage in Seoul"
BACK = "Cloud SQL for MySQL: Backups in Seoul"
EGR = "Network Internet Egress from Seoul to Americas"
ODD = "Cloud SQL for MySQL: Something new in Seoul"
DAYS = [dt.date(2026, 9, 19) + dt.timedelta(days=i) for i in range(30)]


def row(day, service, sku, net, month=None, currency="KRW"):
    return {"month": month or day[:4] + day[5:7], "service": service, "sku": sku,
            "day": dt.date.fromisoformat(day), "currency": currency, "net": net}


def month_rows():
    rows = []
    for d in range(1, 19):
        day = "2026-10-%02d" % d
        rows += [row(day, SQL, INST, 340), row(day, SQL, DISK, 77),
                 row(day, SQL, BACK, 26), row(day, SQL, EGR, 9)]
    rows.append(row("2026-10-09", SQL, BACK, 95))
    rows.append(row("2026-10-12", "BigQuery", "Analysis", 12))
    rows.append(row("2026-10-05", SQL, ODD, 3))
    rows.append(row("2026-09-30", SQL, INST, 340, month="202609"))
    return rows


def cf_resp(req_by_day, cut_by_day=None, q_by_day=None, p50=4800, p99=21600):
    """Cloudflare GraphQL 응답 모양(cost_cloudflare.graphql_query 의 별칭 inv·cpuDaily·cpuAll·hyd)."""
    cut_by_day = cut_by_day or {}
    q_by_day = q_by_day or {}
    inv = []
    for d, n in req_by_day.items():
        cut = cut_by_day.get(d, 0)
        inv.append({"dimensions": {"date": d.isoformat(), "status": "success"}, "sum": {"requests": n - cut}})
        if cut:
            inv.append({"dimensions": {"date": d.isoformat(), "status": "exceededResources"},
                        "sum": {"requests": cut}})
    daily_cpu = [{"dimensions": {"date": d.isoformat()}, "quantiles": {"cpuTimeP99": 20000}}
                 for d in req_by_day]
    return {"data": {"viewer": {"accounts": [{
        "inv": inv, "cpuDaily": daily_cpu,
        "cpuAll": [{"quantiles": {"cpuTimeP50": p50, "cpuTimeP99": p99}}],
        "hyd": [{"dimensions": {"date": d.isoformat()}, "count": n} for d, n in q_by_day.items()],
    }]}}, "errors": None}
```

```python
# tests/test_cost_billing.py
import datetime as dt

from scripts.ops import cost_billing as b
from ops_cost_fixtures import BACK, DISK, EGR, INST, ODD, SQL, month_rows, row


def test_고정비_SKU_를_알아봅니다():
    assert b.is_fixed(INST) and b.is_fixed(DISK)
    assert not b.is_fixed(BACK) and not b.is_fixed(EGR)


def test_서비스_묶음():
    assert b.service_group("Cloud SQL") == "Cloud SQL"
    assert b.service_group("BigQuery") == "BigQuery"
    assert b.service_group("Cloud Monitoring") == "Cloud Monitoring"
    assert b.service_group("Secret Manager") == "기타"


def test_이번_달_요약():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    total = 18 * (340 + 77 + 26 + 9) + 95 + 12 + 3
    assert s["total"] == total
    assert s["days_elapsed"] == 18 and s["days_in_month"] == 31
    assert s["forecast"] == round(total / 18 * 31)
    assert s["ratio_pct"] == round(total / 30000 * 100, 1)


def test_월별_표는_오래된_달부터이고_진행_중인_달을_표시합니다():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    assert [m["month"] for m in s["months"]] == ["2026-09", "2026-10"]
    assert s["months"][0]["Cloud SQL"] == 340 and not s["months"][0]["partial"]
    assert s["months"][1]["BigQuery"] == 12 and s["months"][1]["partial"]


def test_Cloud_SQL_SKU_세부와_모르는_SKU():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    kinds = {x["sku"]: x["kind"] for x in s["sql_skus"]}
    assert kinds[INST] == "고정" and kinds[BACK] == "변동"
    assert s["sql_skus"][0]["sku"] == INST
    assert s["unknown_sql_skus"] == [ODD]


def test_일별은_30일이고_고정비와_변동비를_나눕니다():
    s = b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)
    assert len(s["daily"]) == 30 and s["daily"][-1]["day"] == "2026-10-18"
    assert s["daily"][-1]["partial"] and not s["daily"][-2]["partial"]
    d9 = next(x for x in s["daily"] if x["day"] == "2026-10-09")
    assert d9["fixed"] == 417 and d9["백업·PITR 로그"] == 26 + 95 and d9["네트워크"] == 9
    d5 = next(x for x in s["daily"] if x["day"] == "2026-10-05")
    assert d5["기타"] == 3


def test_원이_아닌_통화가_있으면_알립니다():
    rows = [row("2026-10-01", SQL, INST, 1, currency="USD")]
    s = b.summarize(rows, "2026-10", dt.date(2026, 10, 1), 30000)
    assert s["currencies"] == ["USD"]


def test_질의는_크레딧을_더한_순액이고_한국_날짜입니다():
    sql = b.billing_sql("p.d.t")
    assert "UNNEST(credits)" in sql and "'Asia/Seoul'" in sql and "`p.d.t`" in sql
    assert "@start" in sql
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_cost_billing.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현합니다**

```python
# -*- coding: utf-8 -*-
"""GCP 결제 빅쿼리 내보내기(표준 사용 비용)를 보고서 숫자로 바꿉니다.

질의 글자와 순수 계산만 둡니다. 빅쿼리 호출은 cost_report.py 가 합니다.
순액 = 비용 + 크레딧 합(크레딧은 음수). 날짜는 사용 시작 시각의 KST 날짜,
월은 청구 월(invoice.month)입니다.
"""
import calendar
import datetime as dt
import re
import statistics

SERVICES = ("Cloud SQL", "BigQuery", "Cloud Monitoring")
VAR_KEYS = ("백업·PITR 로그", "네트워크", "BigQuery", "기타")

# 매일 같은 금액이 붙는 Cloud SQL SKU 입니다. 첫 실제 실행에서 '기준과 주의'의
# SKU 목록을 보고 evan 이 확인합니다. 목록에 없으면 짐작하지 않고 변동비로 둡니다.
FIXED_SKU_PATTERNS = [r"\bmicro instance\b", r"\bsmall instance\b", r"\bvcpu\b", r"\bram\b",
                      r"\bstandard storage\b", r"\bssd storage\b"]


def billing_sql(table):
    return (
        "SELECT invoice.month AS month, service.description AS service, sku.description AS sku, "
        "DATE(usage_start_time, 'Asia/Seoul') AS day, currency, "
        "SUM(cost) + SUM(IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) c), 0)) AS net "
        "FROM `%s` "
        "WHERE project.id = 'bstats-kbo' AND DATE(usage_start_time, 'Asia/Seoul') >= @start "
        "GROUP BY month, service, sku, day, currency" % table)


def is_fixed(sku):
    s = (sku or "").lower()
    return any(re.search(p, s) for p in FIXED_SKU_PATTERNS)


def service_group(service):
    return service if service in SERVICES else "기타"


def var_key(service, sku):
    s = (sku or "").lower()
    if service == "Cloud SQL" and ("backup" in s or "log" in s):
        return "백업·PITR 로그"
    if "egress" in s or "network" in s:
        return "네트워크"
    if service == "BigQuery":
        return "BigQuery"
    return "기타"


def _ym(month):
    return "%s-%s" % (month[:4], month[4:6])


def summarize(rows, month, today, budget):
    y, m = int(month[:4]), int(month[5:7])
    days_in_month = calendar.monthrange(y, m)[1]
    days_elapsed = today.day if (today.year, today.month) == (y, m) else days_in_month

    months = {}
    for r in rows:
        k = _ym(r["month"])
        mm = months.setdefault(k, {"month": k, **{s: 0 for s in SERVICES}, "기타": 0})
        mm[service_group(r["service"])] += r["net"]
    month_list = []
    for k in sorted(months):
        mm = months[k]
        mm["total"] = sum(mm[s] for s in (*SERVICES, "기타"))
        mm["partial"] = k == month and days_elapsed < days_in_month
        month_list.append(mm)
    total = months.get(month, {}).get("total", 0)

    sku_sum, unknown = {}, set()
    for r in rows:
        if _ym(r["month"]) == month and r["service"] == "Cloud SQL":
            sku_sum[r["sku"]] = sku_sum.get(r["sku"], 0) + r["net"]
            if not is_fixed(r["sku"]) and var_key("Cloud SQL", r["sku"]) == "기타":
                unknown.add(r["sku"])
    sql_total = sum(sku_sum.values()) or 1
    sql_skus = [{"sku": k, "amount": v, "kind": "고정" if is_fixed(k) else "변동",
                 "share_pct": round(v / sql_total * 100, 1)}
                for k, v in sorted(sku_sum.items(), key=lambda kv: -kv[1])]

    days = [today - dt.timedelta(days=i) for i in range(29, -1, -1)]
    daily = {d: {"day": d.isoformat(), "fixed": 0, **{k: 0 for k in VAR_KEYS}, "partial": d == today}
             for d in days}
    for r in rows:
        d = r["day"]
        if d not in daily:
            continue
        if r["service"] == "Cloud SQL" and is_fixed(r["sku"]):
            daily[d]["fixed"] += r["net"]
        else:
            daily[d][var_key(r["service"], r["sku"])] += r["net"]
    daily_list = [daily[d] for d in days]
    past = daily_list[:-1]
    fixed_per_day = round(sum(x["fixed"] for x in past) / len(past))
    var_median = statistics.median(sum(x[k] for k in VAR_KEYS) for x in past)

    forecast = round(total / days_elapsed * days_in_month) if days_elapsed else 0
    return {
        "month": month, "days_elapsed": days_elapsed, "days_in_month": days_in_month,
        "total": total, "avg_per_day": round(total / days_elapsed) if days_elapsed else 0,
        "forecast": forecast, "budget": budget,
        "ratio_pct": round(total / budget * 100, 1),
        "forecast_ratio_pct": round(forecast / budget * 100, 1),
        "months": month_list, "sql_skus": sql_skus, "daily": daily_list,
        "fixed_per_day": fixed_per_day, "var_median": var_median,
        "unknown_sql_skus": sorted(unknown),
        "currencies": sorted({r["currency"] for r in rows} - {"KRW"}),
    }
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_cost_billing.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add scripts/ops/__init__.py scripts/ops/cost_billing.py tests/ops_cost_fixtures.py tests/test_cost_billing.py
git commit -m "feat(ops): 비용 보고서 결제 집계(순액·월별·SKU·일별 고정/변동)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Cloudflare 집계 `cost_cloudflare.py`

**Files:**
- Create: `scripts/ops/cost_cloudflare.py`
- Test: `tests/test_cost_cloudflare.py`

**Interfaces:**
- Produces:
  - `WORKER = "kbo-api"`, `WORKERS_FREE_PER_DAY = 100_000`, `HYPERDRIVE_FREE_PER_DAY: int`, `CPU_LIMIT_MS = 10`, `LIMIT_LINE_AT = 0.5`
  - `graphql_query() -> str` — 변수 `$acct: String!`, `$start: Date!`, `$end: Date!`.
  - `summarize(resp: dict, days: list[date]) -> dict` — 키:
    `requests`(날마다 int 30개), `queries`(30개), `cut`(30개), `p99_by_day`(ms float 30개),
    `cpu_p50_ms`, `cpu_p99_ms`(30일 전체), `cut_total`, `cut_pct`, `req_peak`, `req_peak_day`,
    `hyd_peak`, `hyd_peak_day`, `show_limit_line: {"requests": bool, "queries": bool}`.
  - `class SchemaMismatch(Exception)` — 응답에 기대한 칸이 없을 때(예: 데이터셋 이름이 다름).

**먼저 할 일(구현 첫 단계, 설계 §6-3):** Cloudflare 문서와 실제 GraphQL 스키마로 아래를 확인하고, 확인한 날짜를 상수 옆 주석에 적습니다. 토큰(`~/.bstats/cf_analytics_token.txt`)이 아직 없으면 문서 기준으로 만들고, Task 6 의 첫 실제 실행이 확인 단계가 됩니다(그때 `SchemaMismatch` 가 나면 이 파일만 고칩니다).
1. Workers 호출 데이터셋 `workersInvocationsAdaptive` 의 `dimensions{date status scriptName}`, `sum{requests}`, `quantiles{cpuTimeP50 cpuTimeP99}`(단위 마이크로초).
2. CPU 한도 초과 상태 값(`status` 가 `exceededResources` 인지).
3. Hyperdrive 질의 데이터셋 이름과 날짜·개수 칸(문서 기준 `hyperdriveQueriesAdaptiveGroups`, `dimensions{date}`, `count`).
4. Hyperdrive 무료 플랜 하루 질의 한도 값.

이 확인을 위해 KBO 주소는 물론 다른 바깥 주소도 부르지 않습니다. 부르는 곳은 `https://api.cloudflare.com/client/v4/graphql` 하나입니다.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```python
# tests/test_cost_cloudflare.py
import pytest

from scripts.ops import cost_cloudflare as c
from ops_cost_fixtures import DAYS
from ops_cost_fixtures import cf_resp as resp


def test_날마다_요청_질의_끊긴_수를_30칸으로_맞춥니다():
    s = c.summarize(resp({DAYS[0]: 100, DAYS[5]: 300}, {DAYS[5]: 2}, {DAYS[5]: 400}), DAYS)
    assert len(s["requests"]) == 30 and s["requests"][0] == 100 and s["requests"][1] == 0
    assert s["requests"][5] == 300 and s["cut"][5] == 2 and s["queries"][5] == 400
    assert s["cut_total"] == 2 and s["cut_pct"] == round(2 / 400 * 100, 3)


def test_CPU_는_밀리초입니다():
    s = c.summarize(resp({DAYS[0]: 1}), DAYS)
    assert s["cpu_p50_ms"] == 4.8 and s["cpu_p99_ms"] == 21.6 and s["p99_by_day"][0] == 20.0


def test_가장_많은_날과_한도선_규칙():
    big = {d: 1000 for d in DAYS}
    big[DAYS[10]] = 60_000
    s = c.summarize(resp(big), DAYS)
    assert s["req_peak"] == 60_000 and s["req_peak_day"] == DAYS[10]
    assert s["show_limit_line"]["requests"] is True
    s2 = c.summarize(resp({DAYS[0]: 12_480}), DAYS)
    assert s2["show_limit_line"]["requests"] is False


def test_칸이_없으면_스키마가_다르다고_알립니다():
    with pytest.raises(c.SchemaMismatch):
        c.summarize({"data": {"viewer": {"accounts": [{}]}}, "errors": None}, DAYS)


def test_GraphQL_오류는_스키마가_다르다고_알립니다():
    with pytest.raises(c.SchemaMismatch):
        c.summarize({"data": None, "errors": [{"message": "unknown field hyd"}]}, DAYS)


def test_질의는_kbo_api_만_봅니다():
    q = c.graphql_query()
    assert '"kbo-api"' in q and "$acct" in q and "$start" in q and "$end" in q
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_cost_cloudflare.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현합니다**

```python
# -*- coding: utf-8 -*-
"""Cloudflare GraphQL 분석 API 응답을 무료 한도 대비 일별 값으로 바꿉니다.

날짜는 Cloudflare 집계 기준인 UTC 하루입니다. CPU 시간은 마이크로초로 오므로
밀리초로 바꿉니다. 호출은 cost_report.py 가 합니다.

데이터셋·칸 이름과 한도 값은 Cloudflare 문서·스키마로 확인한 값입니다.
(확인 날짜를 아래 상수 옆에 적습니다. 다르면 SchemaMismatch 로 멈춥니다.)
"""
import datetime as dt

WORKER = "kbo-api"
WORKERS_FREE_PER_DAY = 100_000      # 확인: YYYY-MM-DD, Workers Free 하루 요청 한도
HYPERDRIVE_FREE_PER_DAY = 100_000   # 확인: YYYY-MM-DD, Hyperdrive Free 하루 질의 한도
CPU_LIMIT_MS = 10
LIMIT_LINE_AT = 0.5                 # 가장 많은 날이 한도의 50% 를 넘으면 한도선을 그립니다
CUT_STATUS = "exceededResources"    # 확인: YYYY-MM-DD


class SchemaMismatch(Exception):
    """응답에 기대한 칸이 없습니다(데이터셋·칸 이름이 바뀌었을 수 있음)."""


def graphql_query():
    w = '{scriptName: "%s", date_geq: $start, date_leq: $end}' % WORKER
    return (
        "query($acct: String!, $start: Date!, $end: Date!) { viewer { accounts(filter: {accountTag: $acct}) {"
        " inv: workersInvocationsAdaptive(limit: 10000, filter: %s) { dimensions { date status } sum { requests } }"
        " cpuDaily: workersInvocationsAdaptive(limit: 100, filter: %s) { dimensions { date } quantiles { cpuTimeP99 } }"
        " cpuAll: workersInvocationsAdaptive(limit: 1, filter: %s) { quantiles { cpuTimeP50 cpuTimeP99 } }"
        " hyd: hyperdriveQueriesAdaptiveGroups(limit: 100, filter: {date_geq: $start, date_leq: $end})"
        " { dimensions { date } count }"
        " } } }" % (w, w, w))


def _get(acc, key):
    if key not in acc or acc[key] is None:
        raise SchemaMismatch("응답에 %s 가 없습니다" % key)
    return acc[key]


def summarize(resp, days):
    if resp.get("errors"):
        raise SchemaMismatch("; ".join(e.get("message", "") for e in resp["errors"]))
    try:
        acc = resp["data"]["viewer"]["accounts"][0]
    except (TypeError, KeyError, IndexError):
        raise SchemaMismatch("응답에 accounts 가 없습니다") from None
    idx = {d.isoformat(): i for i, d in enumerate(days)}
    n = len(days)
    req, cut, qs, p99d = [0] * n, [0] * n, [0] * n, [0.0] * n
    for g in _get(acc, "inv"):
        i = idx.get(g["dimensions"]["date"])
        if i is None:
            continue
        v = int(g["sum"]["requests"])
        req[i] += v
        if g["dimensions"]["status"] == CUT_STATUS:
            cut[i] += v
    for g in _get(acc, "cpuDaily"):
        i = idx.get(g["dimensions"]["date"])
        if i is not None:
            p99d[i] = round(g["quantiles"]["cpuTimeP99"] / 1000, 1)
    for g in _get(acc, "hyd"):
        i = idx.get(g["dimensions"]["date"])
        if i is not None:
            qs[i] += int(g["count"])
    all_q = _get(acc, "cpuAll")
    if not all_q:
        raise SchemaMismatch("cpuAll 이 비었습니다")
    q = all_q[0]["quantiles"]
    ri = max(range(n), key=lambda i: req[i])
    hi = max(range(n), key=lambda i: qs[i])
    total = sum(req)
    return {
        "days": days, "requests": req, "queries": qs, "cut": cut, "p99_by_day": p99d,
        "cpu_p50_ms": round(q["cpuTimeP50"] / 1000, 1), "cpu_p99_ms": round(q["cpuTimeP99"] / 1000, 1),
        "cut_total": sum(cut), "cut_pct": round(sum(cut) / total * 100, 3) if total else 0.0,
        "req_peak": req[ri], "req_peak_day": days[ri], "hyd_peak": qs[hi], "hyd_peak_day": days[hi],
        "show_limit_line": {"requests": req[ri] >= WORKERS_FREE_PER_DAY * LIMIT_LINE_AT,
                            "queries": qs[hi] >= HYPERDRIVE_FREE_PER_DAY * LIMIT_LINE_AT},
    }
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_cost_cloudflare.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add scripts/ops/cost_cloudflare.py tests/test_cost_cloudflare.py
git commit -m "feat(ops): 비용 보고서 Cloudflare 무료 한도 집계(요청·질의·끊긴 요청·CPU)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: 보고서 그리기 `cost_render.py` + 틀

**Files:**
- Create: `scripts/ops/cost_report_template.html`, `scripts/ops/cost_render.py`
- Test: `tests/test_cost_render.py`

**Interfaces:**
- Consumes: Task 3 `summarize()` 의 dict(`billing`), Task 4 `summarize()` 의 dict(`cf`), 둘 다 `None` 일 수 있음(그 칸은 안내 글).
- Produces:
  - `render(billing: dict | None, cf: dict | None, meta: dict) -> str` — HTML 전체. `meta` 키: `made_at`(str), `billing_note`(str, 빈 칸 이유), `cf_note`(str), `font_dir`(str, 상대 경로 `fonts`).
  - 틀은 `string.Template`. 자리 표시자: `$month_label $made_at $billing_html $cf_html $notes_html $colors_json` 여섯 개.

틀과 코드는 Step 3 에 있습니다. 모양·툴팁 문구는 미리보기 3차안과 같습니다.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```python
# tests/test_cost_render.py
import datetime as dt
import re

from scripts.ops import cost_billing as b
from scripts.ops import cost_cloudflare as c
from scripts.ops import cost_render as r
from ops_cost_fixtures import DAYS, ODD, month_rows
from ops_cost_fixtures import cf_resp as resp

META = {"made_at": "2026-10-18 21:40 KST", "billing_note": "", "cf_note": "", "font_dir": "fonts"}


def billing():
    return b.summarize(month_rows(), "2026-10", dt.date(2026, 10, 18), 30000)


def cf():
    return c.summarize(resp({d: 5000 for d in DAYS}, {DAYS[3]: 4}, {d: 6000 for d in DAYS}), DAYS)


def test_모든_칸이_나옵니다():
    html = r.render(billing(), cf(), META)
    for h in ("이번 달 요약", "GCP 서비스별 월 비용", "Cloud SQL 세부", "GCP 일별 변동비",
              "Cloudflare 무료 한도 대비 사용량", "CPU 한도 초과로 끊긴 요청", "기준과 주의"):
        assert h in html
    assert "2026-10-18 21:40 KST" in html
    assert "미리보기 목업" not in html and "#demo" not in html


def test_자리_표시자가_남지_않습니다():
    html = r.render(billing(), cf(), META)
    assert not re.search(r"\$[a-z_]+", html.split("<script>")[0])


def test_모르는_SKU_를_주의에_적습니다():
    html = r.render(billing(), cf(), META)
    assert ODD in html and "변동비로 넣은" in html


def test_Cloudflare_가_없으면_그_칸만_안내합니다():
    html = r.render(billing(), None, dict(META, cf_note="토큰 없음: ~/.bstats/cf_analytics_token.txt"))
    assert "토큰 없음" in html and "GCP 서비스별 월 비용" in html
    assert "Workers 요청 수" not in html


def test_결제가_없으면_그_칸만_안내합니다():
    html = r.render(None, cf(), dict(META, billing_note="내보내기 데이터 없음"))
    assert "내보내기 데이터 없음" in html and "Workers 요청 수" in html


def test_글자를_이스케이프합니다():
    rows = month_rows() + [{"month": "202610", "service": "Cloud SQL", "sku": "<b>x</b>",
                            "day": dt.date(2026, 10, 2), "currency": "KRW", "net": 1}]
    s = b.summarize(rows, "2026-10", dt.date(2026, 10, 18), 30000)
    html = r.render(s, None, META)
    assert "<b>x</b>" not in html and "&lt;b&gt;x&lt;/b&gt;" in html


def test_한도선은_규칙대로만_그립니다():
    html = r.render(None, cf(), META)
    assert 'class="limit"' not in html
    big = {d: 1000 for d in DAYS}
    big[DAYS[1]] = 70_000
    html2 = r.render(None, c.summarize(resp(big), DAYS), META)
    assert 'class="limit"' in html2
```

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_cost_render.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 틀과 `cost_render.py` 를 만듭니다**

틀: 참고 파일을 복사한 뒤 세 군데를 바꿉니다.

```bash
cp docs/superpowers/plans/assets/2026-10-18-data-ops/cost_report_mock_template.html scripts/ops/cost_report_template.html
```

1. `<body>` 바로 아래 `<div class="wrap">` 부터 `<script>` 바로 앞 `</div>` 까지를 통째로 아래로 바꿉니다.

```html
<div class="wrap">
  <header>
    <div>
      <span class="priv">비공개 · evan 님 PC 전용</span>
      <h1>bstats 비용 보고서</h1>
      <div class="sub">GCP · Cloudflare 무료 플랜 · $month_label</div>
    </div>
    <div class="meta">만든 시각 $made_at</div>
  </header>
  $billing_html
  $cf_html
  <section>
    <h2>기준과 주의</h2>
    <ul class="notes">$notes_html</ul>
  </section>
</div>
```

2. `<script>` 안의 `// 미리보기 캡처용` 주석부터 그 `if (location.hash === '#demo') { … }` 덩어리 끝까지 지웁니다.
3. `<script>` 안의 `var COLORS = $colors_json;` 는 그대로 둡니다. 틀 안의 다른 `$` 는 정규식 끝 `$$/` 하나뿐입니다(그대로 둠).

`scripts/ops/cost_render.py`:

```python
# -*- coding: utf-8 -*-
"""비용 보고서 HTML 을 그립니다(인라인 SVG, 툴팁).

모양과 툴팁 문구는 미리보기 3차안(docs/superpowers/plans/assets/2026-10-18-data-ops/)
그대로입니다. 숫자는 cost_billing.summarize·cost_cloudflare.summarize 의 dict 입니다.
둘 중 하나가 None 이면 그 칸만 안내 글로 바꿉니다.
"""
import datetime as dt
import html
import json
import math
from pathlib import Path
from string import Template

from scripts.ops import cost_cloudflare as cfm
from scripts.ops.cost_billing import VAR_KEYS

TEMPLATE = Path(__file__).with_name("cost_report_template.html")
WD = "월화수목금토일"
MCOLOR = {"Cloud SQL": "#3b82f6", "BigQuery": "#8b5cf6", "Cloud Monitoring": "#10b981", "기타": "#94a3b8"}
VCOLOR = {"백업·PITR 로그": "#3b82f6", "네트워크": "#0ea5e9", "BigQuery": "#8b5cf6", "기타": "#94a3b8"}


def _e(s):
    return html.escape(str(s), quote=True)


def _won(v):
    return f"{v:,.0f}"


def _tip(*lines):
    return f' tabindex="0" data-tip="{_e(chr(10).join(lines))}"'


def _info(*lines):
    return f'<span class="info"{_tip(*lines)}>i</span>'


def _nice_ceil(v):
    if v <= 0:
        return 1
    e = 10 ** math.floor(math.log10(v))
    for m in (1, 2, 2.5, 5, 10):
        if m * e >= v:
            return m * e
    return 10 * e


def _dlabel(day):
    d = dt.date.fromisoformat(day) if isinstance(day, str) else day
    return f"{d.isoformat()} ({WD[d.weekday()]})"


# ---- GCP ----------------------------------------------------------------

def _summary(b):
    return (
        '<section><h2>이번 달 요약 '
        + _info("이번 달 요약", "GCP 에서 이번 달에 나간 돈을 세 가지로 봅니다.",
                "모든 금액은 크레딧을 뺀 순액(원)입니다.",
                "순액 = 비용 + 크레딧 합계(크레딧은 음수로 들어옵니다).")
        + '</h2><p class="h2sub">GCP 금액은 크레딧을 뺀 순액(원)입니다.</p><div class="tiles">'
        + '<div class="tile"><div class="k">이번 달 누적 '
        + _info("이번 달 누적", "1일부터 결제 데이터가 들어온 마지막 시각까지 GCP 순액을 더한 값입니다.",
                "계산식: 1일부터 마지막 반영 시각까지 (비용 + 크레딧) 합계",
                "결제 데이터는 몇 시간에서 하루 늦게 들어오므로 오늘 쓴 돈은 아직 덜 잡혀 있습니다.")
        + f'</div><div class="v">{_won(b["total"])}<small>원</small></div>'
        + f'<div class="f">{b["month"]} 1일 ~ {b["days_elapsed"]}일 · 하루 평균 {_won(b["avg_per_day"])}원</div></div>'
        + '<div class="tile"><div class="k">월말 예상 (단순 추정) '
        + _info("월말 예상 (단순 추정)", "지금까지의 하루 평균이 월말까지 이어진다고 보고 곱한 값입니다.",
                f"계산식: 누적 ÷ 지난 날 수({b['days_elapsed']}) × 그 달 일수({b['days_in_month']})",
                "학습 기간: 이번 달 1일 ~ 마지막 반영일. 예측 범위: 이번 달 말일까지.",
                "DB 사양 변경, 새 서비스 추가, 백업 증가처럼 쓰임이 바뀌면 맞지 않습니다. 오차 범위는 따로 계산하지 않습니다.")
        + f'</div><div class="v">{_won(b["forecast"])}<small>원</small></div>'
        + f'<div class="f">누적 ÷ 지난 날 수({b["days_elapsed"]}) × 그 달 일수({b["days_in_month"]})</div></div>'
        + '<div class="tile"><div class="k">예산 대비 '
        + _info("예산 대비", "이번 달 누적이 월 예산의 몇 % 인지 봅니다.",
                f"계산식: 누적 ÷ {_won(b['budget'])}원 × 100 (월말 예상 기준: 월말 예상 ÷ {_won(b['budget'])}원 × 100)",
                "GCP 예산 알림은 이와 별도로 50·90·100% 에서 메일로 옵니다.")
        + f'</div><div class="v">{b["ratio_pct"]}<small>%</small></div>'
        + f'<div class="gauge"><span style="width:{min(b["ratio_pct"], 100)}%"></span></div>'
        + f'<div class="f">누적 ÷ 월 예산 {_won(b["budget"])}원 · 월말 예상 기준 {b["forecast_ratio_pct"]}%</div></div>'
        + '</div></section>')


def _month_row(m, budget):
    tot = m["total"]
    label = m["month"] + (" (진행 중)" if m["partial"] else "")
    lines = [label, f"합계 {_won(tot)}원 · 예산의 {tot / budget * 100:.1f}%"]
    lines += [f"{k}\t{_won(m[k])}원" for k in MCOLOR]
    lines.append(f"=합계\t{_won(tot)}원")
    if m["partial"]:
        lines.append("진행 중인 달입니다. 결제 데이터가 들어온 마지막 날까지의 값입니다.")
    cells = "".join(f"<td>{_won(m[k])}</td>" for k in MCOLOR)
    return f'<tr{_tip(*lines)}><th scope="row">{_e(label)}</th>{cells}<td class="sum">{_won(tot)}</td></tr>'


HEAD_TIPS = {
    "Cloud SQL": ("Cloud SQL", "bstats 의 MySQL 데이터베이스 비용입니다.",
                  "서버가 켜져 있는 시간, 디스크, 백업, 나가는 트래픽이 모두 이 칸에 들어갑니다. 오른쪽 '세부' 표에서 나눠 봅니다."),
    "BigQuery": ("BigQuery", "주간 복사본과 결제 내보내기 표의 저장·조회 비용입니다.",
                 "무료 한도(저장 10GB, 조회 월 1TB) 안이면 0원입니다.", "0원이 아니면 큰 조회가 있었는지 확인할 대상입니다."),
    "Cloud Monitoring": ("Cloud Monitoring", "가동 확인과 경보의 비용입니다.", "무료 한도 안이면 0원입니다."),
    "기타": ("기타", "위 세 서비스 밖의 비용입니다.", "꾸준히 0원이 아니면 무엇이 붙는지 확인할 대상입니다."),
}


def _months(b):
    th = "".join("<th>%s%s</th>" % ("Monitoring" if k == "Cloud Monitoring" else k, _info(*HEAD_TIPS[k]))
                 for k in MCOLOR)
    rows = "".join(_month_row(m, b["budget"]) for m in b["months"])
    return (
        '<section><h2>GCP 서비스별 월 비용 '
        + _info("GCP 서비스별 월 비용", "달마다 서비스별 순액을 원 단위로 더한 표입니다.",
                "결제 내보내기를 켠 뒤 들어온 달만 나옵니다. 그 전 달은 결제 콘솔에서 확인하십시오.")
        + '</h2><p class="h2sub">단위: 원 · 결제 내보내기를 켠 뒤 들어온 달만 나옵니다.</p>'
        + f'<table><thead><tr><th>월</th>{th}<th>합계'
        + _info("합계", "그 달 네 칸을 더한 순액입니다.", "계산식: Cloud SQL + BigQuery + Monitoring + 기타")
        + f'</th></tr></thead><tbody>{rows}</tbody></table></section>')


def _skus(b):
    total = sum(x["amount"] for x in b["sql_skus"])
    rows = []
    for x in b["sql_skus"]:
        tip = _info(x["sku"], f"{_won(x['amount'])}원 · Cloud SQL 의 {x['share_pct']}% · {x['kind']}비",
                    "고정비는 매일 같은 금액이 붙는 항목, 변동비는 쓰임에 따라 달라지는 항목입니다.",
                    f"비중 = {_won(x['amount'])} ÷ {_won(total)} × 100")
        kcls = "fx" if x["kind"] == "고정" else "vr"
        rows.append(f'<tr><th scope="row">{_e(x["sku"])} <span class="kind {kcls}">{x["kind"]}</span></th>'
                    f'<td>{_won(x["amount"])}</td><td><div class="bar"><span style="width:{x["share_pct"]}%"></span></div></td>'
                    f'<td>{x["share_pct"]}% {tip}</td></tr>')
    return (
        '<section><h2>Cloud SQL 세부 '
        + _info("Cloud SQL 세부", "Cloud SQL 비용을 요금 항목(SKU)별로 나눈 표입니다.",
                "DB 사양을 바꿀지, 디스크를 줄일지 판단할 때 씁니다.")
        + f'</h2><p class="h2sub">합계 {_won(total)}원 · 비중 = 그 항목 금액 ÷ Cloud SQL 합계 × 100</p>'
        + '<table><thead><tr><th>항목</th><th>금액</th><th></th><th>비중</th></tr></thead>'
        + f'<tbody>{"".join(rows)}</tbody></table></section>')


def _var_chart(b, w=1080, h=210):
    days = b["daily"]
    pad_l, pad_r, pad_t, pad_b = 48, 12, 12, 34
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    vsum = [sum(d[k] for k in VAR_KEYS) for d in days]
    vmax = _nice_ceil(max(vsum + [1]) * 1.1)
    n = len(days)
    bw = iw / n * 0.68
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="GCP 일별 변동비">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 8}" y="{y + 4:.1f}" class="ax" text-anchor="end">{g:,.0f}</text>')
    my = pad_t + ih - ih * b["var_median"] / vmax
    out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{my:.1f}" y2="{my:.1f}" class="med"/>')
    hits = []
    for i, d in enumerate(days):
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        y0 = pad_t + ih
        for key in VAR_KEYS:
            v = d[key]
            if v <= 0:
                continue
            hh = ih * v / vmax
            y0 -= hh
            op = ' opacity="0.35"' if d["partial"] else ''
            out.append(f'<rect x="{x:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{hh:.1f}" fill="{VCOLOR[key]}"{op} rx="1.5"/>')
        if i % 3 == 0 or d["partial"]:
            out.append(f'<text x="{x + bw / 2:.1f}" y="{h - 14}" class="ax" text-anchor="middle">'
                       f'{int(d["day"][5:7])}/{int(d["day"][8:])}</text>')
        vs = vsum[i]
        if d["partial"]:
            second = "집계 중: 결제 데이터가 아직 다 들어오지 않았습니다."
        elif b["var_median"]:
            second = f"변동비 {_won(vs)}원 · 지난 29일 중앙값의 {vs / b['var_median'] * 100:.0f}%"
        else:
            second = f"변동비 {_won(vs)}원"
        lines = [_dlabel(d["day"]), second]
        lines += [f"{k}\t{_won(d[k])}원" for k in VAR_KEYS]
        lines += [f"=변동비 합계\t{_won(vs)}원", f"고정비\t{_won(d['fixed'])}원",
                  f"=그날 전체\t{_won(vs + d['fixed'])}원"]
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" '
                    f'height="{ih}" data-tip="{_e(chr(10).join(lines))}"/>')
    out.append(f'<text x="{w - pad_r}" y="{h - 1}" class="ax note" text-anchor="end">집계 중</text>')
    out += hits
    out.append('</svg>')
    return "".join(out)


def _daily(b):
    past = b["daily"][:-1]
    avg_all = sum(d["fixed"] + sum(d[k] for k in VAR_KEYS) for d in past) / len(past)
    share = round(b["fixed_per_day"] / avg_all * 100) if avg_all else 0
    legend = "".join(f'<span class="lg"><i style="background:{c}"></i>{k}</span>' for k, c in VCOLOR.items())
    legend += f'<span class="lg"><i class="dash"></i>점선: 지난 29일 변동비 중앙값 {_won(b["var_median"])}원</span>'
    return (
        '<section><h2>GCP 일별 변동비 (최근 30일) '
        + _info("GCP 일별 변동비",
                "날마다 달라지는 비용만 쌓은 막대입니다. 매일 같은 고정비는 위 회색 줄에 따로 적었습니다.",
                "변동비 = 백업·PITR 로그 + 네트워크 + BigQuery + 기타",
                "점선은 지난 29일 변동비의 중앙값입니다. 막대가 점선보다 훨씬 높은 날은 재적재·큰 복사·큰 조회가 있었는지 확인할 날입니다.",
                "날짜는 결제 데이터의 사용 시작 시각을 KST 로 바꾼 날 기준입니다. 오늘 칸은 결제 데이터가 아직 다 들어오지 않아 흐리게 그립니다.")
        + '</h2><p class="h2sub">단위: 원/일 · 막대에 마우스를 올리면 그날 고정비를 더한 전체 금액도 나옵니다.</p>'
        + '<div class="fixline"><span class="kind fx">고정</span><span>Cloud SQL 고정 항목 '
        + f'<b>하루 {_won(b["fixed_per_day"])}원</b> · 지난 29일 평균 · 하루 비용의 약 {share}% '
        + _info("고정비", "Cloud SQL 인스턴스 시간과 디스크 저장소처럼 매일 같은 금액이 붙는 항목입니다. 막대에서 뺐습니다.",
                "비율 계산식: 고정비 ÷ 지난 29일 하루 평균 전체 비용 × 100",
                "이 줄이 바뀌면 DB 사양이나 디스크 크기가 바뀐 것입니다.")
        + f'</span></div><div class="legend">{legend}</div>{_var_chart(b)}</section>')


def _billing_html(b, note):
    if b is None:
        return f'<section><h2>GCP 비용</h2><p class="h2sub">{_e(note)}</p></section>'
    return _summary(b) + f'<div class="two">{_months(b)}{_skus(b)}</div>' + _daily(b)


# ---- Cloudflare -----------------------------------------------------------

def _usage_chart(vals, days, limit, show_limit, color, label, unit, tipfn=None, w=360, h=170):
    pad_l, pad_r, pad_t, pad_b = 40, 8, 10, 24
    iw, ih = w - pad_l - pad_r, h - pad_t - pad_b
    peak = max(vals + [0])
    vmax = limit if show_limit else _nice_ceil(peak * 1.1)
    if not show_limit and peak <= 40:
        vmax = max(4, math.ceil(peak * 1.1 / 4) * 4)  # 건수가 작으면 눈금을 정수로
    n = len(vals)
    bw = iw / n * 0.66

    def fmt(v):
        return f"{v / 1000:g}천" if v >= 1000 else f"{v:g}"
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="{_e(label)}">']
    for k in range(5):
        g = vmax * k / 4
        y = pad_t + ih - ih * g / vmax
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>')
        out.append(f'<text x="{pad_l - 6}" y="{y + 4:.1f}" class="ax" text-anchor="end">{fmt(g)}</text>')
    if show_limit:
        out.append(f'<line x1="{pad_l}" x2="{w - pad_r}" y1="{pad_t}" y2="{pad_t}" class="limit"/>')
    imax = max(range(n), key=lambda i: vals[i])
    avg = sum(vals) / n
    hits = []
    for i, v in enumerate(vals):
        x = pad_l + iw / n * i + (iw / n - bw) / 2
        hh = ih * v / vmax
        out.append(f'<rect x="{x:.1f}" y="{pad_t + ih - hh:.1f}" width="{bw:.1f}" height="{hh:.1f}" '
                   f'fill="{color}" opacity="{1 if i == imax else 0.72}" rx="1.5"/>')
        d = days[i]
        if tipfn:
            lines = tipfn(i, v, avg, i == imax)
        else:
            lines = [f"{d.isoformat()} (UTC, {WD[d.weekday()]})", f"{v:,}{unit} · 무료 한도의 {v / limit * 100:.1f}%",
                     f"30일 평균 {avg:,.0f}{unit}" + (" · 30일 중 가장 많은 날" if i == imax else ""),
                     f"남은 여유: {limit - v:,}{unit}"]
        hits.append(f'<rect class="hit" x="{pad_l + iw / n * i:.1f}" y="{pad_t}" width="{iw / n:.1f}" '
                    f'height="{ih}" data-tip="{_e(chr(10).join(lines))}"/>')
    for i, anchor in ((0, "start"), (n // 2, "middle"), (n - 1, "end")):
        x = {"start": pad_l, "middle": pad_l + iw / n * i + iw / n / 2, "end": w - pad_r}[anchor]
        out.append(f'<text x="{x:.1f}" y="{h - 6}" class="ax" text-anchor="{anchor}">{days[i].month}/{days[i].day}</text>')
    out += hits
    out.append('</svg>')
    return "".join(out)


def _gauge(peak, limit, unit):
    pct = peak / limit * 100
    tip = _tip("무료 한도까지 거리", f"30일 중 가장 많은 날 {peak:,}{unit} = 한도 {limit:,}{unit} 의 {pct:.1f}%",
               "계산식: 가장 많은 날 값 ÷ 하루 무료 한도 × 100",
               f"이 비율이 {cfm.LIMIT_LINE_AT * 100:.0f}% 를 넘으면 아래 차트 세로축을 한도까지 늘리고 빨간 한도 선을 그립니다.")
    return (f'<div class="lim"{tip}><div class="limbar"><span style="width:{min(pct, 100):.1f}%"></span></div>'
            f'<div class="limtxt"><b>최고 {pct:.1f}%</b><span>한도 {limit:,}/일</span></div></div>')


def _cf_html(c, note):
    if c is None:
        return f'<section><h2>Cloudflare 무료 한도 대비 사용량</h2><p class="h2sub">{_e(note)}</p></section>'
    days = c["days"]

    def cut_tip(i, v, avg, is_max):
        d = days[i]
        req = c["requests"][i]
        return [f"{d.isoformat()} (UTC, {WD[d.weekday()]})",
                f"끊긴 요청 {v}건 · 그날 요청의 {v / req * 100:.3f}%" if req else f"끊긴 요청 {v}건",
                f"그날 요청 {req:,}건 · CPU P99 {c['p99_by_day'][i]}ms",
                f"30일 평균 {avg:.1f}건" + (" · 30일 중 가장 많은 날" if is_max else "")]
    req_svg = _usage_chart(c["requests"], days, cfm.WORKERS_FREE_PER_DAY, c["show_limit_line"]["requests"],
                           "#f59e0b", "Workers 요청 수", "건")
    hyd_svg = _usage_chart(c["queries"], days, cfm.HYPERDRIVE_FREE_PER_DAY, c["show_limit_line"]["queries"],
                           "#0ea5e9", "Hyperdrive 질의 수", "건")
    cut_svg = _usage_chart(c["cut"], days, None, False, "#ef4444", "CPU 한도 초과로 끊긴 요청", "건", tipfn=cut_tip)
    ci = max(range(len(days)), key=lambda i: c["cut"][i])
    times = c["cpu_p99_ms"] / cfm.CPU_LIMIT_MS
    rp, hp = c["req_peak_day"], c["hyd_peak_day"]
    return (
        '<section><h2>Cloudflare 무료 한도 대비 사용량 (최근 30일) '
        + _info("Cloudflare 무료 한도 대비 사용량",
                "bstats API 는 Cloudflare 무료 플랜이라 금액은 0원입니다. 대신 하루 한도를 넘으면 그날 남은 요청이 오류가 되므로 한도까지 얼마나 남았는지 봅니다.",
                "회색 게이지가 30일 중 가장 많은 날이 한도의 몇 % 였는지 보여 줍니다. 가운데 점선이 50% 입니다.",
                "차트 세로축은 실제 값에 맞춰 날마다의 차이가 보이게 했습니다. 가장 많은 날이 한도의 50% 를 넘으면 세로축을 한도까지 늘리고 빨간 한도 선을 그립니다.",
                "날짜는 Cloudflare 집계 기준인 UTC 하루입니다(KST 오전 9시에 바뀝니다).")
        + '</h2><p class="h2sub">금액은 0원(무료 플랜)입니다. 게이지 = 한도까지 거리, 차트 = 날마다의 변화(세로축은 실제 값). 날짜 기준 UTC 하루.</p>'
        + '<div class="cf">'
        + f'<div class="cfbox"><h3>Workers 요청 수 · {cfm.WORKER} '
        + _info("Workers 요청 수", f"bstats API Worker({cfm.WORKER})가 처리한 요청 수입니다.",
                "화면 한 번 열 때 보통 여러 건이 나갑니다.",
                f"무료 플랜 한도: 하루 {cfm.WORKERS_FREE_PER_DAY:,}건. 넘으면 그날 남은 요청이 오류로 돌아갑니다.")
        + f'</h3><div class="peak">가장 많은 날 <b>{rp.month}/{rp.day} · {c["req_peak"]:,}건</b><br>막대에 마우스를 올리면 그날 값이 나옵니다.</div>'
        + _gauge(c["req_peak"], cfm.WORKERS_FREE_PER_DAY, "건") + req_svg + '</div>'
        + '<div class="cfbox"><h3>Hyperdrive 질의 수 '
        + _info("Hyperdrive 질의 수", "Worker 가 Hyperdrive 를 거쳐 MySQL 에 보낸 질의 수입니다. Hyperdrive 캐시에서 바로 답한 질의도 포함합니다.",
                "무료 플랜 하루 한도 기준입니다. 한도 값은 Cloudflare 안내에 따라 바뀔 수 있습니다.")
        + f'</h3><div class="peak">가장 많은 날 <b>{hp.month}/{hp.day} · {c["hyd_peak"]:,}건</b><br>요청 1건이 질의 여러 건을 부르기도 합니다.</div>'
        + _gauge(c["hyd_peak"], cfm.HYPERDRIVE_FREE_PER_DAY, "건") + hyd_svg + '</div>'
        + '<div class="cfbox"><h3>CPU 한도 초과로 끊긴 요청 '
        + _info("CPU 한도 초과로 끊긴 요청",
                f"CPU 한도(요청당 {cfm.CPU_LIMIT_MS}ms)를 넘어 Cloudflare 가 중간에 멈춘 요청 수입니다. 이 요청은 사용자 화면에 오류나 빈칸으로 보입니다.",
                "끊긴 비율 = 30일 끊긴 요청 ÷ 30일 전체 요청 × 100",
                "CPU 중앙값·P99 는 요청 하나가 Worker 에서 쓴 CPU 시간입니다(MySQL 응답을 기다린 시간은 빠짐). P99 는 가장 무거운 1% 의 경계입니다.",
                "무료 플랜은 가끔 넘는 요청을 봐주기도 해서, P99 가 한도를 넘어도 끊긴 요청은 적게 나올 수 있습니다.")
        + f'</h3><div class="stats"><span>30일 <b class="hot">{c["cut_total"]}건</b></span>'
        + f'<span>전체의 <b>{c["cut_pct"]}%</b></span><span>CPU 중앙값 <b>{c["cpu_p50_ms"]}ms</b></span>'
        + f'<span>P99 <b>{c["cpu_p99_ms"]}ms</b> (한도의 {times:.1f}배)</span></div>'
        + f'<div class="limnone">한도 없음: 0건이 목표입니다 · 가장 많은 날 {days[ci].month}/{days[ci].day} {c["cut"][ci]}건</div>'
        + cut_svg + '</div></div></section>')


def _notes_html(b, c):
    notes = ["GCP: 결제 빅쿼리 내보내기(표준 사용 비용) 기준입니다. 결제 데이터는 몇 시간에서 하루 늦게 들어옵니다.",
             "내보내기를 켜기 전 기간은 비어 있을 수 있습니다. 그 기간은 결제 콘솔에서 확인하십시오.",
             "Cloudflare: GraphQL 분석 API 기준입니다. 무료 한도 값은 코드 상수(확인 날짜 주석)를 따르며 바뀔 수 있습니다."]
    if b:
        if b["unknown_sql_skus"]:
            notes.append("고정비 목록에 없어 변동비로 넣은 Cloud SQL 항목: " + ", ".join(b["unknown_sql_skus"]))
        if b["currencies"]:
            notes.append("원 말고 다른 통화가 있습니다: " + ", ".join(b["currencies"]))
        notes.append("이번 달 Cloud SQL 항목 분류: " + "; ".join(f"{x['sku']} = {x['kind']}" for x in b["sql_skus"]))
    return "".join(f"<li>{_e(n)}</li>" for n in notes)


def render(billing, cf, meta):
    month = billing["month"] if billing else ""
    tpl = Template(TEMPLATE.read_text(encoding="utf-8"))
    return tpl.substitute(
        month_label=_e(f"{month[:4]}년 {int(month[5:7])}월" if month else ""),
        made_at=_e(meta["made_at"]),
        billing_html=_billing_html(billing, meta.get("billing_note", "")),
        cf_html=_cf_html(cf, meta.get("cf_note", "")),
        notes_html=_notes_html(billing, cf),
        colors_json=json.dumps({**MCOLOR, **VCOLOR, "고정비": "#475569"}, ensure_ascii=False),
    )
```

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_cost_render.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add scripts/ops/cost_render.py scripts/ops/cost_report_template.html tests/test_cost_render.py
git commit -m "feat(ops): 비용 보고서 그리기(미리보기 3차안, 인라인 SVG·툴팁)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: 실행 `cost_report.py` 와 첫 실제 실행

**Files:**
- Create: `scripts/ops/cost_report.py`
- Test: `tests/test_cost_report.py`

**Interfaces:**
- Consumes: Task 3·4·5.
- Produces: CLI `py -m scripts.ops.cost_report --month 2026-10 [--budget 30000] [--out DIR] [--no-png]`
  - `read_secret(name) -> str | None` — `~/.bstats/<name>` 의 앞뒤 공백 뺀 글자, 없으면 None.
  - `bq_rows(client, table, start) -> list[dict]` — 시험 실행으로 바이트를 먼저 보고 `MAX_BYTES = 50 * 1024 * 1024` 를 넘으면 `RuntimeError`.
  - `cf_fetch(token, acct, days) -> dict` — POST `https://api.cloudflare.com/client/v4/graphql`, 헤더 `Authorization: Bearer <token>`.
  - `out_dir(base, today) -> Path` — 기본 `~/Desktop/bstats_비용보고/<YYYY-MM-DD>/`.
  - `main(argv) -> int`

흐름:
1. 결제: `billing_export_table.txt` 가 없으면 `billing=None, billing_note="결제 내보내기 표 이름이 없습니다(~/.bstats/billing_export_table.txt)"`. 있으면 `gcloud --configuration=bstats auth print-access-token` 으로 토큰을 받아 `google.oauth2.credentials.Credentials(token)` + `bigquery.Client(project="bstats-kbo", credentials=…)`. 질의 시작일 = 30일 전과 그 달 1일 중 이른 날 기준으로 **세 달 전 1일**(월별 표용). 행이 0개면 `billing=None, billing_note="결제 내보내기 데이터가 아직 없습니다. 켠 뒤 몇 시간에서 하루가 걸립니다"`.
2. Cloudflare: 토큰·계정 ID 가 없으면 `cf=None, cf_note="토큰 없음: …"`. 날짜는 UTC 오늘 기준 30일. `SchemaMismatch` 면 `cf=None, cf_note="Cloudflare 응답 모양이 예상과 다릅니다: <메시지>"` 로 두고 끝 값 1 로 끝냄(보고서는 그대로 만듦).
3. `cost_render.render(...)` → `out/report.html`, 저장소의 `dashboard_js/assets/fonts/KBO-Dia-Gothic_*.woff` 를 `out/fonts/` 로 복사.
4. `--no-png` 가 아니면 헤드리스 Edge 로 `out/report.png`. Edge 는 `C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe`, 인자 `--headless=new --no-sandbox --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --virtual-time-budget=7000 --window-size=1200,1900 --user-data-dir=<임시 폴더> --screenshot=<임시 png> file:///<out/report.html>`. 이미 떠 있는 Edge 에 붙지 않도록 `subprocess.run` 으로 새 프로세스, 입출력은 `tempfile.mkdtemp()`(ASCII 경로)에서 하고 끝나면 `shutil.copy` 로 옮깁니다. PNG 가 안 생기면 경고만 찍습니다.
5. 끝에 출력 폴더 경로를 찍습니다.

- [ ] **Step 1: 실패하는 시험을 씁니다**

```python
# tests/test_cost_report.py
import datetime as dt

import pytest

from scripts.ops import cost_report as cr


def test_비밀값_파일이_없으면_None(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "SECRET_DIR", tmp_path)
    assert cr.read_secret("cf_analytics_token.txt") is None
    (tmp_path / "cf_analytics_token.txt").write_text("  abc \n", encoding="utf-8")
    assert cr.read_secret("cf_analytics_token.txt") == "abc"


def test_출력_폴더는_바탕화면_날짜_폴더입니다(tmp_path):
    assert cr.out_dir(tmp_path, dt.date(2026, 10, 18)) == tmp_path / "bstats_비용보고" / "2026-10-18"


class FakeJob:
    def __init__(self, nbytes, rows=()):
        self.total_bytes_processed = nbytes
        self._rows = rows

    def result(self):
        return list(self._rows)


class FakeBQ:
    def __init__(self, nbytes):
        self.nbytes, self.calls = nbytes, []

    def query(self, sql, job_config=None):
        self.calls.append(bool(job_config and job_config.dry_run))
        return FakeJob(self.nbytes, [] if job_config and job_config.dry_run else [{"month": "202610"}])


def test_시험_실행이_50MB_를_넘으면_멈춥니다():
    with pytest.raises(RuntimeError):
        cr.bq_rows(FakeBQ(60 * 1024 * 1024), "p.d.t", dt.date(2026, 7, 1))


def test_시험_실행_뒤에_진짜_질의를_합니다():
    q = FakeBQ(400_000)
    rows = cr.bq_rows(q, "p.d.t", dt.date(2026, 7, 1))
    assert q.calls == [True, False] and rows == [{"month": "202610"}]


def test_토큰이_없어도_보고서를_만듭니다(tmp_path, monkeypatch):
    monkeypatch.setattr(cr, "SECRET_DIR", tmp_path / "secrets")
    code = cr.main(["--month", "2026-10", "--out", str(tmp_path / "o"), "--no-png",
                    "--today", "2026-10-18"])
    html = (tmp_path / "o" / "report.html").read_text(encoding="utf-8")
    assert code == 0
    assert "결제 내보내기 표 이름이 없습니다" in html and "토큰 없음" in html
    assert (tmp_path / "o" / "fonts" / "KBO-Dia-Gothic_bold.woff").exists()


def test_코드에_결제_계정_ID_나_토큰을_넣지_않습니다():
    from pathlib import Path
    for f in Path("scripts/ops").glob("*.py"):
        text = f.read_text(encoding="utf-8")
        assert "gcp_billing_export_v1_" not in text
        assert "Bearer " not in text or "token" in text
```

(`main` 에 시험용 `--today YYYY-MM-DD` 인자를 둡니다. `--out` 을 주면 그 폴더를 그대로 씁니다.)

- [ ] **Step 2: 시험이 실패하는지 봅니다**

Run: `py -m pytest tests/test_cost_report.py -q`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: 구현합니다**

```python
# -*- coding: utf-8 -*-
"""bstats 비공개 비용 보고서를 만듭니다(evan PC 에서 손으로 실행).

    py -m scripts.ops.cost_report --month 2026-10

- GCP: 결제 빅쿼리 내보내기(표준 사용 비용). 표 이름은 ~/.bstats/billing_export_table.txt.
  인증은 개인 gcloud 설정(bstats)의 액세스 토큰입니다. application-default login 은 쓰지 않습니다.
- Cloudflare: GraphQL 분석 API. 토큰·계정 ID 는 ~/.bstats/cf_analytics_token.txt·cf_account_id.txt.
- 출력: 바탕화면/bstats_비용보고/<날짜>/report.html·report.png·fonts/

비밀값은 코드와 출력에 넣지 않습니다. 부분마다 따로 실패합니다(그 칸만 안내 글).
설계: docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §6
"""
import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from scripts.ops import cost_billing, cost_cloudflare, cost_render

ROOT = Path(__file__).resolve().parents[2]
SECRET_DIR = Path.home() / ".bstats"
FONT_SRC = ROOT / "dashboard_js" / "assets" / "fonts"
MAX_BYTES = 50 * 1024 * 1024
CF_URL = "https://api.cloudflare.com/client/v4/graphql"
EDGE = Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe")
KST = dt.timezone(dt.timedelta(hours=9))


def read_secret(name):
    p = SECRET_DIR / name
    if not p.is_file():
        return None
    v = p.read_text(encoding="utf-8").strip()
    return v or None


def out_dir(base, today):
    return Path(base) / "bstats_비용보고" / today.isoformat()


def gcloud_token():
    exe = shutil.which("gcloud") or shutil.which("gcloud.cmd")
    if not exe:
        raise RuntimeError("gcloud 를 찾지 못했습니다")
    r = subprocess.run([exe, "--configuration=bstats", "auth", "print-access-token"],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("gcloud 토큰을 받지 못했습니다(bstats 설정 로그인 확인)")
    return r.stdout.strip()


def bq_client():
    from google.cloud import bigquery
    from google.oauth2.credentials import Credentials
    return bigquery.Client(project="bstats-kbo", credentials=Credentials(gcloud_token()))


def bq_rows(client, table, start):
    """시험 실행으로 읽을 바이트를 보고 MAX_BYTES 안이면 질의합니다."""
    from google.cloud import bigquery
    params = [bigquery.ScalarQueryParameter("start", "DATE", start)]
    sql = cost_billing.billing_sql(table)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(
        dry_run=True, use_query_cache=False, query_parameters=params))
    if dry.total_bytes_processed > MAX_BYTES:
        raise RuntimeError("읽을 데이터가 %.1fMB 로 한도 %dMB 를 넘어 멈췄습니다"
                           % (dry.total_bytes_processed / 1e6, MAX_BYTES // (1024 * 1024)))
    job = client.query(sql, job_config=bigquery.QueryJobConfig(query_parameters=params))
    out = []
    for r in job.result():
        d = dict(r)
        if "net" in d:
            d["net"] = float(d["net"] or 0)
        out.append(d)
    return out


def cf_fetch(token, acct, days):
    body = json.dumps({"query": cost_cloudflare.graphql_query(),
                       "variables": {"acct": acct, "start": days[0].isoformat(),
                                     "end": days[-1].isoformat()}}).encode("utf-8")
    req = urllib.request.Request(CF_URL, data=body, method="POST", headers={
        "Authorization": "Bearer " + token, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as res:
        return json.loads(res.read().decode("utf-8"))


def make_billing(month, today, budget):
    table = read_secret("billing_export_table.txt")
    if not table:
        return None, "결제 내보내기 표 이름이 없습니다(~/.bstats/billing_export_table.txt)"
    first = dt.date(int(month[:4]), int(month[5:7]), 1)
    start = min(first, today - dt.timedelta(days=29))
    start = dt.date(start.year - (start.month <= 3), (start.month - 4) % 12 + 1, 1)  # 세 달 전 1일
    try:
        rows = bq_rows(bq_client(), table, start)
    except Exception as e:  # noqa: BLE001  칸 하나만 안내로 바꿉니다
        return None, "결제 데이터를 읽지 못했습니다: %s" % str(e)[:200]
    if not rows:
        return None, "결제 내보내기 데이터가 아직 없습니다. 켠 뒤 몇 시간에서 하루가 걸립니다"
    return cost_billing.summarize(rows, month, today, budget), ""


def make_cf(utc_today):
    token, acct = read_secret("cf_analytics_token.txt"), read_secret("cf_account_id.txt")
    if not token or not acct:
        return None, "토큰 없음: ~/.bstats/cf_analytics_token.txt·cf_account_id.txt 를 만드십시오", 0
    days = [utc_today - dt.timedelta(days=i) for i in range(29, -1, -1)]
    try:
        return cost_cloudflare.summarize(cf_fetch(token, acct, days), days), "", 0
    except cost_cloudflare.SchemaMismatch as e:
        return None, "Cloudflare 응답 모양이 예상과 다릅니다: %s" % str(e)[:200], 1
    except Exception as e:  # noqa: BLE001
        return None, "Cloudflare 를 읽지 못했습니다: %s" % str(e)[:200], 1


def screenshot(html_path, png_path):
    if not EDGE.exists():
        print("경고: Edge 가 없어 PNG 를 만들지 않았습니다")
        return
    work = Path(tempfile.mkdtemp(prefix="bstats_cost_"))
    try:
        src = work / "report.html"
        shutil.copy(html_path, src)
        shutil.copytree(Path(html_path).parent / "fonts", work / "fonts")
        shot = work / "report.png"
        subprocess.run([str(EDGE), "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
                        "--force-device-scale-factor=1", "--virtual-time-budget=7000",
                        "--window-size=1200,1900", "--user-data-dir=%s" % (work / "ud").as_posix(),
                        "--screenshot=%s" % shot, src.as_uri()],
                       capture_output=True, timeout=120)
        if shot.exists():
            shutil.copy(shot, png_path)
        else:
            print("경고: PNG 를 만들지 못했습니다")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description="bstats 비공개 비용 보고서")
    ap.add_argument("--month", required=True, help="YYYY-MM")
    ap.add_argument("--budget", type=int, default=30000)
    ap.add_argument("--out", default=None, help="출력 폴더(기본: 바탕화면/bstats_비용보고/<오늘>)")
    ap.add_argument("--no-png", action="store_true")
    ap.add_argument("--today", default=None, help="시험용 KST 오늘(YYYY-MM-DD)")
    args = ap.parse_args(argv)

    now = dt.datetime.now(KST)
    today = dt.date.fromisoformat(args.today) if args.today else now.date()
    utc_today = dt.datetime.now(dt.timezone.utc).date() if not args.today else today
    out = Path(args.out) if args.out else out_dir(Path.home() / "Desktop", today)
    out.mkdir(parents=True, exist_ok=True)

    billing, bnote = make_billing(args.month, today, args.budget)
    cf, cnote, code = make_cf(utc_today)
    html = cost_render.render(billing, cf, {"made_at": now.strftime("%Y-%m-%d %H:%M KST"),
                                            "billing_note": bnote, "cf_note": cnote})
    (out / "report.html").write_text(html, encoding="utf-8")
    (out / "fonts").mkdir(exist_ok=True)
    for f in FONT_SRC.glob("KBO-Dia-Gothic_*.woff"):
        shutil.copy(f, out / "fonts" / f.name)
    if not args.no_png:
        screenshot(out / "report.html", out / "report.png")
    print("비용 보고서: %s" % out)
    return code


if __name__ == "__main__":
    sys.exit(main())
```

시험 `test_코드에_결제_계정_ID_나_토큰을_넣지_않습니다` 의 두 번째 단언은 `"Bearer " + token` 처럼 토큰을 변수로만 붙이는지 봅니다(위 코드 그대로면 통과).

- [ ] **Step 4: 시험을 돌립니다**

Run: `py -m pytest tests/test_cost_report.py tests/test_cost_render.py tests/test_cost_billing.py tests/test_cost_cloudflare.py -q`
Expected: 전부 PASS

- [ ] **Step 5: 커밋합니다**

```bash
git add scripts/ops/cost_report.py tests/test_cost_report.py
git commit -m "feat(ops): 비용 보고서 실행(결제 내보내기·Cloudflare 읽기, 바탕화면 날짜 폴더에 HTML·PNG)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 6: 첫 실제 실행(evan 준비가 끝난 뒤, evan 이 보는 앞에서)**

evan 이 설계 §7 의 1·2(결제 내보내기 켜기, Cloudflare 토큰)를 끝냈다고 알려 주면:

Run: `py -m scripts.ops.cost_report --month 2026-10`
확인할 것:
- 결제 칸: '기준과 주의'의 Cloud SQL SKU 목록과 고정/변동 분류를 evan 에게 보여 주고 맞는지 묻습니다. 틀리면 `FIXED_SKU_PATTERNS` 만 고쳐 다시 커밋.
- Cloudflare 칸: `SchemaMismatch` 가 나면 메시지대로 `cost_cloudflare.py` 의 질의·칸 이름을 고치고, 상수 옆 "확인: YYYY-MM-DD" 에 오늘 날짜를 적어 커밋.
- PNG 를 Read 로 열어 눈으로 확인하고 경로를 evan 에게 알립니다.

---

### Task 7: 계보가 그대로인지와 전체 시험

**Files:** 없음(확인만)

- [ ] **Step 1: 계보 결과가 바뀌지 않았는지 봅니다**

Run: `py -m pytest tests/test_lineage.py -q`
Expected: 전부 PASS. 실패하면 이 계획의 어떤 파일이 계보 결과를 바꾼 것이므로 멈추고 evan 에게 알립니다(계획 B 로 옮겨야 함).

- [ ] **Step 2: 전체 시험**

Run: `py -m pytest tests -q` 그리고 `npm test`
Expected: 이 브랜치 시작 때와 같은 결과(새 시험은 모두 통과). 시작 때 이미 실패하던 시험이 있으면 그 이름을 적어 둡니다.

- [ ] **Step 3: 보고**

`git log origin/main..HEAD --oneline` 을 evan 에게 보여 주고 push·병합 여부를 묻습니다. 계획 B 가 끝날 때 같이 올릴지도 묻습니다.
