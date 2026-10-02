import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import daily_pbp_to_d1 as m  # noqa: E402


def test_mysql_write_deletes_day_then_inserts_without_pbp_id(fake_sink):
    rows = [{"pbp_id": "9", "gameID": "20261003LGOB02026", "game_date": "20261003"}]
    assert m.mysql_write_pbp(fake_sink, "20261003", rows) == 1
    assert [c[0] for c in fake_sink.calls] == ["execute", "insert", "refresh_count"]
    _, sql, params = fake_sink.calls[0]
    assert sql == "DELETE FROM `play_by_play` WHERE `game_date` = %s"
    assert params == [20261003]
    _, table, cols, inserted = fake_sink.calls[1]
    assert table == "play_by_play" and "pbp_id" not in cols and "gameID" in cols
    assert inserted == rows


def test_mysql_only_copies_day_from_d1(monkeypatch):
    calls = []

    def fake_query(sql, db_name="kbo-stats"):
        calls.append((sql, db_name))
        if "FROM games" in sql:
            return [{"g": "20261003LGOB02026"}]
        return [{"pbp_id": 7, "gameID": "20261003LGOB02026", "game_date": 20261003}]

    seen = {}

    def fake_mirror(job, fn, required=False):
        seen.update(job=job, required=required)
        return 1

    monkeypatch.setattr(m, "query", fake_query)
    monkeypatch.setattr(m, "mirror", fake_mirror)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: pytest.fail("크롤러를 부르면 안 됩니다"))
    monkeypatch.setattr(m, "run_d1_file", lambda *a, **k: pytest.fail("D1 에 쓰면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20261003", "--mysql-only"])
    assert m.main() == 0
    assert seen == {"job": "pbp", "required": True}
    assert calls[0][1] == "kbo-stats" and "game_date = 20261003" in calls[0][0]
    assert calls[1][1] == "kbo-pbp-2024-2026" and "ORDER BY pbp_id" in calls[1][0]


def test_mysql_only_stops_on_wrong_dates(monkeypatch):
    def fake_query(sql, db_name="kbo-stats"):
        if "FROM games" in sql:
            return [{"g": "33330929LTOB0"}]
        return [{"gameID": "33330929LTOB0", "game_date": "TOB00929"}]

    monkeypatch.setattr(m, "query", fake_query)
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("넣으면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20091029", "--mysql-only"])
    assert m.main() == 1
