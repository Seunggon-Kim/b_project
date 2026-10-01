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
