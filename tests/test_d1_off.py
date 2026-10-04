# -*- coding: utf-8 -*-
"""D1 끄기(BSTATS_D1=off)입니다.

D1 무료 읽기 한도가 바닥나 사이트가 멈춘 일이 이어져(2026-10-03), 수집이
MySQL 만 쓰게 했습니다. 스위치는 하나(`d1_load.d1_enabled`)이고, 꺼져
있으면 다음이 지켜져야 합니다.

- D1 에 쓰는 함수(run_d1·run_d1_file·refresh_count)는 wrangler 를 부르지
  않고 "D1 꺼짐" 한 줄만 남깁니다.
- 읽기(query·d1_columns)는 같은 SELECT 를 MySQL 에서 돌리고, D1 이 주던
  파이썬 타입으로 맞춰 돌려줍니다.
- mirror() 는 MySQL 이 유일한 저장소라 실패하면 작업을 실패시킵니다.
- D1 이 있어야만 뜻이 있는 도구(대조 등)는 아예 멈춥니다.
"""
import ast
import datetime
import decimal
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from data_collection import d1_load as dl
from data_collection import mysql_sink as ms

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def d1_off(monkeypatch):
    monkeypatch.setenv(dl.D1_ENV, "off")

    def boom(*a, **k):
        pytest.fail("D1 이 꺼져 있는데 wrangler(subprocess)를 불렀습니다: %r" % (a,))

    monkeypatch.setattr(subprocess, "run", boom)


class FakeCur:
    def __init__(self, con):
        self.con = con
        self.description = [(n,) for n in con.names]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.con.fail:
            raise RuntimeError("boom")
        self.con.log.append((sql, params))

    def fetchall(self):
        return self.con.rows


class FakeCon:
    def __init__(self, names=(), rows=(), fail=False):
        self.names, self.rows, self.fail = list(names), list(rows), fail
        self.log = []
        self.rollbacks = self.closed = self.commits = 0

    def cursor(self):
        return FakeCur(self)

    def rollback(self):
        self.rollbacks += 1

    def commit(self):
        self.commits += 1

    def close(self):
        self.closed += 1


# --- 스위치 ------------------------------------------------------------------

def test_스위치는_없으면_on_입니다(monkeypatch):
    monkeypatch.delenv(dl.D1_ENV, raising=False)
    assert dl.d1_enabled() is True
    monkeypatch.setenv(dl.D1_ENV, " OFF ")
    assert dl.d1_enabled() is False
    monkeypatch.setenv(dl.D1_ENV, "on")
    assert dl.d1_enabled() is True


def test_스위치에_모르는_값이면_멈춥니다(monkeypatch):
    monkeypatch.setenv(dl.D1_ENV, "maybe")
    with pytest.raises(ValueError, match="BSTATS_D1"):
        dl.d1_enabled()


# --- 쓰기는 건너뜁니다 ---------------------------------------------------------

def test_꺼져_있으면_D1_쓰기는_한_줄만_남기고_건너뜁니다(d1_off, tmp_path, capsys):
    f = tmp_path / "x.sql"
    f.write_text("DELETE FROM games;", encoding="utf-8")
    assert dl.run_d1("INSERT INTO meta_job_runs VALUES (1);") == ""
    assert dl.run_d1_file(f, db_name="kbo-pbp-a") == ""
    assert dl.refresh_count("games") is None
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert all(line.startswith("D1 꺼짐: ") for line in lines)
    assert "x.sql" in lines[1] and "kbo-pbp-a" in lines[1]
    assert "meta_table_counts(games)" in lines[2]


def test_켜져_있으면_예전처럼_wrangler_를_부릅니다(monkeypatch):
    monkeypatch.delenv(dl.D1_ENV, raising=False)
    seen = []

    class R:
        returncode, stdout, stderr = 0, "ok", ""

    def fake_run(cmd, **k):
        seen.append(cmd)
        return R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert dl.run_d1("SELECT 1;") == "ok"
    assert seen and seen[0][:5] == ["npx", "--yes", "wrangler@4", "d1", "execute"]


