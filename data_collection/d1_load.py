# -*- coding: utf-8 -*-
"""D1 에 직접 넣을 때 쓰는 공통 조각입니다.

수집 스크립트들이 저마다 SQL 을 만들면 같은 실수를 여러 번 합니다.
실제로 `daily_pbp_to_d1.py` 에서 문 길이를 **글자 수**로 세는 버그가
있었습니다. 한글은 UTF-8 로 3바이트라 문 하나가 108,774바이트가 되어
D1 한도 100,000 을 넘었고, wrangler 가 `D1_RESET_DO` 로 실패했습니다.
그런 계산은 한 곳에만 두는 편이 안전합니다.

GitHub Actions 러너에는 `database/kbo_stats.db` 가 없습니다. 226MB 라
git 에 두지 않기 때문입니다. 그래서 수집한 값을 로컬 SQLite 를 거치지
않고 바로 D1 에 넣습니다.

## D1 끄기(BSTATS_D1)

    BSTATS_D1   on(기본)  지금처럼 D1 에 쓰고 D1 을 읽습니다
                off       D1 에 손대지 않습니다. 쓰기는 건너뛰고(한 줄 알림),
                          읽기(query·d1_columns)는 Cloud SQL(MySQL)에서 합니다

D1 무료 읽기 한도(하루 500만 행)가 바닥나 사이트가 멈춘 일이 이어져
(2026-10-03), 사이트가 MySQL 을 읽게 된 뒤로 수집도 MySQL 만 쓰게 했습니다.
워크플로는 저장소 변수 `D1_WRITE=on` 일 때만 on 으로 둡니다(되돌리기용).
켜고 끄는 판단은 `d1_enabled()` 한 곳에서만 합니다.

off 일 때 MySQL 접속 파일은 `BSTATS_MYSQL_SETTINGS`(migration/mysql/conn.py)
입니다. 쓰기는 각 스크립트의 `mysql_sink.mirror()` 가 하고, off 에서는 실패하면
작업이 실패합니다(MySQL 이 유일한 저장소이기 때문입니다).
"""
import datetime
import decimal
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DB_NAME = "kbo-stats"

D1_ENV = "BSTATS_D1"
D1_MODES = ("on", "off")


def d1_enabled():
    """D1 을 쓰고 읽는지 봅니다. 환경 변수 BSTATS_D1 이 없으면 on 입니다.

    로컬 도구와 테스트는 따로 정하지 않으면 지금처럼 D1 을 씁니다.
    """
    v = (os.environ.get(D1_ENV) or "on").strip().lower()
    if v not in D1_MODES:
        raise ValueError("%s 는 on·off 중 하나여야 합니다: %r" % (D1_ENV, v))
    return v == "on"


def skipped(what):
    """D1 이 꺼져 있어 건너뛴 일을 한 줄로 남깁니다."""
    print("D1 꺼짐: %s" % " ".join(str(what).split())[:160], flush=True)


def require_d1(what):
    """D1 이 있어야만 뜻이 있는 도구(대조·D1 내려받기·D1 되채우기)를 막습니다.

    off 에서 돌면 D1 대신 MySQL 을 읽어 "MySQL 과 MySQL 을 견주는" 식으로
    틀렸는데 맞아 보이는 결과를 내므로, 아예 멈춥니다.
    """
    if not d1_enabled():
        raise SystemExit("D1 이 꺼져 있어(%s=off) 멈춥니다: %s. "
                         "D1 이 필요하면 %s=on 으로 돌리십시오." % (D1_ENV, what, D1_ENV))

# subprocess 에 **리스트**를 주면서 shell=True 를 켜면 두 플랫폼이 다르게
# 동작합니다. 윈도우는 리스트를 이어붙여 실행하지만, POSIX 는 첫 항목만
# 실행하고 나머지를 $0, $1... 로 넘깁니다. 러너(우분투)에서는 `npx` 만
# 돌고 끝났습니다.
#
# **오류도 안 보였습니다.** 0.x초 만에 실패하고, 워크플로 단계가
# continue-on-error 라 초록 체크로 표시됐습니다. 그래서 "성공했는데
# 데이터가 안 들어온" 상태로 보였습니다. 로컬(윈도우) 수동 실행은
# 멀쩡히 되니 더 찾기 어려웠습니다.
#
# 윈도우에서는 `npx` 가 실제로 `npx.cmd` 라 shell 없이는 찾지 못합니다.
# 그래서 플랫폼을 보고 켭니다.
USE_SHELL = os.name == "nt"

