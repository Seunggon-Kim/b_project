import collections
import sqlite3

import pytest

from migration.mysql import load


class FakeCursor:
    def __init__(self, log):
        self.log = log

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def executemany(self, sql, rows):
        self.log.append((sql, list(rows)))


class FakeConn:
    def __init__(self):
        self.log = []
        self.commits = 0

    def cursor(self):
        return FakeCursor(self.log)

    def commit(self):
        self.commits += 1


def test_insert_sql_quotes_names():
    assert load.insert_sql("t", ["a", "rank"]) == \
        "INSERT INTO `t` (`a`, `rank`) VALUES (%s, %s)"


def test_convert_row_counts_fixes_and_names_bad_cells():
    fixes = collections.Counter()
    row = load.convert_row(("78513.0", "", "가"), ["int", "double", "text"],
                           ["batter_ID", "px", "nm"], "pbp", fixes)
    assert row == (78513, None, "가")
    assert fixes[("pbp", "batter_ID", "소수점 표기 → 정수")] == 1
    assert fixes[("pbp", "px", "빈 값 → NULL")] == 1
    with pytest.raises(ValueError, match="pbp.batter_ID"):
        load.convert_row(("abc",), ["int"], ["batter_ID"], "pbp", fixes)


def test_load_table_skips_renumbered_column_and_keeps_rowid_order():
    sq = sqlite3.connect(":memory:")
    sq.execute('CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT, px REAL)')
    sq.executemany("INSERT INTO play_by_play VALUES (?,?,?)",
                   [(5, "1.0", 0.5), (1, "2", ""), (5, "3", 1.0)])
    spec = {"columns": [["pbp_id", "int"], ["batter_ID", "int"], ["px", "double"]],
            "renumber": "pbp_id"}
    my = FakeConn()
    fixes = collections.Counter()
    n = load.load_table(sq, my, "play_by_play", spec, fixes, batch=2)
    assert n == 3
    sql, first = my.log[0]
    assert sql == "INSERT INTO `play_by_play` (`batter_ID`, `px`) VALUES (%s, %s)"
    assert first == [(1, 0.5), (2, None)]
    assert my.log[1][1] == [(3, 1.0)]
    assert my.commits == 2


def test_orphan_queries_parse_post_sql():
    post = ("CREATE INDEX `i` ON `t` (`a`);\n"
            "ALTER TABLE `players` ADD CONSTRAINT `fk_players_team_id` FOREIGN KEY "
            "(`team_id`) REFERENCES `teams` (`team_id`);\n")
    (label, sql), = load.orphan_queries(post)
    assert label == "players.team_id → teams.team_id"
    assert "LEFT JOIN `teams` p ON c.`team_id` = p.`team_id`" in sql
    assert "p.`team_id` IS NULL" in sql
