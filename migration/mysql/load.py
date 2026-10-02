# -*- coding: utf-8 -*-
"""SQLite 스냅샷을 MySQL 로 옮깁니다.

    py -m migration.mysql.load --snapshot ~/.bstats/snapshots/d1_20261002.db --fresh
    py -m migration.mysql.load --snapshot … --tables players,teams
    py -m migration.mysql.load --snapshot … --resume

--fresh 는 표를 지우고 schema.sql 로 새로 만든 뒤, 다 넣고 나서
schema_post.sql(인덱스·외래키)을 적용합니다. --tables 는 --fresh 로 완료한
뒤에 특정 표만 다시 넣을 때 씁니다(인덱스·외래키는 이미 있습니다). 연결이
끊기면 묶음마다 최대 8번(약 5분) 다시 연결해 이어 넣습니다.

--resume 은 멈춘 --fresh 를 이어서 넣습니다(--fresh·--tables 와 함께 쓸 수
없습니다). 플레이 기록은 이미 들어간 번호(pbp_id = 스냅샷 줄 번호) 뒤부터 넣고,
작은 표는 행 수가 같으면 건너뛰고 다르면 비우고 다시 넣습니다. 번호가 비어
있으면 이어 넣을 수 없으므로 --fresh 로 다시 넣으십시오. 끝나면 없는
인덱스·외래키만 만듭니다.

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
RETRIES = 8        # 한 묶음이 처음 실패한 뒤 다시 시도하는 최대 횟수
RETRYABLE = (2003, 2006, 2013, 2055)   # MySQL 클라이언트의 연결 오류 번호
_sleep = time.sleep                    # 테스트에서 바꿔 끼웁니다
_POST_INDEX = re.compile(r"CREATE (?:UNIQUE )?INDEX `([^`]+)` ON `([^`]+)`")
_POST_FK = re.compile(r"ALTER TABLE `([^`]+)` ADD CONSTRAINT `([^`]+)` FOREIGN KEY")
_FK = re.compile(r"ALTER TABLE `([^`]+)` ADD CONSTRAINT `[^`]+` FOREIGN KEY "
                 r"\(`([^`]+)`\) REFERENCES `([^`]+)` \(`([^`]+)`\)")


def retry_wait(attempt):
    """다시 시도 전 기다리는 초(1부터 세는 시도 번호). 5, 10, 20, 40, 60, 60, …"""
    return min(60, 5 * 2 ** (attempt - 1))


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
            _sleep(retry_wait(attempt))
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


def load_table(sq, my, table, spec, fixes, batch=BATCH, start_after=0, already=0):
    """스냅샷 표 하나를 rowid 순서대로 옮깁니다. 표에 들어 있는 행 수를 돌려줍니다.

    이어 넣을 때는 start_after(번호 열이 있는 표만: 이 rowid 보다 큰 행부터)와
    already(이미 들어 있는 행 수, 커밋 확인용 시작 값)를 줍니다.

    새 번호 열(pbp_id)에는 스냅샷 줄 번호(rowid)를 그대로 넣습니다. 그래서
    재시도해도 번호가 밀리지 않고, 같은 행이 두 번 들어가면 오류로 드러납니다.
    """
    renumber = spec.get("renumber")
    names = [c for c, _ in spec["columns"] if c != renumber]
    kinds = [k for c, k in spec["columns"] if c != renumber]
    where = " WHERE rowid > %d" % int(start_after) if renumber and start_after else ""
    src = sq.execute('SELECT %s%s FROM "%s"%s ORDER BY rowid'
                     % ("rowid, " if renumber else "",
                        ", ".join('"%s"' % c for c in names), table, where))
    ins = insert_sql(table, [renumber] + names if renumber else names)
    n = already
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


def resume_table(sq, my, table, spec, fixes, batch=BATCH):
    """멈춘 적재를 이어서 이 표를 채웁니다. 표에 들어 있는 행 수를 돌려줍니다."""
    renumber = spec.get("renumber")
    with my.cursor() as cur:
        if renumber:
            cur.execute("SELECT COALESCE(MAX(%s), 0), COUNT(*) FROM %s"
                        % (q(renumber), q(table)))
            top, count = cur.fetchone()
            if top != count:
                raise SystemExit("%s: 번호가 비어 있어(최대 %s, 행 %s) 이어서 넣을 수 없습니다. "
                                 "--fresh 로 다시 넣으십시오." % (table, top, count))
            print("   %s: %s행까지 들어 있어 그 뒤부터 넣습니다" % (table, format(top, ",")),
                  flush=True)
            return load_table(sq, my, table, spec, fixes, batch,
                              start_after=top, already=top)
        cur.execute("SELECT COUNT(*) FROM %s" % q(table))
        have = cur.fetchone()[0]
        want = sq.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        if have == want:
            print("%s: 이미 다 들어 있어 건너뜁니다" % table, flush=True)
            return have
        cur.execute("TRUNCATE TABLE %s" % q(table))
    my.commit()
    return load_table(sq, my, table, spec, fixes, batch)


def post_object(stmt):
    """후처리 문장이 만드는 개체를 (종류, 표, 이름)으로 돌려줍니다.
    종류는 'index' 또는 'fk' 입니다."""
    m = _POST_INDEX.match(stmt)
    if m:
        return ("index", m.group(2), m.group(1))
    m = _POST_FK.match(stmt)
    if m:
        return ("fk", m.group(1), m.group(2))
    raise ValueError("알 수 없는 후처리 문장: %s" % stmt[:80])


_EXISTS = {
    "index": ("SELECT COUNT(*) FROM information_schema.STATISTICS "
              "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND INDEX_NAME = %s"),
    "fk": ("SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS "
           "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND CONSTRAINT_NAME = %s "
           "AND CONSTRAINT_TYPE = 'FOREIGN KEY'"),
}


def apply_post_skipping_existing(cur, post_sql):
    """schema_post.sql 중 아직 없는 인덱스·외래키만 만듭니다."""
    for stmt in split_sql(post_sql):
        kind, table, name = post_object(stmt)
        cur.execute(_EXISTS[kind], (table, name))
        if cur.fetchone()[0]:
            print("   후처리: 이미 있어 건너뜁니다 %s %s.%s" % (kind, table, name), flush=True)
            continue
        print("   후처리: %s" % stmt[:80], flush=True)
        cur.execute(stmt)


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


def render_report(snapshot, counts, fixes, orphans, secs, resumed=False):
    lines = ["# MySQL 적재 보고", "",
             "- 스냅샷: `%s`" % Path(snapshot).name,
             "- 적재 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "- 걸린 시간: %.0f분" % (secs / 60), "",
             "| 표 | 행 |", "|---|---|"]
    lines += ["| %s | %s |" % (t, format(n, ",")) for t, n in counts.items()]
    if resumed:
        lines += ["", "- 이어서 넣기(--resume): 값 정리 건수는 이번 실행에서 넣은 행만 셉니다"]
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
    ap.add_argument("--resume", action="store_true",
                    help="멈춘 --fresh 를 이어서 넣습니다(--fresh·--tables 와 함께 쓸 수 없습니다)")
    args = ap.parse_args()

    if args.fresh and args.tables:
        ap.error("--fresh 와 --tables 는 함께 쓸 수 없습니다. --fresh 는 모든 표를 지우고 새로 만듭니다.")
    if args.resume and (args.fresh or args.tables):
        ap.error("--resume 은 --fresh·--tables 와 함께 쓸 수 없습니다. "
                 "멈춘 --fresh 를 이어서 넣을 때만 씁니다.")

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
            elif not args.resume:
                for t in tables:
                    cur.execute("TRUNCATE TABLE %s" % q(t))
        my.commit()

        t0 = time.time()
        fixes = collections.Counter()
        counts = {}
        for t in tables:
            try:
                if args.resume:
                    counts[t] = resume_table(sq, my, t, types[t], fixes)
                else:
                    counts[t] = load_table(sq, my, t, types[t], fixes)
                print("%-34s %12s행" % (t, format(counts[t], ",")), flush=True)
            except Exception as e:
                print("%s 를 넣다가 멈췄습니다." % t, flush=True)
                print("   인덱스·외래키는 아직 만들지 않았습니다. 이 표는 일부만 들어갔을 수 있습니다.", flush=True)
                print("   네트워크가 돌아오면 --resume 으로 이어서 넣으십시오(번호가 비면 --fresh).",
                      flush=True)
                raise

        post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
        orphans = []
        with my.cursor() as cur:
            if args.fresh:
                for stmt in split_sql(post):
                    print("   후처리: %s" % stmt[:80], flush=True)
                    cur.execute(stmt)
            elif args.resume:
                apply_post_skipping_existing(cur, post)
            for label, sql in orphan_queries(post):
                cur.execute(sql)
                orphans.append((label, cur.fetchone()[0]))
            cur.execute("SET FOREIGN_KEY_CHECKS=1")
        my.commit()

        if args.fresh or args.resume:
            REPORT.parent.mkdir(parents=True, exist_ok=True)
            REPORT.write_text(render_report(args.snapshot, counts, fixes, orphans,
                                            time.time() - t0, resumed=args.resume),
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
