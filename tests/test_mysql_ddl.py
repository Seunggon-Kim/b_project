import json
import sqlite3

from migration.mysql import ddl


def _snapshot(tmp_path):
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE teams (team_id TEXT PRIMARY KEY, team_name TEXT NOT NULL);
        CREATE TABLE players (
            player_id TEXT PRIMARY KEY, player_name TEXT NOT NULL,
            team_id TEXT, back_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (team_id) REFERENCES teams(team_id));
        CREATE TABLE play_by_play (pbp_id INTEGER, batter_ID TEXT, px REAL, gameID TEXT);
        CREATE INDEX idx_pbp_game ON play_by_play(gameID);
        CREATE TABLE meta (k INTEGER PRIMARY KEY, v TEXT DEFAULT '1군');
        CREATE TABLE futures (code TEXT UNIQUE, n INTEGER);
        CREATE TABLE wrc_bak (a INTEGER);
    """)
    con.execute("INSERT INTO teams VALUES ('KIA', 'KIA 타이거즈')")
    con.execute("INSERT INTO players (player_id, player_name, team_id, back_number) "
                "VALUES ('62404', '구자욱', 'KIA', 7)")
    con.executemany("INSERT INTO play_by_play VALUES (?,?,?,?)",
                    [(1, "78513.0", 1.5, "G1"), (1, "12", "", "G1")])
    con.execute("INSERT INTO meta (v) VALUES ('2군')")
    con.execute("INSERT INTO futures VALUES ('SS', 1)")
    con.commit()
    con.close()
    return p


def test_build_skips_backup_tables_and_renumbers_pbp(tmp_path):
    creates, posts, types, notes = ddl.build(_snapshot(tmp_path))
    assert set(types) == {"teams", "players", "play_by_play", "meta", "futures"}
    pbp = next(c for c in creates if c.startswith("CREATE TABLE `play_by_play`"))
    assert "`pbp_id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT" in pbp
    assert "PRIMARY KEY (`pbp_id`)" in pbp
    assert "`batter_ID` INT UNSIGNED" in pbp
    assert "`px` DOUBLE" in pbp
    assert types["play_by_play"]["renumber"] == "pbp_id"


def test_build_keeps_keys_defaults_and_foreign_keys(tmp_path):
    creates, posts, types, notes = ddl.build(_snapshot(tmp_path))
    players = next(c for c in creates if c.startswith("CREATE TABLE `players`"))
    assert "`player_id` INT UNSIGNED NOT NULL" in players
    assert "`created_at` DATETIME DEFAULT CURRENT_TIMESTAMP" in players
    assert "`back_number` INT" in players
    meta = next(c for c in creates if c.startswith("CREATE TABLE `meta`"))
    assert "`k` INT NOT NULL AUTO_INCREMENT" in meta
    assert "DEFAULT '1군'" in meta
    assert ("ALTER TABLE `players` ADD CONSTRAINT `fk_players_team_id` "
            "FOREIGN KEY (`team_id`) REFERENCES `teams` (`team_id`);") in posts
    assert "CREATE INDEX `idx_pbp_game` ON `play_by_play` (`gameID`);" in posts
    assert "CREATE UNIQUE INDEX `uq_futures_1` ON `futures` (`code`);" in posts


def test_notes_explain_value_fixes(tmp_path):
    _, _, _, notes = ddl.build(_snapshot(tmp_path))
    joined = "\n".join(notes)
    assert "play_by_play.batter_ID" in joined
    assert "소수점 표기 1개 → 정수" in joined
    assert "play_by_play.px: 빈 값 1개 → NULL" in joined


def test_split_sql():
    text = "CREATE TABLE `a` (\n  `x` INT\n);\n\nCREATE TABLE `b` (`y` INT);\n"
    assert ddl.split_sql(text) == ["CREATE TABLE `a` (\n  `x` INT\n)",
                                   "CREATE TABLE `b` (`y` INT)"]


def test_default_clause():
    assert ddl.default_clause("CURRENT_TIMESTAMP", "datetime", "DATETIME") == \
        (" DEFAULT CURRENT_TIMESTAMP", None)
    clause, why = ddl.default_clause("CURRENT_TIMESTAMP", "text", "VARCHAR(32)")
    assert clause == "" and "뺐습니다" in why
    assert ddl.default_clause("0", "int", "INT") == (" DEFAULT 0", None)
    assert ddl.default_clause("'x'", "text", "TEXT") == (" DEFAULT ('x')", None)
    assert ddl.default_clause(None, "int", "INT") == ("", None)


def test_main_writes_files(tmp_path, monkeypatch):
    out = tmp_path / "out"
    monkeypatch.setattr(ddl, "OUT_DIR", out)
    monkeypatch.setattr(ddl, "REPORT", tmp_path / "report.md")
    monkeypatch.setattr("sys.argv", ["ddl", "--snapshot", str(_snapshot(tmp_path))])
    assert ddl.main() == 0
    types = json.loads((out / "schema_types.json").read_text(encoding="utf-8"))
    assert types["play_by_play"]["columns"][0] == ["pbp_id", "int"]
    assert ddl.split_sql((out / "schema.sql").read_text(encoding="utf-8"))
    assert "# MySQL 스키마 보고" in (tmp_path / "report.md").read_text(encoding="utf-8")


def test_indexes_before_foreign_keys(tmp_path):
    """후처리는 인덱스 전부 → 외래키 전부 순서입니다."""
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE z_parent (code TEXT UNIQUE);
        CREATE TABLE a_child (code TEXT, FOREIGN KEY (code) REFERENCES z_parent(code));
    """)
    con.execute("INSERT INTO z_parent VALUES ('SS')")
    con.execute("INSERT INTO a_child VALUES ('SS')")
    con.commit()
    con.close()

    _, posts, _, _ = ddl.build(p)
    idx_pos = next((i for i, s in enumerate(posts) if "CREATE UNIQUE INDEX" in s and "z_parent" in s), None)
    fk_pos = next((i for i, s in enumerate(posts) if "ALTER TABLE" in s and "a_child" in s), None)
    assert idx_pos is not None and fk_pos is not None, "Both index and FK should be in posts"
    assert idx_pos < fk_pos, "Indexes must come before foreign keys"


