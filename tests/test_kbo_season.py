# -*- coding: utf-8 -*-
"""시즌 경계(data_collection/kbo_season.py)를 날짜를 넣어 봅니다.

    2026-10-05  오늘. 예전(2026 고정)과 같은 값이어야 합니다.
    2027-02-15  비시즌. 2027 자료가 없습니다.
    2027-04-15  개막 뒤.

네이버 일정은 가짜로 넣습니다. 시험이 인터넷을 타지 않습니다.
"""
import datetime
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import kbo_season as ks  # noqa: E402

D = datetime.date


def game(day, round_code, status="RESULT"):
    return {"gameDate": day, "roundCode": round_code, "statusCode": status}


# 2026 은 실제 일정 모양입니다. 시범경기가 03-24 까지, 개막이 03-28 입니다.
# 2027 은 개막을 03-27 로 가정합니다. 일정은 나왔고 아직 경기 전입니다.
SCHEDULE = {
    (2026, 3): [game("2026-03-12", "kbo_e"), game("2026-03-24", "kbo_e"),
                game("2026-03-28", "kbo_r"), game("2026-03-29", "kbo_r")],
    (2026, 10): [game("2026-10-03", "kbo_r")],
    (2027, 3): [game("2027-03-13", "kbo_e"), game("2027-03-24", "kbo_e"),
                game("2027-03-27", "kbo_r", "BEFORE"), game("2027-03-28", "kbo_r", "BEFORE")],
}


def fake(schedule):
    calls = []

    def fetch(year, month):
        calls.append((year, month))
        return schedule.get((year, month), [])
    fetch.calls = calls
    return fetch


def played_2027(upto):
    """2027 정규시즌 경기가 upto 날짜까지 끝난 일정입니다."""
    s = dict(SCHEDULE)
    s[(2027, 3)] = [game("2027-03-13", "kbo_e"), game("2027-03-24", "kbo_e")] + [
        game(d, "kbo_r", "RESULT" if d <= upto else "BEFORE")
        for d in ("2027-03-27", "2027-03-28")]
    s[(2027, 4)] = [game("2027-04-14", "kbo_r", "RESULT" if "2027-04-14" <= upto else "BEFORE")]
    return s


def test_마지막_시즌은_한국_날짜의_올해이고_2026_이상입니다():
    # src/lib/pbpseasons.js 의 pbpLastSeason 과 같은 값이어야 합니다.
    assert ks.last_season("2026-10-05") == 2026
    assert ks.last_season("2025-12-31") == 2026
    assert ks.last_season("2027-01-01") == 2027
    assert ks.last_season("2027-02-15") == 2027
    assert ks.last_season("2027-04-15") == 2027
    assert ks.last_season(D(2031, 3, 20)) == 2031


def test_UTC_자정_전후의_한국_날짜를_씁니다():
    # 러너는 UTC 입니다. 2026-12-31 15:30 UTC 는 한국으로 2027-01-01 입니다.
    utc = datetime.timezone.utc
    assert ks.kst_today(datetime.datetime(2026, 12, 31, 15, 30, tzinfo=utc)) == D(2027, 1, 1)
    assert ks.kst_today(datetime.datetime(2026, 12, 31, 14, 30, tzinfo=utc)) == D(2026, 12, 31)


def test_계산_범위는_오늘은_2026_까지입니다():
    assert ks.seasons_through(2008, "2026-10-05") == list(range(2008, 2027))
    assert ks.seasons_through(2008, "2027-02-15") == list(range(2008, 2028))
    assert ks.seasons_through(2008, "2027-04-15")[-1] == 2027


def test_개막일은_첫_kbo_r_경기입니다():
    assert ks.opening_day(2026, fetch=fake(SCHEDULE)) == D(2026, 3, 28)
    # 일정에 올라온 경기라면 아직 안 했어도 개막일입니다.
    assert ks.opening_day(2027, fetch=fake(SCHEDULE)) == D(2027, 3, 27)


def test_시범경기와_연습경기는_개막일이_아닙니다():
    # 2020 은 연습경기(kbo_p, 04-21~)가 먼저 있고 개막(kbo_r)은 05-05 였습니다.
    s = {(2020, 4): [game("2020-04-21", "kbo_p")],
         (2020, 5): [game("2020-05-01", "kbo_p"), game("2020-05-05", "kbo_r")]}
    assert ks.opening_day(2020, fetch=fake(s)) == D(2020, 5, 5)
    # 시범경기만 있으면 아직 개막일이 없습니다.
    s = {(2027, 3): [game("2027-03-13", "kbo_e")]}
    assert ks.opening_day(2027, fetch=fake(s)) is None


def test_일정이_아직_없으면_None_입니다():
    f = fake({})
    assert ks.opening_day(2027, fetch=f) is None
    assert f.calls == [(2027, m) for m in ks.OPENING_MONTHS]


def test_끝난_경기만_볼_때는_경기_전_개막일을_세지_않습니다():
    assert ks.opening_day(2027, fetch=fake(SCHEDULE), played=True) is None
    assert ks.opening_day(2027, fetch=fake(played_2027("2027-03-27")), played=True) == D(2027, 3, 27)


