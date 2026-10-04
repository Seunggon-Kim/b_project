# -*- coding: utf-8 -*-
"""주간 빅쿼리 복사(migration/mysql/sqlite_to_bigquery.py)를 봅니다.

빅쿼리에는 붙지 않습니다. 적재는 가짜 클라이언트로 부른 모양만 봅니다.
"""
import datetime
import decimal
import io
import re
import sqlite3
import sys
from pathlib import Path

import pyarrow.parquet as pq
import pytest
import yaml
from google.cloud import bigquery

from migration import sqlite_to_d1
from migration.mysql import sqlite_to_bigquery as m

ROOT = Path(__file__).resolve().parent.parent
WEEKLY = ROOT / ".github" / "workflows" / "weekly.yml"
sys.path.insert(0, str(ROOT / "scripts"))

import lineage_extract as lx  # noqa: E402


# --- 타입 규칙 -------------------------------------------------------------

@pytest.mark.parametrize("data_type, column_type, p, s, want", [
    ("int", "int", 10, 0, "INT64"),
    ("int", "int unsigned", 10, 0, "INT64"),
    ("bigint", "bigint unsigned", 20, 0, "INT64"),
    ("tinyint", "tinyint(1)", 3, 0, "INT64"),
    ("smallint", "smallint", 5, 0, "INT64"),
    ("mediumint", "mediumint", 7, 0, "INT64"),
    ("year", "year", None, None, "INT64"),
    ("bit", "bit(1)", 1, None, "INT64"),
    ("decimal", "decimal(10,2)", 10, 2, "NUMERIC"),
    ("decimal", "decimal(38,9)", 38, 9, "NUMERIC"),
    ("decimal", "decimal(29,0)", 29, 0, "NUMERIC"),
    ("decimal", "decimal(38,0)", 38, 0, "FLOAT64"),     # 정수부 38자리 > 29
    ("decimal", "decimal(30,10)", 30, 10, "FLOAT64"),   # 소수 10자리 > 9
    ("float", "float", 12, None, "FLOAT64"),
    ("double", "double", 22, None, "FLOAT64"),
    ("date", "date", None, None, "DATE"),
    ("datetime", "datetime", None, None, "DATETIME"),
    ("timestamp", "timestamp", None, None, "DATETIME"),
    ("time", "time", None, None, "STRING"),
    ("char", "char(1)", None, None, "STRING"),
    ("varchar", "varchar(16)", None, None, "STRING"),
    ("text", "text", None, None, "STRING"),
    ("mediumtext", "mediumtext", None, None, "STRING"),
    ("longtext", "longtext", None, None, "STRING"),
    ("enum", "enum('a','b')", None, None, "STRING"),
    ("set", "set('a','b')", None, None, "STRING"),
    ("json", "json", None, None, "STRING"),
    ("binary", "binary(4)", None, None, "BYTES"),
    ("varbinary", "varbinary(8)", None, None, "BYTES"),
    ("blob", "blob", None, None, "BYTES"),
    ("mediumblob", "mediumblob", None, None, "BYTES"),
    ("longblob", "longblob", None, None, "BYTES"),
])
def test_타입_규칙(data_type, column_type, p, s, want):
    assert m.bq_type(data_type, column_type, p, s) == want


def test_모르는_타입은_실패합니다():
    with pytest.raises(ValueError, match="geometry"):
        m.bq_type("geometry", "geometry")


# --- 열 이름 ---------------------------------------------------------------

def test_쓸_수_있는_이름은_그대로입니다():
    names = ["batter_ID", "window", "AVG", "raw_RV_1B", "_x"]
    assert m.bq_column_names(names) == names


def test_쓸_수_없는_이름은_규칙대로_고칩니다():
    assert m.bq_column_name("2B") == "_2B"
    assert m.bq_column_name("a-b") == "a_b"
    assert m.bq_column_name("K/9") == "K_9"
    assert m.bq_column_name("선수") == "__"
    assert m.bq_column_name("") == "_"
    assert m.bq_column_name("_TABLE_x") == "c_TABLE_x"
    assert m.bq_column_name("_partitiontime") == "c_partitiontime"
    assert len(m.bq_column_name("a" * 400)) == 300


