# -*- coding: utf-8 -*-
"""MySQL 의 모든 표를 빅쿼리 `bstats` 데이터셋에 매주 통째로 복사합니다(4단계).

## 왜 이렇게 하나

빅쿼리 `EXTERNAL_QUERY` 는 Cloud SQL MySQL 8.4 를 읽지 못합니다. 빅쿼리 쪽
MySQL 클라이언트가 caching_sha2_password 를 지원하지 않고, 8.4 는
mysql_native_password 계정을 받지 않습니다(구글 문서에 우회 방법이 없다고
적혀 있습니다). 그래서 주간 작업이 매주 표를 통째로 바꿔 넣습니다. 정본은
MySQL 이고, 빅쿼리는 길게는 한 주 늦은 읽기용 사본입니다.

## 무엇을 복사하나

- 표 목록과 열 타입은 MySQL `information_schema.columns` 에서 읽습니다. MySQL 의
  표를 하나도 빼지 않고 복사합니다. SQLite 에만 있는 계산용 표(truncated_games,
  _bak 백업)는 MySQL 표가 아니라 복사하지 않습니다.
- 표마다 행을 어디서 읽을지 고릅니다(plan).
  - sqlite: 주간 작업의 로컬 SQLite(`$KBO_DB`)에 있는 표입니다. `mysql_to_sqlite`
    가 MySQL 에서 내려받았고, 주간 계산이 다시 만든 결과 표는 "결과 표 적재"가
    MySQL 에 올렸으므로 MySQL 과 같습니다. play_by_play 처럼 큰 표를 MySQL 에서
    한 번 더 읽지 않으려는 것입니다.
  - mysql: SQLite 에 없는 표(주간 작업은 계산에 쓰는 표만 내려받습니다)와,
    주간 계산이 로컬에서만 고치고 MySQL 에 올리지 않는 표(LOCAL_ONLY_EDITS)는
    MySQL 에서 바로 읽습니다. MySQL 에서 읽는 표는 모두 한 시점(일관된
    스냅샷)에서 읽습니다.

## 어떻게

표마다 Parquet 파일 하나를 만듭니다. SQLite 커서나 MySQL 서버 쪽(버퍼 없는)
커서로 20만 행씩 읽어 행 그룹 하나로 씁니다. play_by_play 를 통째로 메모리에
올리지 않습니다. 그 파일을 적재 작업 하나로 올립니다(WRITE_TRUNCATE, 명시
스키마). 올린 뒤 빅쿼리 행 수가 읽은 쪽(SQLite 나 MySQL) 행 수와 같은지 봅니다.
표 하나가 실패해도 나머지를 마저 하고, 하나라도 실패하면 0 이 아닌 값으로
끝납니다.

## 타입 규칙(MySQL → 빅쿼리, 모든 열 NULLABLE)

    tinyint·smallint·mediumint·int·bigint(unsigned 포함)·year·bit  INT64
        tinyint(1)·bit 도 숫자로 둡니다(BOOL 로 짐작하지 않습니다).
        bigint unsigned 가 INT64 를 넘으면 그 표는 실패합니다(조용히 자르지 않음).
    decimal(p,s)   s <= 9 이고 p - s <= 29 면 NUMERIC, 아니면 FLOAT64
        NUMERIC 은 정수부 29자리·소수부 9자리입니다. 그보다 크면 담지 못합니다.
    float·double   FLOAT64
    date           DATE
    datetime·timestamp   DATETIME
    time           STRING
        MySQL TIME 은 시간 간격이라 -838:59:59 ~ 838:59:59 입니다. 빅쿼리 TIME 은
        하루 안(00:00:00 ~ 23:59:59)만 담으므로 글자로 둡니다.
    char·varchar·text 류·enum·set·json   STRING
    binary·varbinary·blob 류   BYTES

열 이름은 빅쿼리에 쓸 수 있으면 그대로 둡니다. 쓸 수 없으면 정해진 규칙으로
고치고(bq_column_names), 바꾼 이름을 표 설명과 열 설명에 적습니다.

## 자격

GitHub Actions 에서는 google-github-actions/auth 가 만든 자격 파일(ADC)을
씁니다. 로컬에서는 --token-env 로 OAuth 액세스 토큰이 든 환경 변수 이름을
넘깁니다. `gcloud auth application-default login` 은 쓰지 않습니다.

MySQL 접속은 `migration.mysql.conn` 을 씁니다(BSTATS_MYSQL_SETTINGS, CI 는 수집
계정 bstats_loader 로 SELECT 만 합니다).

    python -m migration.mysql.sqlite_to_bigquery --db "$KBO_DB"
    py -m migration.mysql.sqlite_to_bigquery --db x.db --tables teams,players --token-env BQ_TOKEN
    py -m migration.mysql.sqlite_to_bigquery --db x.db --dry-run
"""
import argparse
import datetime
import decimal
import os
import re
import sqlite3
import sys
import tempfile
import time
from collections import namedtuple
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pymysql
from google.cloud import bigquery

