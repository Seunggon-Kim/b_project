# -*- coding: utf-8 -*-
import sqlite3

from migration.export_schema import build_schema_sql


def test_drops_before_create():
    """같은 파일을 다시 실행해도 되도록 DROP 이 앞에 옵니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    sql = build_schema_sql(conn)
    assert sql.index("DROP TABLE IF EXISTS \"t\"") < sql.index("CREATE TABLE t")


def test_skips_sqlite_internal_tables():
    """sqlite_sequence 같은 내부 테이블은 직접 만들지 않습니다."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER PRIMARY KEY AUTOINCREMENT)")
    conn.execute("INSERT INTO t DEFAULT VALUES")
    sql = build_schema_sql(conn)
    assert "sqlite_sequence" not in sql


def test_includes_indexes():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER)")
    conn.execute("CREATE INDEX idx_t_a ON t(a)")
    sql = build_schema_sql(conn)
    assert "CREATE INDEX idx_t_a" in sql