def test_고친_이름이_겹치면_번호를_붙입니다():
    got = m.bq_column_names(["a-b", "a b", "A_B", "x"])
    assert got == ["a_b", "a_b_2", "A_B_3", "x"]
    # 같은 입력이면 늘 같은 결과입니다.
    assert m.bq_column_names(["a-b", "a b", "A_B", "x"]) == got


def test_바꾼_이름을_표_설명과_열_설명에_적습니다():
    cols = m.table_columns([("a-b", "int", "int", 10, 0), ("ok", "varchar", "varchar(16)", None, None)])
    now = datetime.datetime(2026, 10, 6, 5, 47, tzinfo=m.KST)
    desc = m.table_description("t", cols, now)
    assert "MySQL bstats.t 의 주간 사본" in desc and "2026-10-06 05:47 KST" in desc
    assert "a-b -> a_b" in desc
    schema = m.bq_schema(cols)
    assert [f.name for f in schema] == ["a_b", "ok"]
    assert "MySQL 열 이름 a-b" in schema[0].description
    assert schema[1].description == "MySQL varchar(16)"
    assert all(f.mode == "NULLABLE" for f in schema)


def test_바꾼_이름이_없으면_설명에_적지_않습니다():
    cols = m.table_columns([("ok", "int", "int", 10, 0)])
    assert "이름을 바꾼" not in m.table_description("t", cols, datetime.datetime.now(m.KST))


# --- 표 고르기 -------------------------------------------------------------

SPECS = {
    "games": [("game_id", "varchar", "varchar(32)", None, None)],
    "teams": [("team_id", "varchar", "varchar(16)", None, None)],
    "players": [("player_id", "int", "int unsigned", 10, 0)],
    "team_stadium_by_season": [("season", "int", "int", 10, 0)],
}


def test_MySQL_에_없는_표와_로컬에_없는_표를_뺍니다():
    local = {"games", "teams", "truncated_games", "kbo_woba_weights_by_season_bak",
             "team_stadium_by_season"}
    copy, skipped = m.plan(SPECS, local)
    assert copy == ["games", "teams"]
    why = dict(skipped)
    assert "MySQL 에 없는" in why["truncated_games"]
    assert "MySQL 에 없는" in why["kbo_woba_weights_by_season_bak"]
    assert "로컬 SQLite 에 없습니다" in why["players"]
    assert "build_wrc_plus" in why["team_stadium_by_season"]


def test_고른_표만_봅니다():
    copy, skipped = m.plan(SPECS, {"games", "teams", "players"}, ["teams", "players"])
    assert copy == ["teams", "players"] and skipped == []
    copy, skipped = m.plan(SPECS, {"games"}, ["games", "nope"])
    assert copy == ["games"] and [t for t, _ in skipped] == ["nope"]


def test_SQLite_내부_표는_목록에_없습니다(tmp_path):
    sq = sqlite3.connect(str(tmp_path / "x.db"))
    sq.execute("CREATE TABLE a (id INTEGER PRIMARY KEY AUTOINCREMENT, v TEXT)")
    sq.execute("INSERT INTO a (v) VALUES ('x')")
    assert m.sqlite_tables(sq) == {"a"}


def test_MySQL_열_목록을_순서대로_읽습니다():
    class Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def execute(self, sql, args):
            self.sql, self.args = sql, args

        def fetchall(self):
            assert "ORDER BY c.TABLE_NAME, c.ORDINAL_POSITION" in self.sql
            assert "BASE TABLE" in self.sql and self.args == ("bstats",)
            return [("t", "b", "int", "int", 10, 0), ("t", "a", b"varchar", "varchar(16)", None, None),
                    ("u", "x", "date", "date", None, None)]

    class Con:
        def cursor(self):
            return Cur()

    got = m.mysql_columns(Con())
    assert got == {"t": [("b", "int", "int", 10, 0), ("a", "varchar", "varchar(16)", None, None)],
                   "u": [("x", "date", "date", None, None)]}


# --- Parquet ---------------------------------------------------------------

