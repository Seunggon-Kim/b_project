# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 MySQL 로 옮깁니다.

    py -m migration.mysql.load --snapshot ~/.bstats/snapshots/d1_20261002.db --fresh
    py -m migration.mysql.load --snapshot … --tables players,teams

--fresh 는 표를 지우고 schema.sql 로 새로 만든 뒤, 다 넣고 나서
schema_post.sql(인덱스·외래키)을 적용합니다. --tables 는 --fresh 로 완료한
뒤에 특정 표만 다시 넣을 때씁니다(인덱스·외래키는 이미 있습니다). --fresh 가
도중에 실패했을 땐 다시 --fresh 로 처음부터 넣으십시오.

외래키 검사는 넣는 동안 끕니다. 대신 끝나고 외래키마다 고아 행을 세어
보고서에 남깁니다. 넣는 순서를 맞추는 것보다 확실합니다.
"""
import argparse
import collections
import datetime as dt
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, ROOT, q, split_sql

REPORT = ROOT / "docs" / "mysql-migration" / "load-report.md"
BATCH = 2000
SESSION_SETUP = ("SET FOREIGN_KEY_CHECKS=0",
                 "SET SESSION sql_mode = CONCAT(@@SESSION.sql_mode, ',NO_AUTO_VALUE_ON_ZERO')")
_FK = re.compile(r"ALTER TABLE `([^`]+)` ADD CONSTRAINT `[^`]+` FOREIGN KEY "
                 r"\(`([^`]+)`\) REFERENCES `([^`]+)` \(`([^`]+)`\)")


def insert_sql(table, columns):
    return "INSERT INTO %s (%s) VALUES (%s)" % (
        q(table), ", ".join(q(c) for c in columns), ", ".join(["%s"] * len(columns)))


def convert_row(row, kinds, names, table, fixes):
    """한 행을 MySQL 값으로 바꾸고, 고친 값의 수를 fixes 에 셉니다."""
    out = []
    for v, kind, col in zip(row, kinds, names):
        try:
            nv = tm.normalize(v, kind)
        except ValueError as e:
            raise ValueError("%s.%s: %s" % (table, col, e)) from None
        if v is not None and nv is None:
            fixes[(table, col, "빈 값 → NULL")] += 1
        elif kind == "int" and isinstance(v, str) and "." in v:
            fixes[(table, col, "소수점 표기 → 정수")] += 1
        out.append(nv)
    return tuple(out)


def load_table(sq, my, table, spec, fixes, batch=BATCH):
    """스냅샷 표 하나를 rowid 순서대로 옮깁니다. 넣은 행 수를 돌려줍니다."""
    renumber = spec.get("renumber")
    names = [c for c, _ in spec["columns"] if c != renumber]
    kinds = [k for c, k in spec["columns"] if c != renumber]
    src = sq.execute('SELECT %s FROM "%s" ORDER BY rowid'
                     % (", ".join('"%s"' % c for c in names), table))
    ins = insert_sql(table, names)
    n = 0
    try:
        with my.cursor() as cur:
            while True:
                chunk = src.fetchmany(batch)
                if not chunk:
                    break
                cur.executemany(ins, [convert_row(r, kinds, names, table, fixes)
                                      for r in chunk])
                my.commit()
                n += len(chunk)
                if n % 100000 < batch:
                    print("   %s %s행" % (table, format(n, ",")), flush=True)
    except Exception as e:
        raise RuntimeError("%s: %s행을 넣은 뒤 멈췄습니다: %s" % (table, format(n, ","), e)) from e
    return n


def orphan_queries(post_sql):
    """schema_post.sql 의 외래키마다 고아 행을 세는 질의입니다."""
    out = []
    for child, ccol, parent, pcol in _FK.findall(post_sql):
        out.append(("%s.%s → %s.%s" % (child, ccol, parent, pcol),
                    "SELECT COUNT(*) FROM `%s` c LEFT JOIN `%s` p "
                    "ON c.`%s` = p.`%s` WHERE c.`%s` IS NOT NULL AND p.`%s` IS NULL"
                    % (child, parent, ccol, pcol, ccol, pcol)))
    expected = post_sql.count("FOREIGN KEY")
    if len(out) != expected:
        raise ValueError("외래키 %d개 중 %d개만 읽었습니다. schema_post.sql 형식을 확인하십시오."
                        % (expected, len(out)))
    return out


def render_report(snapshot, counts, fixes, orphans, secs):
    lines = ["# MySQL 적재 보고", "",
             "- 스냅샷: `%s`" % Path(snapshot).name,
             "- 적재 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "- 걸린 시간: %.0f분" % (secs / 60), "",
             "| 표 | 행 |", "|---|---|"]
    lines += ["| %s | %s |" % (t, format(n, ",")) for t, n in counts.items()]
    lines += ["", "## 값 정리", "", "| 표.열 | 처리 | 건수 |", "|---|---|---|"]
    lines += ["| %s.%s | %s | %s |" % (t, c, what, format(n, ","))
              for (t, c, what), n in sorted(fixes.items())]
    lines += ["", "## 외래키 고아 행", "", "| 관계 | 고아 행 |", "|---|---|"]
    lines += ["| %s | %s |" % (label, format(n, ",")) for label, n in orphans]
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--fresh", action="store_true",
                    help="표를 지우고 schema.sql 로 새로 만듭니다")
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 이 표만 비우고 다시 넣습니다")
    args = ap.parse_args()

    if args.fresh and args.tables:
        ap.error("--fresh 와 --tables 는 함께 쓸 수 없습니다. --fresh 는 모든 표를 지우고 새로 만듭니다.")

    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    table_list = ([t.strip() for t in args.tables.split(",") if t.strip()]
                  if args.tables else list(types))
    tables = list(dict.fromkeys(table_list))
    unknown = [t for t in tables if t not in types]
    if unknown:
        raise SystemExit("schema_types.json 에 없는 표: %s" % ", ".join(unknown))

    sq = sqlite3.connect(Path(args.snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    my = myconn.connect()
    try:
        with my.cursor() as cur:
            for stmt in SESSION_SETUP:
                cur.execute(stmt)
            if args.fresh:
                for t in types:
                    cur.execute("DROP TABLE IF EXISTS %s" % q(t))
                for stmt in split_sql((OUT_DIR / "schema.sql").read_text(encoding="utf-8")):
                    cur.execute(stmt)
            else:
                for t in tables:
                    cur.execute("TRUNCATE TABLE %s" % q(t))
        my.commit()

        t0 = time.time()
        fixes = collections.Counter()
        counts = {}
        for t in tables:
            try:
                counts[t] = load_table(sq, my, t, types[t], fixes)
                print("%-34s %12s행" % (t, format(counts[t], ",")), flush=True)
            except Exception as e:
                print("%s 를 넣다가 멈췄습니다." % t, flush=True)
                print("   인덱스·외래키는 아직 만들지 않았습니다. 이 표는 일부만 들어갔을 수 있습니다.", flush=True)
                print("   --fresh 로 처음부터 다시 넣으십시오.", flush=True)
                raise

        post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
        orphans = []
        with my.cursor() as cur:
            if args.fresh:
                for stmt in split_sql(post):
                    print("   후처리: %s" % stmt[:80], flush=True)
                    cur.execute(stmt)
            for label, sql in orphan_queries(post):
                cur.execute(sql)
                orphans.append((label, cur.fetchone()[0]))
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        my.commit()

        if args.fresh:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(render_report(args.snapshot, counts, fixes, orphans,
                                            time.time() - t0),
                              encoding="utf-8", newline="\n")
            print("보고서: %s" % REPORT)
        else:
            print("일부 표만 다시 넣었으므로 %s 는 고치지 않았습니다." % REPORT.name)
            print()
            for t, n in counts.items():
                print("%-34s %12s행" % (t, format(n, ",")), flush=True)

        bad = [(label, n) for label, n in orphans if n]
        for label, n in bad:
            print("고아 행 %s: %s" % (label, format(n, ",")))
        return 1 if bad else 0
    finally:
        my.close()
        sq.close()


if __name__ == "__main__":
    sys.exit(main())
