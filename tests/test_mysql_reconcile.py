import datetime
import decimal

from migration.mysql import reconcile as r


def test_canon_matches_load_rules():
    assert r.canon("") is None and r.canon("-") is None
    assert r.canon(datetime.date(2026, 10, 3)) == "2026-10-03"
    assert r.canon(datetime.datetime(2026, 10, 3, 4, 5, 6)) == "2026-10-03 04:05:06"
    assert r.canon(decimal.Decimal("3.0")) == 3
    assert r.canon(0.1 + 0.2) == 0.3


def test_d1_value_uses_column_kind():
    assert r.d1_value("7.0", "int") == 7
    assert r.d1_value("00", "text") == "00"
    assert r.d1_value("", "int") is None


def test_compare_counts_lists_only_differences():
    assert r.compare_counts({"a": 1, "b": 2}, {"a": 1, "b": 3}) == ["b 행 수: D1 2 / MySQL 3"]


def test_compare_keyed_reports_missing_and_changed():
    kinds = {"player_id": "int", "team_id": "text", "back_number": "int"}
    cols = ["player_id", "team_id", "back_number"]
    d1 = [{"player_id": "1", "team_id": "LG", "back_number": "07"},
          {"player_id": "2", "team_id": "KT", "back_number": None},
          {"player_id": "4", "team_id": "NC", "back_number": "9"}]
    my = [{"player_id": 1, "team_id": "LG", "back_number": 7},
          {"player_id": 3, "team_id": "SS", "back_number": 1},
          {"player_id": 4, "team_id": "NC", "back_number": 10}]
    probs = r.compare_keyed("players", cols, ["player_id"], d1, my, kinds)
    assert any("D1 에만 1행" in p for p in probs)
    assert any("MySQL 에만 1행" in p for p in probs)
    assert any("(4,)" in p and "back_number" in p for p in probs)
    assert len(probs) == 3


def test_count_sql():
    assert r.count_sql(["a", "b"], r.q) == (
        "SELECT 'a' AS t, COUNT(*) AS n FROM `a` UNION ALL "
        "SELECT 'b' AS t, COUNT(*) AS n FROM `b`")


def _run_check(monkeypatch, names):
    d1_sqls, my_sqls = [], []

    def fake(sqls, is_d1):
        def f(*a, **k):
            sql = a[0] if is_d1 else a[1]
            sqls.append(sql)
            if sql.startswith("SELECT '"):
                return [{"t": n, "n": 1} for n in names if "'%s'" % n in sql]
            if "COUNT(*) AS n FROM `play_by_play`" in sql and "gameID" not in sql:
                return [{"n": 0}]
            if "meta_table_counts" in sql:
                return [{"n": 0}]
            return []
        return f
    monkeypatch.setattr(r, "d1_query", fake(d1_sqls, True))
    monkeypatch.setattr(r, "my_query", fake(my_sqls, False))
    types = {n: {"columns": {"a": "int"}} for n in names}
    r.check(None, types, 3)
    count = lambda sqls: [s for s in sqls if s.startswith("SELECT '")]
    return count(d1_sqls), count(my_sqls)


def test_check_skips_record_tables_in_counts(monkeypatch):
    names = ["games", "players", "kbo_roster", "kbo_roster_moves",
             "meta_table_counts", "play_by_play"]
    d1, my = _run_check(monkeypatch, names)
    for sql in d1 + my:
        assert "meta_table_counts" not in sql and "play_by_play" not in sql


def test_check_chunks_d1_count_query(monkeypatch):
    names = ["t%d" % i for i in range(10)] + ["players", "games", "kbo_roster", "kbo_roster_moves"]
    d1, my = _run_check(monkeypatch, names)
    assert all(s.count("UNION ALL") + 1 <= r.D1_UNION_MAX for s in d1)
    for n in names:
        assert sum("'%s' AS t" % n in s for s in d1) == 1
    assert len(my) == 1