MIXED_SPECS = [
    ("n", "int", "int", 10, 0),
    ("f", "double", "double", 22, None),
    ("s", "varchar", "varchar(16)", None, None),
    ("d", "date", "date", None, None),
    ("dt", "datetime", "datetime", None, None),
    ("num", "decimal", "decimal(10,3)", 10, 3),
    ("b", "mediumblob", "mediumblob", None, None),
    ("big", "bigint", "bigint unsigned", 20, 0),
]

MIXED_ROWS = [
    (1, 1.5, "a", "2026-10-03", "2026-10-03 01:02:03", 1.25, b"\x00\x01", 7),
    (3.0, 2, 123, None, None, "0.5", "ab", None),
    ("12", "1.5", "", "", "", "", None, 2 ** 40),
    ("", "-", None, "2026-01-01", "2026-01-01T09:00:00", None, None, None),
    (None, None, "끝", None, None, 2, None, 0),
]


def make_db(path, rows=MIXED_ROWS, specs=MIXED_SPECS, table="mixed"):
    sq = sqlite3.connect(str(path))
    # 주간 계산이 만든 표처럼 타입 선언이 느슨한 표입니다.
    sq.execute("CREATE TABLE %s (%s)" % (table, ", ".join('"%s"' % s[0] for s in specs)))
    sq.executemany("INSERT INTO %s VALUES (%s)" % (table, ", ".join("?" * len(specs))), rows)
    sq.commit()
    return sq


def test_Parquet_을_덩어리로_나눠_쓰고_값을_맞춥니다(tmp_path):
    sq = make_db(tmp_path / "x.db")
    cols = m.table_columns(MIXED_SPECS)
    out = tmp_path / "mixed.parquet"
    assert m.write_parquet(sq, "mixed", cols, out, chunk_rows=2) == 5
    f = pq.ParquetFile(str(out))
    assert f.metadata.num_rows == 5
    assert f.metadata.num_row_groups == 3          # 2 + 2 + 1행
    t = f.read()
    assert [str(x.type) for x in t.schema] == [
        "int64", "double", "string", "date32[day]", "timestamp[us]",
        "decimal128(38, 9)", "binary", "int64"]
    got = t.to_pydict()
    assert got["n"] == [1, 3, 12, None, None]
    assert got["f"] == [1.5, 2.0, 1.5, None, None]
    # 글자 열의 '' 는 그대로 둡니다. 숫자는 글자로 바꿉니다.
    assert got["s"] == ["a", "123", "", None, "끝"]
    assert got["d"] == [datetime.date(2026, 10, 3), None, None, datetime.date(2026, 1, 1), None]
    assert got["dt"] == [datetime.datetime(2026, 10, 3, 1, 2, 3), None, None,
                         datetime.datetime(2026, 1, 1, 9, 0), None]
    assert got["num"] == [decimal.Decimal("1.25"), decimal.Decimal("0.5"), None, None,
                          decimal.Decimal("2")]
    assert got["b"] == [b"\x00\x01", b"ab", None, None, None]
    assert got["big"] == [7, None, 2 ** 40, None, 0]


def test_빈_표도_파일을_만듭니다(tmp_path):
    sq = make_db(tmp_path / "x.db", rows=[])
    out = tmp_path / "e.parquet"
    assert m.write_parquet(sq, "mixed", m.table_columns(MIXED_SPECS), out) == 0
    assert pq.ParquetFile(str(out)).metadata.num_rows == 0


@pytest.mark.parametrize("bad, spec", [
    ("abc", ("n", "int", "int", 10, 0)),
    (1.5, ("n", "int", "int", 10, 0)),
    ("x", ("n", "double", "double", 22, None)),
    ("2026-13-01", ("n", "date", "date", None, None)),
    ("9223372036854775808", ("n", "bigint", "bigint unsigned", 20, 0)),   # INT64 최대 + 1
])
def test_못_바꾸는_값은_표와_열_이름을_달고_실패합니다(tmp_path, bad, spec):
    sq = make_db(tmp_path / "x.db", rows=[(bad,)], specs=[spec], table="t")
    with pytest.raises(ValueError, match=r"^t\.n: "):
        m.write_parquet(sq, "t", m.table_columns([spec]), tmp_path / "t.parquet")


