import datetime
import sqlite3

from migration.mysql import mysql_to_sqlite as m


class FakeCur:
    def __init__(self, con):
        self.con = con
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, args=None):
        self.con.log.append(sql)
        if "KEY_COLUMN_USAGE" in sql:
            self.rows = [("game_id",)]
        elif "STATISTICS" in sql:
            self.rows = [("idx_games_date", 1, "game_date")]
        elif sql.startswith("SELECT `game_id`"):
            self.rows = list(self.con.data)
        else:
            self.rows = []

    def fetchall(self):
        rows, self.rows = self.rows, []
        return rows

    def fetchmany(self, n):
        rows, self.rows = self.rows[:n], self.rows[n:]
        return rows


class FakeMy:
    def __init__(self, data):
        self.data, self.log = data, []

    def cursor(self, cls=None):
        return FakeCur(self)


def test_copy_table_keeps_pk_dates_and_indexes():
    spec = {"columns": [["game_id", "text"], ["game_date", "int"], ["as_of", "date"]]}
    my = FakeMy([("g1", 20261003, datetime.date(2026, 10, 3)), ("g2", 20261004, None)])
    sq = sqlite3.connect(":memory:")
    assert m.copy_table(my, sq, "games", spec, batch=1) == 2
    assert sq.execute("SELECT * FROM games ORDER BY game_id").fetchall() == [
        ("g1", 20261003, "2026-10-03"), ("g2", 20261004, None)]
    ddl = sq.execute("SELECT sql FROM sqlite_master WHERE name='games'").fetchone()[0]
    assert 'PRIMARY KEY ("game_id")' in ddl
    assert sq.execute("SELECT 1 FROM sqlite_master WHERE type='index' "
                      "AND name='idx_games_date'").fetchone()
    assert any("ORDER BY `game_id`" in s for s in my.log)


def test_play_by_play_has_no_primary_key():
    ddl = m.sqlite_ddl("play_by_play", {"columns": [["pbp_id", "int"], ["gameID", "text"]]},
                       ["pbp_id"])
    assert "PRIMARY KEY" not in ddl
    assert '"pbp_id" INTEGER' in ddl


def test_to_sqlite_values():
    assert m.to_sqlite(datetime.datetime(2026, 10, 3, 1, 2, 3)) == "2026-10-03 01:02:03"
    assert m.to_sqlite(datetime.date(2026, 10, 3)) == "2026-10-03"
    import decimal
    assert m.to_sqlite(decimal.Decimal("0.5")) == 0.5
