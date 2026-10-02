import sqlite3

from migration import d1_to_sqlite as m


def test_idempotent_index_adds_if_not_exists_once():
    assert (m.idempotent_index("CREATE INDEX idx_a ON t(a)")
            == "CREATE INDEX IF NOT EXISTS idx_a ON t(a)")
    assert (m.idempotent_index("CREATE UNIQUE INDEX u ON t(a)")
            == "CREATE UNIQUE INDEX IF NOT EXISTS u ON t(a)")
    assert (m.idempotent_index("CREATE INDEX IF NOT EXISTS i ON t(a)")
            == "CREATE INDEX IF NOT EXISTS i ON t(a)")
    # D1 정의에는 공백이 여러 칸인 것도 있습니다(idx_roster_team   ON …).
    assert (m.idempotent_index("CREATE INDEX idx_roster_team   ON kbo_roster(team)")
            == "CREATE INDEX IF NOT EXISTS idx_roster_team   ON kbo_roster(team)")


def test_copy_indexes_only_for_tables_we_have():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE games (game_id TEXT, game_date INTEGER)")
    fake = {"kbo-stats": [
        ("games", "CREATE INDEX idx_games_date ON games(game_date)"),
        ("players", "CREATE INDEX idx_players_team ON players(team_id)"),
    ]}
    assert m.copy_indexes(conn, ["kbo-stats"], fetch=fake.__getitem__) == 1
    names = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    assert names == {"idx_games_date"}
    # 두 번 불러도 실패하지 않습니다.
    assert m.copy_indexes(conn, ["kbo-stats"], fetch=fake.__getitem__) == 1
