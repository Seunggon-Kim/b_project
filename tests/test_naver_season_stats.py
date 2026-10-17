# -*- coding: utf-8 -*-
"""네이버 시즌 기록 칸(data_collection/naver_season_stats.py).

트레이드 선수는 경기 수가 가장 큰 행, 반올림은 반 올림, 이닝 표기는 KBO 처럼.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_season_stats as ns  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "naver"


def rows(tmp_path):
    shutil.copy(FIX / "players_2025.json", tmp_path / "2025.json")
    return ns.season_rows(2025, {("HH", 2025): "한화", ("NC", 2025): "NC"}, cache=tmp_path)


def test_트레이드_선수는_시즌_합계_행입니다(tmp_path):
    bat, _ = rows(tmp_path)
    son = [b for b in bat.values() if b["player_name"] == "손아섭"]
    assert len(son) == 1 and son[0]["games"] == 111 and son[0]["player_team"] == "한화"


def test_반올림은_반_올림입니다():
    assert ns.r(0.3125, 3) == 0.313
    assert ns.r(3.4534883720930236, 2) == 3.45
    assert ns.fmt2(3.855) == "3.86"


def test_이닝_표기():
    assert ns.ip_text("0 1/3") == "1/3" and ns.ip_text("149 1/3") == "149 1/3"
    assert ns.ip_outs("149 1/3") == 448 and ns.ip_outs("1/3") == 1 and ns.ip_outs("2/3") == 2
    assert ns.ip_outs("172") == 516


def test_타자_칸(tmp_path):
    bat, pit = rows(tmp_path)
    b = next(iter(bat.values()))
    assert b["total_bases"] == b["single"] + b["double"] + 2 * b["triple"] + 3 * b["home_run"]
    assert b["extra_base_hits"] == b["double"] + b["triple"] + b["home_run"]
    assert len(pit) == 3
    p = next(iter(pit.values()))
    assert isinstance(p["k_bb"], str)


def test_타수_0_이면_비율은_비웁니다():
    x = {"playerId": "1", "playerName": "가", "teamId": "NC", "hitterAb": 0, "hitterHra": 0,
         "hitterSlg": 0, "hitterObp": 0.5}
    b = ns.batter_row(x, 2025, {})
    assert b["batting_average"] is None and b["slugging_percentage"] is None


def test_순수장타율은_루타에서_안타를_뺀_값입니다():
    x = {"playerId": "1", "playerName": "가", "teamId": "NC", "hitterAb": 27, "hitterHit": 8,
         "hitterH2": 2, "hitterH3": 0, "hitterHr": 1, "hitterHra": 0.296, "hitterSlg": 0.481,
         "hitterObp": 0.3, "hitterBb": 2, "hitterHp": 0}
    assert ns.batter_row(x, 2025, {})["isop"] == 0.185  # (2+3)/27 = 0.18518


def test_이닝_0_투수는_비율을_비웁니다():
    x = {"playerId": "1", "playerName": "가", "teamId": "NC", "pitcherInning": "0",
         "pitcherEr": 2, "pitcherBb": 0, "pitcherKk": 0, "pitcherKkBbRate": 99.99}
    p = ns.pitcher_row(x, 2025, {})
    assert p["earned_run_average"] is None and p["k_9"] is None and p["k_bb"] is None


def test_ERA_는_개수에서_다시_셉니다():
    x = {"playerId": "1", "playerName": "가", "teamId": "NC", "pitcherInning": "149 1/3",
         "pitcherEr": 50, "pitcherHit": 140, "pitcherBb": 40, "pitcherKk": 120}
    p = ns.pitcher_row(x, 2025, {})
    assert p["earned_run_average"] == 3.01 and p["walks_plus_hits_per_inning_pitched"] == 1.21
    assert p["k_bb"] == "3.00"
