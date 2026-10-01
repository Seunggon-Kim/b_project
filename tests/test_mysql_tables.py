from migration.mysql.tables import is_migrated, migrated_tables


def test_skips_internal_and_backup_tables():
    for name in ["sqlite_sequence", "_cf_KV", "d1_migrations",
                 "wrc_plus_comparison_bak", "kbo_official_batter_stats_bak_pre12"]:
        assert not is_migrated(name), name


def test_keeps_real_tables():
    for name in ["players", "kbo_roster_moves", "meta_table_counts",
                 "meta_backfill", "team_logos"]:
        assert is_migrated(name), name


def test_migrated_tables_adds_shard_only_table_once():
    assert migrated_tables(["teams", "players", "sqlite_sequence"]) == \
        ["players", "teams", "play_by_play"]
    assert migrated_tables(["play_by_play"]) == ["play_by_play"]
