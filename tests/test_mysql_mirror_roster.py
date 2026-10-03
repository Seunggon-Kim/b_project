import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import add_new_players  # noqa: E402
import futures_records  # noqa: E402
import roster_to_d1  # noqa: E402
import sync_players_from_roster as sync  # noqa: E402


def test_roster_upserts_then_prunes(fake_sink):
    rows = [{"team": "LG", "name": "가", "back_number": "07"},
            {"team": "KT", "name": "나", "back_number": "1"}]
    moves = [{"move_date": "2026-10-02", "kind": "등록", "team": "LG", "name": "가"}]
    roster_to_d1.mysql_write_roster(fake_sink, rows, moves)
    kinds = [(c[0], c[1]) for c in fake_sink.calls]
    assert kinds == [("upsert", "kbo_roster"), ("upsert", "kbo_roster_moves"),
                     ("execute", fake_sink.calls[2][1])]
    _, sql, params = fake_sink.calls[2]
    assert sql == ("DELETE FROM `kbo_roster` WHERE (`team`, `name`, `back_number`) "
                   "NOT IN ((%s, %s, %s), (%s, %s, %s))")
    assert params == ["LG", "가", "07", "KT", "나", "1"]


def test_sync_uses_mysql_rows_and_skips_unknown_teams(fake_sink):
    fake_sink.answers = {
        "FROM teams": [{"team_id": "LG"}],
        "FROM kbo_roster r": [
            {"pid": 1, "nm": "가", "rt": "LG", "rb": "07", "pt": "OB", "pb": 7},
            {"pid": 2, "nm": "나", "rt": "상무", "rb": "1", "pt": "LG", "pb": 1},
            {"pid": 3, "nm": "다", "rt": "LG", "rb": "5", "pt": "LG", "pb": 5},
        ],
    }
    assert sync.mysql_write_sync(fake_sink) == 1
    updates = [c for c in fake_sink.calls if c[0] == "execute"]
    assert len(updates) == 1
    assert updates[0][1].startswith("UPDATE `players` SET `team_id`=%s, `back_number`=%s")
    assert updates[0][2] == ["LG", 7, 1]


def _found():
    return [
        ("가", "LG", {"player_id": "51234", "position": "투수", "back_number": "7"}, {"pos"}),
        ("나", "KT", {"player_id": "51235", "position": "포수", "back_number": "12"}, {"pos", "bn"}),
        ("다", "OB", {"player_id": "51236", "position": "내야수", "back_number": "3"}, set()),
    ]


def test_d1_update_sql_matches_old_text():
    """함수로 옮겨도 D1 에 보내는 글자는 예전과 같아야 합니다."""
    got = [add_new_players.d1_update_sql(*t) for t in add_new_players.id_fill_targets(_found())]
    assert got == [
        "UPDATE kbo_roster SET player_id=51234 WHERE player_id IS NULL AND name='가' AND team='LG' AND role='투수';",
        "UPDATE kbo_roster_moves SET player_id=51234 WHERE player_id IS NULL AND name='가' AND team='LG' AND position='투수';",
        "UPDATE kbo_roster SET player_id=51235 WHERE player_id IS NULL AND name='나' AND team='KT' AND role='포수' AND back_number='12';",
        "UPDATE kbo_roster SET player_id=51236 WHERE player_id IS NULL AND name='다' AND team='OB';",
        "UPDATE kbo_roster_moves SET player_id=51236 WHERE player_id IS NULL AND name='다' AND team='OB';",
    ]


def test_mysql_new_players(fake_sink):
    targets = add_new_players.id_fill_targets(_found())
    rows = [{"player_id": 51234, "player_name": "가"}]
    assert add_new_players.mysql_write_new_players(fake_sink, rows, targets) == 1
    assert fake_sink.calls[0][:4] == ("insert_missing", "players",
                                      add_new_players.NEW_PLAYER_COLS, ["player_id"])
    _, sql, params = fake_sink.calls[1]
    assert sql == ("UPDATE `kbo_roster` SET `player_id`=%s WHERE `player_id` IS NULL "
                   "AND `name`=%s AND `team`=%s AND `role`=%s")
    assert params == [51234, "가", "LG", "투수"]
    assert len([c for c in fake_sink.calls if c[0] == "execute"]) == 5


def test_futures_records(fake_sink):
    futures_records.mysql_write_futures_stats(fake_sink, [{"player_id": "1"}],
                                              ["player_id", "season", "kind", "AVG"])
    assert fake_sink.calls[0][:4] == ("upsert", "futures_season_stats",
                                      ["player_id", "season", "kind", "AVG"],
                                      ["player_id", "season", "kind"])
