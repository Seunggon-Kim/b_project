# -*- coding: utf-8 -*-
import sqlite3

from migration.verify_d1 import compare_counts, local_counts, parse_d1_json


def test_parse_d1_json_reads_wrangler_shape():
    """wrangler --json 은 결과를 배열로 감싸 돌려줍니다."""
    raw = '[{"results":[{"n":42}],"success":true}]'
    assert parse_d1_json(raw) == [{"n": 42}]


def test_parse_d1_json_tolerates_leading_noise():
    """wrangler 가 JSON 앞에 진행 메시지를 섞어 내보낼 때가 있습니다."""
    raw = '─ wrangler 4.0\n[{"results":[{"n":7}],"success":true}]\n'
    assert parse_d1_json(raw) == [{"n": 7}]


def test_local_counts_skips_missing_tables():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE teams (a INTEGER)")
    conn.execute("INSERT INTO teams VALUES (1)")
    counts = local_counts(conn, ["teams", "없는테이블"])
    assert counts == {"teams": 1}


def test_compare_counts_reports_only_mismatches():
    local = {"teams": 10, "games": 719}
    remote = {"teams": 10, "games": 700}
    diffs = compare_counts(local, remote)
    assert diffs == [("games", 719, 700)]


def test_compare_counts_treats_absent_remote_as_zero():
    diffs = compare_counts({"teams": 10}, {})
    assert diffs == [("teams", 10, 0)]


def test_compare_counts_empty_when_equal():
    assert compare_counts({"teams": 10}, {"teams": 10}) == []