from migration.mysql.typemap import EMPTY_TEXT, INT_LIKE, NUM_LIKE

PROJECT = "bstats-kbo"
DATASET = "bstats"
LOCATION = "asia-northeast3"
MYSQL_DATABASE = "bstats"
CHUNK_ROWS = 200_000
KST = datetime.timezone(datetime.timedelta(hours=9))

# 주간 계산이 로컬 SQLite 에서만 고치고 MySQL 에 올리지 않는 표입니다. SQLite 의
# 것은 MySQL 과 다르므로 MySQL 에서 바로 읽습니다. tests/test_sqlite_to_bigquery.py
# 가 park_factors 스크립트를 훑어 빠진 표가 없는지 봅니다.
LOCAL_ONLY_EDITS = {
    "team_stadium_by_season":
        "build_wrc_plus.py 가 올 시즌 행을 로컬에서만 채우고 MySQL 에 올리지 않습니다",
}

SQLITE, MYSQL = "sqlite", "mysql"

INT_TYPES = {"tinyint", "smallint", "mediumint", "int", "integer", "bigint", "year", "bit"}
FLOAT_TYPES = {"float", "double", "real"}
DECIMAL_TYPES = {"decimal", "numeric"}
STRING_TYPES = {"char", "varchar", "tinytext", "text", "mediumtext", "longtext",
                "enum", "set", "json", "time"}
BYTES_TYPES = {"binary", "varbinary", "tinyblob", "blob", "mediumblob", "longblob"}

# 빅쿼리 NUMERIC 은 정밀도 38, 소수 9자리입니다(정수부 29자리).
NUMERIC_SCALE = 9
NUMERIC_INT_DIGITS = 29
NUMERIC_QUANTUM = decimal.Decimal(1).scaleb(-NUMERIC_SCALE)

# 빅쿼리 열 이름 규칙: 글자·숫자·밑줄, 첫 글자는 글자나 밑줄, 300자까지.
# 아래 접두사는 빅쿼리가 예약해 두었습니다. 대소문자만 다른 이름은 같은 이름입니다.
BQ_NAME_MAX = 300
RESERVED_PREFIXES = ("_TABLE_", "_FILE_", "_PARTITION", "_ROW_TIMESTAMP", "__ROOT__",
                     "_COLIDENTIFIER", "_CHANGE_SEQUENCE_NUMBER", "_CHANGE_TYPE",
                     "_CHANGE_TIMESTAMP")

Column = namedtuple("Column", "name bq_name bq_type mysql_type")
Result = namedtuple("Result", "table source rows seconds error")


# --- 타입과 이름 -----------------------------------------------------------

def bq_type(data_type, column_type="", precision=None, scale=None):
    """MySQL 열 타입 하나를 빅쿼리 타입 이름으로 바꿉니다. 모르는 타입은 ValueError."""
    d = (data_type or "").lower()
    if d in INT_TYPES:
        return "INT64"
    if d in DECIMAL_TYPES:
        p = 10 if precision is None else int(precision)
        s = 0 if scale is None else int(scale)
        return "NUMERIC" if s <= NUMERIC_SCALE and p - s <= NUMERIC_INT_DIGITS else "FLOAT64"
    if d in FLOAT_TYPES:
        return "FLOAT64"
    if d == "date":
        return "DATE"
    if d in ("datetime", "timestamp"):
        return "DATETIME"
    if d in STRING_TYPES:
        return "STRING"
    if d in BYTES_TYPES:
        return "BYTES"
    raise ValueError("빅쿼리 타입을 정하지 않은 MySQL 타입입니다: %s" % (column_type or data_type))