def test_require_d1_은_꺼져_있으면_멈춥니다(monkeypatch):
    monkeypatch.setenv(dl.D1_ENV, "off")
    with pytest.raises(SystemExit, match="D1 이 꺼져"):
        dl.require_d1("대조")
    monkeypatch.setenv(dl.D1_ENV, "on")
    dl.require_d1("대조")


# --- 읽기는 MySQL 에서 합니다 ---------------------------------------------------

def test_끝의_세미콜론을_떼고_큰따옴표_이름을_백틱으로_바꿉니다():
    sql, params = dl.to_mysql('SELECT "a", b FROM "play_by_play" WHERE x = 1;;  ')
    assert sql == "SELECT `a`, b FROM `play_by_play` WHERE x = 1"
    assert params is None


def test_작은따옴표_글자_안은_건드리지_않습니다():
    sql, _ = dl.to_mysql("""SELECT "n" FROM t WHERE a = 'say "hi"' AND b = 'it''s' AND c = "d";""")
    assert sql == """SELECT `n` FROM t WHERE a = 'say "hi"' AND b = 'it''s' AND c = `d`"""


def test_이름_안의_큰따옴표와_백틱을_옮깁니다():
    sql, _ = dl.to_mysql('SELECT "a""b", "c`d" FROM t')
    assert sql == "SELECT `a\"b`, `c``d` FROM t"


@pytest.mark.parametrize("sql", [
    "INSERT INTO t VALUES (1)",
    "UPDATE players SET x = 1",
    "DELETE FROM games",
    "INSERT OR REPLACE INTO meta_table_counts SELECT 1",
    "PRAGMA quick_check",
    "CREATE TABLE x (a)",
    "  with t as (select 1) delete from games",
])
def test_SELECT_가_아니면_거절합니다(sql):
    with pytest.raises(ValueError, match="SELECT"):
        dl.to_mysql(sql)


@pytest.mark.parametrize("sql", [
    "SELECT a || b FROM t",
    "SELECT name FROM players WHERE team_id || '' = 'LG'",
    'SELECT "a"||"b" FROM t',
])
def test_글자_밖의_연결_연산자는_거절합니다(sql):
    # SQLite 의 || 는 글자 잇기지만 MySQL 에서는 OR 라 조용히 0·1 이 나옵니다.
    with pytest.raises(ValueError, match="CONCAT"):
        dl.to_mysql(sql)


def test_글자_안의_연결_연산자는_그대로_둡니다():
    sql, _ = dl.to_mysql("SELECT name FROM t WHERE note = 'a||b' OR x = '|'")
    assert sql == "SELECT name FROM t WHERE note = 'a||b' OR x = '|'"


def test_닫히지_않은_큰따옴표는_거절합니다():
    with pytest.raises(ValueError, match="큰따옴표"):
        dl.to_mysql('SELECT "a FROM t')


def test_PRAGMA_table_info_는_information_schema_로_바꿉니다():
    for raw in ('PRAGMA table_info("play_by_play");', "pragma table_info(play_by_play)"):
        sql, params = dl.to_mysql(raw)
        assert "information_schema.columns" in sql
        assert "ORDER BY ORDINAL_POSITION" in sql
        assert "COLUMN_NAME AS name" in sql
        assert params == ["play_by_play"]


