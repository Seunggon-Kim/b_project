# -*- coding: utf-8 -*-
"""수집기가 2027 시즌으로 넘어가는지, 오늘(2026-10-05)은 그대로인지 봅니다.

    2026-10-05  오늘. 예전과 같은 시즌을 받아야 합니다(2026).
    2027-02-15  비시즌. 기록실에 2027 이 없거나 비어 있습니다. 2026 을 받습니다.
    2027-04-15  개막 뒤. 2027 을 받습니다.

네이버 일정은 가짜로 넣습니다(kbo_season.record_season 의 fetch).
"""
import datetime
import importlib.util
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import kbo_season  # noqa: E402


def load_official():
    spec = importlib.util.spec_from_file_location(
        "official_stats_http", ROOT / "data_collection" / "official_stats_http.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def g(day, rc, status="RESULT"):
    return {"gameDate": day, "roundCode": rc, "statusCode": status}


SCHEDULE = {
    (2026, 3): [g("2026-03-24", "kbo_e"), g("2026-03-28", "kbo_r")],
    (2027, 3): [g("2027-03-24", "kbo_e"), g("2027-03-27", "kbo_r", "BEFORE")],
}
# 개막(03-27) 뒤의 일정입니다.
SCHEDULE_IN = dict(SCHEDULE)
SCHEDULE_IN[(2027, 3)] = [g("2027-03-24", "kbo_e"), g("2027-03-27", "kbo_r")]

CASES = [("2026-10-05", SCHEDULE, 2026), ("2027-02-15", SCHEDULE, 2026),
         ("2027-04-15", SCHEDULE_IN, 2027)]


def record(schedule):
    return lambda today: kbo_season.record_season(
        today, fetch=lambda y, m: schedule.get((y, m), []))


# ------------------------------------------------------------ 공식 기록

@pytest.mark.parametrize("today,schedule,want", CASES)
def test_공식_기록의_기본_시즌(today, schedule, want):
    m = load_official()
    assert m.default_year(today, record=record(schedule)) == want


def test_공식_기록은_받은_시즌을_다음_단계에_알립니다(tmp_path):
    m = load_official()
    out = tmp_path / "out.txt"
    m.announce_season(2026, env={"GITHUB_OUTPUT": str(out)})
    assert out.read_text(encoding="utf-8") == "season=2026\n"
    # Actions 밖에서는 아무것도 쓰지 않습니다.
    m.announce_season(2026, env={})


def test_daily_적재는_수집이_알린_시즌의_CSV_를_읽습니다():
    wf = (ROOT / ".github" / "workflows" / "daily.yml").read_text(encoding="utf-8")
    runs = "\n".join(line for line in wf.splitlines() if not line.strip().startswith("#"))
    assert "date +%Y" not in runs
    for kind, step in (("batter", "scrape_batter"), ("pitcher", "scrape_pitcher")):
        assert ("%s_stats_${{ steps.%s.outputs.season }}.csv" % (kind, step)) in wf
        assert re.search(r"id: %s\s" % step, wf)
