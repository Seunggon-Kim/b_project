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
    assert len(calls) == 1
    sql, db = calls[0]
    assert db == "kbo-pbp-2024-2026"
    assert "gameID >= '20261003'" in sql and "gameID >= '44441003'" in sql
    assert "ORDER BY pbp_id" in sql and "games" not in sql


def test_d1_day_rows_filters_other_years(monkeypatch):
    rows = [{"gameID": "20261003LGOB0"}, {"gameID": "44441003NCSS02026"},
            {"gameID": "44441003NCSS02025"}, {"gameID": "33331003SSLT0"}]
    monkeypatch.setattr(m, "query", lambda sql, db_name="kbo-stats": rows)
    got = m.d1_day_rows("20261003", "kbo-pbp-2024-2026")
    assert [r["gameID"] for r in got] == ["20261003LGOB0", "44441003NCSS02026"]


def test_mysql_only_stops_on_wrong_dates(monkeypatch):
    monkeypatch.setattr(m, "query", lambda sql, db_name="kbo-stats":
                        [{"gameID": "20091029SKOB0", "game_date": "TOB00929"}])
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("넣으면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20091029", "--mysql-only"])
    assert m.main() == 1