def test_sqlite_master_표_있는지_보기는_information_schema_로_바꿉니다():
    sql, params = dl.to_mysql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='self_park_factor';")
    assert "information_schema.tables" in sql and "table_name = %s" in sql
    assert params == ["self_park_factor"]
    sql, params = dl.to_mysql(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;")
    assert "information_schema.tables" in sql and params is None


def test_모르는_sqlite_master_질의는_거절합니다():
    with pytest.raises(ValueError, match="sqlite_master"):
        dl.to_mysql("SELECT tbl_name, sql FROM sqlite_master WHERE type='index'")


def test_MySQL_값을_D1_타입으로_맞춥니다():
    assert dl.d1_value(decimal.Decimal("12")) == 12
    assert isinstance(dl.d1_value(decimal.Decimal("12.000")), int)
    assert dl.d1_value(decimal.Decimal("0.325")) == pytest.approx(0.325)
    assert isinstance(dl.d1_value(decimal.Decimal("0.325")), float)
    assert dl.d1_value(datetime.date(2026, 10, 3)) == "2026-10-03"
    assert dl.d1_value(datetime.datetime(2026, 10, 3, 4, 5, 6)) == "2026-10-03 04:05:06"
    assert dl.d1_value(b"\x00\x01") == b"\x00\x01"
    assert dl.d1_value(None) is None
    assert dl.d1_value("00") == "00"
    assert dl.d1_value(3.5) == 3.5


def test_mysql_query_는_읽기_전용으로_읽고_닫습니다():
    con = FakeCon(names=["n", "d", "s"],
                  rows=[(decimal.Decimal("3"), datetime.date(2026, 10, 3), "가")])
    rows = dl.mysql_query('SELECT COUNT(*) AS n, "d", s FROM t;', connect=lambda: con)
    assert rows == [{"n": 3, "d": "2026-10-03", "s": "가"}]
    assert con.log[0] == ("START TRANSACTION READ ONLY", None)
    assert con.log[1] == ("SELECT COUNT(*) AS n, `d`, s FROM t", None)
    assert con.rollbacks == 1 and con.closed == 1 and con.commits == 0


def test_mysql_query_는_실패해도_연결을_닫습니다():
    con = FakeCon(fail=True)
    with pytest.raises(RuntimeError):
        dl.mysql_query("SELECT 1", connect=lambda: con)
    assert con.closed == 1


def test_꺼져_있으면_query_와_d1_columns_가_MySQL_을_읽습니다(d1_off, monkeypatch):
    con = FakeCon(names=["cid", "name", "type", "notnull", "pk"],
                  rows=[(0, "pbp_id", "int", 1, 1), (1, "gameID", "varchar(32)", 0, 0)])
    monkeypatch.setattr(dl, "_mysql_connect", lambda: con)
    # 샤드 이름(db_name)은 보지 않습니다. MySQL 은 DB 가 하나입니다.
    assert dl.d1_columns("play_by_play", db_name="kbo-pbp-2024-2026") == ["pbp_id", "gameID"]
    assert "information_schema.columns" in con.log[1][0]
    assert con.log[1][1] == ["play_by_play"]

    con2 = FakeCon(names=["team_id"], rows=[("LG",), ("KT",)])
    monkeypatch.setattr(dl, "_mysql_connect", lambda: con2)
    assert dl.query("SELECT team_id FROM teams;") == [{"team_id": "LG"}, {"team_id": "KT"}]


def test_꺼져_있으면_query_에_쓰기_SQL_을_넣어도_MySQL_에_닿지_않습니다(d1_off, monkeypatch):
    monkeypatch.setattr(dl, "_mysql_connect", lambda: pytest.fail("붙으면 안 됩니다"))
    with pytest.raises(ValueError):
        dl.query("DELETE FROM kbo_roster;")


# --- mirror 는 꺼져 있으면 꼭 써야 합니다 --------------------------------------

def test_꺼져_있으면_mirror_모드가_off_여도_씁니다(d1_off, monkeypatch):
    monkeypatch.delenv(ms.MODE_ENV, raising=False)
    con = FakeCon()
    assert ms.mirror("j", lambda s: 5, connect=lambda: con) == 5
    assert con.commits == 1


def test_꺼져_있으면_mirror_실패가_shadow_여도_작업을_실패시킵니다(d1_off, monkeypatch, tmp_path):
    monkeypatch.setenv(ms.MODE_ENV, "shadow")
    log = tmp_path / "fail.jsonl"
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(log))
    con = FakeCon()

    def bad(sink):
        raise RuntimeError("MySQL 이 죽었습니다")

    with pytest.raises(RuntimeError, match="MySQL 이 죽었습니다"):
        ms.mirror("games", bad, connect=lambda: con)
    assert con.rollbacks == 1 and con.commits == 0
    # 실패 기록도 남깁니다. 워크플로의 실패 확인 단계가 이 파일을 봅니다.
    assert json.loads(log.read_text(encoding="utf-8").splitlines()[0])["job"] == "games"


