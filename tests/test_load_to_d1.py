# -*- coding: utf-8 -*-
import json
import sqlite3

import pytest

from migration.load_to_d1 import (
    index_counts,
    pending_files,
    plan_batch,
    write_cost,
)


def test_pending_excludes_recorded(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    b = tmp_path / "01_t_0002.sql"
    a.write_text("x", encoding="utf-8")
    b.write_text("y", encoding="utf-8")
    progress = tmp_path / ".progress"
    progress.write_text("01_t_0001.sql\n", encoding="utf-8")
    assert pending_files([a, b], progress) == [b]


def test_pending_returns_all_when_no_progress(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    a.write_text("x", encoding="utf-8")
    progress = tmp_path / ".progress"
    assert pending_files([a], progress) == [a]


def test_pending_ignores_blank_lines(tmp_path):
    a = tmp_path / "01_t_0001.sql"
    a.write_text("x", encoding="utf-8")
    progress = tmp_path / ".progress"
    progress.write_text("\n\n", encoding="utf-8")
    assert pending_files([a], progress) == [a]


def test_index_counts_reads_local_schema():
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t (a INTEGER, b INTEGER)")
    conn.execute("CREATE INDEX i1 ON t(a)")
    conn.execute("CREATE INDEX i2 ON t(b)")
    conn.execute("CREATE TABLE u (a INTEGER)")
    counts = index_counts(conn)
    assert counts["t"] == 2
    assert counts["u"] == 0


def test_write_cost_includes_index_writes():
    """D1 은 인덱스마다 쓰기 행을 하나 더 셉니다. 1,000행 x (1+3) = 4,000."""
    assert write_cost(1000, 3) == 4000


def test_write_cost_without_index_is_row_count():
    assert write_cost(1000, 0) == 1000


def test_plan_batch_stops_at_budget(tmp_path):
    """예산을 넘기 직전까지만 담습니다. 한도에 부딪혀 실패하는 대신 멈춥니다."""
    manifest = {
        "files": [
            {"name": "a.sql", "table": "t", "rows": 1000},
            {"name": "b.sql", "table": "t", "rows": 1000},
            {"name": "c.sql", "table": "t", "rows": 1000},
        ]
    }
    files = [tmp_path / n for n in ("a.sql", "b.sql", "c.sql")]
    chosen, cost = plan_batch(files, manifest, {"t": 3}, budget=9000)
    # 파일당 4,000 이므로 두 개까지만 들어갑니다.
    assert [f.name for f in chosen] == ["a.sql", "b.sql"]
    assert cost == 8000


def test_plan_batch_zero_budget_takes_everything(tmp_path):
    manifest = {"files": [{"name": "a.sql", "table": "t", "rows": 1000}]}
    files = [tmp_path / "a.sql"]
    chosen, cost = plan_batch(files, manifest, {"t": 3}, budget=0)
    assert chosen == files
    assert cost == 4000


def test_plan_batch_takes_at_least_one_file(tmp_path):
    """예산보다 큰 파일 하나뿐이면 그것만이라도 시도합니다. 영원히 멈추지 않도록."""
    manifest = {"files": [{"name": "a.sql", "table": "t", "rows": 1000}]}
    files = [tmp_path / "a.sql"]
    chosen, _ = plan_batch(files, manifest, {"t": 3}, budget=10)
    assert chosen == files


def test_plan_batch_unknown_file_raises(tmp_path):
    """목록에 없는 파일은 비용을 셀 수 없으므로 조용히 넘기지 않습니다."""
    manifest = {"files": []}
    with pytest.raises(KeyError):
        plan_batch([tmp_path / "ghost.sql"], manifest, {}, budget=0)


def test_plan_batch_reads_real_manifest_shape(tmp_path):
    """export_to_d1 이 실제로 쓰는 manifest 모양을 그대로 받습니다."""
    m = {
        "source": "database/kbo_stats.db",
        "files": [{"name": "20_play_by_play_0001.sql",
                   "table": "play_by_play", "rows": 1000, "bytes": 550000}],
        "totals": {"rows": 1000, "files": 1},
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    chosen, cost = plan_batch(
        [tmp_path / "20_play_by_play_0001.sql"], loaded,
        {"play_by_play": 3}, budget=0)
    assert cost == 4000
    assert len(chosen) == 1
