# -*- coding: utf-8 -*-
"""칸·시즌 검증(migration/naver_verify.py): 비운 행은 따로 세고, 쓴 행 99% 기준."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "migration"))

import naver_verify as nv  # noqa: E402


def test_비운_행은_따로_셉니다():
    old = [{"player_id": "1", "a": "3"}, {"player_id": "2", "a": "4"}, {"player_id": "3", "a": ""}]
    new = [{"player_id": 1, "a": 3}, {"player_id": 2, "a": None}, {"player_id": 3, "a": None}]
    assert nv.rates(old, new, ["player_id", "a"]) == {"a": (2, 2, 1)}


def test_통과_기준():
    t = {2014: {"a": (99, 100, 5), "b": (98, 100, 0), "c": (0, 0, 10)}}
    assert nv.passed(t) == {"a": [2014]}
