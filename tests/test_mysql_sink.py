import json

import pytest

from data_collection import mysql_sink as ms


class Cur:
    def __init__(self, con):
        self.con = con
        self.description = con.desc
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if self.con.fail_on and self.con.fail_on in sql:
            raise RuntimeError("boom")
        self.con.log.append((sql, params))

    def fetchall(self):
        return self.con.rows


class Con:
    def __init__(self, rows=None, desc=None, fail_on=None):
        self.log, self.rows, self.desc, self.fail_on = [], rows or [], desc, fail_on
        self.commits = self.rollbacks = self.closed = 0

    def cursor(self):
        return Cur(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed += 1


GAME = {"game_id": "20261003LGOB02026", "game_date": "20261003", "season": "2026",
        "game_type": "정규시즌", "home_team_id": "OB", "away_team_id": "LG",
        "home_score": "3", "away_score": "-", "stadium": "잠실"}


def test_upsert_uses_row_alias_and_parameters():
    con = Con()
    cols = list(GAME)
    assert ms.Sink(con).upsert("games", cols, ["game_id"], [GAME]) == 1
    sql, params = con.log[0]
    assert sql.startswith("INSERT INTO `games` (`game_id`, `game_date`")
    assert " AS new ON DUPLICATE KEY UPDATE `game_date`=new.`game_date`" in sql
    assert "`game_id`=new" not in sql
    # '-' 는 D1 처럼 NULL, 정수 열은 정수입니다.
    assert params[1] == 20261003 and params[2] == 2026 and params[7] is None


def test_raw_열은_빈_글자를_NULL_로_바꾸지_않습니다():
    # 기본 키 열(kbo_roster.back_number)은 NULL 을 못 받습니다. 부르는 쪽이
    # raw 로 고른 열만 빈 글자를 그대로 넘깁니다.
    con = Con()
    row = {"team": "한화", "name": "나", "back_number": "", "role": "내야수",
           "player_id": "", "as_of": "2026-10-04", "league": "퓨처스"}
    cols = list(row)
    ms.Sink(con).upsert("kbo_roster", cols, ["team", "name", "back_number"], [row],
                        raw=["back_number"])
    _, params = con.log[0]
    assert params[2] == "" and params[4] is None
    con2 = Con()
    ms.Sink(con2).upsert("kbo_roster", cols, ["team", "name", "back_number"], [row])
    assert con2.log[0][1][2] is None


def test_upsert_touch_and_keep():
    con = Con()
    ms.Sink(con).upsert("futures_games", ["game_id", "season", "status", "updated_at"],
                        ["game_id"], [{"game_id": "x", "season": 2026, "status": "final",
                                       "updated_at": "t"}],
                        touch="updated_at", keep=["season"])
    sql = con.log[0][0]
    assert "`status`=new.`status`" in sql
    assert "`updated_at`=UTC_TIMESTAMP()" in sql
    assert "`season`=new" not in sql


def test_upsert_without_updatable_columns_is_an_error():
    with pytest.raises(ValueError):
        ms.Sink(Con()).upsert("teams", ["team_id"], ["team_id"], [{"team_id": "LG"}])


def test_insert_splits_batches():
    con = Con()
    rows = [{"job": "j%d" % i, "last_run_at": "2026-10-02 10:00", "status": "ok"}
            for i in range(5)]
    ms.Sink(con).insert("meta_job_runs", ["job", "last_run_at", "status"], rows, batch=2)
    assert len(con.log) == 3
    assert con.log[0][0].count("(%s, %s, %s)") == 2


def test_insert_missing_is_a_no_op_update():
    con = Con()
    ms.Sink(con).insert_missing("players", ["player_id", "player_name"], ["player_id"],
                                [{"player_id": "51234", "player_name": "가"}])
    sql, params = con.log[0]
    assert sql.endswith(" ON DUPLICATE KEY UPDATE `player_id`=`player_id`")
    assert params == [51234, "가"]


def test_bad_value_names_table_and_column():
    with pytest.raises(ValueError, match="games.home_score"):
        ms.Sink(Con()).insert("games", ["game_id", "home_score"],
                              [{"game_id": "g", "home_score": "abc"}])


def test_unknown_column_is_an_error():
    with pytest.raises(KeyError):
        ms.Sink(Con()).insert("games", ["nope"], [{"nope": 1}])


def test_refresh_count_writes_meta():
    con = Con(rows=[(3983367,)], desc=[("n",)])
    assert ms.Sink(con).refresh_count("play_by_play") == 3983367
    assert con.log[0][0] == "SELECT COUNT(*) AS n FROM `play_by_play`"
    assert con.log[1][0].startswith("INSERT INTO `meta_table_counts`")
    assert con.log[1][1][:2] == ["play_by_play", 3983367]


def test_mirror_always_writes_without_any_switch(monkeypatch):
    """MySQL 이 유일한 저장소라 켜고 끄는 환경 변수 없이 늘 씁니다."""
    monkeypatch.delenv("BSTATS_MYSQL_MIRROR", raising=False)
    monkeypatch.delenv("BSTATS_D1", raising=False)
    con = Con()
    assert ms.mirror("j", lambda s: 7, connect=lambda: con) == 7
    assert con.commits == 1 and con.closed == 1
    assert "innodb_lock_wait_timeout" in con.log[0][0]


def test_mirror_old_mode_variable_does_not_skip_or_swallow(monkeypatch, tmp_path):
    """예전 BSTATS_MYSQL_MIRROR=off·shadow 가 남아 있어도 건너뛰거나 실패를 삼키지 않습니다."""
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(tmp_path / "f.jsonl"))
    for old in ("off", "shadow"):
        monkeypatch.setenv("BSTATS_MYSQL_MIRROR", old)
        assert ms.mirror("j", lambda s: 1, connect=Con) == 1
        with pytest.raises(RuntimeError):
            ms.mirror("j", lambda s: s.execute("INSERT 1"), connect=lambda: Con(fail_on="INSERT"))


def test_mirror_failure_records_rolls_back_and_raises(monkeypatch, tmp_path, capsys):
    log = tmp_path / "fail.jsonl"
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(log))
    con = Con(fail_on="INSERT")
    with pytest.raises(RuntimeError, match="boom"):
        ms.mirror("games", lambda s: s.execute("INSERT INTO x VALUES (1)"), connect=lambda: con)
    assert con.rollbacks == 1 and con.commits == 0 and con.closed == 1
    # 워크플로의 "MySQL 적재 실패 확인" 단계가 이 파일을 봅니다.
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert rec["job"] == "games" and "boom" in rec["error"]
    assert "::warning" not in capsys.readouterr().out


def test_mirror_connect_failure_is_recorded_and_raised(monkeypatch, tmp_path):
    log = tmp_path / "fail.jsonl"
    monkeypatch.setenv(ms.FAIL_LOG_ENV, str(log))

    def no_db():
        raise ConnectionError("MySQL 이 죽었습니다")

    with pytest.raises(ConnectionError):
        ms.mirror("pbp", lambda s: 1, connect=no_db)
    assert json.loads(log.read_text(encoding="utf-8"))["job"] == "pbp"


def test_mirror_has_no_mode_or_required_switch():
    import inspect
    assert not hasattr(ms, "mode") and not hasattr(ms, "MODE_ENV")
    assert list(inspect.signature(ms.mirror).parameters) == ["job", "fn", "connect"]
