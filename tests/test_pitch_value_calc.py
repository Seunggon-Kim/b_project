# -*- coding: utf-8 -*-
import pytest

from data_collection import pitch_value_calc as pv


def row(pbp_id, *, game="G1", inning=1, tb="초", outs=0, balls=0, strikes=0,
        b1=False, b2=False, b3=False, result="볼", runs=0, pitcher=1,
        ptype="직구", stands="우", throws="우"):
    return {"gameID": game, "pbp_id": pbp_id, "inning": inning, "inning_topbot": tb,
            "outs": outs, "balls": balls, "strikes": strikes,
            "on_1b": b1, "on_2b": b2, "on_3b": b3, "pitch_result": result,
            "runs_scored": runs, "pitcher_ID": pitcher, "pitch_type": ptype,
            "stands": stands, "throws": throws}


def test_상태는_주자_합_아웃_볼_스트라이크입니다():
    assert pv.state_of(row(1, b1=True, b3=True, outs=2, balls=1, strikes=2)) == (5, 2, 1, 2)


def test_볼_4는_3으로_봅니다():
    assert pv.state_of(row(1, balls=4)) == (0, 0, 3, 0)


def test_반이닝은_경기_이닝_초말로_나눕니다():
    rows = [row(1), row(2), row(3, tb="말"), row(4, inning=2), row(5, game="G2")]
    assert [[r["pbp_id"] for r in h] for h in pv.split_halves(rows)] == [[1, 2], [3], [4], [5]]


def test_경기마다_마지막_반이닝을_찾습니다():
    halves = pv.split_halves([row(1), row(2, tb="말"), row(3, game="G2")])
    assert pv.last_half_index(halves) == {1, 2}


def test_기대_득점은_그_공부터_반이닝_끝까지_득점_평균입니다():
    # 반이닝 A: 0-0 에서 시작해 두 번째 공에 1점, 반이닝 B: 0-0 에서 무득점
    a = [row(1), row(2, balls=1, result="타격", runs=1)]
    b = [row(3, inning=2)]
    re, n = pv.build_re([a, b])
    assert n[(0, 0, 0, 0)] == 2
    assert re[(0, 0, 0, 0)] == pytest.approx(0.5)
    assert re[(0, 0, 1, 0)] == pytest.approx(1.0)


def test_사건_행은_기대_득점_표에_들지_않지만_득점은_셉니다():
    a = [row(1), row(2, result=None, runs=1), row(3, balls=1)]
    re, n = pv.build_re([a])
    assert (0, 0, 1, 0) in re and n[(0, 0, 0, 0)] == 1
    assert re[(0, 0, 0, 0)] == pytest.approx(1.0)  # 폭투 득점도 "그 뒤 득점"
    assert re[(0, 0, 1, 0)] == pytest.approx(0.0)


def test_표는_경기_마지막_반이닝을_빼고_빈_상태는_전체로_메웁니다():
    first = [row(1), row(2, balls=1)]
    last = [row(3, tb="말", runs=0), row(4, tb="말", strikes=2, runs=1)]
    re, n = pv.expectancy_table([first, last])
    assert re[(0, 0, 0, 0)] == pytest.approx(0.0)          # 마지막 반이닝 빠짐
    assert n[(0, 0, 0, 0)] == 1
    assert re[(0, 0, 0, 2)] == pytest.approx(1.0)          # 전체 표로 메움


def test_스위치_타자는_투수_반대쪽입니다():
    assert pv.bat_side("양", "우") == "L"
    assert pv.bat_side("양", "좌") == "R"
    assert pv.bat_side("좌", "우") == "L"
    assert pv.bat_side("우", "좌") == "R"
    assert pv.bat_side(None, None) == "R"


def test_공_가치는_다음_행_상태와_득점으로_재고_투수_쪽_부호입니다():
    re = {(0, 0, 0, 0): 0.5, (0, 0, 1, 0): 0.6, (1, 0, 0, 0): 0.9}
    h = [row(1, ptype="직구"),                      # 0-0 → 1-0 : +0.1 → 투수 −0.1
         row(2, balls=1, result="타격", ptype="커브", stands="좌", runs=1)]  # 반이닝 끝: 0 − 0.6 + 1
    vals = pv.pitch_values([h], re)
    assert vals[(1, "직구", "R")] == [1, pytest.approx(-0.1)]
    assert vals[(1, "커브", "L")] == [1, pytest.approx(-0.4)]


def test_사건_몫은_공에_붙지_않습니다():
    re = {(0, 0, 0, 0): 0.5, (2, 0, 0, 0): 0.7, (2, 0, 1, 0): 0.8, (1, 0, 0, 0): 0.6}
    # 1루 주자, 볼 → 0-0 직후 상태(1루)가 사건 행에 적힘 → 도루로 2루 → 다음 공 1-0
    h = [row(1, b1=True, ptype="직구"),
         row(2, b1=True, balls=1, result=None),     # 도루 행(직전 상태 = 볼 직후)
         row(3, b2=True, balls=1, ptype="커브")]
    re[(1, 0, 1, 0)] = 0.65
    vals = pv.pitch_values([h], re)
    assert vals[(1, "직구", "R")][1] == pytest.approx(-(0.65 - 0.6))


def test_구종_없는_공은_가치_표에_넣지_않습니다():
    re = {(0, 0, 0, 0): 0.5}
    vals = pv.pitch_values([[row(1, ptype=None)], [row(2, ptype="-")]], re)
    assert vals == {}


def test_투수_ID_가_빈_공은_가치_표에_넣지_않습니다():
    re = {(0, 0, 0, 0): 0.5}
    vals = pv.pitch_values([[row(1, pitcher=None)]], re)
    assert vals == {}
