# -*- coding: utf-8 -*-
import sqlite3

import pytest

from migration.export_to_d1 import (
    TABLE_ORDER,
    build_statements,
    export_table,
    missing_from_order,
    rows_to_insert,
    sql_literal,
)


def test_sql_literal_escapes_single_quote():
    assert sql_literal("O'Brien") == "'O''Brien'"


def test_sql_literal_handles_none():
    assert sql_literal(None) == "NULL"


def test_sql_literal_keeps_numbers_unquoted():
    assert sql_literal(3) == "3"
    assert sql_literal(1.5) == "1.5"


def test_rows_to_insert_builds_multi_row_statement():
    sql = rows_to_insert("t", ["a", "b"], [(1, "x"), (2, "y")])
    assert sql.startswith('INSERT INTO "t" ("a","b") VALUES')
    assert "(1,'x')" in sql
    assert "(2,'y')" in sql
    assert sql.endswith(";")


def test_export_table_splits_by_rows_per_file(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.executemany("INSERT INTO t VALUES (?)", [(i,) for i in range(250)])
    pairs = export_table(conn, "t", tmp_path, rows_per_file=100, order=5)
    assert [p.name for p, _ in pairs] == ["05_t_0001.sql", "05_t_0002.sql",
                                          "05_t_0003.sql"]
    assert [n for _, n in pairs] == [100, 100, 50]


def test_export_table_empty_returns_no_files(tmp_path):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    assert export_table(conn, "t", tmp_path, rows_per_file=100, order=5) == []


def test_build_statements_keeps_each_statement_under_limit():
    """D1 은 SQL 문 하나가 100,000 바이트를 넘으면 거부합니다."""
    rows = [("x" * 200,) for _ in range(400)]
    stmts = build_statements("t", ["a"], rows, max_stmt_bytes=10_000)
    assert len(stmts) > 1
    for s in stmts:
        assert len(s.encode("utf-8")) <= 10_000


def test_build_statements_preserves_every_row():
    """문을 나누는 과정에서 행이 사라지면 안 됩니다."""
    rows = [(i, "y" * 50) for i in range(137)]
    stmts = build_statements("t", ["a", "b"], rows, max_stmt_bytes=2_000)
    assert sum(s.count("(") - 1 for s in stmts) == 137


def test_build_statements_rejects_oversized_single_row():
    """한 행이 이미 한도를 넘으면 조용히 넘기지 않고 멈춥니다."""
    with pytest.raises(ValueError, match="한도"):
        build_statements("t", ["a"], [("z" * 5_000,)], max_stmt_bytes=1_000)


def test_export_table_handles_wide_rows(tmp_path):
    """team_logos 처럼 행 하나가 수십 KB 인 테이블도 나눠 담습니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a TEXT)")
    conn.executemany("INSERT INTO t VALUES (?)", [("q" * 40_000,) for _ in range(5)])
    pairs = export_table(conn, "t", tmp_path, rows_per_file=100, order=1)
    assert len(pairs) == 1
    body = pairs[0][0].read_text(encoding="utf-8")
    # 한 문에 두 행까지만 들어가므로 문이 여러 개로 쪼개집니다.
    assert body.count("INSERT INTO") >= 3
    for line in body.splitlines():
        assert len(line.encode("utf-8")) <= 90_000


def test_missing_from_order_reports_unlisted_tables():
    """TABLE_ORDER 에 없는 테이블이 DB 에 있으면 이름을 돌려줍니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE teams (a INTEGER)")
    conn.execute("CREATE TABLE 신규테이블 (a INTEGER)")
    assert missing_from_order(conn) == ["신규테이블"]


def test_missing_from_order_ignores_sqlite_internals():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE teams (a INTEGER PRIMARY KEY AUTOINCREMENT)")
    conn.execute("INSERT INTO teams DEFAULT VALUES")
    assert missing_from_order(conn) == []


def test_table_order_has_no_duplicates():
    assert len(TABLE_ORDER) == len(set(TABLE_ORDER))


def test_play_by_play_is_last():
    """가장 큰 테이블을 마지막에 둬야 앞의 소형 테이블이 먼저 안착합니다."""
    assert TABLE_ORDER[-1] == "play_by_play"