def bq_column_name(name):
    """열 이름 하나를 빅쿼리에 쓸 수 있게 고칩니다. 쓸 수 있는 이름은 그대로입니다."""
    s = re.sub(r"[^A-Za-z0-9_]", "_", name)
    if not re.match(r"[A-Za-z_]", s):
        s = "_" + s
    if s.upper().startswith(RESERVED_PREFIXES):
        s = "c" + s
    return s[:BQ_NAME_MAX]


def bq_column_names(names):
    """표 하나의 열 이름들을 고칩니다. 고친 뒤 겹치면(대소문자 무시) 뒤에 _2, _3 을 붙입니다.

    열 순서대로 정하므로 같은 입력이면 늘 같은 결과입니다.
    """
    out, seen = [], set()
    for n in names:
        base = bq_column_name(n)
        b, k = base, 2
        while b.lower() in seen:
            suffix = "_%d" % k
            b = base[:BQ_NAME_MAX - len(suffix)] + suffix
            k += 1
        seen.add(b.lower())
        out.append(b)
    return out


def table_columns(specs):
    """information_schema 의 (이름, DATA_TYPE, COLUMN_TYPE, 정밀도, 소수) 목록을 Column 으로."""
    names = bq_column_names([s[0] for s in specs])
    return [Column(s[0], b, bq_type(s[1], s[2], s[3], s[4]), s[2])
            for s, b in zip(specs, names)]


# --- 값 바꾸기 -------------------------------------------------------------
#
# SQLite 는 선언과 다른 타입의 값도 받습니다. MySQL 에서 내려받은 표는 값이
# 이미 맞지만, 주간 계산이 다시 만든 표는 정수 열에 3.0 이 들어 있을 수 있습니다.
# MySQL 에 올릴 때와 같은 규칙(typemap.normalize)으로 맞춥니다. 숫자·날짜 열의
# '' 와 '-' 는 NULL 입니다. 글자 열의 '' 는 그대로 둡니다.

def _blank(t):
    return t in EMPTY_TEXT


def to_int(v):
    if isinstance(v, bool):
        return int(v)
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        if v != v:
            return None
        if not v.is_integer():
            raise ValueError("정수가 아닙니다: %r" % v)
        return int(v)
    if isinstance(v, decimal.Decimal):
        if v != v.to_integral_value():
            raise ValueError("정수가 아닙니다: %r" % v)
        return int(v)
    if isinstance(v, (bytes, bytearray)):
        return int.from_bytes(v, "big")          # BIT 값입니다
    if isinstance(v, str):
        t = v.strip()
        if _blank(t):
            return None
        if not INT_LIKE.match(t):
            raise ValueError("정수가 아닙니다: %r" % v)
        return int(t.split(".")[0])
    raise ValueError("정수로 바꿀 수 없습니다: %r" % (v,))


def to_float(v):
    if isinstance(v, (int, float, decimal.Decimal)):
        return float(v)
    if isinstance(v, str):
        t = v.strip()
        if _blank(t):
            return None
        if not NUM_LIKE.match(t):
            raise ValueError("숫자가 아닙니다: %r" % v)
        return float(t)
    raise ValueError("숫자로 바꿀 수 없습니다: %r" % (v,))


def to_numeric(v):
    if isinstance(v, str):
        t = v.strip()
        if _blank(t):
            return None
        if not NUM_LIKE.match(t):
            raise ValueError("숫자가 아닙니다: %r" % v)
        d = decimal.Decimal(t)
    elif isinstance(v, float):
        d = decimal.Decimal(repr(v))
    elif isinstance(v, (int, decimal.Decimal)):
        d = decimal.Decimal(v)
    else:
        raise ValueError("숫자로 바꿀 수 없습니다: %r" % (v,))
    return d.quantize(NUMERIC_QUANTUM, rounding=decimal.ROUND_HALF_EVEN)


