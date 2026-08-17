# -*- coding: utf-8 -*-
"""로컬 SQLite 스키마를 D1 적용용 SQL 로 변환합니다."""
import sqlite3
import sys
from pathlib import Path

# SQLite 가 내부적으로 관리하는 테이블. 직접 만들지 않습니다.
INTERNAL = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}

# 인덱스를 추가하지 않습니다.
#
# 이유 1 — 쓰기 한도. D1 은 인덱스마다 쓰기 행을 하나씩 더 셉니다("Indexes will add
#   an additional written row"). 실측으로 확인했습니다. play_by_play 1,000행을
#   인덱스 6개인 상태로 넣으니 rows_written 이 7,007 이었습니다. 무료 한도가 하루
#   100,000행이므로 인덱스 하나하나가 적재 일수를 늘립니다.
#   `CREATE INDEX` 를 적재 뒤로 미루는 방법도 쓸 수 없습니다. 1,000행 테이블에
#   인덱스를 만드니 rows_written 이 1,001 이었습니다. 229,667행이면 단일 DDL 하나가
#   하루 한도를 그 자체로 넘고, DDL 은 며칠에 나눠 실행할 수 없습니다.
#   인덱스를 먼저 만들어 두고 적재해야 비용이 행 단위로 쪼개져 여러 날에 나뉩니다.
#
# 이유 2 — 안 쓰는 인덱스였습니다. api/main.py 의 play_by_play 쿼리는 시즌을 모두
#   `substr(gameID,1,4)` 로 거릅니다. `game_date` 로 거르는 쿼리가 하나도 없어
#   game_date 기반 인덱스는 한 번도 쓰이지 않습니다.
#
# 그래서 로컬에 이미 있는 세 개(gameID / batter_ID / pitcher_ID)만 그대로 옮깁니다.
# 이 셋은 각각 games 조인, 타자 조회, 투수 조회에 실제로 쓰입니다.
# 행당 쓰기는 1(테이블) + 3(인덱스) = 4 이므로 하루 25,000행씩 넣을 수 있습니다.
EXTRA_INDEXES = []


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
