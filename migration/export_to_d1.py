# -*- coding: utf-8 -*-
"""SQLite 테이블을 D1 적재용 INSERT 청크 파일로 내보냅니다.

D1 제약과 이 도구의 대응
------------------------
- **SQL 문 하나가 100,000 바이트를 넘을 수 없습니다.**
  행 크기가 테이블마다 크게 달라 고정 묶음은 위험합니다. `team_logos` 는 한 행이
  87KB 이고 `play_by_play` 는 1.3KB 입니다. 그래서 행을 하나씩 붙여 보며
  `max_stmt_bytes` 를 넘기 직전에 문을 끊습니다.
- **무료 플랜은 하루 100,000 행까지 씁니다.**
  하루치를 세려면 파일 단위 행 수를 알아야 하므로 `manifest.json` 에 기록합니다.
- 파일 하나에 INSERT 문 여러 개를 담습니다. `wrangler d1 execute --file` 이
  파일 안의 문을 순서대로 실행하므로, 이렇게 하면 호출 횟수가 크게 줄어듭니다.
  파일당 행 수는 `rows_per_file` 로 정합니다.

파일명 규칙: `{순번2자리}_{테이블명}_{청크번호4자리}.sql`
"""
import json
import sqlite3
import sys
from pathlib import Path

# 적재 순서. 참조되는 쪽을 먼저 넣고, 가장 큰 play_by_play 를 마지막에 둡니다.
#
# 아직 없는 테이블(player_history, re24_matrix_by_season, kbo_run_values_by_season)도
# 목록에 남겨 둡니다. 원천을 다시 수집해 생기면 이 파일을 고치지 않아도 함께 실립니다.
TABLE_ORDER = [
    # 마스터
    "teams",
    "team_logos",
    "futures_teams",
    "stadium_dim",
    "team_stadium_by_season",
    "players",
    "player_history",
    # 경기·기록
    "games",
    "game_team_stats",
    "futures_games",
    "kbo_official_batter_stats",
    "kbo_official_pitcher_stats",
    # 파크팩터·세이버메트릭스
    "self_park_factor",
    "statiz_park_factor",
    "statiz_yearly_constants",
    "weighted_pf_by_batter_season",
    "wrc_plus_comparison",
    "re24_matrix_by_season",
    "kbo_run_values_by_season",
    # 대용량
    "play_by_play",
]

# SQLite 가 내부적으로 관리하는 테이블. 적재 대상이 아닙니다.
INTERNAL = {"sqlite_sequence", "sqlite_stat1", "sqlite_stat4"}

# D1 한도는 100,000 바이트입니다. 10% 를 여유로 남깁니다.
MAX_STATEMENT_BYTES = 90_000

# 파일 하나에 담을 행 수. 하루 한도(100,000행)를 파일 단위로 세기 좋게 나눕니다.
ROWS_PER_FILE = 1_000

MANIFEST_NAME = "manifest.json"


def sql_literal(value):
    """파이썬 값을 SQL 리터럴 문자열로 바꿉니다."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, bytes):
        return "X'%s'" % value.hex()
    return "'" + str(value).replace("'", "''") + "'"


def rows_to_insert(table, columns, rows):
    """행 묶음을 다중 VALUES INSERT 문 하나로 만듭니다."""
    cols = ",".join('"%s"' % c for c in columns)
    values = ",".join(
        "(" + ",".join(sql_literal(v) for v in row) + ")" for row in rows
    )
    return 'INSERT INTO "%s" (%s) VALUES %s;' % (table, cols, values)


def missing_from_order(conn):
    """DB 에는 있는데 TABLE_ORDER 에 없는 테이블 이름을 돌려줍니다.

    목록에서 빠진 테이블은 아무 소리 없이 D1 에 안 들어갑니다.
    적재를 마치고 나서야 알아차리는 일을 막으려고 둔 장치입니다.
    """
    known = set(TABLE_ORDER) | INTERNAL
    return sorted(
        name
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
        if name not in known
    )


def build_statements(table, columns, rows, max_stmt_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 크기 한도를 지키는 INSERT 문 여러 개로 나눕니다.

    행 하나가 이미 한도를 넘으면 `ValueError` 를 냅니다. 그런 행은 D1 이
    받아 주지 않으므로 조용히 넘기지 않고 멈춥니다.
    """
    prefix_len = len(
        ('INSERT INTO "%s" (%s) VALUES ;' % (
            table, ",".join('"%s"' % c for c in columns))).encode("utf-8"))

    statements = []
    batch = []
    batch_len = 0
    for row in rows:
        piece = "(" + ",".join(sql_literal(v) for v in row) + ")"
        piece_len = len(piece.encode("utf-8"))
        if prefix_len + piece_len > max_stmt_bytes:
            raise ValueError(
                "%s 의 행 하나가 %d 바이트로 한도 %d 를 넘습니다. "
                "이 행은 D1 에 넣을 수 없습니다."
                % (table, prefix_len + piece_len, max_stmt_bytes))
        # 쉼표 한 글자를 더한 길이로 넘침을 판정합니다.
        added = piece_len + (1 if batch else 0)
        if batch and prefix_len + batch_len + added > max_stmt_bytes:
            statements.append(rows_to_insert(table, columns, batch))
            batch = []
            batch_len = 0
            added = piece_len
        batch.append(row)
        batch_len += added
    if batch:
        statements.append(rows_to_insert(table, columns, batch))
    return statements


