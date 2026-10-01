import datetime as dt
import sqlite3
from decimal import Decimal
from unittest.mock import MagicMock

from migration.mysql import verify as v


def test_sqlite_side_treats_empty_as_null_and_dot_zero_as_number():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("b" TEXT, "px" REAL, "nm" TEXT)')
    con.executemany("INSERT INTO t VALUES (?,?,?)",
                    [("78513.0", 1.5, ""), ("", "", "가나"), ("12", 2.0, None)])
    exprs = []
    for c, k in [("b", "int"), ("px", "double"), ("nm", "text")]:
        exprs.extend(v.sqlite_expr(c, k))
    row = con.execute("SELECT %s FROM t" % ", ".join(exprs)).fetchone()
    assert row == (2, 78525, 2, 3.5, 2, 2)


def test_mysql_expressions_match_kinds():
    assert v.mysql_expr("px", "double") == ("COUNT(`px`)", "SUM(`px`)")
    assert v.mysql_expr("nm", "text") == ("COUNT(`nm`)", "SUM(CHAR_LENGTH(`nm`))")
    assert v.mysql_expr("d", "date") == \
        ("COUNT(`d`)", "SUM(CAST(DATE_FORMAT(`d`,'%Y%m%d') AS UNSIGNED))")
    assert v.mysql_expr("img", "blob") == ("COUNT(`img`)", "SUM(LENGTH(`img`))")


def test_close_allows_float_noise_only():
    assert v.close(1e12, 1e12 + 0.0001)
    assert v.close(None, 0)
    assert not v.close(100.0, 101.0)


def test_same_sum_is_exact_except_double():
    assert not v.same_sum(81_000_000_000_000, 81_000_000_000_070, "int")
    assert v.same_sum(Decimal("5"), 5, "int")
    assert v.same_sum(1e12, 1e12 + 0.0001, "double")
    assert v.same_sum(None, 0, "text")


def test_sqlite_date_and_datetime_checksums():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("d" TEXT, "dt" TEXT)')
    con.executemany("INSERT INTO t VALUES (?,?)",
                    [("2026-09-30", "2026-09-30 07:31:00"),
                     (" 2026-09-28 ", None),
                     ("", None),
                     ("-", None)])
    d_count, d_sum = con.execute(
        "SELECT %s, %s FROM t" % v.sqlite_expr("d", "date")).fetchone()
    assert (d_count, d_sum) == (2, 40521858)
    dt_count, dt_sum = con.execute(
        "SELECT %s, %s FROM t" % v.sqlite_expr("dt", "datetime")).fetchone()
    assert (dt_count, dt_sum) == (1, 20287990)


def test_sqlite_whitespace_matches_strip():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("i" TEXT)')
    con.executemany("INSERT INTO t VALUES (?)", [("\t",), ("　",), ("12",)])
    count, total = con.execute(
        "SELECT %s, %s FROM t" % v.sqlite_expr("i", "int")).fetchone()
    assert (count, total) == (1, 12)


def test_mysql_expr_for_dates_uses_content():
    d_count, d_sum = v.mysql_expr("d", "date")
    assert "DATE_FORMAT" in d_sum
    dt_count, dt_sum = v.mysql_expr("dt", "datetime")
    assert "TIME_TO_SEC" in dt_sum
    t_count, t_sum = v.mysql_expr("t", "text")
    assert "CHAR_LENGTH" in t_sum


def test_verify_table_reports_missing_snapshot_column():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("a" INTEGER)')
    spec = {"columns": [["a", "int"], ["b", "text"]]}
    fake_my = MagicMock()
    snap_rows, my_rows, problems = v.verify_table(sq, fake_my, "t", spec)
    assert snap_rows == 0
    assert my_rows is None
    assert any("스냅샷에 없는 열: b" in p for p in problems)


