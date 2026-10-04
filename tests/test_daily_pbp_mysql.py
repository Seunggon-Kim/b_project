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


def _day_csv(tmp_path, day, game_date=None):
    """그날 경기 CSV 하나를 크롤러와 같은 자리(<save-dir>/<연도>/)에 둡니다."""
    d = tmp_path / day[:4]
    d.mkdir(parents=True, exist_ok=True)
    (d / (day + "LGOB02026.csv")).write_text(
        "gameID,game_date,pitcher\n%sLGOB02026,%s,가\n" % (day, game_date or day),
        encoding="utf-8")


def test_main_writes_mysql_only(monkeypatch, tmp_path):
    """CSV 를 읽어 mirror 로만 씁니다. SQL 파일을 만들거나 다른 곳에 쓰지 않습니다."""
    _day_csv(tmp_path, "20261003")
    seen = {}

    def fake_mirror(job, fn):
        seen["job"] = job
        return 1

    monkeypatch.setattr(m, "d1_columns", lambda table: ["pbp_id", "gameID", "game_date", "pitcher"])
    monkeypatch.setattr(m, "mirror", fake_mirror)
    monkeypatch.setattr(m.subprocess, "run", lambda *a, **k: pytest.fail("크롤러를 부르면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20261003", "--skip-crawl",
                                      "--save-dir", str(tmp_path)])
    before = sorted(p.name for p in (ROOT / "migration").iterdir())
    assert m.main() == 0
    assert seen == {"job": "pbp"}
    # 예전에는 D1 에 올릴 SQL 파일(migration/daily_pbp.sql)을 만들었습니다.
    assert sorted(p.name for p in (ROOT / "migration").iterdir()) == before


def test_main_dry_run_does_not_write(monkeypatch, tmp_path):
    _day_csv(tmp_path, "20261003")
    monkeypatch.setattr(m, "d1_columns", lambda table: ["pbp_id", "gameID"])
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("미리보기는 쓰면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20261003", "--skip-crawl", "--dry-run",
                                      "--save-dir", str(tmp_path)])
    assert m.main() == 0


def test_main_stops_on_wrong_dates(monkeypatch, tmp_path):
    _day_csv(tmp_path, "20261003", game_date="TOB00929")
    monkeypatch.setattr(m, "d1_columns", lambda table: pytest.fail("멈춰야 합니다"))
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("넣으면 안 됩니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20261003", "--skip-crawl",
                                      "--save-dir", str(tmp_path)])
    assert m.main() == 1


def test_no_game_day_is_ok(monkeypatch, tmp_path):
    """경기가 없는 날은 성공입니다. 새 시즌에 샤드 같은 준비물이 없어도 막지 않습니다."""
    monkeypatch.setattr(m, "mirror", lambda *a, **k: pytest.fail("넣을 것이 없습니다"))
    monkeypatch.setattr(sys, "argv", ["x", "--date", "20990401", "--skip-crawl",
                                      "--save-dir", str(tmp_path)])
    assert m.main() == 0