def test_켜져_있으면_mirror_shadow_는_예전처럼_넘어갑니다(monkeypatch, tmp_path):
    monkeypatch.delenv(dl.D1_ENV, raising=False)
    monkeypatch.setenv(ms.MODE_ENV, "shadow")
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(tmp_path / "f.jsonl"))

    def bad(sink):
        raise RuntimeError("x")

    assert ms.mirror("games", bad, connect=FakeCon) is None


# --- 스크립트 단위 --------------------------------------------------------------

def test_대조는_꺼져_있으면_MySQL_에_붙기_전에_멈춥니다(d1_off, monkeypatch):
    from migration.mysql import reconcile
    monkeypatch.setattr(reconcile.myconn, "connect", lambda *a, **k: pytest.fail("붙으면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["reconcile", "--days", "3"])
    with pytest.raises(SystemExit, match="D1 이 꺼져"):
        reconcile.main()


def test_결과_표_올리기는_꺼져_있으면_MySQL_에만_씁니다(d1_off, monkeypatch, tmp_path, capsys):
    from migration import sqlite_to_d1 as m
    db = tmp_path / "k.db"
    con = sqlite3.connect(str(db))
    con.execute('CREATE TABLE "self_park_factor" (season INTEGER, stadium TEXT, pf REAL)')
    con.execute("INSERT INTO self_park_factor VALUES (2026, '잠실', 98.5)")
    con.commit()
    con.close()
    seen = {}

    def fake_mirror(job, fn, required=False):
        seen["job"] = job
        return 1

    monkeypatch.setattr(m, "mirror", fake_mirror)
    monkeypatch.setattr(sys, "argv", ["sqlite_to_d1", "--db", str(db), "--tables",
                                      "self_park_factor"])
    assert m.main() == 0
    assert seen["job"] == "sqlite_push"
    out = capsys.readouterr().out
    assert "D1" not in out and "올림" not in out
    assert "MySQL 반영: self_park_factor" in out


def test_실행_기록은_꺼져_있으면_MySQL_에만_남깁니다(d1_off, monkeypatch, capsys):
    sys.path.insert(0, str(ROOT / "data_collection"))
    import record_job_run as m
    seen = {}
    monkeypatch.setattr(m, "mirror", lambda job, fn: seen.setdefault("job", job))
    monkeypatch.setattr(sys, "argv", ["record_job_run", "--job", "reconcile", "--status", "skip"])
    assert m.main() == 0
    assert seen["job"] == "job_runs"
    assert "D1" not in capsys.readouterr().out


def test_사진_보정_질의는_파생_표에_별칭이_있습니다():
    """MySQL 은 별칭 없는 파생 표를 거절합니다(D1 이 꺼지면 이 질의를 MySQL 이 받음)."""
    sys.path.insert(0, str(ROOT / "data_collection"))
    import heal_player_photos as m
    seen = []
    orig = m.query
    try:
        m.query = lambda sql: seen.append(sql) or [{"s": 2026}]
        m.current_season()
        m.load_players()
    finally:
        m.query = orig
    for sql in seen:
        assert ") AS t" in sql, sql
    # SQLite(D1)에서도 그대로 돕니다.
    con = sqlite3.connect(":memory:")
    con.executescript(
        "CREATE TABLE kbo_official_batter_stats (player_id INTEGER, season INTEGER);"
        "CREATE TABLE kbo_official_pitcher_stats (player_id INTEGER, season INTEGER);"
        "CREATE TABLE players (player_id INTEGER, image_url TEXT);"
        "INSERT INTO players VALUES (1, 'u');"
        "INSERT INTO kbo_official_batter_stats VALUES (1, 2025);"
        "INSERT INTO kbo_official_pitcher_stats VALUES (1, 2026);")
    assert con.execute(seen[0].rstrip(";")).fetchone()[0] == 2026
    assert con.execute(seen[1].rstrip(";")).fetchall() == [(1, "u", 2026)]


# --- 워크플로 수집 스크립트의 실제 질의 -------------------------------------------
#
# 워크플로가 부르는 파이썬 파일에서 `query(...)` 에 넘기는 SQL 글자를 모아,
# 하나하나 MySQL 로 바뀌는지 봅니다. 새 질의가 SQLite 에만 있는 말투(||,
# 별칭 없는 sqlite_master 질의 등)를 쓰면 D1 이 꺼진 날 러너에서야 죽으므로
# 여기서 먼저 잡습니다. `%` 서식 자리는 1 이나 x 로 채웁니다.

_FMT = re.compile(r"%(?:\([^)]*\))?[-#0 +]*\d*(?:\.\d+)?[sdifr%]")
# 글자를 모을 수 없는 곳입니다. 대조는 D1 이 꺼져 있으면 멈춥니다(require_d1).
_DYNAMIC_OK = {"migration/mysql/reconcile.py"}


def _fill(fmt):
    return _FMT.sub(lambda m: {"%": "%", "d": "1", "i": "1", "f": "1.0"}.get(
        m.group(0)[-1], "x"), fmt)


def _const_str(node, consts):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        a, b = _const_str(node.left, consts), _const_str(node.right, consts)
        return None if a is None or b is None else a + b
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Mod):
        a = _const_str(node.left, consts)
        return None if a is None else _fill(a)
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value if isinstance(v, ast.Constant) else "x" for v in node.values)
    return None