# D1 문 하나의 상한은 100,000 바이트입니다. 여유를 두고 자릅니다.
MAX_STATEMENT_BYTES = 90_000


def sql_literal(v):
    """값 하나를 SQL 리터럴로 만듭니다.

    CSV 는 모든 값이 문자열입니다. 빈 칸은 NULL 로, 나머지는 문자열로
    넣습니다. 숫자로 바꾸지 않는 이유가 있습니다. **컬럼 타입은 D1 이
    알고 있고 SQLite 는 문자열을 알아서 변환합니다.** 여기서 추측해
    바꾸면 `007` 같은 값이 7 이 되어 원본과 달라집니다.
    """
    if v is None:
        return "NULL"
    s = str(v)
    # 크롤러가 없는 값을 '-' 로 씁니다. 그대로 넣으면 숫자 컬럼에
    # 문자열 '-' 가 들어가 계산이 어긋납니다.
    if s == "" or s == "-":
        return "NULL"
    return "'" + s.replace("'", "''") + "'"


def _row_piece(row, columns):
    return "(" + ",".join(sql_literal(row.get(c)) for c in columns) + ")"


def _batched(head, tail, pieces, max_bytes):
    """조각들을 바이트 한도에 맞춰 문 여러 개로 나눕니다.

    **글자 수가 아니라 바이트로 셉니다.** 선수 이름과 상황 서술이
    한글이라 UTF-8 로 세 배가 됩니다.
    """
    fixed = len(head.encode("utf-8")) + len(tail.encode("utf-8"))
    out, batch, size = [], [], 0
    for piece in pieces:
        n = len(piece.encode("utf-8"))
        # 한 행이라도 넣고 나서 크기를 봅니다. 빈 배치를 내보내면
        # 문법 오류가 됩니다.
        if batch and size + n + 1 > max_bytes - fixed:
            out.append(head + ",".join(batch) + tail)
            batch, size = [], 0
        batch.append(piece)
        size += n + 1
    if batch:
        out.append(head + ",".join(batch) + tail)
    return out