def test_same_value():
    assert v.same_value(None, None, "int")
    assert not v.same_value(None, 0, "int")
    assert v.same_value(1, Decimal("1"), "int")
    assert v.same_value(dt.date(2026, 9, 30), "2026-09-30", "date")
    assert v.same_value(1e12, 1e12 + 0.0001, "double")
    assert v.same_value(b"ab", b"ab", "blob")


def test_compare_rows_reports_missing_and_different():
    expected = {(1,): (1, "가"), (2,): (2, "나")}
    actual = {(1,): (1, "다")}
    problems = v.compare_rows(expected, actual, ["x", "nm"], ["int", "text"])
    assert any("가 MySQL 에 없습니다" in p or "(2,)" in p for p in problems)
    assert any("다" in p for p in problems)
    assert len(problems) <= 20


def test_verify_games_groups_binary():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play ("gameID" TEXT)')
    sq.executemany("INSERT INTO play_by_play VALUES (?)", [("G1",), ("G1",), ("G1",)])
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = [(b"G1", 3)]
    fake_cur.__enter__.return_value = fake_cur
    fake_my = MagicMock()
    fake_my.cursor.return_value = fake_cur
    games, bad = v.verify_games(sq, fake_my)
    assert games == 1
    assert bad == []
    assert "AS BINARY" in fake_cur.execute.call_args[0][0]


class PyFakeCursor:
    """PyMySQL-like cursor that formats query with parameters."""
    def __init__(self, handler, log):
        self.handler, self.log, self._rows = handler, log, []
    def __enter__(self): return self
    def __exit__(self, *exc): return False
    def execute(self, query, args=None):
        if args is not None:
            lit = lambda a: "'%s'" % a if isinstance(a, str) else str(a)
            query = query % tuple(lit(a) for a in args)
        self.log.append(query)
        self._rows = list(self.handler(query))
    def fetchone(self): return self._rows[0] if self._rows else None
    def fetchall(self): return self._rows


class PyFakeConn:
    """PyMySQL-like connection."""
    def __init__(self, handler): self.handler, self.log = handler, []
    def cursor(self): return PyFakeCursor(self.handler, self.log)


def test_sample_renumber_path_formats_and_matches():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play ("pbp_id" INTEGER, "x" TEXT)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?)", [(1,"a"), (2,"b"), (3,"c")])
    spec = {"columns": [["pbp_id","int"], ["x","text"]], "renumber": "pbp_id"}

    def handler(query):
        if "COUNT(*)" in query:
            return [(3, 3)]
        return [(1,"a"), (2,"b"), (3,"c")]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "play_by_play", spec)
    assert checked == 3
    assert not problems
    assert note is None
    assert "IN (" in my.log[-1]
    assert "%," not in my.log[-1]


def test_sample_composite_key_uses_row_constructor():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("pid" TEXT, "yr" INTEGER, "v" TEXT)')
    sq.executemany("INSERT INTO t VALUES (?,?,?)", [("62404",2025,"x"), ("62404",2026,"y")])
    spec = {"columns": [["pid","int"], ["yr","int"], ["v","text"]]}

    def handler(query):
        if "information_schema" in query:
            return [("pid",), ("yr",)]
        return [(62404, 2025, "x"), (62404, 2026, "y")]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "t", spec)
    assert checked == 2
    assert not problems
    assert "(`pid`, `yr`) IN ((" in my.log[-1]
    assert "`yr` =" not in my.log[-1]


def test_sample_date_key_matches_date_objects():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("d" TEXT, "v" INTEGER)')
    sq.execute("INSERT INTO t VALUES (?,?)", ("2026-09-30", 1))
    spec = {"columns": [["d","date"], ["v","int"]]}

    def handler(query):
        if "information_schema" in query:
            return [("d",)]
        return [(dt.date(2026, 9, 30), 1)]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "t", spec)
    assert checked == 1
    assert not problems