def mysql_time_text(td):
    """MySQL TIME 값(파이썬 timedelta)을 MySQL 이 보여 주는 글자로 바꿉니다.

    24시간을 넘거나 음수일 수 있습니다: '838:59:59', '-01:30:00'.
    """
    sign = "-" if td < datetime.timedelta(0) else ""
    td = abs(td)
    h, rem = divmod(td.days * 86400 + td.seconds, 3600)
    out = "%s%02d:%02d:%02d" % (sign, h, rem // 60, rem % 60)
    return out + (".%06d" % td.microseconds if td.microseconds else "")


def to_string(v):
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).decode("utf-8")
    if isinstance(v, datetime.timedelta):
        return mysql_time_text(v)
    return str(v)


def to_bytes(v):
    if isinstance(v, (bytes, bytearray, memoryview)):
        return bytes(v)
    return str(v).encode("utf-8")


def to_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    if isinstance(v, str):
        t = v.strip()
        if _blank(t):
            return None
        return datetime.date.fromisoformat(t)
    raise ValueError("날짜로 바꿀 수 없습니다: %r" % (v,))


def to_datetime(v):
    if isinstance(v, datetime.datetime):
        d = v
    elif isinstance(v, datetime.date):
        d = datetime.datetime(v.year, v.month, v.day)
    elif isinstance(v, str):
        t = v.strip()
        if _blank(t):
            return None
        d = datetime.datetime.fromisoformat(t)
    else:
        raise ValueError("일시로 바꿀 수 없습니다: %r" % (v,))
    if d.tzinfo is not None:
        # MySQL DATETIME 은 시간대가 없습니다. 시간대가 붙은 글자는 UTC 로 맞춥니다.
        d = d.astimezone(datetime.timezone.utc).replace(tzinfo=None)
    return d


# 빅쿼리 타입 -> (그대로 둘 파이썬 타입, 바꾸는 함수, Parquet 타입)
CASTS = {
    "INT64": (int, to_int, pa.int64()),
    "FLOAT64": (float, to_float, pa.float64()),
    "NUMERIC": (None, to_numeric, pa.decimal128(38, NUMERIC_SCALE)),
    "STRING": (str, to_string, pa.string()),
    "BYTES": (bytes, to_bytes, pa.binary()),
    "DATE": (None, to_date, pa.date32()),
    "DATETIME": (None, to_datetime, pa.timestamp("us")),
}


def cast_column(values, bq):
    """한 열의 값들을 빅쿼리 타입에 맞춥니다. 대부분은 이미 맞아 그대로 지나갑니다."""
    keep, fn, _ = CASTS[bq]
    if keep is None:
        return [None if v is None else fn(v) for v in values]
    return [v if v is None or type(v) is keep else fn(v) for v in values]


# --- 읽기와 쓰기 -----------------------------------------------------------

def qi(name):
    """SQLite 이름 따옴표입니다."""
    return '"%s"' % name.replace('"', '""')


def qm(name):
    """MySQL 이름 따옴표입니다."""
    return "`%s`" % name.replace("`", "``")


def mysql_columns(con, database=MYSQL_DATABASE):
    """MySQL 표마다 열 목록(ORDINAL_POSITION 순)입니다. 뷰는 뺍니다."""
    sql = ("SELECT c.TABLE_NAME, c.COLUMN_NAME, c.DATA_TYPE, c.COLUMN_TYPE, "
           "c.NUMERIC_PRECISION, c.NUMERIC_SCALE "
           "FROM information_schema.COLUMNS c JOIN information_schema.TABLES t "
           "ON t.TABLE_SCHEMA = c.TABLE_SCHEMA AND t.TABLE_NAME = c.TABLE_NAME "
           "WHERE c.TABLE_SCHEMA = %s AND t.TABLE_TYPE = 'BASE TABLE' "
           "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION")
    out = {}
    with con.cursor() as cur:
        cur.execute(sql, (database,))
        for row in cur.fetchall():
            t, name, dt, ct, p, s = [x.decode("utf-8") if isinstance(x, bytes) else x
                                     for x in row]
            out.setdefault(t, []).append((name, dt, ct, p, s))
    return out


