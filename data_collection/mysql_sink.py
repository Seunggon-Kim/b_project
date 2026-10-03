# -*- coding: utf-8 -*-
"""수집 결과를 Cloud SQL(MySQL)에도 씁니다. 2단계 이중 적재입니다.

D1 에 쓰는 코드는 그대로 두고, 각 스크립트가 D1 적재를 마친 뒤
`mirror()` 로 같은 내용을 MySQL 에 씁니다. 사이트는 3단계까지 D1 을
읽으므로 MySQL 이 실패해도 D1 적재를 막지 않습니다. 대신 실패를 파일에
남기고, 워크플로 마지막 판정이 그 파일을 보고 빨간색으로 끝냅니다.

## 켜고 끄기

    BSTATS_MYSQL_MIRROR    off(기본)  MySQL 에 손대지 않습니다
                           shadow     쓰고, 실패하면 기록만 하고 넘어갑니다
                           strict     쓰고, 실패하면 예외를 그대로 올립니다
    BSTATS_MYSQL_SETTINGS  접속 파일(migration/mysql/conn.py)
    BSTATS_MYSQL_FAIL_LOG  실패 기록 파일(기본 logs/mysql_mirror_failures.jsonl)

## D1 과 같은 값 쓰기

D1 쪽은 `d1_load.sql_literal` 이 ''·'-' 를 NULL 로 바꿉니다. 여기서도
같게 한 뒤, 열 종류(schema_types.json)에 맞춰 1단계 적재와 같은 규칙
(`typemap.normalize`)으로 바꿉니다. 값은 SQL 글자에 붙이지 않고
파라미터로 넘깁니다. MySQL 엄격 모드는 '12345.0' 같은 글자를 정수 열에
넣으면 실패하기 때문입니다.
"""
import datetime
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migration.mysql import typemap as tm  # noqa: E402

TYPES_PATH = ROOT / "migration" / "mysql" / "schema_types.json"
MODE_ENV = "BSTATS_MYSQL_MIRROR"
FAIL_LOG_ENV = "BSTATS_MYSQL_FAIL_LOG"
DEFAULT_FAIL_LOG = ROOT / "logs" / "mysql_mirror_failures.jsonl"
MODES = ("off", "shadow", "strict")
BATCH = 500
# 행 잠금 대기 한도(초)입니다. 수집 단계마다 시간 제한이 있어 오래 기다리지 않습니다.
LOCK_WAIT_SEC = 30

_types = None


def mode():
    m = (os.environ.get(MODE_ENV) or "off").strip().lower()
    if m not in MODES:
        raise ValueError("%s 는 off·shadow·strict 중 하나여야 합니다: %r" % (MODE_ENV, m))
    return m


def q(name):
    return "`%s`" % str(name).replace("`", "``")


def blank(v):
    """d1_load.sql_literal 과 같이 ''·'-' 를 값 없음으로 봅니다."""
    if v is None:
        return None
    s = str(v)
    if s == "" or s == "-":
        return None
    return v


def table_spec(table):
    global _types
    if _types is None:
        _types = json.loads(TYPES_PATH.read_text(encoding="utf-8"))
    if table not in _types:
        raise KeyError("schema_types.json 에 없는 표입니다: %s" % table)
    return _types[table]


def table_columns(table):
    return [c for c, _ in table_spec(table)["columns"]]


