# -*- coding: utf-8 -*-
"""players 테이블에 분류 플래그 컬럼 추가 (멱등).

추가 컬럼:
  nationality TEXT          국적 ('대한민국' / 국가명 / NULL=국적미상)
  player_type TEXT          '국내' | '외국인' | '아시아쿼터'  (기본 '국내')
  is_foreign  INTEGER       0 | 1  (기본 0)
  is_active   INTEGER       1=현역(현 로스터 보유) | 0=비현역  (기본 NULL→백필에서 산출)

SQLite 의 ALTER TABLE ADD COLUMN 은 컬럼 존재 시 에러이므로 PRAGMA 로 선검사한다.
운영 적용 전 DB 백업 권장:  copy kbo_stats.db kbo_stats.db.bak_YYYYMMDD
"""

import os
import sqlite3

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "kbo_stats.db")

# (컬럼명, 타입+기본값) — players 에 없으면 추가
NEW_COLUMNS = [
    ("nationality", "TEXT"),
    ("player_type", "TEXT DEFAULT '국내'"),
    ("is_foreign", "INTEGER DEFAULT 0"),
    ("is_active", "INTEGER"),
]


def existing_columns(con, table):
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})")}


def ensure_columns(con):
    """누락된 플래그 컬럼을 추가하고, 추가한 컬럼명 리스트를 반환 (멱등)."""
    have = existing_columns(con, "players")
    added = []
    for name, decl in NEW_COLUMNS:
        if name not in have:
            con.execute(f"ALTER TABLE players ADD COLUMN {name} {decl}")
            added.append(name)
    # 조회 성능용 인덱스 (멱등)
    con.execute("CREATE INDEX IF NOT EXISTS idx_players_is_active ON players(is_active)")
    con.execute("CREATE INDEX IF NOT EXISTS idx_players_player_type ON players(player_type)")
    con.commit()
    return added


def main(db_path=DEFAULT_DB):
    con = sqlite3.connect(db_path)
    try:
        added = ensure_columns(con)
        print(f"[migrate] DB: {db_path}")
        print(f"[migrate] 추가된 컬럼: {added if added else '(없음 — 이미 적용됨)'}")
        cols = existing_columns(con, "players")
        print(f"[migrate] players 컬럼 수: {len(cols)}")
    finally:
        con.close()


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB)
