import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import heal_player_photos  # noqa: E402
from migration import sqlite_to_d1  # noqa: E402


def test_replace_deletes_inserts_and_counts_each_table(fake_sink):
    tables = [("self_park_factor", ["season", "stadium"], [{"season": 2026, "stadium": "잠실"}]),
              ("players", ["player_id"], [{"player_id": 1}])]
    assert sqlite_to_d1.mysql_replace_tables(fake_sink, tables) == 2
    assert [c[0] for c in fake_sink.calls] == ["execute", "insert", "refresh_count"] * 2
    assert fake_sink.calls[0][1] == "DELETE FROM `self_park_factor`"
    assert fake_sink.calls[1][1:] == ("self_park_factor", ["season", "stadium"],
                                      [{"season": 2026, "stadium": "잠실"}])


def test_photos(fake_sink):
    n = heal_player_photos.mysql_write_photos(fake_sink, [("51234", "https://x/51234.jpg")])
    assert n == 1
    _, sql, params = fake_sink.calls[0]
    assert sql == ("UPDATE `players` SET `image_url`=%s, `updated_at`=UTC_TIMESTAMP() "
                   "WHERE `player_id`=%s")
    assert params == ["https://x/51234.jpg", 51234]
