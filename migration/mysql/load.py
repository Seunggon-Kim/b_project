# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 MySQL 로 옮깁니다.

    py -m migration.mysql.load --snapshot ~/.bstats/snapshots/d1_20261002.db --fresh
    py -m migration.mysql.load --snapshot … --tables players,teams

--fresh 는 표를 지우고 schema.sql 로 새로 만든 뒤, 다 넣고 나서
schema_post.sql(인덱스·외래키)을 적용합니다. --tables 는 --fresh 로 완료한
뒤에 특정 표만 다시 넣을 때 씁니다(인덱스·외래키는 이미 있습니다). 짧은 연결
끊김은 묶음마다 최대 3번 다시 연결해 이어 넣으므로, 다시 시도를 다 쓰고도
--fresh 가 도중에 실패했을 때만 다시 --fresh 로 처음부터 넣으십시오.

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

import pymysql

from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, ROOT, q, split_sql

REPORT = ROOT / "docs" / "mysql-migration" / "load-report.md"
BATCH = 2000
SESSION_SETUP = ("SET FOREIGN_KEY_CHECKS=0",
                 "SET SESSION sql_mode = CONCAT(@@SESSION.sql_mode, ',NO_AUTO_VALUE_ON_ZERO')")
RETRIES = 3        # 한 묶음이 처음 실패한 뒤 다시 시도하는 최대 횟수
RETRY_WAIT = 5     # 다시 시도 전 기다리는 초(시도 번호를 곱합니다)
RETRYABLE = (2003, 2006, 2013, 2055)   # MySQL 클라이언트의 연결 오류 번호
_sleep = time.sleep                    # 테스트에서 바꿔 끼웁니다
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


def is_retryable(exc):
    """연결이 끊겨서 난 오류인지 봅니다. 값·제약 오류(IntegrityError, DataError,
    변환 중 ValueError 등)는 다시 해도 같으므로 False 입니다."""
    if isinstance(exc, (pymysql.err.OperationalError, pymysql.err.InterfaceError)):
        return bool(exc.args) and exc.args[0] in RETRYABLE
    return isinstance(exc, (ConnectionError, TimeoutError, OSError))


def _reconnect_and_count(my, table):
    """다시 연결하고 표의 행 수를 돌려줍니다. 세션 설정은 연결과 함께 사라지므로
    SESSION_SETUP 을 다시 겁니다."""
    my.ping(reconnect=True)
    with my.cursor() as cur:
        for stmt in SESSION_SETUP:
            cur.execute(stmt)
        cur.execute("SELECT COUNT(*) FROM %s" % q(table))
        return cur.fetchone()[0]


def _insert_batch(my, cur, table, ins, rows, done):
    """한 묶음을 넣고 커밋합니다. 연결이 끊기면 최대 RETRIES번 다시 시도합니다.

    done 은 이 묶음 앞까지 이미 들어간 행 수입니다. 커밋 응답을 받기 전에 끊겼을
    수 있으므로, 다시 연결한 뒤 표의 행 수로 이 묶음이 들어갔는지 확인합니다.
    행 수가 done 이면 안 들어간 것이라 다시 넣고, done + 묶음 크기면 이미 들어간
    것이라 넘어갑니다. 그 밖이면 상태를 알 수 없으므로 멈춥니다.
    """
    last = None
    for attempt in range(RETRIES + 1):
        if attempt:
            print("   %s: 연결이 끊겨 %d번째 다시 시도합니다(%s행까지 들어감)"
                  % (table, attempt, format(done, ",")), flush=True)
            _sleep(RETRY_WAIT * attempt)
            try:
                count = _reconnect_and_count(my, table)
            except Exception as e:
                if not is_retryable(e):
                    raise
                last = e
                continue
            if count == done + len(rows):
                return
            if count != done:
                raise RuntimeError(
                    "연결이 끊긴 뒤 표에 %s행이 있어, 이 묶음이 들어갔는지 알 수 없습니다"
                    "(%s행 또는 %s행이어야 합니다)"
                    % (format(count, ","), format(done, ","),
                       format(done + len(rows), ","))) from last
        try:
            cur.executemany(ins, rows)
            my.commit()
            return
        except Exception as e:
            if not is_retryable(e):
                raise
            last = e
    raise last


def load_table(sq, my, table, spec, fixes, batch=BATCH):
    """스냅샷 표 하나를 rowid 순서대로 옮깁니다. 넣은 행 수를 돌려줍니다.

    새 번호 열(pbp_id)에는 스냅샷 줄 번호(rowid)를 그대로 넣습니다. 그래서
    재시도해도 번호가 밀리지 않고, 같은 행이 두 번 들어가면 오류로 드러납니다.
    """
    renumber = spec.get("renumber")
    names = [c for c, _ in spec["columns"] if c != renumber]
    kinds = [k for c, k in spec["columns"] if c != renumber]
    src = sq.execute('SELECT %s%s FROM "%s" ORDER BY rowid'
                     % ("rowid, " if renumber else "",
                        ", ".join('"%s"' % c for c in names), table))
    ins = insert_sql(table, [renumber] + names if renumber else names)
    n = 0
    try:
        with my.cursor() as cur:
            while True:
                chunk = src.fetchmany(batch)
                if not chunk:
                    break
                if renumber:
                    rows = [(int(r[0]),) + convert_row(r[1:], kinds, names, table, fixes)
                            for r in chunk]
                else:
                    rows = [convert_row(r, kinds, names, table, fixes) for r in chunk]
                _insert_batch(my, cur, table, ins, rows, n)
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