def test_SQLite_에_MySQL_열이_없으면_실패합니다(tmp_path):
    sq = make_db(tmp_path / "x.db", rows=[(1,)], specs=[("n", "int", "int", 10, 0)], table="t")
    cols = m.table_columns([("n", "int", "int", 10, 0), ("gone", "int", "int", 10, 0)])
    with pytest.raises(ValueError, match="gone"):
        m.write_parquet(sq, "t", cols, tmp_path / "t.parquet")


def test_열_이름은_대소문자를_가리지_않고_찾습니다(tmp_path):
    sq = make_db(tmp_path / "x.db", rows=[(1,)], specs=[("batter_id", "int", "int", 10, 0)], table="t")
    cols = m.table_columns([("batter_ID", "int", "int unsigned", 10, 0)])
    assert m.write_parquet(sq, "t", cols, tmp_path / "t.parquet") == 1


# --- 적재 ------------------------------------------------------------------

class FakeTable:
    def __init__(self, num_rows):
        self.num_rows = num_rows
        self.description = None


class FakeJob:
    def __init__(self, error=None):
        self.error = error

    def result(self):
        if self.error:
            raise self.error


class FakeClient:
    """load_table_from_file·get_table·update_table 만 흉내 냅니다."""

    def __init__(self, rows_delta=0, fail=()):
        self.loads, self.updates = [], []
        self.rows_delta, self.fail = rows_delta, set(fail)
        self.loaded = {}

    def load_table_from_file(self, f, table_id, job_config=None, location=None):
        data = f.read()
        n = pq.ParquetFile(io.BytesIO(data)).metadata.num_rows
        self.loads.append({"table_id": table_id, "config": job_config,
                           "location": location, "rows": n})
        if table_id.split(".")[-1] in self.fail:
            return FakeJob(RuntimeError("적재 실패(가짜)"))
        self.loaded[table_id] = n
        return FakeJob()

    def get_table(self, table_id):
        return FakeTable(self.loaded[table_id] + self.rows_delta)

    def update_table(self, table, fields):
        self.updates.append((table.description, list(fields)))
        return table


def two_table_db(tmp_path):
    sq = make_db(tmp_path / "x.db")
    sq.execute('CREATE TABLE "teams" ("team_id", "name")')
    sq.executemany('INSERT INTO "teams" VALUES (?, ?)', [("LG", "LG"), ("SS", "삼성")])
    sq.commit()
    specs = {"mixed": MIXED_SPECS,
             "teams": [("team_id", "varchar", "varchar(16)", None, None),
                       ("name", "varchar", "varchar(32)", None, None)]}
    return sq, specs


def test_표마다_WRITE_TRUNCATE_와_명시_스키마로_올립니다(tmp_path):
    sq, specs = two_table_db(tmp_path)
    client = FakeClient()
    now = datetime.datetime(2026, 10, 6, 5, 47, tzinfo=m.KST)
    res = m.copy_tables(sq, specs, ["mixed", "teams"], client, tmp_path, now=now)
    assert [(r.table, r.rows, r.error) for r in res] == [("mixed", 5, None), ("teams", 2, None)]
    assert [ld["table_id"] for ld in client.loads] == ["bstats-kbo.bstats.mixed",
                                                       "bstats-kbo.bstats.teams"]
    for ld in client.loads:
        cfg = ld["config"]
        assert cfg.write_disposition == bigquery.WriteDisposition.WRITE_TRUNCATE
        assert cfg.source_format == bigquery.SourceFormat.PARQUET
        assert ld["location"] == "asia-northeast3"
    schema = client.loads[0]["config"].schema
    assert [(f.name, f.field_type, f.mode) for f in schema] == [
        ("n", "INT64", "NULLABLE"), ("f", "FLOAT64", "NULLABLE"), ("s", "STRING", "NULLABLE"),
        ("d", "DATE", "NULLABLE"), ("dt", "DATETIME", "NULLABLE"),
        ("num", "NUMERIC", "NULLABLE"), ("b", "BYTES", "NULLABLE"), ("big", "INT64", "NULLABLE")]
    assert client.updates[1] == (
        "MySQL bstats.teams 의 주간 사본입니다. 정본은 MySQL 이고, 주간 작업이 매주 통째로 "
        "바꿉니다. 복사 시각 2026-10-06 05:47 KST.", ["description"])
    # 올린 뒤 임시 Parquet 은 지웁니다.
    assert not list(tmp_path.glob("*.parquet"))