def test_composite_key_too_wide(tmp_path):
    """복합 기본키가 3072바이트 한도를 넘으면 멈춥니다."""
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE wide (a TEXT, b TEXT, PRIMARY KEY (a, b));
    """)
    con.execute("INSERT INTO wide VALUES (?, ?)", ('x' * 200, 'y' * 200))
    con.commit()
    con.close()

    import pytest
    with pytest.raises(ValueError) as exc_info:
        ddl.build(p)
    assert "wide" in str(exc_info.value) and "3072" in str(exc_info.value)


def test_row_too_wide(tmp_path):
    """행이 65,535바이트 한도를 넘으면 멈춥니다."""
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE wide_row (
            c0 TEXT, c1 TEXT, c2 TEXT, c3 TEXT, c4 TEXT,
            c5 TEXT, c6 TEXT, c7 TEXT, c8 TEXT, c9 TEXT,
            c10 TEXT, c11 TEXT, c12 TEXT, c13 TEXT, c14 TEXT, c15 TEXT
        );
    """)
    placeholders = ", ".join(["?" for _ in range(16)])
    con.execute("INSERT INTO wide_row VALUES (" + placeholders + ")",
                tuple('x' * 500 for _ in range(16)))
    con.commit()
    con.close()

    import pytest
    with pytest.raises(ValueError) as exc_info:
        ddl.build(p)
    assert "행" in str(exc_info.value)


def test_references_without_column(tmp_path):
    """참조 열을 명시하지 않아도 부모 표의 기본키를 사용합니다."""
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE p (id TEXT PRIMARY KEY);
        CREATE TABLE c (pid TEXT, FOREIGN KEY (pid) REFERENCES p);
    """)
    con.execute("INSERT INTO p VALUES ('A')")
    con.execute("INSERT INTO c VALUES ('A')")
    con.commit()
    con.close()

    _, posts, _, _ = ddl.build(p)
    fk_stmt = next((s for s in posts if "ALTER TABLE" in s and "`c`" in s), None)
    assert fk_stmt is not None, "FK should be present"
    assert "REFERENCES `p` (`id`)" in fk_stmt, "FK should reference p(id)"


def test_expression_index_skipped(tmp_path):
    """식 인덱스는 옮기지 않고 메모를 남깁니다."""
    p = tmp_path / "snap.db"
    con = sqlite3.connect(str(p))
    con.executescript("""
        CREATE TABLE e (a TEXT);
        CREATE INDEX ix_expr ON e(lower(a));
    """)
    con.execute("INSERT INTO e VALUES ('X')")
    con.commit()
    con.close()

    _, posts, _, notes = ddl.build(p)
    assert not any("ix_expr" in s for s in posts), "Expression index should not be in posts"
    assert any("ix_expr" in n for n in notes), "Expression index should be noted"


def test_renumber_column_not_profiled(tmp_path, monkeypatch):
    """새로 매기는 pbp_id 열은 훑지 않습니다."""
    profiled = []
    original_profile = ddl.tm.profile_column

    def mock_profile(con, table, col):
        profiled.append((table, col))
        return original_profile(con, table, col)

    monkeypatch.setattr(ddl.tm, "profile_column", mock_profile)
    ddl.build(_snapshot(tmp_path))
    assert ("play_by_play", "pbp_id") not in profiled, "pbp_id should not be profiled"
