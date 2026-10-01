import sqlite3

from migration import d1_to_sqlite as m


def test_export_jobs_limits_shards_when_asked():
    jobs = m.export_jobs(["teams", "play_by_play"],
                         shards={"DB_2008_2011", "DB_2012_2014"})
    assert ("teams", "kbo-stats", "teams") in jobs
    pbp = [j for j in jobs if j[0] == "play_by_play"]
    assert [j[1] for j in pbp] == ["kbo-pbp-2008-2011", "kbo-pbp-2012-2014"]


def test_export_jobs_without_filter_keeps_all_six_shards():
    pbp = [j for j in m.export_jobs(["play_by_play"]) if j[0] == "play_by_play"]
    assert len(pbp) == 6


def test_has_rows(tmp_path):
    con = sqlite3.connect(str(tmp_path / "x.db"))
    assert not m._has_rows(con, "t")
    con.execute("CREATE TABLE t (a)")
    assert not m._has_rows(con, "t")
    con.execute("INSERT INTO t VALUES (1)")
    assert m._has_rows(con, "t")
