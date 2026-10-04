# -*- coding: utf-8 -*-
"""수집 스크립트가 Cloud SQL(MySQL)을 읽을 때 쓰는 공통 조각입니다.

모듈 이름(d1_load)은 예전 이름이 남은 것입니다. 지금은 MySQL 만 읽습니다.
D1 은 2026-10-04 에 수집 쪽에서 걷어냈습니다. 이름 바꾸기는 따로 합니다.

쓰기는 여기서 하지 않습니다. 각 스크립트의 `mysql_sink.mirror()` 가 한
트랜잭션으로 쓰고, 실패하면 작업이 실패합니다(MySQL 이 유일한 저장소).

MySQL 접속 파일은 `BSTATS_MYSQL_SETTINGS`(migration/mysql/conn.py)입니다.
"""
import datetime
import decimal
import re
import sys
from pathlib import Path


def query(sql):
    """SELECT 결과를 dict 목록으로 돌려줍니다. MySQL 에서 읽습니다(`mysql_query`)."""
    return mysql_query(sql)


# --- SQLite 말투 SELECT 를 MySQL 로 ---------------------------------------------
#
# 수집 스크립트의 SELECT 는 예전 D1(SQLite) 말투로 쓰여 있습니다. 바꿔야 하는 것만
# 바꿉니다. 끝의 `;` 를 떼고, 큰따옴표 이름("x")을 백틱(`x`)으로 바꿉니다.
# MySQL 은 큰따옴표를 글자로 읽어 `SELECT "name"` 이 열이 아니라 글자
# 'name' 이 되기 때문입니다. 작은따옴표 안의 글자는 건드리지 않습니다.
# 글자 밖의 `||`(SQLite 글자 잇기, MySQL 에서는 OR)는 바꾸지 않고 거절합니다.
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
        elif ch == "|" and i + 1 < n and sql[i + 1] == "|":
            # SQLite 의 `||` 는 글자 잇기지만 MySQL(기본 sql_mode)에서는 OR 입니다.
            # 오류 없이 0·1 이 나와 틀렸는데 맞아 보이므로 바꾸지 않고 멈춥니다.
            raise ValueError("SQLite 글자 잇기(||)는 MySQL 에서 OR 로 읽힙니다. "
                             "CONCAT() 으로 바꾸십시오: %s" % sql[:120])
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def to_mysql(sql):
    """SQLite 말투 SELECT 하나를 MySQL 에서 돌릴 (SQL, 인자) 로 바꿉니다.

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
        raise ValueError("query() 는 SELECT 만 돌립니다(쓰기는 mysql_sink.mirror): %s"
                         % s[:120])
    return _quote_idents(s), None


def d1_value(v):
    """MySQL 값을 수집 코드가 기대하는 파이썬 타입으로 맞춥니다.

    MySQL 은 SUM·정수 나눗셈을 Decimal 로, DATE·DATETIME 열을 날짜 객체로
    줍니다. 수집 코드는 D1 시절의 정수·실수·글자를 전제로 `int(...)`·
    `str(...)`·문자열 비교를 하므로 모양을 맞춥니다. 바이트는 그대로 둡니다.
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


def d1_columns(table):
    """MySQL 표의 실제 열 순서를 읽습니다(information_schema.columns).

    CSV 헤더를 그대로 믿지 않습니다. 크롤러가 컬럼을 더하거나 순서를
    바꿔도 표 스키마가 정본입니다. 다른 컬럼을 넣으려 하면 적재가
    통째로 실패합니다. 이름(d1_)은 예전 이름이 남은 것입니다.
    """
    return [r["name"] for r in query('PRAGMA table_info("%s");' % table)]


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
