# -*- coding: utf-8 -*-
"""주간 파크팩터·wRC+·RE24 계산의 마지막 시즌이 날짜를 따라가는지 봅니다.

예전에는 세 스크립트에 2026 이 박혀 있었습니다(2026-10-05 검토).

    compute_self_park_factors.py   LAST_SEASON = 2026
    build_wrc_plus.py              YEARS = range(2008, 2027)
    build_re24_run_values.py       ALLYEARS = range(2008, 2027), COMPLETE = range(2008, 2026)

그대로면 2027 파크팩터·wRC+·RE24·wOBA 가중치가 영영 안 생깁니다. 이제
마지막 시즌은 data_collection/kbo_season.last_season(한국 날짜의 올해)입니다.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = [
    ROOT / "park_factors" / "compute_self_park_factors.py",
    ROOT / "park_factors" / "build_wrc_plus.py",
    ROOT / "park_factors" / "build_re24_run_values.py",
]


def code(path):
    """주석을 뺀 본문입니다."""
    return "\n".join(ln.split("#", 1)[0] for ln in path.read_text(encoding="utf-8").splitlines())


@pytest.mark.parametrize("path", SCRIPTS, ids=lambda p: p.name)
def test_마지막_시즌을_박지_않습니다(path):
    src = code(path).replace(" ", "")
    for bad in ("range(2008,2027)", "range(2008,2026)", "=2008,2026", "season=2026"):
        assert bad not in src, "%s 에 %s 가 남아 있습니다" % (path.name, bad)
    assert "fromkbo_seasonimportlast_season" in src
    assert "last_season(" in src.split("importlast_season", 1)[1]


def load_re24():
    pytest.importorskip("pandas")
    pytest.importorskip("numpy")
    sys.path.insert(0, str(ROOT / "park_factors"))
    import build_re24_run_values as r
    return r


@pytest.mark.parametrize("today,last,complete_last", [
    ("2026-10-05", 2026, 2025),   # 오늘: 예전(2008..2026, 모음 2008..2025)과 같습니다
    ("2027-02-15", 2027, 2026),   # 비시즌: 2027 은 자료가 없어 'no data' 로 건너뜁니다
    ("2027-04-15", 2027, 2026),   # 개막 뒤: 2027 을 만들고, 모음에는 아직 넣지 않습니다
])
def test_RE24_시즌_범위(today, last, complete_last):
    r = load_re24()
    assert r.all_years(today) == list(range(2008, last + 1))
    assert r.complete_years(today) == list(range(2008, complete_last + 1))


def test_RE24_오늘_범위가_예전과_같습니다():
    r = load_re24()
    assert r.all_years("2026-10-05") == list(range(2008, 2027))
    assert r.complete_years("2026-10-05") == list(range(2008, 2026))