def test_행_수가_다르면_실패하고_나머지_표는_마저_합니다(tmp_path):
    sq, specs = two_table_db(tmp_path)
    client = FakeClient(rows_delta=-1)
    res = m.copy_tables(sq, specs, ["mixed", "teams"], client, tmp_path)
    assert len(client.loads) == 2
    assert all("빅쿼리 행 수가 다릅니다" in r.error for r in res)


def test_적재_오류가_나도_나머지_표는_마저_합니다(tmp_path):
    sq, specs = two_table_db(tmp_path)
    client = FakeClient(fail={"mixed"})
    res = m.copy_tables(sq, specs, ["mixed", "teams"], client, tmp_path)
    assert "적재 실패" in res[0].error and res[1].error is None
    assert m.summary_note(res) == "1개 표 2행, 실패 mixed"


def test_dry_run_은_올리지_않습니다(tmp_path, capsys):
    sq, specs = two_table_db(tmp_path)
    res = m.copy_tables(sq, specs, ["teams"], None, tmp_path, dry_run=True)
    assert res[0].error is None and res[0].rows == 2
    out = capsys.readouterr().out
    assert "team_id" in out and "STRING" in out and "varchar(16)" in out


def run_main(tmp_path, monkeypatch, client, argv=()):
    sq, specs = two_table_db(tmp_path)
    sq.execute('CREATE TABLE "truncated_games" ("game_id")')
    sq.commit()
    sq.close()
    monkeypatch.setattr(m, "read_specs", lambda: specs)
    monkeypatch.setattr(m, "make_client", lambda token_env=None: client)
    out = tmp_path / "gh_output.txt"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    code = m.main(["--db", str(tmp_path / "x.db"), *argv])
    return code, out.read_text(encoding="utf-8") if out.exists() else ""


def test_main_은_모두_맞으면_0_이고_메모를_남깁니다(tmp_path, monkeypatch, capsys):
    code, note = run_main(tmp_path, monkeypatch, FakeClient())
    assert code == 0
    assert note == "note=2개 표 7행\n"
    assert "truncated_games" in capsys.readouterr().out


def test_main_은_행_수가_다르면_0_이_아닙니다(tmp_path, monkeypatch):
    code, note = run_main(tmp_path, monkeypatch, FakeClient(rows_delta=1))
    assert code == 1 and "실패 mixed, teams" in note


def test_main_은_고른_표가_없으면_멈춥니다(tmp_path, monkeypatch):
    with pytest.raises(SystemExit, match="nope"):
        run_main(tmp_path, monkeypatch, FakeClient(), ["--tables", "teams,nope"])


def test_토큰_환경_변수로_자격을_만듭니다(monkeypatch):
    monkeypatch.setenv("BQ_TEST_TOKEN", "tok-value")
    c = m.make_client("BQ_TEST_TOKEN")
    assert c.project == "bstats-kbo" and c.location == "asia-northeast3"
    assert c._credentials.token == "tok-value"
    monkeypatch.delenv("BQ_TEST_TOKEN")
    with pytest.raises(SystemExit, match="BQ_TEST_TOKEN"):
        m.make_client("BQ_TEST_TOKEN")


# --- 로컬에서만 고친 표 ----------------------------------------------------

WRITE_SQL = re.compile(
    r"\b(?:INSERT(?:\s+OR\s+[A-Z]+)?\s+INTO|REPLACE\s+INTO|DELETE\s+FROM|UPDATE|"
    r"DROP\s+TABLE(?:\s+IF\s+EXISTS)?|CREATE\s+TABLE(?:\s+IF\s+NOT\s+EXISTS)?|ALTER\s+TABLE)"
    r"\s+[\"'`]?(\w+)")
TO_SQL = re.compile(r"\.to_sql\(\s*[\"'](\w+)")


def weekly_park_scripts():
    return sorted(set(re.findall(r"python\s+(park_factors/\w+\.py)",
                                 WEEKLY.read_text(encoding="utf-8"))))


