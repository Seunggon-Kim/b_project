import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import daily_pbp_to_d1 as m  # noqa: E402


def test_모두_그날이면_빈_목록():
    rows = [{"game_date": "20261003"}, {"game_date": "20261003"}]
    assert m.wrong_dates(rows, "20261003") == []


def test_소수점_표기는_같은_날로_봅니다():
    # D1 은 INTEGER 친화성으로 20261003.0 을 20261003 으로 받습니다.
    assert m.wrong_dates([{"game_date": "20261003.0"}], "20261003") == []


def test_다른_날짜와_글자_날짜를_돌려줍니다():
    rows = [{"game_date": "20261003"}, {"game_date": "TOB00929"},
            {"game_date": "20261002"}, {"game_date": "TOB00929"}]
    assert m.wrong_dates(rows, "20261003") == ["20261002", "TOB00929"]


def test_비었거나_없으면_잘못입니다():
    assert m.wrong_dates([{"game_date": ""}, {}], "20261003") == [""]
