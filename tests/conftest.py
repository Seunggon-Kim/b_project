import pytest


class FakeSink:
    """data_collection.mysql_sink.Sink 를 흉내 냅니다. 부른 순서대로 calls 에 남깁니다."""

    def __init__(self):
        self.calls = []
        self.answers = {}

    def columns(self, table):
        from data_collection import mysql_sink
        return mysql_sink.table_columns(table)

    def value(self, table, column, v):
        from data_collection import mysql_sink
        return mysql_sink.Sink(None).value(table, column, v)

    def execute(self, sql, params=None):
        self.calls.append(("execute", sql, None if params is None else list(params)))
        return 1

    def query(self, sql, params=None):
        self.calls.append(("query", sql, params))
        for piece, rows in self.answers.items():
            if piece in sql:
                return rows
        return []

    def insert(self, table, columns, rows, batch=None):
        rows = list(rows)
        self.calls.append(("insert", table, list(columns), rows))
        return len(rows)

    def upsert(self, table, columns, keys, rows, touch=None, keep=(), batch=None):
        rows = list(rows)
        self.calls.append(("upsert", table, list(columns), list(keys), rows, touch, tuple(keep)))
        return len(rows)

    def insert_missing(self, table, columns, keys, rows, batch=None):
        rows = list(rows)
        self.calls.append(("insert_missing", table, list(columns), list(keys), rows))
        return len(rows)

    def refresh_count(self, table):
        self.calls.append(("refresh_count", table))
        return 0


@pytest.fixture
def fake_sink():
    return FakeSink()