def test_sample_pk_float_style_id_matches():
    # 스냅샷 기본키가 '78513.0' 같은 글자여도 적재 규칙(normalize)대로 78513 이 됩니다.
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("player_id" TEXT PRIMARY KEY, "v" INTEGER)')
    sq.executemany("INSERT INTO t VALUES (?,?)", [("78513.0", 1), ("62404", 2)])
    spec = {"columns": [["player_id","int"], ["v","int"]], "renumber": None}

    def handler(query):
        if "information_schema" in query:
            return [("player_id",)]
        return [(78513, 1), (62404, 2)]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "t", spec)
    assert checked == 2
    assert not problems
    assert note is None


def test_sample_date_key_with_spaces_matches():
    # 적재 때 앞뒤 공백을 지우므로, 스냅샷 날짜 키도 공백을 지워서 만들어야 합니다.
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("d" TEXT PRIMARY KEY, "v" INTEGER)')
    sq.execute("INSERT INTO t VALUES (?,?)", (" 2026-09-30 ", 1))
    spec = {"columns": [["d","date"], ["v","int"]]}

    def handler(query):
        if "information_schema" in query:
            return [("d",)]
        return [(dt.date(2026, 9, 30), 1)]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "t", spec)
    assert checked == 1
    assert not problems


def test_sample_notes_no_pk_and_empty():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE t ("v" INTEGER)')
    sq.execute("INSERT INTO t VALUES (1)")
    spec = {"columns": [["v","int"]]}

    def handler(query):
        if "information_schema" in query:
            return []
        return [(1,)]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "t", spec)
    assert checked == 0
    assert note == "기본키 없음"

    # Empty renumber case
    sq2 = sqlite3.connect(":memory:")
    sq2.execute('CREATE TABLE pbp ("pbp_id" INTEGER)')
    spec2 = {"columns": [["pbp_id","int"]], "renumber": "pbp_id"}

    def handler2(query):
        if "COUNT(*)" in query:
            return [(0, None)]
        return []

    my2 = PyFakeConn(handler2)
    checked2, problems2, note2 = v.verify_sample(sq2, my2, "pbp", spec2)
    assert checked2 == 0
    assert note2 == "빈 표"
    assert not problems2


def test_sample_reports_difference():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play ("pbp_id" INTEGER, "x" TEXT)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?)", [(1,"a"), (2,"b"), (3,"c")])
    spec = {"columns": [["pbp_id","int"], ["x","text"]], "renumber": "pbp_id"}

    def handler(query):
        if "COUNT(*)" in query:
            return [(3, 3)]
        return [(1,"a"), (2,"z"), (3,"c")]

    my = PyFakeConn(handler)
    checked, problems, note = v.verify_sample(sq, my, "play_by_play", spec)
    assert checked == 3
    # 문제 줄에 키와 열 이름, 예상값('b')과 실제값('z')이 모두 들어 있어야 합니다.
    line = next(p for p in problems if "x" in p)
    assert "(2,)" in line
    assert "'b'" in line and "'z'" in line


def test_verify_games_non_str_snapshot_keys():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play ("gameID" INTEGER)')
    sq.executemany("INSERT INTO play_by_play VALUES (?)", [(5,), (5,)])
    fake_cur = MagicMock()
    fake_cur.fetchall.return_value = [(b"5", 2)]
    fake_cur.__enter__.return_value = fake_cur
    fake_my = MagicMock()
    fake_my.cursor.return_value = fake_cur
    games, bad = v.verify_games(sq, fake_my)
    assert games == 1
    assert bad == []


def test_sqlite_numeric_sum_trims_nbsp():
    con = sqlite3.connect(":memory:")
    con.execute('CREATE TABLE t ("i" TEXT)')
    con.executemany("INSERT INTO t VALUES (?)", [(" 12",), ("14",)])
    count, total = con.execute(
        "SELECT %s, %s FROM t" % v.sqlite_expr("i", "int")).fetchone()
    assert (count, total) == (2, 26)
