# -*- coding: utf-8 -*-
"""적재 스크립트가 나뉜 표를 올바른 D1 로 보내는지 봅니다.

`play_by_play` 를 시즌별 D1 네 개로 나눈 뒤에도 수집 스크립트들이
공용 DB(kbo-stats)만 보고 있었습니다. 그러면 오류가 나지 않습니다.
행은 아무도 읽지 않는 표에 쌓이고 화면만 조용히 어제에 멈춥니다.
그 고장을 다시 만들지 않으려고 여기서 걸러 냅니다.
"""
import ast
import re
from pathlib import Path

import pytest

from migration import d1_to_sqlite, shard_plan

ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------- 배정표

def test_모든_시즌이_담당_D1_을_가집니다():
    for y in shard_plan.all_seasons():
        assert shard_plan.db_of(y), "%d 시즌 담당 D1 이 없습니다" % y


def test_배정에_없는_시즌은_None_입니다():
    # 2027 이 오면 배정표를 먼저 늘려야 합니다. 조용히 어딘가로
    # 흘러가면 안 됩니다.
    assert shard_plan.db_of(2027) is None


def test_공용_DB_는_샤드가_아닙니다():
    names = {s["database"] for s in shard_plan.shards()}
    assert shard_plan.shared_db() not in names


# ------------------------------------------------- 매일 적재가 샤드를 봅니다

DAILY_PBP = ROOT / "data_collection" / "daily_pbp_to_d1.py"


def _daily_source():
    return DAILY_PBP.read_text(encoding="utf-8")


def test_매일_pbp_적재가_담당_D1_을_고릅니다():
    src = _daily_source()
    assert "shard_plan.db_of(" in src, (
        "daily_pbp_to_d1.py 가 시즌별 D1 을 고르지 않습니다. "
        "공용 DB 에 넣으면 워커가 읽지 않습니다."
    )


@pytest.mark.parametrize("fn", ["d1_columns", "run_d1_file", "refresh_count"])
def test_매일_pbp_적재가_D1_이름을_넘깁니다(fn):
    """기본값이 kbo-stats 라서, 안 넘기면 공용 DB 로 갑니다."""
    src = _daily_source()
    calls = re.findall(re.escape(fn) + r"\((.*?)\)", src, re.DOTALL)
    # import 줄에서 걸린 것은 인자가 없습니다.
    calls = [c for c in calls if c.strip()]
    assert calls, "%s 호출을 찾지 못했습니다" % fn
    for c in calls:
        assert "db_name=" in c, (
            "%s 가 db_name 없이 불립니다. 기본값이 공용 DB 입니다: %s"
            % (fn, c.strip())
        )


def test_매일_pbp_적재가_문법적으로_성립합니다():
    ast.parse(_daily_source())


# --------------------------------------- 주간 내려받기가 샤드 전부를 훑습니다

def test_나뉜_표는_샤드마다_한_번씩_받습니다():
    jobs = d1_to_sqlite.export_jobs(["play_by_play", "games"])
    pbp = [j for j in jobs if j[0] == "play_by_play"]
    assert len(pbp) == len(shard_plan.shards())
    assert {j[1] for j in pbp} == {s["database"] for s in shard_plan.shards()}
    # 파일 이름이 겹치면 뒤엣것이 앞엣것을 덮어써 1/4 만 남습니다.
    assert len({j[2] for j in pbp}) == len(pbp)


def test_안_나뉜_표는_공용_DB_한_번입니다():
    jobs = d1_to_sqlite.export_jobs(["games", "teams"])
    assert jobs == [
        ("games", d1_to_sqlite.DB_NAME, "games"),
        ("teams", d1_to_sqlite.DB_NAME, "teams"),
    ]


def test_파이프라인_표에_나뉜_표가_들어_있습니다():
    assert "play_by_play" in d1_to_sqlite.PIPELINE_TABLES


def test_두_번째_조각부터_CREATE_가_죽지_않습니다():
    """샤드 네 개를 같은 SQLite 에 이어 넣습니다."""
    import sqlite3

    dump = (
        'CREATE TABLE "play_by_play" (pbp_id INTEGER PRIMARY KEY, a TEXT);\n'
        'CREATE INDEX idx_a ON "play_by_play" (a);\n'
        'CREATE UNIQUE INDEX ux_a ON "play_by_play" (pbp_id, a);\n'
    )
    sql = d1_to_sqlite.idempotent_ddl(dump)
    conn = sqlite3.connect(":memory:")
    conn.executescript(sql)
    conn.executescript(sql)  # 두 번째 샤드 조각
    conn.executescript(sql)  # 세 번째
    n = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE name='play_by_play'"
    ).fetchone()[0]
    assert n == 1


def test_이미_IF_NOT_EXISTS_인_것은_그대로_둡니다():
    s = 'CREATE TABLE IF NOT EXISTS "t" (a TEXT);'
    assert d1_to_sqlite.idempotent_ddl(s) == s


def test_값_안의_CREATE_는_건드리지_않습니다():
    """이걸 놓치면 데이터가 조용히 바뀝니다."""
    s = "INSERT INTO \"t\" VALUES ('CREATE TABLE x');"
    assert d1_to_sqlite.idempotent_ddl(s) == s


def test_들여쓴_CREATE_도_바꿉니다():
    s = '  CREATE TABLE "t" (a TEXT);'
    assert "IF NOT EXISTS" in d1_to_sqlite.idempotent_ddl(s)


def test_섞인_덤프에서_DDL_만_바뀝니다():
    dump = (
        'CREATE TABLE "t" (a TEXT);\n'
        "INSERT INTO \"t\" VALUES ('CREATE INDEX 사기');\n"
        'CREATE INDEX ix ON "t" (a);\n'
    )
    got = d1_to_sqlite.idempotent_ddl(dump)
    assert got.count("IF NOT EXISTS") == 2
    assert "('CREATE INDEX 사기')" in got
