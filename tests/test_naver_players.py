# -*- coding: utf-8 -*-
"""선수 정보(data_collection/naver_players.py): 결정 5 칸별 처리."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_players as np_  # noqa: E402

D = {"playerName": "소형준", "backNo": 30, "position": "PITCHER", "dateOfBirth": "2001-09-16",
     "height": 189, "weight": 92, "playerPlayType": "우투우타", "salary": "33,000만원",
     "career": "유신고", "draftInfo": "20 KT 1차", "teamId": "KT", "isRetire": False}


def test_현역은_네이버_값입니다():
    r = np_.build_row(50030, D, "KT", {}, {}, "u")
    assert (r["throw"], r["bat"], r["birthday"], r["position"]) == ("R", "R", "20010916", "투수")
    assert r["salary"] == 330000000 and r["team_id"] == "KT" and r["image_url"] == "u"


def test_드래프트_경력은_네이버_값_계약금은_비웁니다():
    r = np_.build_row(50030, D, "KT", {}, {}, "u")
    assert (r["draft_year"], r["draft_order"], r["career"]) == ("20KT", "20 KT 1차", "유신고")
    assert r["signing_bonus"] is None


def test_드래프트_표기():
    assert np_.draft("20 LG 2차 8R 73순위") == ("20LG", "8라운드 73순위")
    assert np_.draft("23 키움 11R 106순위") == ("23키움", "11라운드 106순위")
    assert np_.draft("20 두산 육성선수") == ("20두산", "20 두산 육성선수")
    assert np_.draft(None) == (None, None)


def test_소속은_시즌_기록_상세_빈값_차례():
    names = {("OB", 2026): "두산"}
    assert np_.team_of(1, None, 2026, {1: "LG"}, names) == ("LG", "season")
    d = {"teamId": "OB", "year": 2026, "isRetire": False}
    assert np_.team_of(2, d, 2026, {}, names) == ("두산", "detail")
    assert np_.team_of(3, dict(d, isRetire=True), 2026, {}, names) == (None, None)
    assert np_.team_of(4, dict(d, year=2024), 2026, {}, names) == (None, None)


def test_은퇴_선수는_소속_연봉_없이():
    r = np_.build_row(50030, dict(D, isRetire=True), None, {}, {}, None)
    assert r["team_id"] == "" and r["salary"] is None


def test_네이버가_비운_투타는_PBP_다수_값():
    rows = [{"pitch_number": 1, "pitcher_ID": 7, "throws": "좌", "batter_ID": 8, "stands": "양"}] * 9 + \
           [{"pitch_number": 1, "pitcher_ID": 7, "throws": "우", "batter_ID": 8, "stands": "우"}]
    th, bt = np_.hands_from_pbp(rows)
    assert th[7] == "L" and bt[8] == "S"
    r = np_.build_row(7, dict(D, playerPlayType=None), None, th, bt, None)
    assert r["throw"] == "L"


def test_타석_방향이_갈리면_비웁니다():
    rows = [{"pitch_number": 1, "batter_ID": 8, "stands": "좌"}] * 6 + \
           [{"pitch_number": 1, "batter_ID": 8, "stands": "우"}] * 4
    _, bt = np_.hands_from_pbp(rows)
    assert 8 not in bt


def test_표기():
    assert np_.play_type("우언양타") == ("R", "S")
    assert np_.won("50,000만원") == 500000000 and np_.won(None) is None
    assert np_.won("1,100,000달러") == 1100000


def test_사진은_404_면_비웁니다():
    assert np_.photo(1, opener=lambda u: 404, gap=0) is None
    assert np_.photo(1, opener=lambda u: 200, gap=0).endswith("/1.png")
