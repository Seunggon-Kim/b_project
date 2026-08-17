# -*- coding: utf-8 -*-
import sqlite3

from migration.golden_matrix import build_matrix, safe_name


def _conn(with_derived=True):
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE players (player_id TEXT, player_name TEXT)")
    conn.executemany(
        "INSERT INTO players VALUES (?,?)",
        [("1001", "가나다"), ("1002", "라마바"), ("1003", "사아자")],
    )
    conn.execute("CREATE TABLE games (season INTEGER)")
    conn.executemany("INSERT INTO games VALUES (?)", [(2025,), (2025,)])
    if with_derived:
        conn.execute(
            "CREATE TABLE wrc_plus_comparison (batter_ID TEXT, season INTEGER, PA INTEGER)")
        conn.executemany(
            "INSERT INTO wrc_plus_comparison VALUES (?,?,?)",
            [("5001", 2025, 500), ("5002", 2025, 400),
             ("5003", 2019, 450), ("5004", 2015, 300)],
        )
    return conn


def test_safe_name_strips_special_characters():
    assert safe_name("/stats/batters?season=2025") == "stats_batters_season_2025"


def test_matrix_covers_every_endpoint_path():
    matrix = build_matrix(_conn())
    paths = {item["path"].split("?")[0] for item in matrix}
    assert "/dashboard/stats" in paths
    assert "/teams" in paths
    assert "/stats/batters" in paths
    assert "/wrc/leaderboard" in paths
    assert "/db/tables" in paths


def test_matrix_includes_nonexistent_id_case():
    names = {item["name"] for item in build_matrix(_conn())}
    assert any("nonexistent" in n for n in names)


def test_matrix_includes_zero_result_case():
    matrix = build_matrix(_conn())
    assert any(item["params"].get("min_pa") == 999 for item in matrix)


def test_matrix_names_are_unique():
    names = [item["name"] for item in build_matrix(_conn())]
    assert len(names) == len(set(names))


def test_hangul_and_empty_query_do_not_collide():
    """safe_name 이 한글을 지우므로 q=김 과 q= 의 이름이 겹칠 수 있습니다."""
    matrix = build_matrix(_conn())
    search = [i for i in matrix if i["path"] == "/players/search"]
    names = [i["name"] for i in search]
    assert len(search) == 3
    assert len(names) == len(set(names))


def test_matrix_is_deterministic():
    """같은 DB 로 두 번 만들면 이름과 순서가 같아야 합니다."""
    a = build_matrix(_conn())
    b = build_matrix(_conn())
    assert [i["name"] for i in a] == [i["name"] for i in b]


def test_wrc_batter_uses_batter_id_not_player_id():
    """wRC+ 조회는 wrc_plus_comparison.batter_ID 를 씁니다.

    players.player_id 를 넣으면 거의 모두 빈 응답이라 이식 검증에 쓸모가 없습니다.
    """
    matrix = build_matrix(_conn())
    ids = {i["path"].rsplit("/", 1)[-1]
           for i in matrix if i["path"].startswith("/wrc/batter/")}
    assert "5001" in ids
    assert "1001" not in ids


def test_matrix_covers_past_seasons_of_derived_tables():
    """파생 테이블은 과거 시즌까지 있으므로 그 이식도 검증해야 합니다."""
    matrix = build_matrix(_conn())
    seasons = {i["params"].get("season")
               for i in matrix if i["path"] == "/wrc/leaderboard"}
    assert 2025 in seasons
    assert 2015 in seasons


def test_leaderboard_covers_every_supported_sort():
    """api/main.py 가 받는 sort 값 네 가지를 모두 훑습니다."""
    matrix = build_matrix(_conn())
    sorts = {i["params"].get("sort")
             for i in matrix if i["path"] == "/wrc/leaderboard"}
    assert {"home", "half", "weighted", "wOBA"} <= sorts


def test_build_matrix_survives_missing_derived_tables():
    """파생 테이블이 없는 DB 에서도 죽지 않아야 합니다."""
    matrix = build_matrix(_conn(with_derived=False))
    assert len(matrix) > 20
