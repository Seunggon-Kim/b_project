# -*- coding: utf-8 -*-
"""크롤러의 시즌 구간(개막일~포스트시즌 시작)을 봅니다.

예전에는 `regular_start`·`playoff_start` 표에 그해 값이 없으면 KeyError 로
PBP 수집이 죽었습니다. 표는 2026 까지라 2027년 1월 2일(2027-01-01 경기
조회)부터 매일 실패했을 것입니다(2026-10-05 검토).

표에 있는 해(2008~2026)는 예전 값 그대로이고, 없는 해는 네이버 일정의
개막일(첫 kbo_r 경기)로 시범경기를 거릅니다.
"""
import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler"))

import download  # noqa: E402

D = datetime.date


@pytest.fixture(autouse=True)
def _fresh_cache():
    download._OPENING.clear()
    yield
    download._OPENING.clear()


def no_lookup(year):
    raise AssertionError("표에 있는 해는 일정을 묻지 않아야 합니다: %d" % year)


@pytest.mark.parametrize("year", range(2008, 2027))
def test_표에_있는_해는_예전_값_그대로입니다(year):
    reg = download.regular_start[str(year)]
    po = download.playoff_start[str(year)]
    assert download.season_window(year, lookup=no_lookup) == (
        D(year, int(reg[:2]), int(reg[2:])), D(year, int(po[:2]), int(po[2:])))


def test_표는_2026_에서_멈춥니다():
    # 해마다 값을 넣는 표로 되돌아가지 않게 합니다.
    years = [int(k) for k in download.regular_start if k.startswith("20")]
    assert max(years) == 2026
    assert sorted(download.regular_start) == sorted(download.playoff_start)


def test_표에_없는_해는_네이버_개막일을_씁니다():
    calls = []

    def lookup(year):
        calls.append(year)
        return D(2027, 3, 27)
    assert download.season_window(2027, lookup=lookup) == (D(2027, 3, 27), D(2027, 12, 31))
    # 한 번 찾은 값은 다시 묻지 않습니다.
    assert download.season_window(2027, lookup=lookup) == (D(2027, 3, 27), D(2027, 12, 31))
    assert calls == [2027]


def test_개막_일정이_아직_없으면_None_입니다():
    assert download.season_window(2027, lookup=lambda y: None) is None


class FakeCalendar:
    """네이버 달력 API 대신 답합니다. {'YYYY-MM': [(gameId, statusCode), ...]}."""

    def __init__(self, months):
        self.months = months
        self.urls = []

    def get(self, url, *a, **k):
        self.urls.append(url)
        ym = url.rsplit("date=", 1)[1][:7]
        games = self.months.get(ym, [])
        outer = self

        class Resp:
            status_code = 200

            def json(self):
                return {"result": {"dates": [
                    {"gameInfos": [{"gameId": g, "statusCode": s} for g, s in games]}]}}

            def close(self):
                pass
        outer.last = Resp()
        return outer.last


def run(monkeypatch, months, start, end, lookup):
    cal = FakeCalendar(months)
    monkeypatch.setattr(download.requests, "get", cal.get)
    monkeypatch.setattr(download, "opening_day", lookup)
    # season_window 의 기본 인자는 import 때 묶이므로 함수를 바꿔 끼웁니다.
    real = download.season_window
    monkeypatch.setattr(download, "season_window", lambda y: real(y, lookup=lookup))
    return download.get_game_ids(start, end)


def test_오늘_daily_는_예전과_같은_경기를_받습니다(monkeypatch):
    months = {"2026-10": [("20261004LGSS02026", "RESULT"), ("20261004HHKT02026", "RESULT"),
                          ("20261005OBNC02026", "BEFORE")]}
    got = run(monkeypatch, months, D(2026, 10, 4), D(2026, 10, 4), no_lookup)
    assert got == ["20261004LGSS02026", "20261004HHKT02026"]


def test_2027_시범경기는_빼고_개막부터_받습니다(monkeypatch):
    months = {"2027-03": [("20270313LGSS02027", "RESULT"), ("20270324HHKT02027", "RESULT"),
                          ("20270327OBNC02027", "RESULT"), ("20270328LTSK02027", "RESULT")]}
    got = run(monkeypatch, months, D(2027, 3, 1), D(2027, 3, 31), lambda y: D(2027, 3, 27))
    assert got == ["20270327OBNC02027", "20270328LTSK02027"]


def test_2027_개막_일정이_없으면_아무것도_받지_않습니다(monkeypatch):
    # 시범경기만 있는 때입니다. 죽지 않고 빈 목록입니다.
    months = {"2027-03": [("20270313LGSS02027", "RESULT")]}
    assert run(monkeypatch, months, D(2027, 3, 13), D(2027, 3, 13), lambda y: None) == []


def test_비시즌_daily_는_죽지_않고_일정도_묻지_않습니다(monkeypatch):
    # 2027-01-02 새벽 daily 는 2027-01-01 을 봅니다. 예전에는 여기서 KeyError 였습니다.
    def lookup(year):
        raise AssertionError("경기가 없는 달에는 개막일을 묻지 않습니다")
    assert run(monkeypatch, {}, D(2027, 1, 1), D(2027, 1, 1), lookup) == []


def test_2027_포스트시즌도_daily_가_받습니다(monkeypatch):
    # 2026 처럼 포스트시즌 시작을 12-31 로 둡니다(경기 ID 로 따로 판정).
    months = {"2027-10": [("20271020LGSS02027", "RESULT")]}
    got = run(monkeypatch, months, D(2027, 10, 20), D(2027, 10, 20), lambda y: D(2027, 3, 27))
    assert got == ["20271020LGSS02027"]
