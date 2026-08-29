# -*- coding: utf-8 -*-
"""파크팩터 계열이 정규시즌만 보게 강제합니다.

## 무엇이 틀렸었나

세 스크립트가 제각각이었습니다.

    build_re24_run_values.py    game_date 로만 걸러 포스트시즌이 섞임
    compute_self_park_factors.py  substr(gameID,1,4) 로 걸러 6666 이 빠짐
    build_wrc_plus.py           위와 같음

`substr(gameID,1,4)` 는 정규시즌 경기 ID 가 날짜로 시작한다는 데
기댑니다. 포스트시즌은 그 자리에 시리즈 코드가 들어갑니다.

    33331013LGWO02016   3333 = 준플레이오프
    66661031KTSS02021   6666 = 순위결정전, **정규시즌입니다**

그래서 포스트시즌은 우연히 걸러졌지만 순위결정전까지 함께 버려졌고,
RE24 는 반대로 포스트시즌을 그대로 넣고 있었습니다. 실측하면 이랬습니다.

    RE24        2016 -1,688행  2017 -1,056행   (포스트시즌이 섞여 있었음)
    파크팩터    2021   +267행  2024   +277행   (순위결정전이 빠져 있었음)

## 지금 기준

`games.game_type` 하나만 봅니다. 그 값은
`data_collection/game_type.py` 가 정하고, 시즌은 `game_date` 에서
뽑습니다.

2008~2014 를 되채우면 포스트시즌 103경기가 더 들어옵니다. 그때 이
기준이 없으면 오염이 열 배가 됩니다.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "park_factors" / "build_re24_run_values.py",
    ROOT / "park_factors" / "build_wrc_plus.py",
    ROOT / "park_factors" / "compute_self_park_factors.py",
]


def body(path):
    """주석을 뺀 본문입니다. 주석 속 설명에 걸리지 않게 합니다."""
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0]
        out.append(s)
    return "\n".join(out)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_정규시즌만_읽습니다(path):
    src = body(path)
    assert "play_by_play" in src, "%s 가 PBP 를 안 읽습니다" % path.name
    assert "game_type" in src, (
        "%s 가 game_type 을 안 봅니다. 포스트시즌 타석이 정규시즌 지표에 "
        "섞입니다." % path.name)
    assert "'정규시즌'" in src, (
        "%s 가 정규시즌으로 거르지 않습니다." % path.name)


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_gameID_앞자리로_시즌을_정하지_않습니다(path):
    """`substr(gameID,1,4)` 는 포스트시즌에서 연도가 아닙니다.

    쓰면 그 경기가 '3333' 시즌이 되어 조용히 사라집니다. 시즌은
    `game_date` 에서 뽑아야 합니다.
    """
    src = body(path)
    bad = re.findall(r"substr\(\s*\w*\.?gameID\s*,\s*1\s*,\s*4\s*\)", src)
    assert not bad, (
        "%s 에 substr(gameID,1,4) 가 %d곳 남아 있습니다: %s\n"
        "시즌은 game_date 로 정하십시오." % (path.name, len(bad), bad))


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: p.name)
def test_games_와_조인합니다(path):
    src = body(path)
    joined = re.search(r"JOIN\s+games\s+\w*\s*ON", src, re.I)
    assert joined, (
        "%s 가 games 와 조인하지 않습니다. game_type 을 볼 방법이 "
        "없습니다." % path.name)


# --- 시즌 범위는 2008년부터입니다 -----------------------------------
#
# 2008~2014 PBP 를 되채우기 전에는 2015년부터만 계산할 수 있었습니다.
# 2026-08-29 에 3,870경기·120만 행이 모두 들어와 이제 2008년까지
# 볼 수 있습니다.
#
# ## 파크팩터가 더 맞아집니다
#
# `compute_self_park_factors.py` 는 3년 창으로 계산합니다. 앞이 없으면
# 뒤로 채우는데, 2015년에는 앞이 아예 없어서 **미래 두 해**로 채우고
# 있었습니다.
#
#     2015   [2015, 2016, 2017]   <- 미래를 봅니다
#     2016   [2015, 2016, 2017]
#     2017   [2015, 2016, 2017]
#
# 되채운 뒤에는 이렇게 됩니다.
#
#     2015   [2013, 2014, 2015]
#     2016   [2014, 2015, 2016]
#     2017   [2015, 2016, 2017]   <- 그대로
#
# 2015·2016 수치가 바뀝니다. 그 해 파크팩터를 그 해 이전 자료로
# 계산하게 되므로 방법론이 나아지는 쪽입니다.

YEAR_SOURCES = [
    ROOT / "park_factors" / "compute_self_park_factors.py",
    ROOT / "park_factors" / "build_wrc_plus.py",
    ROOT / "park_factors" / "build_re24_run_values.py",
]


@pytest.mark.parametrize("path", YEAR_SOURCES, ids=lambda p: p.name)
def test_시즌_범위가_2008년부터입니다(path):
    src = path.read_text(encoding="utf-8")
    # 숫자를 그대로 쓰든 상수로 빼든 시작 해가 2008 이면 됩니다.
    ok = "range(2008," in src or "FIRST_SEASON, LAST_SEASON = 2008" in src
    assert ok, (
        "%s 가 아직 2015년부터만 봅니다. 2008~2014 PBP 가 들어와 있습니다."
        % path.name)


@pytest.mark.parametrize("path", YEAR_SOURCES, ids=lambda p: p.name)
def test_2015가_시즌_경계로_남아_있지_않습니다(path):
    # 범위를 넓히면서 한 곳만 고치면 창 계산이 어긋납니다. 실제로
    # window_for 안에 2015 가 따로 박혀 있었습니다.
    src = path.read_text(encoding="utf-8")
    # 주석은 뺍니다. 설명에는 2015 가 나올 수 있습니다.
    code = "\n".join(ln.split("#")[0] for ln in src.splitlines())
    assert "2015 <=" not in code and "<= 2015" not in code, (
        "%s 에 2015 경계가 남아 있습니다." % path.name)