def _workflow_scripts():
    sys.path.insert(0, str(ROOT / "scripts"))
    import lineage_extract as lx
    out = set()
    for name in ("daily", "roster", "weekly", "monthly"):
        text = (ROOT / ".github" / "workflows" / (name + ".yml")).read_text(encoding="utf-8")
        out |= {st["script"] for st in lx.parse_workflow(text)["steps"]
                if st["script"].endswith(".py")}
    return sorted(out)


def _collected_queries():
    found, unknown = [], []
    for rel in _workflow_scripts():
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        consts = {}
        for n in tree.body:
            if (isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
                    and isinstance(n.value.value, str)):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        consts[t.id] = n.value.value
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id == "query" and node.args):
                sql = _const_str(node.args[0], consts)
                if sql is None:
                    unknown.append((rel, node.lineno))
                else:
                    found.append((rel, node.lineno, sql))
    return found, unknown


def test_워크플로_수집_스크립트의_질의가_모두_MySQL_로_바뀝니다():
    found, unknown = _collected_queries()
    files = {rel for rel, _, _ in found}
    # 헛돌지 않게, 읽기가 있는 수집 스크립트가 모두 잡혔는지 봅니다.
    for rel in ("data_collection/team_ranks.py", "data_collection/roster_to_d1.py",
                "data_collection/sync_players_from_roster.py",
                "data_collection/add_new_players.py", "data_collection/heal_player_photos.py",
                "data_collection/daily_games_to_d1.py"):
        assert rel in files, rel
    assert len(found) >= 12, found
    assert {rel for rel, _ in unknown} <= _DYNAMIC_OK, unknown
    bad = []
    for rel, line, sql in found:
        try:
            dl.to_mysql(sql)
        except ValueError as e:
            bad.append("%s:%d %s" % (rel, line, e))
    assert not bad, bad
