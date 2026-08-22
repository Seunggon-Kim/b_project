# -*- coding: utf-8 -*-
"""로컬 SQLite 의 표 몇 개를 D1 으로 되돌립니다.

파크팩터 파이프라인이 만든 결과 표만 올릴 때 씁니다. 원천(`play_by_play`)은
이미 D1 에 있으므로 다시 올리지 않습니다.

**표를 통째로 바꿉니다**(DELETE 후 INSERT). 파생 표는 매번 전부 다시
계산되므로 부분 갱신이 의미가 없고, 옛 행이 남으면 계산에서 빠진 선수가
화면에 계속 보입니다.

    py migration/sqlite_to_d1.py --db /tmp/kbo.db \
        --tables self_park_factor,wrc_plus_comparison
"""
import argparse
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_collection.d1_load import (  # noqa: E402
    build_inserts, query, refresh_count, run_d1, run_d1_file,
)

ROOT = Path(__file__).resolve().parent.parent

# 파크팩터 파이프라인이 쓰는 표입니다.
DERIVED_TABLES = [
    "self_park_factor",
    "kbo_woba_weights_by_season",
    "wrc_plus_comparison",
    "weighted_pf_by_batter_season",
    "re24_matrix_by_season",
    "kbo_run_values_by_season",
]

# 파이프라인이 남기는 롤링 백업입니다. D1 에 올릴 이유가 없습니다.
SKIP_SUFFIXES = ("_bak",)


def d1_has(table):
    rows = query("SELECT name FROM sqlite_master WHERE type='table' "
                 "AND name='%s';" % table)
    return bool(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 기본값은 파생 표 전부")
    ap.add_argument("--out-dir", default="migration/push")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else DERIVED_TABLES)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    pushed, skipped = [], []
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

        lines = []
        if not d1_has(table):
            # D1 에 없으면 만들어야 합니다. 로컬 정의를 그대로 씁니다.
            print("%s: D1 에 없어 새로 만듭니다." % table)
            lines.append(row[0].replace("CREATE TABLE",
                                        "CREATE TABLE IF NOT EXISTS", 1) + ";")
        lines.append('DELETE FROM "%s";' % table)
        lines += build_inserts(table, cols, rows)

        path = out_dir / ("%s.sql" % table)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print("%-32s %8s행  문 %d개" % (table, format(len(rows), ","),
                                       len(lines)))
        if args.dry_run:
            continue

        t0 = time.time()
        run_d1_file(path)
        refresh_count(table)
        print("  올림 %.0f초" % (time.time() - t0))
        pushed.append((table, len(rows)))

    conn.close()

    print()
    if args.dry_run:
        print("[dry-run] 올리지 않았습니다.")
        return 0
    for t, n in pushed:
        print("올림: %-32s %s행" % (t, format(n, ",")))
    for t, why in skipped:
        print("건너뜀: %-30s %s" % (t, why))
    # 하나도 못 올렸으면 실패입니다. 조용히 성공으로 끝내면 화면이
    # 옛 값을 보여 주는 것을 아무도 모릅니다.
    return 0 if pushed else 1


if __name__ == "__main__":
    sys.exit(main())