def build_inserts(table, columns, rows, max_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 INSERT 문 여러 개로 나눕니다."""
    if not rows:
        return []
    head = 'INSERT INTO "%s" (%s) VALUES ' % (
        table, ",".join('"%s"' % c for c in columns))
    pieces = (_row_piece(r, columns) for r in rows)
    return _batched(head, ";", pieces, max_bytes)


def build_upserts(table, columns, keys, rows, touch=None, keep=(),
                  max_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 UPSERT(있으면 갱신) 문 여러 개로 나눕니다.

    공식 통계는 시즌 내내 같은 (player_id, season) 이 매일 갱신됩니다.
    지웠다 넣으면 그 사이에 표가 비어 화면이 깨지고, 쓰기도 두 배로
    계상됩니다. ON CONFLICT 로 제자리 갱신합니다.

    touch 는 갱신할 때 `datetime('now')` 로 채울 컬럼입니다
    (보통 updated_at).

    keep 은 넣을 때만 쓰고 갱신할 때는 건드리지 않을 컬럼입니다
    (보통 created_at). 이게 없으면 매일 갱신할 때마다 최초 등록 시각이
    오늘로 덮여 "언제부터 있던 선수인지"를 잃습니다.
    """
    if not rows:
        return []
    # touch 컬럼을 여기서 빼야 합니다. 빼지 않으면 SET 절에 같은 컬럼이
    # 두 번(`=excluded.x` 와 `=datetime('now')`) 들어가 SQLite 가
    # "duplicate column name" 으로 거부합니다.
    keyset = set(keys) | set(keep) | ({touch} if touch else set())
    updatable = [c for c in columns if c not in keyset]
    if not updatable:
        raise ValueError("갱신할 컬럼이 없습니다: %s" % table)

    head = 'INSERT INTO "%s" (%s) VALUES ' % (
        table, ",".join('"%s"' % c for c in columns))
    sets = ['"%s"=excluded."%s"' % (c, c) for c in updatable]
    if touch:
        sets.append('"%s"=datetime(\'now\')' % touch)
    tail = " ON CONFLICT(%s) DO UPDATE SET %s;" % (
        ",".join('"%s"' % k for k in keys), ",".join(sets))
    pieces = (_row_piece(r, columns) for r in rows)
    return _batched(head, tail, pieces, max_bytes)


def run_d1(sql, json_out=False, db_name=DB_NAME):
    if not d1_enabled():
        skipped("%s 에 SQL 보내기 (%s)" % (db_name, sql[:80]))
        return ""
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", db_name,
           "--remote", "--command", sql, "--yes"]
    if json_out:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, shell=USE_SHELL,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def run_d1_file(path, db_name=DB_NAME):
    if not d1_enabled():
        skipped("%s 에 %s 올리기" % (db_name, Path(path).name))
        return ""
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", db_name,
           "--remote", "--file", str(path), "--yes"]
    r = subprocess.run(cmd, capture_output=True, text=True, shell=USE_SHELL,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def query(sql, db_name=DB_NAME):
    """SELECT 결과를 dict 목록으로 돌려줍니다.

    D1 이 꺼져 있으면 같은 SELECT 를 MySQL 에서 돌립니다(`mysql_query`).
    샤드 DB 이름(db_name)은 보지 않습니다. MySQL 은 play_by_play 가 표
    하나라 DB 도 하나입니다.
    """
    if not d1_enabled():
        return mysql_query(sql)
    out = run_d1(sql, json_out=True, db_name=db_name)
    # wrangler 가 배너를 먼저 찍으므로 JSON 시작 지점부터 읽습니다.
    data = json.loads(out[out.find("["):])
    return data[0]["results"]


# --- D1 이 꺼져 있을 때의 읽기(MySQL) ----------------------------------------
#
# 수집 스크립트의 SELECT 는 D1(SQLite) 말투로 쓰여 있습니다. 바꿔야 하는 것만
# 바꿉니다. 끝의 `;` 를 떼고, 큰따옴표 이름("x")을 백틱(`x`)으로 바꿉니다.
# MySQL 은 큰따옴표를 글자로 읽어 `SELECT "name"` 이 열이 아니라 글자
# 'name' 이 되기 때문입니다. 작은따옴표 안의 글자는 건드리지 않습니다.
#
# SQLite 에만 있는 표 정보 읽기 두 가지는 information_schema 로 바꿉니다.
#   PRAGMA table_info(x)                              -> information_schema.columns
#   SELECT name FROM sqlite_master WHERE type='table' -> information_schema.tables

_PRAGMA_TABLE_INFO = re.compile(
    r"""^PRAGMA\s+table_info\(\s*["`']?([A-Za-z0-9_]+)["`']?\s*\)$""", re.I)
_SQLITE_MASTER_TABLES = re.compile(
    r"^SELECT\s+name\s+FROM\s+sqlite_master\s+WHERE\s+type\s*=\s*'table'"
    r"(?:\s+AND\s+name\s*=\s*'([A-Za-z0-9_]+)')?"
    r"(?:\s+ORDER\s+BY\s+name)?$", re.I)

MYSQL_COLUMNS_SQL = (
    "SELECT ORDINAL_POSITION - 1 AS cid, COLUMN_NAME AS name, COLUMN_TYPE AS type, "
    "IF(IS_NULLABLE = 'NO', 1, 0) AS `notnull`, IF(COLUMN_KEY = 'PRI', 1, 0) AS pk "
    "FROM information_schema.columns "
    "WHERE table_schema = DATABASE() AND table_name = %s ORDER BY ORDINAL_POSITION")
MYSQL_TABLES_SQL = (
    "SELECT TABLE_NAME AS name FROM information_schema.tables "
    "WHERE table_schema = DATABASE() AND table_type = 'BASE TABLE'")


def _quote_idents(sql):
    """작은따옴표 글자 밖의 "이름" 을 `이름` 으로 바꿉니다."""
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            # 작은따옴표 글자는 '' 가 따옴표 하나입니다. 통째로 옮깁니다.
            j = i + 1
            while j < n:
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            out.append(sql[i:j + 1])
            i = j + 1
        elif ch == '"':
            j, name = i + 1, []
            while j < n:
                if sql[j] == '"':
                    if j + 1 < n and sql[j + 1] == '"':
                        name.append('"')
                        j += 2
                        continue
                    break
                name.append(sql[j])
                j += 1
            if j >= n:
                raise ValueError("닫히지 않은 큰따옴표가 있습니다: %s" % sql[:120])
            out.append("`%s`" % "".join(name).replace("`", "``"))
            i = j + 1
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def to_mysql(sql):
    """D1 말투 SELECT 하나를 MySQL 에서 돌릴 (SQL, 인자) 로 바꿉니다.

    SELECT 가 아니면 ValueError 입니다. 이 경로는 읽기 전용입니다. 쓰기는
    `mysql_sink.mirror()` 만 합니다.
    """
    s = (sql or "").strip()
    while s.endswith(";"):
        s = s[:-1].rstrip()
    m = _PRAGMA_TABLE_INFO.match(s)
    if m:
        return MYSQL_COLUMNS_SQL, [m.group(1)]
    if re.search(r"\bsqlite_master\b", s, re.I):
        m = _SQLITE_MASTER_TABLES.match(s)
        if not m:
            raise ValueError("이 sqlite_master 질의는 MySQL 로 옮기지 못합니다: %s" % s[:120])
        if m.group(1):
            return MYSQL_TABLES_SQL + " AND table_name = %s ORDER BY TABLE_NAME", [m.group(1)]
        return MYSQL_TABLES_SQL + " ORDER BY TABLE_NAME", None
    if not re.match(r"SELECT\b", s, re.I):
        raise ValueError("D1 이 꺼져 있을 때 query() 는 SELECT 만 MySQL 에서 돌립니다: %s"
                         % s[:120])
    return _quote_idents(s), None


def d1_value(v):
    """MySQL 값을 D1(wrangler --json) 이 주던 파이썬 타입으로 맞춥니다.

    MySQL 은 SUM·정수 나눗셈을 Decimal 로, DATE·DATETIME 열을 날짜 객체로
    줍니다. D1 은 정수·실수·글자였습니다. 수집 코드가 `int(...)`·`str(...)`·
    문자열 비교를 하므로 모양을 맞춥니다. 바이트는 그대로 둡니다.
    """
    if isinstance(v, decimal.Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.isoformat()
    return v


def _mysql_connect():
    root = Path(__file__).resolve().parent.parent
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    from migration.mysql import conn as myconn
    return myconn.connect()


def mysql_query(sql, connect=None):
    """SELECT 하나를 MySQL 에서 돌려 dict 목록으로 돌려줍니다.

    부를 때마다 새로 붙고 닫습니다. 연결을 오래 두면 앞서 시작한 읽기
    시점에 묶여, 그 사이 mirror() 가 쓴 값이 안 보일 수 있기 때문입니다.
    읽기 전용 트랜잭션으로 열어 실수로 쓰는 문이 지나가지 못하게 합니다.
    """
    stmt, params = to_mysql(sql)
    con = (connect or _mysql_connect)()
    try:
        with con.cursor() as cur:
            cur.execute("START TRANSACTION READ ONLY")
            cur.execute(stmt, params)
            names = [d[0] for d in cur.description]
            rows = [{k: d1_value(v) for k, v in zip(names, r)} for r in cur.fetchall()]
        con.rollback()
        return rows
    finally:
        con.close()


def d1_columns(table, db_name=DB_NAME):
    """D1 의 실제 컬럼 순서를 읽습니다.

    CSV 헤더를 그대로 믿지 않습니다. 크롤러가 컬럼을 더하거나 순서를
    바꿔도 D1 스키마가 정본입니다. 다른 컬럼을 넣으려 하면 적재가
    통째로 실패합니다.

    D1 이 꺼져 있으면 MySQL 의 열 순서(information_schema.columns)입니다.
    """
    return [r["name"] for r in query('PRAGMA table_info("%s");' % table,
                                     db_name=db_name)]


def refresh_count(table, db_name=DB_NAME):
    """meta_table_counts 를 갱신합니다.

    빠뜨리면 데이터 탐색기가 어제 행 수를 계속 보여 줍니다
    (src/lib/counts.js).

    D1 이 꺼져 있으면 건너뜁니다. MySQL 쪽은 mirror() 안에서
    Sink.refresh_count 가 갱신합니다.
    """
    if not d1_enabled():
        skipped("%s 의 meta_table_counts(%s) 갱신" % (db_name, table))
        return
    run_d1("INSERT OR REPLACE INTO meta_table_counts "
           "SELECT '%s', COUNT(*), datetime('now') FROM \"%s\";"
           % (table, table), db_name=db_name)


def purge_cache(base_url, token):
    """Worker 캐시를 비웁니다.

    적재만 하고 비우지 않으면 캐시가 만료될 때까지(기본 한 시간) 화면이
    어제 숫자를 보여 줍니다. 2026 시즌을 넣었을 때 실제로 겪었습니다.
    """
    import urllib.request
    import urllib.error
    req = urllib.request.Request(
        base_url.rstrip("/") + "/admin/purge-cache", method="POST")
    req.add_header("Authorization", "Bearer " + token)
    # Cloudflare 엣지가 Python-urllib UA 를 1010 으로 막습니다.
    req.add_header("User-Agent", "Mozilla/5.0 (compatible; kbo-actions)")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8")[:200]
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:200]


def _self_test():
    """자체 점검입니다. `py data_collection/d1_load.py` 로 돌립니다.

    여기 걸린 두 가지는 실제로 났던 버그입니다. 다시 나면 여기서
    먼저 걸립니다.
    """
    import sqlite3

    ok = True

    # 1. 한글이 섞여도 문 하나가 100,000 바이트를 넘지 않아야 합니다.
    rows = [{"a": "가" * 100, "b": i} for i in range(500)]
    big = max(len(s.encode("utf-8"))
              for s in build_inserts("t", ["a", "b"], rows))
    big2 = max(len(s.encode("utf-8"))
               for s in build_upserts("t", ["a", "b"], ["b"], rows,
                                      touch="updated_at"))
    print("최대 문 크기  INSERT %s / UPSERT %s 바이트 (한도 100,000)"
          % (format(big, ","), format(big2, ",")))
    if big >= 100_000 or big2 >= 100_000:
        print("  실패: 한도를 넘습니다")
        ok = False

    # 2. UPSERT 가 실제 SQLite 에서 의도대로 동작해야 합니다.
    #    같은 컬럼이 SET 절에 두 번 들어가면 여기서 예외가 납니다.
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a TEXT, b INTEGER, v TEXT, "
                 "created_at TEXT, updated_at TEXT, PRIMARY KEY(a,b))")
    cols = ["a", "b", "v", "created_at", "updated_at"]
    old = {"a": "x", "b": "1", "v": "처음",
           "created_at": "2020-01-01 00:00:00",
           "updated_at": "2020-01-01 00:00:00"}
    new = dict(old, v="나중", created_at="2030-09-09 00:00:00",
               updated_at="2030-09-09 00:00:00")
    for batch in (old, new):
        for s in build_upserts("t", cols, ["a", "b"], [batch],
                               touch="updated_at", keep=["created_at"]):
            conn.execute(s)
    n, v, created = conn.execute(
        "SELECT COUNT(*), MAX(v), MAX(created_at) FROM t").fetchone()
    print("UPSERT  행 %d개, v=%s, created_at=%s" % (n, v, created))
    if n != 1 or v != "나중" or not created.startswith("2020"):
        print("  실패: 갱신이 의도와 다릅니다")
        ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_self_test())
