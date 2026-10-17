# -*- coding: utf-8 -*-
"""네이버 호출 도우미(data_collection/naver_http.py)를 지킵니다.

KBO 사이트를 부르지 않는 것(약관), 초당 1회 이하, 4xx 는 다시 묻지 않는 것.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_http as nh  # noqa: E402


class Clock:
    def __init__(self):
        self.t = 0.0
        self.slept = []

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept.append(round(s, 3))
        self.t += s


def ok(body=None):
    return lambda u: (200, json.dumps(body or {"code": 200, "success": True, "result": {}}))


def test_KBO_사이트는_부르지_않습니다():
    c = nh.Client(opener=ok())
    for u in ("https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx",
              "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/1.jpg",
              "https://m.sports.naver.com/x"):
        with pytest.raises(ValueError):
            c.get(u)


def test_경로만_주면_네이버_주소가_됩니다():
    c = nh.Client(opener=ok())
    assert c.url("/statistics/x", {"a": 1}) == "https://api-gw.sports.naver.com/statistics/x?a=1"


def test_호출_간격을_지킵니다():
    k = Clock()
    c = nh.Client(clock=k.now, sleep=k.sleep, opener=ok())
    c.get("/a")
    k.t += 0.3
    c.get("/b")
    assert k.slept == [0.8]


def test_4xx_는_다시_묻지_않습니다():
    seen = []

    def opener(u):
        seen.append(u)
        return 400, "{}"
    k = Clock()
    c = nh.Client(clock=k.now, sleep=k.sleep, opener=opener)
    with pytest.raises(nh.NaverError) as e:
        c.get("/a")
    assert e.value.status == 400 and len(seen) == 1


def test_5xx_는_다시_묻습니다():
    answers = [(503, ""), (200, json.dumps({"code": 200, "result": {"x": 1}}))]
    k = Clock()
    c = nh.Client(clock=k.now, sleep=k.sleep, opener=lambda u: answers.pop(0))
    assert c.get("/a")["result"] == {"x": 1}


def test_code_가_200_이_아니면_실패입니다():
    k = Clock()
    c = nh.Client(clock=k.now, sleep=k.sleep, opener=ok({"code": 404, "success": False}))
    with pytest.raises(nh.NaverError):
        c.get("/a")
