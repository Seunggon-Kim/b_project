# -*- coding: utf-8 -*-
"""로컬 SQLite 스키마를 D1 적용용 SQL 로 변환합니다."""
import sqlite3
import sys
from pathlib import Path

# SQLite 가 내부적으로 관리하는 테이블. 직접 만들지 않습니다.
INTERNAL = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}

# play_by_play 조회 성능을 위해 추가하는 인덱스.
# game_date 단독 인덱스와 복합 인덱스가 로컬에는 없습니다.
EXTRA_INDEXES = [
    'CREATE INDEX IF NOT EXISTS idx_pbp_date ON play_by_play(game_date)',
    'CREATE INDEX IF NOT EXISTS idx_pbp_pitcher_date ON play_by_play(pitcher_ID, game_date)',
    'CREATE INDEX IF NOT EXISTS idx_pbp_batter_date ON play_by_play(batter_ID, game_date)',
]


def build_schema_sql(conn):
    """DROP + CREATE TABLE + CREATE INDEX 순서의 SQL 문자열을 만듭니다."""
    tables = [
        (name, sql)
        for name, sql in conn.execute(
            "SELECT name, sql FROM sqlite_master "
            "WHERE type='table' AND sql IS NOT NULL ORDER BY name"
        )
        if name not in INTERNAL
    ]
    indexes = [
        sql
        for (sql,) in conn.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type='index' AND sql IS NOT NULL ORDER BY name"
        )
    ]

    parts = []
    for name, _ in reversed(tables):
        parts.append('DROP TABLE IF EXISTS "%s";' % name)
    for _, sql in tables:
        parts.append(sql.strip().rstrip(";") + ";")
    for sql in indexes:
        parts.append(sql.strip().rstrip(";") + ";")
    for sql in EXTRA_INDEXES:
        parts.append(sql + ";")
    return "\n".join(parts) + "\n"


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    out = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/out/00_schema.sql")
    out.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    out.write_text(build_schema_sql(conn), encoding="utf-8")
    print("wrote %s" % out)


if __name__ == "__main__":
    main()
