import sqlite3

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
    assert row == (2, 78525.0, 2, 3.5, 2, 2.0)


def test_mysql_expressions_match_kinds():
    assert v.mysql_expr("px", "double") == ("COUNT(`px`)", "SUM(`px`)")
    assert v.mysql_expr("nm", "text") == ("COUNT(`nm`)", "SUM(CHAR_LENGTH(`nm`))")
    assert v.mysql_expr("d", "date") == \
        ("COUNT(`d`)", "SUM(CHAR_LENGTH(CAST(`d` AS CHAR)))")
    assert v.mysql_expr("img", "blob") == ("COUNT(`img`)", "SUM(LENGTH(`img`))")


def test_close_allows_float_noise_only():
    assert v.close(1e12, 1e12 + 0.0001)
    assert v.close(None, 0)
    assert not v.close(100.0, 101.0)
