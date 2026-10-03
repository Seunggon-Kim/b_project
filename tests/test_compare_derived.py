import sqlite3

from migration.mysql import compare_derived as cd


def _db(v, x):
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE t (k INTEGER, v TEXT, x REAL)")
    con.execute("INSERT INTO t VALUES (1, ?, ?)", (v, x))
    con.execute("INSERT INTO t VALUES (2, 'z', 3.0)")
    return con


def test_compare_finds_empty_vs_null():
    probs = cd.compare(_db("", 0.1), _db(None, 0.1), "t")
    assert probs[0].startswith("t: A 에만 1행, B 에만 1행")


def test_compare_ignores_float_noise():
    assert cd.compare(_db("a", 0.1 + 0.2), _db("a", 0.3), "t") == []


def test_compare_reports_missing_table():
    a = _db("a", 1.0)
    b = sqlite3.connect(":memory:")
    assert "한쪽에 표가 없습니다" in cd.compare(a, b, "t")[0]