def test_주간_계산이_고치는_MySQL_표는_올리거나_복사에서_뺍니다():
    """로컬에서 고친 표를 MySQL 에 올리지 않으면 SQLite 와 MySQL 이 다릅니다.

    그런 표를 빅쿼리에 복사하면 MySQL 에 없는 값이 빅쿼리에 들어갑니다.
    sqlite_to_d1.DERIVED_TABLES(올림)나 LOCAL_ONLY_EDITS(복사에서 뺌)에 있어야 합니다.
    """
    known = lx.schema_tables((ROOT / "migration" / "mysql" / "schema.sql").read_text(encoding="utf-8"))
    scripts = weekly_park_scripts()
    assert "park_factors/build_wrc_plus.py" in scripts
    edited = set()
    for rel in scripts:
        src = (ROOT / rel).read_text(encoding="utf-8")
        edited |= {t for t in WRITE_SQL.findall(src) + TO_SQL.findall(src) if t in known}
    assert "team_stadium_by_season" in edited       # 검사가 헛돌지 않습니다
    loose = sorted(edited - set(sqlite_to_d1.DERIVED_TABLES) - set(m.LOCAL_ONLY_EDITS))
    assert not loose, "주간 계산이 고치지만 올리지도, 복사에서 빼지도 않는 표: %s" % loose
    # 올리게 되면 MySQL 과 같아지므로 빼는 목록에서 지웁니다.
    assert not set(m.LOCAL_ONLY_EDITS) & set(sqlite_to_d1.DERIVED_TABLES)


# --- 워크플로 --------------------------------------------------------------

def weekly_steps():
    doc = yaml.safe_load(WEEKLY.read_text(encoding="utf-8"))
    return doc["jobs"]["park-factors"]["steps"]


def test_주간_워크플로가_결과_적재_뒤에_빅쿼리에_복사합니다():
    ss = weekly_steps()
    ids = [s.get("id") for s in ss]
    bq = ss[ids.index("bq_copy")]
    assert ids.index("push") < ids.index("bq_copy")
    assert bq["name"] == "빅쿼리 복사"
    assert "python -m migration.mysql.sqlite_to_bigquery --db \"$KBO_DB\"" in bq["run"]
    # 결과 표를 MySQL 에 올린 뒤에만, CSV·캐시 단계 결과와 상관없이 돕니다.
    assert bq["if"] == "${{ !cancelled() && steps.push.outcome == 'success' }}"
    # 실패해도 뒤 단계(기록·판정)를 막지 않습니다. 판정은 아래에서 봅니다.
    assert bq["continue-on-error"] is True
    pip = next(s for s in ss if s.get("name") == "의존성 설치")["run"]
    assert "google-cloud-bigquery" in pip and "pyarrow" in pip
    # 자격 파일(ADC)을 만드는 인증 단계가 앞에 있습니다.
    auth = next(i for i, s in enumerate(ss) if "google-github-actions/auth" in (s.get("uses") or ""))
    assert auth < ids.index("bq_copy")
    assert "create_credentials_file" not in (ss[auth].get("with") or {})


def test_빅쿼리_복사_결과를_bq_copy_로_기록합니다():
    ss = weekly_steps()
    i = next(i for i, s in enumerate(ss) if "--job bq_copy" in (s.get("run") or ""))
    rec = ss[i]
    assert i > [s.get("id") for s in ss].index("bq_copy")
    assert rec["if"] == "always()" and rec["continue-on-error"] is True
    assert "steps.bq_copy.outcome == 'success' && 'ok' || 'fail'" in rec["run"]
    assert "steps.bq_copy.outputs.note" in rec["env"]["NOTE"]


def test_요약과_마지막_판정에_빅쿼리_복사가_있습니다():
    ss = weekly_steps()
    summary = next(s for s in ss if s.get("name") == "요약")["run"]
    assert "| 빅쿼리 복사 | ${{ steps.bq_copy.outcome }} |" in summary
    judge = ss[-1]
    assert judge["name"] == "빅쿼리 복사 판정"
    assert judge["if"] == "${{ always() && steps.bq_copy.outcome == 'failure' }}"
    assert "exit 1" in judge["run"]
