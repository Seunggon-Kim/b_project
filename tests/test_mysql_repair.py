import sqlite3

from migration.mysql import repair as r


def make_snapshot(con, with_unrecoverable=True):
    con.execute("CREATE TABLE games (game_id TEXT PRIMARY KEY, game_date DATE)")
    con.execute("CREATE TABLE play_by_play (gameID TEXT, game_date DATE)")
    con.executemany("INSERT INTO games VALUES (?,?)",
                    [("33330929LTOB0", 20090929), ("20250101AAA0", 20250101)])
    rows = [("33330929LTOB0", "TOB00929"),
            ("33330929LTOB0", "TOB00929"),
            ("20250101AAA0", 20250101)]
    if with_unrecoverable:
        rows.append(("NOGAME0000000", "ABC01010"))
    con.executemany("INSERT INTO play_by_play VALUES (?,?)", rows)
    con.commit()


def test_fix_restores_text_dates_from_games_and_is_idempotent():
    con = sqlite3.connect(":memory:")
    make_snapshot(con)

    assert r.fix_postseason_dates(con) == (2, 1, 1)

    fixed = con.execute(
        "SELECT game_date, typeof(game_date) FROM play_by_play "
        "WHERE gameID='33330929LTOB0'").fetchall()
    assert fixed == [(20090929, "integer"), (20090929, "integer")]
    normal = con.execute(
        "SELECT game_date, typeof(game_date) FROM play_by_play "
        "WHERE gameID='20250101AAA0'").fetchall()
    assert normal == [(20250101, "integer")]
    left = con.execute(
        "SELECT game_date, typeof(game_date) FROM play_by_play "
        "WHERE gameID='NOGAME0000000'").fetchall()
    assert left == [("ABC01010", "text")]

    assert r.fix_postseason_dates(con) == (0, 0, 1)


def test_fix_leaves_text_when_games_date_is_not_integer():
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE games (game_id TEXT PRIMARY KEY, game_date DATE)")
    con.execute("CREATE TABLE play_by_play (gameID TEXT, game_date DATE)")
    con.execute("INSERT INTO games VALUES ('77770101AAAA0', 'TOB00101')")
    con.execute("INSERT INTO play_by_play VALUES ('77770101AAAA0', 'TOB00101')")
    con.commit()
    assert r.fix_postseason_dates(con) == (0, 0, 1)


def test_render_report_has_counts_and_source():
    text = r.render_report("d1_20261002.db", 2, 1, 1)
    assert text.startswith("# 스냅샷 보정 보고")
    assert "d1_20261002.db" in text
    assert "play_by_play.game_date 포스트시즌 날짜 복구: 2행 (1경기)" in text
    assert "남은 글자 날짜: 1행" in text
    assert "games.game_date" in text


def test_render_report_uses_thousands_separators():
    text = r.render_report("x.db", 26450, 85, 0)
    assert "26,450행 (85경기)" in text
    assert "남은 글자 날짜: 0행" in text


def test_main_returns_1_when_text_dates_remain(tmp_path, monkeypatch, capsys):
    snap = tmp_path / "d1_20261002.db"
    con = sqlite3.connect(str(snap))
    make_snapshot(con, with_unrecoverable=True)
    con.close()
    report = tmp_path / "out" / "repair-report.md"
    monkeypatch.setattr(r, "REPORT", report)
    monkeypatch.setattr("sys.argv", ["repair", "--snapshot", str(snap)])

    assert r.main() == 1

    text = report.read_text(encoding="utf-8")
    assert "2행 (1경기)" in text
    assert "남은 글자 날짜: 1행" in text
    out = capsys.readouterr().out
    assert "2행 (1경기)" in out

    # 보정은 파일에 저장됩니다.
    con = sqlite3.connect(str(snap))
    try:
        assert con.execute(
            "SELECT COUNT(*) FROM play_by_play "
            "WHERE typeof(game_date)='text'").fetchone()[0] == 1
    finally:
        con.close()


def test_main_returns_0_when_everything_restored(tmp_path, monkeypatch):
    snap = tmp_path / "d1_20261002.db"
    con = sqlite3.connect(str(snap))
    make_snapshot(con, with_unrecoverable=False)
    con.close()
    report = tmp_path / "out" / "repair-report.md"
    monkeypatch.setattr(r, "REPORT", report)
    monkeypatch.setattr("sys.argv", ["repair", "--snapshot", str(snap)])

    assert r.main() == 0

    assert report.exists()
    assert "남은 글자 날짜: 0행" in report.read_text(encoding="utf-8")