def export_table(conn, table, out_dir, rows_per_file=ROWS_PER_FILE, order=0,
                 max_stmt_bytes=MAX_STATEMENT_BYTES, where=None):
    """테이블 하나를 청크 SQL 파일들로 내보내고 (경로, 행수) 목록을 돌려줍니다.

    `where` 를 주면 그 조건에 맞는 행만 내보냅니다. 시즌 하나를 새로 넣을
    때 표 전체를 다시 올릴 이유가 없습니다. play_by_play 40만 행을 다시
    올리면 쓰기가 160만 계상됩니다(인덱스 3개 포함).

    조건은 호출자가 만든 SQL 조각이 그대로 들어갑니다. 사용자 입력을
    넣지 마십시오.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    columns = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
    if not columns:
        return []

    sql = 'SELECT * FROM "%s"' % table
    if where:
        sql += " WHERE " + where
    cur = conn.execute(sql)
    result = []
    chunk_no = 0
    while True:
        rows = cur.fetchmany(rows_per_file)
        if not rows:
            break
        statements = build_statements(table, columns, rows, max_stmt_bytes)
        chunk_no += 1
        path = out_dir / ("%02d_%s_%04d.sql" % (order, table, chunk_no))
        path.write_text("\n".join(statements) + "\n", encoding="utf-8")
        result.append((path, len(rows)))
    return result


def main():
    db = sys.argv[1] if len(sys.argv) > 1 else "database/kbo_stats.db"
    out_dir = Path(sys.argv[2] if len(sys.argv) > 2 else "migration/out")
    conn = sqlite3.connect(db)

    unlisted = missing_from_order(conn)
    if unlisted:
        print("경고: TABLE_ORDER 에 없어 적재되지 않는 테이블 %d개" % len(unlisted))
        for name in unlisted:
            print("    %s" % name)
        print()

    manifest = {"source": db, "files": []}
    total_rows = 0
    total_files = 0
    for i, table in enumerate(TABLE_ORDER, start=1):
        exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        if not exists:
            print("건너뜀 (테이블 없음): %s" % table)
            continue
        pairs = export_table(conn, table, out_dir, order=i)
        n = conn.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        biggest = 0
        for path, rows in pairs:
            size = path.stat().st_size
            biggest = max(biggest, size)
            manifest["files"].append({
                "name": path.name,
                "table": table,
                "rows": rows,
                "bytes": size,
            })
        total_rows += n
        total_files += len(pairs)
        print("%-32s %8d행 -> 파일 %4d개  최대 %s" % (
            table, n, len(pairs),
            "%.1fMB" % (biggest / 1024 / 1024) if biggest else "-"))

    manifest["totals"] = {"rows": total_rows, "files": total_files}
    (out_dir / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print()
    print("합계 %d행, 파일 %d개" % (total_rows, total_files))
    print("목록: %s" % (out_dir / MANIFEST_NAME))
    return 1 if unlisted else 0


if __name__ == "__main__":
    sys.exit(main())
