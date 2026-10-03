# -*- coding: utf-8 -*-
"""두 SQLite 의 파생 표를 견줍니다.

같은 주간 계산을 D1 기준 스냅샷(A)과 MySQL 에서 내려받은 SQLite(B)에 각각
돌린 뒤 결과 표가 같은지 봅니다. 다르면 MySQL 로 옮기며 바뀐 값 모양
(''→NULL, '78513.0'→78513 등)이 계산에 닿은 것입니다.

    py -m migration.mysql.compare_derived --a C:/tmp/weekly_d1.db --b C:/tmp/weekly_mysql.db
"""
import argparse
import collections
import sqlite3
import sys

from migration.mysql.ddl import ROOT
from migration.sqlite_to_d1 import DERIVED_TABLES

REPORT = ROOT / "docs" / "mysql-migration" / "weekly-compare-report.md"
IGNORE_COLS = {"captured_at"}  # 계산한 시각이라 두 번 돌리면 늘 다릅니다


def canon(v):
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 9)
    return v


def columns(con, table):
    return [r[1] for r in con.execute('PRAGMA table_info("%s")' % table)]


def rows(con, table, cols):
    sql = 'SELECT %s FROM "%s"' % (", ".join('"%s"' % c for c in cols), table)
    return collections.Counter(tuple(canon(v) for v in r) for r in con.execute(sql))


def compare(a, b, table):
    ca, cb = columns(a, table), columns(b, table)
    if not ca or not cb:
        return ["%s: 한쪽에 표가 없습니다 (A %s / B %s)" % (table, bool(ca), bool(cb))]
    ca = [c for c in ca if c not in IGNORE_COLS]
    cb = [c for c in cb if c not in IGNORE_COLS]
    if set(ca) != set(cb):
        return ["%s: 열이 다릅니다 (A만 %s / B만 %s)"
                % (table, sorted(set(ca) - set(cb)), sorted(set(cb) - set(ca)))]
    cols = sorted(ca)
    ra, rb = rows(a, table, cols), rows(b, table, cols)
    only_a, only_b = ra - rb, rb - ra
    if not only_a and not only_b:
        return []
    out = ["%s: A 에만 %d행, B 에만 %d행 (전체 A %d / B %d)"
           % (table, sum(only_a.values()), sum(only_b.values()),
              sum(ra.values()), sum(rb.values()))]
    out += ["   A: %s" % dict(zip(cols, r)) for r in list(only_a)[:3]]
    out += ["   B: %s" % dict(zip(cols, r)) for r in list(only_b)[:3]]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True, help="D1 기준 SQLite")
    ap.add_argument("--b", required=True, help="MySQL 에서 내려받은 SQLite")
    args = ap.parse_args()
    a, b = sqlite3.connect(args.a), sqlite3.connect(args.b)
    lines = ["# 주간 계산 비교(D1 기준 A · MySQL 기준 B)", ""]
    bad = 0
    for t in DERIVED_TABLES:
        probs = compare(a, b, t)
        lines.append("- %s: %s" % (t, "같음" if not probs else "다름"))
        lines += ["  %s" % p for p in probs]
        bad += bool(probs)
    a.close()
    b.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lines))
    print("보고서: %s" % REPORT)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
