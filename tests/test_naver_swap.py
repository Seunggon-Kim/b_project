# -*- coding: utf-8 -*-
"""네이버 전환 스크립트(migration/naver_swap.py): 백업 글자·미리보기 차이."""
import datetime
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "migration"))

import naver_swap as sw  # noqa: E402


def test_백업은_INSERT_글로_씁니다(tmp_path):
    def q(sql):
        return [{"player_id": 1, "player_name": "O'Neil", "x": None, "d": datetime.date(2026, 1, 2)}]
    done = sw.backup(q, tmp_path, "20261018")
    assert len(done) == len(sw.TABLES)
    text = (tmp_path / "players_kbo_20261018.sql").read_text(encoding="utf-8")
    assert "VALUES (1, 'O''Neil', NULL, '2026-01-02');" in text


def test_차이():
    old = [{"player_id": 1, "a": "0.3"}, {"player_id": 2, "a": 1}]
    new = [{"player_id": 1, "a": 0.3}, {"player_id": 3, "a": 1}]
    gone, add, ch = sw.diff_rows(old, new, lambda r: r["player_id"], ["a"])
    assert gone == [2] and add == [3] and ch["a"] == 0


def test_쓰기는_execute_없이는_하지_않습니다(monkeypatch, capsys):
    import types
    fake = types.SimpleNamespace(query=lambda sql: [])
    monkeypatch.setitem(sys.modules, "d1_load", fake)
    monkeypatch.setitem(sys.modules, "kbo_season", types.SimpleNamespace(record_season=lambda: 2026))
    assert sw.main(["--step", "pre2008"]) == 0
    assert "미리보기" in capsys.readouterr().out
