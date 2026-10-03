import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import csv_to_d1  # noqa: E402
import daily_games_to_d1  # noqa: E402
import futures_to_d1  # noqa: E402
import record_job_run  # noqa: E402


def test_games(fake_sink):
    assert daily_games_to_d1.mysql_write_games(fake_sink, [{"game_id": "g"}]) == 1
    assert fake_sink.calls[0][:4] == ("upsert", "games", daily_games_to_d1.GAME_COLS, ["game_id"])
    assert fake_sink.calls[1] == ("refresh_count", "games")


def test_futures_keeps_team_columns(fake_sink):
    futures_to_d1.mysql_write_futures(fake_sink, [{"game_id": "f"}])
    call = fake_sink.calls[0]
    assert call[1] == "futures_games" and call[5] is None
    assert call[6] == tuple(futures_to_d1.KEEP)
    assert fake_sink.calls[1] == ("refresh_count", "futures_games")


def test_official_stats_touch_and_keep(fake_sink):
    csv_to_d1.mysql_write_upsert(
        fake_sink, "kbo_official_batter_stats",
        ["player_id", "season", "created_at", "updated_at"], ["player_id", "season"],
        [{}], "updated_at", ["created_at"])
    call = fake_sink.calls[0]
    assert call[5] == "updated_at" and call[6] == ("created_at",)
    assert fake_sink.calls[1] == ("refresh_count", "kbo_official_batter_stats")


def test_job_run(fake_sink):
    row = record_job_run.job_row("pbp", "2026-10-03 03:40", "ok", None, None)
    assert row == {"job": "pbp", "last_run_at": "2026-10-03 03:40", "status": "ok",
                   "note": None, "duration_sec": None}
    record_job_run.mysql_write_job(fake_sink, row)
    assert fake_sink.calls[0][1:5] == ("meta_job_runs", record_job_run.JOB_COLS, ["job"], [row])


def test_scripts_mirror_inside_main():
    for name in ("daily_games_to_d1", "futures_to_d1", "csv_to_d1", "record_job_run"):
        src = (ROOT / "data_collection" / (name + ".py")).read_text(encoding="utf-8")
        assert "from mysql_sink import mirror" in src, name
        assert "mirror(" in src.split("def main", 1)[1], name
