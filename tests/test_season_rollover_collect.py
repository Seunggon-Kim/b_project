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

import futures_records  # noqa: E402
import kbo_season  # noqa: E402
import team_ranks  # noqa: E402


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


# ------------------------------------------------------------ 팀 순위

def test_팀_순위_current_는_기록_시즌을_씁니다():
    src = (ROOT / "data_collection" / "team_ranks.py").read_text(encoding="utf-8")
    main = src.split("def main", 1)[1]
    assert "record_season()" in main
    assert "current_season()" not in main


@pytest.mark.parametrize("today,schedule,want", CASES)
def test_팀_순위가_고르는_시즌(today, schedule, want):
    # 기록실 목록에 2027 이 비시즌에 이미 올라와 있어도 2026 을 다시 받습니다.
    listed = [2025, 2026, 2027] if today.startswith("2027") else [2025, 2026]
    assert team_ranks.pick_current(listed, record(schedule)(today)) == [want]


def rank_rows(season, names):
    fid = {"KIA": "HT", "LG": "LG", "SSG": "SK"}
    return [{"franchise_id": fid.get(n), "season": season, "team_name": n,
             "league": "단일"} for n in names]


def test_팀_순위는_team_seasons_에_없는_줄만_넣습니다(fake_sink):
    rows = rank_rows(2027, ["KIA", "LG", "SSG", "새이름"])
    team_ranks.mysql_write_ranks(fake_sink, rows, fill_team_seasons=True)
    kinds = [c[0] for c in fake_sink.calls]
    assert kinds == ["upsert", "refresh_count", "insert_missing", "refresh_count"]
    _, table, cols, keys, got = fake_sink.calls[2]
    assert (table, cols, keys) == ("team_seasons", ["franchise_id", "season", "team_name"],
                                   ["franchise_id", "season"])
    # 프랜차이즈를 모르는 이름(구단명 변경)은 넣지 않습니다.
    assert got == [{"franchise_id": "HT", "season": 2027, "team_name": "KIA"},
                   {"franchise_id": "LG", "season": 2027, "team_name": "LG"},
                   {"franchise_id": "SK", "season": 2027, "team_name": "SSG"}]


def test_팀_순위_되채우기는_team_seasons_를_건드리지_않습니다(fake_sink):
    team_ranks.mysql_write_ranks(fake_sink, rank_rows(1999, ["LG"]))
    assert [c[0] for c in fake_sink.calls] == ["upsert", "refresh_count"]


def test_팀_순위_current_만_team_seasons_를_채웁니다():
    src = (ROOT / "data_collection" / "team_ranks.py").read_text(encoding="utf-8")
    assert "fill_team_seasons=args.current" in src


# ------------------------------------------------------------ 퓨처스 기록

@pytest.mark.parametrize("listed,year,want", [
    ([2024, 2025, 2026], 2026, 2026),        # 오늘
    ([2024, 2025, 2026], 2027, 2026),        # 2027 이 목록에 아직 없음
    ([2025, 2026, 2027], 2026, 2026),        # 목록엔 있지만 1군 개막 전
    ([2025, 2026, 2027], 2027, 2027),        # 개막 뒤
])
def test_퓨처스_current_가_고르는_시즌(listed, year, want):
    assert futures_records.current_pick(listed, year) == want


@pytest.mark.parametrize("today,schedule,want", CASES)
def test_퓨처스_current_날짜별(today, schedule, want):
    listed = [2025, 2026, 2027] if today == "2027-04-15" else [2025, 2026]
    assert futures_records.current_pick(listed, record(schedule)(today)) == want


def test_roster_퓨처스는_시즌을_박지_않습니다():
    wf = (ROOT / ".github" / "workflows" / "roster.yml").read_text(encoding="utf-8")
    assert "futures_records.py --current" in wf
    assert not re.search(r"futures_records\.py --season \d{4}", wf)


def test_워크플로에_시즌을_박지_않습니다():
    # 예전에는 roster.yml 이 `--season 2026` 을, daily.yml 이 `date +%Y` 를 썼습니다.
    for name in ("daily.yml", "roster.yml", "weekly.yml", "monthly.yml"):
        wf = (ROOT / ".github" / "workflows" / name).read_text(encoding="utf-8")
        runs = "\n".join(line for line in wf.splitlines() if not line.strip().startswith("#"))
        assert not re.search(r"--(season|year|from|to) 20\d\d", runs), name
