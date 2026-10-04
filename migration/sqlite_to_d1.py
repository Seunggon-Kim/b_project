# -*- coding: utf-8 -*-
"""로컬 SQLite 의 표 몇 개를 Cloud SQL(MySQL)로 올립니다.

파크팩터 파이프라인이 만든 결과 표(weekly)와 월간 선수 프로필(monthly,
`--tables players`)을 올릴 때 씁니다. 파일 이름의 `_to_d1` 은 예전 이름이
남은 것입니다(D1 은 2026-10-04 에 걷어냈습니다).

**표를 통째로 바꿉니다**(DELETE 후 INSERT, 한 트랜잭션). 파생 표는 매번
전부 다시 계산되므로 부분 갱신이 의미가 없고, 옛 행이 남으면 계산에서
빠진 선수가 화면에 계속 보입니다.

    py migration/sqlite_to_d1.py --db /tmp/kbo.db \
        --tables self_park_factor,wrc_plus_comparison
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_collection.mysql_sink import mirror  # noqa: E402

# 파크팩터 파이프라인이 쓰는 표입니다.
DERIVED_TABLES = [
    "self_park_factor",
    "kbo_woba_weights_by_season",
    "wrc_plus_comparison",
    "weighted_pf_by_batter_season",
    "re24_matrix_by_season",
    "kbo_run_values_by_season",
]

# 파이프라인이 남기는 롤링 백업입니다. 올릴 이유가 없습니다.
SKIP_SUFFIXES = ("_bak",)


def mysql_replace_tables(sink, tables):
    """표를 MySQL 에서 통째로 바꿉니다.

    한 트랜잭션이라 중간에 실패하면 모두 되돌아가 옛 값이 그대로 남습니다.
    MySQL 에서 players 를 가리키는 외래키는 없어 지우고 넣어도 됩니다.
    """
    for table, cols, rows in tables:
        sink.execute("DELETE FROM `%s`" % table)
        sink.insert(table, cols, rows)
        sink.refresh_count(table)
    return len(tables)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 기본값은 파생 표 전부")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else DERIVED_TABLES)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    pushed, skipped, mirrored = [], [], []
    for table in tables:
        if table.endswith(SKIP_SUFFIXES):
            skipped.append((table, "백업 표"))
            continue
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
            (table,)).fetchone()
        if not row:
            # 파이프라인이 아직 안 만든 표일 수 있습니다. 조용히 넘기지
            # 않습니다. 빠진 것을 모르면 화면에 옛 값이 남습니다.
            skipped.append((table, "로컬에 없습니다"))
            continue

        cols = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
        rows = [dict(r) for r in conn.execute('SELECT * FROM "%s"' % table)]

        print("%-32s %8s행" % (table, format(len(rows), ",")))
        if args.dry_run:
            continue
        pushed.append((table, len(rows)))
        mirrored.append((table, cols, rows))

    conn.close()

    if mirrored and not args.dry_run:
        mirror("sqlite_push", lambda s: mysql_replace_tables(s, mirrored))

    print()
    if args.dry_run:
        print("[dry-run] 올리지 않았습니다.")
        return 0
    for t, n in pushed:
        print("MySQL 반영: %-28s %s행" % (t, format(n, ",")))
    for t, why in skipped:
        print("건너뜀: %-30s %s" % (t, why))
    # 하나도 못 올렸으면 실패입니다. 조용히 성공으로 끝내면 화면이
    # 옛 값을 보여 주는 것을 아무도 모릅니다.
    return 0 if pushed else 1


if __name__ == "__main__":
    sys.exit(main())
