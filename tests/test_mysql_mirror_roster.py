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



def test_등번호_없는_줄도_KBO_명단_그대로_남깁니다():
    # KBO 퓨처스 명단에 등번호 없이 오른 선수가 있습니다(2026-10-04 한화
    # 노석진). 방출 여부는 KBO 명단이 바뀔 때 따르고, 여기서 빼지 않습니다.
    rows = [{"team": "한화", "name": "가", "back_number": "117"},
            {"team": "한화", "name": "나", "back_number": ""},
            {"team": "LG", "name": "다", "back_number": " "},
            {"team": "LG", "name": "라", "back_number": None},
            {"team": "LG", "name": "마", "back_number": "-"},
            {"team": "KT", "name": "바", "back_number": "0"}]
    blank = roster_to_d1.mark_unnumbered(rows)
    assert [r["name"] for r in rows] == ["가", "나", "다", "라", "마", "바"]
    assert [r["name"] for r in blank] == ["나", "다", "라", "마"]
    assert [r["back_number"] for r in rows] == ["117", "", "", "", "", "0"]


def test_명단_적재는_등번호_빈_글자를_그대로_넘깁니다(fake_sink):
    rows = [{"team": "한화", "name": "나", "back_number": ""}]
    roster_to_d1.mysql_write_roster(fake_sink, rows, [])
    assert fake_sink.raw["kbo_roster"] == ("back_number",)
    _, sql, params = fake_sink.calls[-1]
    assert params == ["한화", "나", ""]


def test_명단_등번호가_비면_players_등번호를_지우지_않습니다(fake_sink):
    fake_sink.answers = {
        "FROM teams": [{"team_id": "HH"}, {"team_id": "LG"}],
        "FROM kbo_roster r": [
            # 같은 팀, 명단 등번호 없음: 바꿀 것 없음
            {"pid": 1, "nm": "가", "rt": "HH", "rb": "", "pt": "HH", "pb": 117},
            # 팀이 바뀜, 명단 등번호 없음: 팀만 바꾸고 등번호는 그대로
            {"pid": 2, "nm": "나", "rt": "LG", "rb": "", "pt": "HH", "pb": 33},
        ],
    }
    assert sync.mysql_write_sync(fake_sink) == 1
    updates = [c for c in fake_sink.calls if c[0] == "execute"]
    assert len(updates) == 1 and updates[0][2] == ["LG", 33, 2]
