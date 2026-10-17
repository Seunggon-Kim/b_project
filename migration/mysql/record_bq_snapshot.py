# -*- coding: utf-8 -*-
"""주간 빅쿼리 복사 결과를 MySQL meta_bq_tables 에 남깁니다.

공개 '데이터 관리' 화면이 GET /ops/storage 로 이 표를 읽습니다. Worker 에는 GCP
자격이 없어서 빅쿼리를 직접 읽지 못하므로, 복사한 쪽이 결과를 MySQL 에 적어
둡니다(설계 docs/superpowers/specs/2026-10-18-data-ops-tab-design.md §4).

- 성공한 표는 행 수·용량·시각을 새 값으로 덮습니다.
- 실패한 표는 지난 성공 값을 남기고 상태·시도 시각·오류만 바꿉니다. 빅쿼리에는
  그 전 사본이 그대로 있기 때문입니다.
- MySQL 에 없는 표의 줄은 지웁니다.

결과 파일이 없거나 깨졌으면 아무것도 쓰지 않고 0 이 아닌 값으로 끝납니다.

    python -m migration.mysql.record_bq_snapshot --result-json bq_result.json
"""
import argparse
import json
import sys
from pathlib import Path

TABLE = "meta_bq_tables"
ERROR_MAX = 300
COLS = ["name", "bq_rows", "bq_bytes", "last_ok_at", "last_try_at", "status", "error"]

DDL = """CREATE TABLE `meta_bq_tables` (
  `name` VARCHAR(64) NOT NULL,
  `bq_rows` BIGINT,
  `bq_bytes` BIGINT,
  `last_ok_at` DATETIME,
  `last_try_at` DATETIME NOT NULL,
  `status` VARCHAR(8) NOT NULL,
  `error` VARCHAR(300),
  PRIMARY KEY (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;"""


def load_result(path):
    """결과 JSON 입니다. 없거나 깨졌거나 모양이 틀리면 ValueError."""
    p = Path(path)
    if not p.is_file():
        raise ValueError("결과 파일이 없습니다: %s" % p)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError("결과 파일을 읽지 못했습니다: %s" % e) from None
    if not isinstance(data, dict) or not all(k in data for k in ("tried_at", "tables", "mysql_tables")):
        raise ValueError("결과 파일 모양이 다릅니다")
    if not data["tables"] or not data["mysql_tables"]:
        raise ValueError("결과 파일에 표가 없습니다")
    return data


def plan_rows(result, existing):
    """(쓸 줄, 지울 이름)입니다. existing 은 {표 이름: 지금 줄}."""
    t = result["tried_at"]
    rows = []
    for item in result["tables"]:
        name = item["name"]
        if name == TABLE:
            continue
        if item.get("error"):
            old = existing.get(name) or {}
            rows.append({"name": name, "bq_rows": old.get("bq_rows"), "bq_bytes": old.get("bq_bytes"),
                         "last_ok_at": old.get("last_ok_at"), "last_try_at": t, "status": "fail",
                         "error": str(item["error"])[:ERROR_MAX]})
        else:
            rows.append({"name": name, "bq_rows": item["rows"], "bq_bytes": item["bytes"],
                         "last_ok_at": t, "last_try_at": t, "status": "ok", "error": None})
    alive = set(result["mysql_tables"])
    deletes = sorted(n for n in existing if n not in alive)
    return rows, deletes


def write(sink, rows, deletes):
    """한 트랜잭션 안의 sink(mysql_sink.Sink)로 씁니다."""
    q = lambda c: "`%s`" % c  # noqa: E731
    head = "INSERT INTO `%s` (%s) VALUES (%s)" % (
        TABLE, ", ".join(q(c) for c in COLS), ", ".join(["%s"] * len(COLS)))
    tail = " AS new ON DUPLICATE KEY UPDATE " + ", ".join(
        "%s=new.%s" % (q(c), q(c)) for c in COLS if c != "name")
    for row in rows:
        sink.execute(head + tail, [row[c] for c in COLS])
    if deletes:
        sink.execute("DELETE FROM `%s` WHERE `name` IN (%s)" % (TABLE, ", ".join(["%s"] * len(deletes))),
                     list(deletes))


class Db:
    """pymysql 연결에 execute·query 두 가지만 붙입니다(mysql_sink.Sink 와 같은 이름)."""

    def __init__(self, con):
        self.con = con

    def execute(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            return cur.rowcount

    def query(self, sql, params=None):
        with self.con.cursor() as cur:
            cur.execute(sql, params)
            names = [d[0] for d in cur.description]
            return [dict(zip(names, r)) for r in cur.fetchall()]


def read_existing(sink):
    out = {}
    for r in sink.query("SELECT %s FROM `%s`" % (", ".join("`%s`" % c for c in COLS), TABLE)):
        for k in ("last_ok_at", "last_try_at"):
            if r.get(k) is not None and not isinstance(r[k], str):
                r[k] = r[k].strftime("%Y-%m-%d %H:%M")
        out[r["name"]] = r
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="빅쿼리 복사 결과를 meta_bq_tables 에 씁니다")
    ap.add_argument("--result-json", required=True)
    args = ap.parse_args(argv)
    try:
        result = load_result(args.result_json)
    except ValueError as e:
        print("빅쿼리 현황 기록 안 함: %s" % e)
        return 1

    # mysql_sink.mirror 는 실패하면 실패 기록 파일에 남기고, 주간 작업의 "MySQL 적재
    # 실패 확인"이 그 파일을 보고 작업을 빨갛게 끝냅니다. 이 기록이 실패해도 주간
    # 판정은 바꾸지 않기로 했으므로(설계 §4-2) 직접 연결합니다.
    from migration.mysql import conn as myconn
    con = myconn.connect()
    try:
        db = Db(con)
        rows, deletes = plan_rows(result, read_existing(db))
        write(db, rows, deletes)
        con.commit()
    except Exception as e:  # noqa: BLE001
        con.rollback()
        print("빅쿼리 현황 기록 실패: %s" % ("%s: %s" % (type(e).__name__, e))[:300])
        return 1
    finally:
        con.close()
    print("빅쿼리 현황 기록: %d개 표, 지운 줄 %d개" % (len(rows), len(deletes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
