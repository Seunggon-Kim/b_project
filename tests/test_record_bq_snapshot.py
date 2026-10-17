import json

import pytest

from migration.mysql import record_bq_snapshot as r

T = "2026-10-20 06:10"


def result(tables, mysql_tables=None):
    return {"tried_at": T, "tables": tables,
            "mysql_tables": mysql_tables or [t["name"] for t in tables]}


def ok(name, rows=10, nbytes=1000):
    return {"name": name, "source": "mysql", "rows": rows, "bytes": nbytes, "error": None}


def bad(name, msg="적재 실패"):
    return {"name": name, "source": "mysql", "rows": None, "bytes": None, "error": msg}


def test_성공한_표는_새_값으로_덮습니다():
    rows, dels = r.plan_rows(result([ok("games", 12, 3400)]), {})
    assert rows == [{"name": "games", "bq_rows": 12, "bq_bytes": 3400, "last_ok_at": T,
                     "last_try_at": T, "status": "ok", "error": None}]
    assert dels == []


def test_실패한_표는_지난_성공_값을_남깁니다():
    before = {"games": {"name": "games", "bq_rows": 11, "bq_bytes": 3300,
                        "last_ok_at": "2026-10-13 06:00", "last_try_at": "2026-10-13 06:00",
                        "status": "ok", "error": None}}
    rows, _ = r.plan_rows(result([bad("games", "x" * 400)]), before)
    assert rows[0]["bq_rows"] == 11 and rows[0]["bq_bytes"] == 3300
    assert rows[0]["last_ok_at"] == "2026-10-13 06:00"
    assert rows[0]["last_try_at"] == T and rows[0]["status"] == "fail"
    assert len(rows[0]["error"]) == 300


def test_처음부터_실패한_표는_성공_값이_비어_있습니다():
    rows, _ = r.plan_rows(result([bad("games")]), {})
    assert rows[0]["bq_rows"] is None and rows[0]["last_ok_at"] is None


def test_MySQL_에_없는_표의_줄은_지웁니다():
    before = {"old": {"name": "old"}, "games": {"name": "games"}}
    _, dels = r.plan_rows(result([ok("games")], ["games", "meta_bq_tables"]), before)
    assert dels == ["old"]


def test_이번에_복사하지_않은_표는_건드리지_않습니다():
    before = {"teams": {"name": "teams", "bq_rows": 10}}
    rows, dels = r.plan_rows(result([ok("games")], ["games", "teams"]), before)
    assert [x["name"] for x in rows] == ["games"] and dels == []


def test_현황_표_자신은_줄을_만들지_않습니다():
    rows, _ = r.plan_rows(result([ok("meta_bq_tables")]), {})
    assert rows == []


@pytest.mark.parametrize("text", ["", "{", '{"tables": []}', '{"tried_at": "x", "tables": [], "mysql_tables": []}'])
def test_결과_파일이_틀리면_멈춥니다(tmp_path, text):
    p = tmp_path / "res.json"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError):
        r.load_result(p)


def test_결과_파일이_없으면_멈춥니다(tmp_path):
    with pytest.raises(ValueError):
        r.load_result(tmp_path / "none.json")


class FakeSink:
    def __init__(self):
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        return 1


def test_쓰기는_UPSERT_와_DELETE_입니다():
    s = FakeSink()
    rows, _ = r.plan_rows(result([ok("games")]), {})
    r.write(s, rows, ["old"])
    assert s.sql[0][0].startswith("INSERT INTO `meta_bq_tables`")
    assert "ON DUPLICATE KEY UPDATE" in s.sql[0][0]
    assert s.sql[0][1] == ["games", 10, 1000, T, T, "ok", None]
    assert s.sql[1] == ("DELETE FROM `meta_bq_tables` WHERE `name` IN (%s)", ["old"])


class BoomCursor:
    description = [("name",)]

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if sql.startswith("INSERT"):
            raise RuntimeError("쓰기 실패(가짜)")

    def fetchall(self):
        return []


class BoomCon:
    def __init__(self):
        self.log = []

    def cursor(self):
        return BoomCursor()

    def commit(self):
        self.log.append("commit")

    def rollback(self):
        self.log.append("rollback")

    def close(self):
        self.log.append("close")


def test_쓰기가_실패해도_주간_작업의_실패_기록을_남기지_않습니다(tmp_path, monkeypatch):
    from migration.mysql import conn as myconn
    con = BoomCon()
    monkeypatch.setattr(myconn, "connect", lambda: con)
    fail_log = tmp_path / "fail.jsonl"
    monkeypatch.setenv("BSTATS_MYSQL_FAIL_LOG", str(fail_log))
    res = tmp_path / "res.json"
    res.write_text(json.dumps(result([ok("games")])), encoding="utf-8")
    assert r.main(["--result-json", str(res)]) == 1
    assert con.log == ["rollback", "close"] and not fail_log.exists()


def test_결과_파일이_없으면_연결하지_않고_1(tmp_path, monkeypatch):
    from migration.mysql import conn as myconn
    monkeypatch.setattr(myconn, "connect", lambda: (_ for _ in ()).throw(AssertionError("연결하면 안 됨")))
    assert r.main(["--result-json", str(tmp_path / "none.json")]) == 1


def test_DDL_은_설계서와_같은_열입니다():
    for col in ("`name` VARCHAR(64) NOT NULL", "`bq_rows` BIGINT", "`bq_bytes` BIGINT",
                "`last_ok_at` DATETIME", "`last_try_at` DATETIME NOT NULL",
                "`status` VARCHAR(8) NOT NULL", "`error` VARCHAR(300)", "PRIMARY KEY (`name`)"):
        assert col in r.DDL