@pytest.mark.parametrize("today,schedule,want", [
    ("2026-10-05", SCHEDULE, 2026),                       # 오늘: 예전과 같습니다
    ("2027-01-10", {}, 2026),                              # 비시즌, 일정 없음
    ("2027-02-15", SCHEDULE, 2026),                        # 비시즌, 일정만 있음
    ("2027-03-20", SCHEDULE, 2026),                        # 시범경기 기간
    ("2027-03-27", played_2027("2027-03-26"), 2026),       # 개막일 새벽(경기 전)
    ("2027-03-28", played_2027("2027-03-27"), 2027),       # 개막 다음 날
    ("2027-04-15", played_2027("2027-04-14"), 2027),       # 시즌 중
    ("2027-05-31", {}, 2026),                              # 아직 비시즌으로 봅니다
    # 6월 1일이 되도록 정규시즌 경기가 없으면 일정이 이상한 것입니다(검토 I1).
    # 지난해로 물러서지 않고 올해로 둡니다. 가장 늦은 개막은 2020-05-05 였습니다.
    ("2027-06-01", {}, 2027),
    ("2027-06-15", {}, 2027),
    ("2026-11-20", {}, 2026),                              # 오늘 구간(포스트시즌 뒤)
])
def test_기록을_받을_시즌(today, schedule, want):
    assert ks.record_season(today, fetch=fake(schedule)) == want


def test_비시즌_1월에는_일정을_묻지_않습니다():
    # 아직 오지 않은 달에는 끝난 경기가 있을 수 없습니다.
    f = fake({})
    assert ks.record_season("2027-01-10", fetch=f) == 2026
    assert f.calls == []


def test_일정을_못_받으면_예전처럼_올해입니다(capsys):
    def broken(year, month):
        raise OSError("연결 실패")
    assert ks.record_season("2027-04-15", fetch=broken) == 2027
    assert "올해(2027)" in capsys.readouterr().out


def test_6월이_되도록_일정이_비면_경고를_찍습니다(capsys):
    assert ks.record_season("2027-06-15", fetch=fake({})) == 2027
    assert "일정이 이상할 수 있어" in capsys.readouterr().out


@pytest.mark.parametrize("odd", [
    {"gameDate": "2027-04-14", "statusCode": "RESULT"},          # roundCode 없음
    {"roundCode": "kbo_r", "statusCode": "RESULT"},               # gameDate 없음
    {"gameDate": "2027-04-14", "roundCode": "kbo_r"},             # statusCode 없음
    "20270414LGSS02027",                                          # dict 가 아님
])
def test_경기_모양이_다르면_예외입니다(odd, capsys):
    s = {(2027, 4): [odd]}
    with pytest.raises(ValueError):
        ks.opening_day(2027, fetch=fake(s))
    # 기록 시즌은 지난해로 숨지 않고 예전처럼 올해로 둡니다(경고와 함께).
    assert ks.record_season("2027-04-15", fetch=fake(s)) == 2027
    assert "못 읽어" in capsys.readouterr().out


@pytest.mark.parametrize("body", [
    {"success": False, "result": {"games": []}},
    {"success": True, "result": {}},
    {"success": True, "result": {"games": None}},
    {"success": True},
    [],
    {"success": True, "result": {"games": [game("2027-04-14", "kbo_r")], "gameTotalCount": 2}},
])
def test_응답_모양이_다르면_예외입니다(body):
    with pytest.raises(ValueError):
        ks.games_of(body)


def test_정상_응답은_경기_목록입니다():
    assert ks.games_of({"code": 200, "success": True,
                        "result": {"games": [], "gameTotalCount": 0}}) == []
    one = [game("2027-04-14", "kbo_r")]
    assert ks.games_of({"success": True, "result": {"games": one, "gameTotalCount": 1}}) == one


class Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_받기가_한_번_실패하면_한_번_더_묻습니다(monkeypatch):
    calls, slept = [], []

    def urlopen(req, timeout=None):
        calls.append(req.full_url)
        if len(calls) == 1:
            raise ks.urllib.error.URLError("잠깐 끊김")
        return Resp(json.dumps({"success": True, "result": {"games": []}}).encode())
    monkeypatch.setattr(ks.urllib.request, "urlopen", urlopen)
    assert ks.fetch_month(2027, 4, sleep=slept.append) == []
    assert len(calls) == 2 and slept == [ks.RETRY_SLEEP_SEC]


def test_두_번_다_실패하면_예외가_나갑니다(monkeypatch):
    slept = []

    def urlopen(req, timeout=None):
        raise TimeoutError("시간 초과")
    monkeypatch.setattr(ks.urllib.request, "urlopen", urlopen)
    with pytest.raises(TimeoutError):
        ks.fetch_month(2027, 4, sleep=slept.append)
    assert slept == [ks.RETRY_SLEEP_SEC]


def test_모양이_다른_응답은_다시_묻지_않고_예외입니다(monkeypatch):
    calls = []

    def urlopen(req, timeout=None):
        calls.append(1)
        return Resp(json.dumps({"success": True, "result": {}}).encode())
    monkeypatch.setattr(ks.urllib.request, "urlopen", urlopen)
    with pytest.raises(ValueError):
        ks.fetch_month(2027, 4, sleep=lambda s: None)
    assert calls == [1]


def test_한_달_치_일정을_묻습니다(monkeypatch):
    seen = []

    def urlopen(req, timeout=None):
        seen.append(req.full_url)
        return Resp(json.dumps({"result": {"games": [game("2027-02-27", "kbo_e")]}}).encode())
    monkeypatch.setattr(ks.urllib.request, "urlopen", urlopen)
    assert ks.fetch_month(2027, 2) == [game("2027-02-27", "kbo_e")]
    assert "fromDate=2027-02-01" in seen[0] and "toDate=2027-02-28" in seen[0]
    assert "roundCode" in seen[0] and "categoryId=kbo" in seen[0]
    ks.fetch_month(2026, 12)
    assert "toDate=2026-12-31" in seen[1]