class Sink:
    """한 트랜잭션 안에서 MySQL 에 씁니다. mirror() 가 만들고 커밋합니다."""

    def __init__(self, con):
        self.con = con

    def columns(self, table):
        return table_columns(table)

    def value(self, table, column, v):
        kinds = dict(table_spec(table)["columns"])
        if column not in kinds:
            raise KeyError("%s 에 없는 열입니다: %s" % (table, column))
        try:
            return tm.normalize(blank(v), kinds[column])
        except ValueError as e:
            raise ValueError("%s.%s: %s" % (table, column, e)) from None

    def execute(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]

    def _write(self, table, columns, rows, tail, batch):
        rows = list(rows)
        head = "INSERT INTO %s (%s) VALUES " % (q(table), ", ".join(q(c) for c in columns))
        one = "(%s)" % ", ".join(["%s"] * len(columns))
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            params = []
            for r in chunk:
                params.extend(self.value(table, c, r.get(c)) for c in columns)
            self.execute(head + ", ".join([one] * len(chunk)) + tail, params)
        return len(rows)

    def insert(self, table, columns, rows, batch=BATCH):
        return self._write(table, columns, rows, "", batch)

    def upsert(self, table, columns, keys, rows, touch=None, keep=(), batch=BATCH):
        """d1_load.build_upserts 와 같은 뜻입니다.

        열쇠·keep·touch 를 뺀 열을 새 값으로 덮고, touch 열은 지금 UTC 시각으로
        둡니다(D1 의 datetime('now') 와 같음).
        """
        keyset = set(keys) | set(keep) | ({touch} if touch else set())
        updatable = [c for c in columns if c not in keyset]
        if not updatable:
            raise ValueError("갱신할 컬럼이 없습니다: %s" % table)
        sets = ["%s=new.%s" % (q(c), q(c)) for c in updatable]
        if touch:
            sets.append("%s=UTC_TIMESTAMP()" % q(touch))
        tail = " AS new ON DUPLICATE KEY UPDATE " + ", ".join(sets)
        return self._write(table, columns, rows, tail, batch)

    def insert_missing(self, table, columns, keys, rows, batch=BATCH):
        """없는 행만 넣습니다.

        D1 의 INSERT OR IGNORE 자리입니다. MySQL 의 INSERT IGNORE 는 값 잘림·
        외래키 오류까지 경고로 삼키므로 쓰지 않습니다.
        """
        k = q(keys[0])
        return self._write(table, columns, rows,
                           " ON DUPLICATE KEY UPDATE %s=%s" % (k, k), batch)

    def refresh_count(self, table):
        """meta_table_counts 를 MySQL 표 전체 행 수로 맞춥니다.

        D1 은 play_by_play 를 샤드마다 따로 셌지만 MySQL 은 한 표라 전체입니다.
        """
        n = self.query("SELECT COUNT(*) AS n FROM %s" % q(table))[0]["n"]
        now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        self.upsert("meta_table_counts", ["name", "n", "updated_at"], ["name"],
                    [{"name": table, "n": n, "updated_at": now}])
        return n


def _connect():
    from migration.mysql import conn as myconn
    return myconn.connect()


def one_line(e):
    return ("%s: %s" % (type(e).__name__, e)).replace("\n", " ")[:300]


def record_failure(job, e):
    path = Path(os.environ.get(FAIL_LOG_ENV) or DEFAULT_FAIL_LOG)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "job": job, "error": one_line(e),
            "at": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        }, ensure_ascii=False) + "\n")
    traceback.print_exc()


def mirror(job, fn, required=False, connect=None):
    """fn(Sink) 를 한 트랜잭션으로 MySQL 에 씁니다. fn 의 값을 돌려줍니다.

    꺼져 있으면(off) 아무것도 하지 않고 None 입니다. required=True 는 MySQL
    에만 쓰는 손 작업(따라잡기)용입니다. 꺼져 있어도 쓰고, 실패하면 예외를
    올립니다.
    """
    m = mode()
    if m == "off" and not required:
        return None
    con = None
    try:
        con = (connect or _connect)()
        with con.cursor() as cur:
            cur.execute("SET SESSION innodb_lock_wait_timeout = %d" % LOCK_WAIT_SEC)
        result = fn(Sink(con))
        con.commit()
        print("MySQL 반영: %s" % job, flush=True)
        return result
    except Exception as e:  # noqa: BLE001
        if con is not None:
            try:
                con.rollback()
            except Exception:  # noqa: BLE001
                pass
        record_failure(job, e)
        if m == "strict" or required:
            raise
        print("::warning title=MySQL 이중 적재 실패::%s: %s" % (job, one_line(e)), flush=True)
        return None
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:  # noqa: BLE001
                pass
