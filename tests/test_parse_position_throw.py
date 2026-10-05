# -*- coding: utf-8 -*-
"""KBO 선수 정보의 포지션 칸에서 투수 손(throw)·타석(bat)을 읽습니다.

KBO 는 사이드암·언더핸드 투수를 '우언'·'좌언'으로 적습니다(예: 우강훈
'투수(우언우타)'). 예전 파서는 '우투'·'좌투'·'양투'만 읽어 이 투수들의
throw 가 비었습니다(2026-10-05 발견, 운영 19명 안팎).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "data_collection"))

import pytest  # noqa: E402

from player_info_scraper import parse_position  # noqa: E402


@pytest.mark.parametrize("text, expected", [
    ("투수(우투우타)", ("투수", "R", "R")),
    ("투수(좌투좌타)", ("투수", "L", "L")),
    ("내야수(우투좌타)", ("내야수", "R", "L")),
    ("투수(우언우타)", ("투수", "R", "R")),
    ("투수(좌언좌타)", ("투수", "L", "L")),
    ("투수(우언좌타)", ("투수", "R", "L")),
    ("투수(우투양타)", ("투수", "R", "S")),
])
def test_투수_손과_타석을_읽습니다(text, expected):
    assert parse_position(text) == expected


def test_괄호가_없거나_빈_값이면_손은_비웁니다():
    assert parse_position("투수") == ("투수", None, None)
    assert parse_position("-") == (None, None, None)
    assert parse_position("") == (None, None, None)