def sqlite_tables(sq):
    return {r[0] for r in sq.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite\\_%' ESCAPE '\\'")}


def plan(specs, local, wanted=None):
    """복사할 표와 읽을 곳, 건너뛸 표(까닭)를 고릅니다.

    specs 는 MySQL 표 -> 열 목록, local 은 SQLite 표 이름들입니다. wanted 를 주면
    그 표만 봅니다. MySQL 표는 모두 복사합니다. SQLite 에 있고 주간 계산이 로컬에서만
    고치지 않는 표는 SQLite 에서, 나머지는 MySQL 에서 읽습니다.
    돌려주는 값: ([(표, "sqlite"|"mysql")], [(건너뛴 표, 까닭)])
    """
    names = wanted if wanted else sorted(set(specs) | set(local))
    copy, skipped = [], []
    for t in names:
        if t not in specs:
            skipped.append((t, "MySQL 에 없는 표입니다(로컬 계산용)"))
        elif t in local and t not in LOCAL_ONLY_EDITS:
            copy.append((t, SQLITE))
        else:
            copy.append((t, MYSQL))
    return copy, skipped


def sqlite_batches(sq, table, columns, chunk_rows=CHUNK_ROWS):
    """SQLite 표에서 chunk_rows 행씩 내놓습니다. MySQL 열이 빠져 있으면 ValueError."""
    have = {r[1].lower() for r in sq.execute("PRAGMA table_info(%s)" % qi(table))}
    missing = [c.name for c in columns if c.name.lower() not in have]
    if missing:
        raise ValueError("로컬 SQLite 의 %s 에 MySQL 열이 없습니다: %s"
                         % (table, ", ".join(missing)))
    cur = sq.execute("SELECT %s FROM %s" % (", ".join(qi(c.name) for c in columns), qi(table)))
    while True:
        rows = cur.fetchmany(chunk_rows)
        if not rows:
            return
        yield rows


def mysql_batches(con, table, columns, chunk_rows=CHUNK_ROWS):
    """MySQL 표에서 chunk_rows 행씩 내놓습니다.

    서버 쪽(버퍼 없는) 커서라 표 전체를 메모리에 올리지 않습니다. 중간에 멈추면
    커서를 닫으며 남은 행을 마저 읽어 버립니다(같은 연결로 다음 질의를 하려면
    필요합니다).
    """
    sql = "SELECT %s FROM %s" % (", ".join(qm(c.name) for c in columns), qm(table))
    with con.cursor(pymysql.cursors.SSCursor) as cur:
        cur.execute(sql)
        while True:
            rows = cur.fetchmany(chunk_rows)
            if not rows:
                return
            yield rows


def write_parquet(batches, table, columns, path):
    """행 묶음들을 Parquet 파일 하나로 씁니다. 묶음 하나가 행 그룹 하나입니다.

    batches 는 sqlite_batches·mysql_batches 가 내놓는 반복자입니다. 쓴 행 수를
    돌려줍니다. 값을 못 바꾸면 '표.열: 까닭' 으로 ValueError 입니다.
    """
    schema = pa.schema([pa.field(c.bq_name, CASTS[c.bq_type][2]) for c in columns])
    n = 0
    try:
        with pq.ParquetWriter(str(path), schema, compression="snappy") as w:
            for rows in batches:
                arrays = []
                for c, values in zip(columns, zip(*rows)):
                    try:
                        arrays.append(pa.array(cast_column(values, c.bq_type),
                                               type=CASTS[c.bq_type][2]))
                    except (ValueError, TypeError, ArithmeticError, pa.ArrowException) as e:
                        raise ValueError("%s.%s: %s" % (table, c.name, e)) from None
                w.write_table(pa.Table.from_arrays(arrays, schema=schema),
                              row_group_size=len(rows))
                n += len(rows)
                del rows, arrays
    finally:
        close = getattr(batches, "close", None)
        if close:
            close()
    return n


def count_rows(sq, my, table, source):
    """읽은 쪽(SQLite 나 MySQL)의 행 수입니다. MySQL 은 같은 스냅샷 안에서 셉니다."""
    if source == SQLITE:
        return sq.execute("SELECT COUNT(*) FROM %s" % qi(table)).fetchone()[0]
    with my.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM %s" % qm(table))
        return cur.fetchone()[0]


def bq_schema(columns):
    out = []
    for c in columns:
        desc = "MySQL %s" % c.mysql_type
        if c.name != c.bq_name:
            desc += " (MySQL 열 이름 %s)" % c.name
        out.append(bigquery.SchemaField(c.bq_name, c.bq_type, mode="NULLABLE",
                                        description=desc))
    return out


def table_description(table, columns, copied_at):
    s = ("MySQL %s.%s 의 주간 사본입니다. 정본은 MySQL 이고, 주간 작업이 매주 통째로 "
         "바꿉니다. 복사 시각 %s KST."
         % (MYSQL_DATABASE, table, copied_at.astimezone(KST).strftime("%Y-%m-%d %H:%M")))
    renamed = [(c.name, c.bq_name) for c in columns if c.name != c.bq_name]
    if renamed:
        s += " 이름을 바꾼 열(MySQL -> 빅쿼리): %s." % ", ".join("%s -> %s" % r for r in renamed)
    return s


def load_table(client, table_id, path, schema, description):
    """Parquet 파일 하나를 표 하나로 올립니다(통째로 바꿈). 올린 뒤 빅쿼리 행 수입니다."""
    cfg = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.PARQUET,
        schema=schema,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    with open(path, "rb") as f:
        job = client.load_table_from_file(f, table_id, job_config=cfg, location=LOCATION)
    job.result()
    t = client.get_table(table_id)
    t.description = description
    client.update_table(t, ["description"])
    return t.num_rows


def one_line(e):
    return ("%s: %s" % (type(e).__name__, e)).replace("\n", " ")[:300]


def copy_tables(sq, my, specs, tables, client, workdir, dry_run=False,
                chunk_rows=CHUNK_ROWS, now=None, dataset="%s.%s" % (PROJECT, DATASET)):
    """표마다 Parquet 을 만들고 올립니다. 실패해도 다음 표로 넘어갑니다. Result 목록.

    tables 는 plan() 이 고른 (표, "sqlite"|"mysql") 목록입니다.
    """
    now = now or datetime.datetime.now(KST)
    results = []
    for i, (t, source) in enumerate(tables, start=1):
        t0 = time.time()
        path = Path(workdir) / ("%s.parquet" % t)
        rows, error = None, None
        try:
            cols = table_columns(specs[t])
            batches = (sqlite_batches(sq, t, cols, chunk_rows) if source == SQLITE
                       else mysql_batches(my, t, cols, chunk_rows))
            rows = write_parquet(batches, t, cols, path)
            want = count_rows(sq, my, t, source)
            if rows != want:
                raise RuntimeError("Parquet 행 수가 다릅니다. %s %s / Parquet %s"
                                   % (source, format(want, ","), format(rows, ",")))
            if dry_run:
                print("  %s (%.1fMB)" % (t, path.stat().st_size / 1e6))
                for c in cols:
                    print("    %-28s %-9s MySQL %s" % (c.bq_name, c.bq_type, c.mysql_type))
            else:
                got = load_table(client, "%s.%s" % (dataset, t), path, bq_schema(cols),
                                 table_description(t, cols, now))
                if got != rows:
                    raise RuntimeError("빅쿼리 행 수가 다릅니다. %s %s / 빅쿼리 %s"
                                       % (source, format(rows, ","), format(got or 0, ",")))
        except Exception as e:  # noqa: BLE001  표 하나가 실패해도 나머지를 마저 합니다
            error = one_line(e)
        finally:
            if path.exists():
                path.unlink()
        secs = time.time() - t0
        results.append(Result(t, source, rows, secs, error))
        print("[%2d/%d] %-32s %-6s %11s행 %6.1f초  %s"
              % (i, len(tables), t, source, "-" if rows is None else format(rows, ","), secs,
                 "실패: " + error if error else ("확인" if dry_run else "복사")), flush=True)
    return results


def make_client(token_env=None, project=PROJECT):
    """빅쿼리 클라이언트입니다. token_env 가 있으면 그 환경 변수의 액세스 토큰을 씁니다."""
    creds = None
    if token_env:
        token = (os.environ.get(token_env) or "").strip()
        if not token:
            raise SystemExit("환경 변수 %s 에 액세스 토큰이 없습니다" % token_env)
        from google.oauth2.credentials import Credentials
        creds = Credentials(token)
    return bigquery.Client(project=project, credentials=creds, location=LOCATION)


def open_mysql():
    """MySQL 연결입니다(BSTATS_MYSQL_SETTINGS). 읽기만 합니다."""
    from migration.mysql import conn as myconn
    return myconn.connect()


def summary_note(results):
    ok = [r for r in results if not r.error]
    note = "%d개 표 %s행" % (len(ok), format(sum(r.rows for r in ok), ","))
    bad = [r.table for r in results if r.error]
    if bad:
        note += ", 실패 %s" % ", ".join(bad)
    return note


def main(argv=None):
    ap = argparse.ArgumentParser(description="MySQL 의 모든 표를 빅쿼리로 통째로 복사합니다")
    ap.add_argument("--db", required=True,
                    help="주간 작업의 SQLite 파일. 여기 있는 표는 여기서 읽습니다")
    ap.add_argument("--tables", default=None, help="쉼표로 구분. 기본값은 MySQL 의 모든 표")
    ap.add_argument("--dry-run", action="store_true", help="Parquet 을 만들고 스키마만 찍습니다")
    ap.add_argument("--token-env", default=None,
                    help="로컬 실행용. OAuth 액세스 토큰이 든 환경 변수 이름")
    args = ap.parse_args(argv)

    db = Path(args.db)
    if not db.is_file():
        raise SystemExit("SQLite 파일이 없습니다: %s" % db)
    wanted = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else None)

    t0 = time.time()
    my = open_mysql()
    try:
        specs = mysql_columns(my)
        # MySQL 에서 읽는 표를 모두 한 시점에서 읽습니다. 쓰지 않습니다.
        with my.cursor() as cur:
            cur.execute("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
        sq = sqlite3.connect(db.resolve().as_uri() + "?mode=ro", uri=True)
        try:
            tables, skipped = plan(specs, sqlite_tables(sq), wanted)
            for t, why in skipped:
                print("건너뜀: %-32s %s" % (t, why))
            if wanted and skipped:
                raise SystemExit("--tables 에 MySQL 에 없는 표가 있습니다: %s"
                                 % ", ".join(t for t, _ in skipped))
            if not tables:
                print("복사할 표가 없습니다.")
                return 1
            from_mysql = [t for t, s in tables if s == MYSQL]
            print("복사할 표 %d개: SQLite 에서 %d개, MySQL 에서 %d개"
                  % (len(tables), len(tables) - len(from_mysql), len(from_mysql)))
            for t in from_mysql:
                if t in LOCAL_ONLY_EDITS:
                    print("  %s 는 MySQL 에서 읽습니다: %s" % (t, LOCAL_ONLY_EDITS[t]))
            client = None if args.dry_run else make_client(args.token_env)
            with tempfile.TemporaryDirectory(prefix="bq_copy_") as work:
                results = copy_tables(sq, my, specs, tables, client, work,
                                      dry_run=args.dry_run)
        finally:
            sq.close()
        my.rollback()
    finally:
        my.close()

    note = summary_note(results)
    print("%s%s (%.0f초)" % ("[dry-run] 올리지 않았습니다. " if args.dry_run else "빅쿼리 복사: ",
                            note, time.time() - t0))
    out = os.environ.get("GITHUB_OUTPUT")
    if out and not args.dry_run:
        with open(out, "a", encoding="utf-8") as f:
            f.write("note=%s\n" % note)
    return 1 if any(r.error for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
