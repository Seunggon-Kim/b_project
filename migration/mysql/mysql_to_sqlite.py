# -*- coding: utf-8 -*-
"""MySQL 의 표를 로컬 SQLite 로 내려받습니다. 주간 파생 지표 계산용입니다.

d1_to_sqlite.py 를 대신합니다. D1 에서 내려받으면 play_by_play 400만 행을
읽어 하루 무료 한도(500만)를 거의 다 씁니다. MySQL 은 읽기 한도가 없습니다.

만드는 SQLite 는 d1_to_sqlite 결과와 같은 모양을 따릅니다.
- play_by_play 는 기본키 없이 둡니다(d1_to_sqlite.drop_primary_key 와 같게).
- 날짜는 'YYYY-MM-DD', 일시는 'YYYY-MM-DD HH:MM:SS' 글자로 둡니다.
- 인덱스는 MySQL 에 있는 것을 따라 만듭니다.
- 모든 표를 한 시점(일관된 스냅샷)에서 읽습니다. 내려받는 동안 수집이 돌아도
  표끼리 어긋나지 않습니다.

    py -m migration.mysql.mysql_to_sqlite --out /tmp/kbo_pipeline.db
    py -m migration.mysql.mysql_to_sqlite --out x.db --tables players,teams
"""
import argparse
import datetime
import decimal
import json
import sqlite3
import sys
import time
from pathlib import Path

import pymysql

from migration.d1_to_sqlite import PIPELINE_TABLES
from migration.mysql import conn as myconn
from migration.mysql.ddl import OUT_DIR, q

SQLITE_TYPES = {"int": "INTEGER", "double": "REAL", "text": "TEXT",
                "date": "TEXT", "datetime": "TEXT", "blob": "BLOB"}
NO_PK = {"play_by_play"}
BATCH = 5000


def sqlite_ddl(table, spec, pk):
    cols = ['"%s" %s' % (c, SQLITE_TYPES[k]) for c, k in spec["columns"]]
    if pk and table not in NO_PK:
        cols.append("PRIMARY KEY (%s)" % ", ".join('"%s"' % c for c in pk))
    return 'CREATE TABLE "%s" (%s)' % (table, ", ".join(cols))


def to_sqlite(v):
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        return float(v)
    return v


def primary_key(cur, table):
    cur.execute("SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s "
                "AND CONSTRAINT_NAME = 'PRIMARY' ORDER BY ORDINAL_POSITION", (table,))
    return [r[0] for r in cur.fetchall()]


def secondary_indexes(cur, table):
    cur.execute("SELECT INDEX_NAME, NON_UNIQUE, COLUMN_NAME FROM information_schema.STATISTICS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME <> 'PRIMARY' "
                "ORDER BY INDEX_NAME, SEQ_IN_INDEX", (table,))
    out = {}
    for name, non_unique, col in cur.fetchall():
        out.setdefault(name, [not int(non_unique), []])[1].append(col)
    return [(n, u, cols) for n, (u, cols) in out.items()]


def copy_table(my, sq, table, spec, batch=BATCH):
    """표 하나를 옮기고 옮긴 행 수를 돌려줍니다."""
    cols = [c for c, _ in spec["columns"]]
    with my.cursor() as cur:
        pk = primary_key(cur, table)
        idx = secondary_indexes(cur, table)
    sq.execute('DROP TABLE IF EXISTS "%s"' % table)
    sq.execute(sqlite_ddl(table, spec, pk))
    ins = 'INSERT INTO "%s" (%s) VALUES (%s)' % (
        table, ", ".join('"%s"' % c for c in cols), ", ".join("?" * len(cols)))
    order = (" ORDER BY " + ", ".join(q(c) for c in pk)) if pk else ""
    n = 0
    with my.cursor(pymysql.cursors.SSCursor) as cur:
        cur.execute("SELECT %s FROM %s%s" % (", ".join(q(c) for c in cols), q(table), order))
        while True:
            rows = cur.fetchmany(batch)
            if not rows:
                break
            sq.executemany(ins, [tuple(to_sqlite(v) for v in r) for r in rows])
            n += len(rows)
    for name, unique, icols in idx:
        sq.execute('CREATE %sINDEX "%s" ON "%s" (%s)' % (
            "UNIQUE " if unique else "", name, table, ", ".join('"%s"' % c for c in icols)))
    sq.commit()
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 기본값은 주간 계산에 쓰는 표(d1_to_sqlite.PIPELINE_TABLES)")
    args = ap.parse_args()

    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else PIPELINE_TABLES)
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    unknown = [t for t in tables if t not in types]
    if unknown:
        raise SystemExit("schema_types.json 에 없는 표: %s" % ", ".join(unknown))

    out = Path(args.out)
    if out.exists():
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)
    sq = sqlite3.connect(str(out))
    my = myconn.connect()
    try:
        with my.cursor() as cur:
            cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        for i, t in enumerate(tables, start=1):
            t0 = time.time()
            n = copy_table(my, sq, t, types[t])
            with my.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM %s" % q(t))
                want = cur.fetchone()[0]
            if want != n:
                raise SystemExit("%s 행 수가 어긋납니다. MySQL %s / 로컬 %s"
                                 % (t, format(want, ","), format(n, ",")))
            print("[%2d/%d] %-34s %10s행 %5.0f초"
                  % (i, len(tables), t, format(n, ","), time.time() - t0), flush=True)
        my.rollback()
    finally:
        my.close()
        sq.close()
    print("만든 DB: %s (%.1fMB)" % (out, out.stat().st_size / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main())
