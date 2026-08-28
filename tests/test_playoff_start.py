# -*- coding: utf-8 -*-
"""경기 종류 판정을 지킵니다.

전에는 `PLAYOFF_START` 라는 날짜 표가 `games_from_pbp.py` 와
`load_year_pbp.py` 두 곳에 복사돼 있었고, 이 테스트는 두 복사본이
어긋나지 않는지만 봤습니다.

이제 판정은 `data_collection/game_type.py` 한 곳에 있습니다. 복사본이
없으니 어긋날 일도 없습니다. 대신 규칙 자체를 지킵니다.

가장 중요한 것은 **`6666` 이 정규시즌** 이라는 점입니다. 생김새가
포스트시즌 코드와 똑같아서, 앞으로 누가 "빠졌네" 하고 넣기 쉽습니다.
넣으면 순위결정전 두 경기가 순위표에서 빠집니다.
"""
import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT / "data_collection"))

from game_type import (  # noqa: E402
    POSTSEASON, POSTSEASON_PREFIXES, REGULAR, classify, classify_game,
    is_skippable, prefix,
)

# 2008~2025 열여덟 시즌을 네이버 roundCode 로 실측한 값입니다.
# (접두어, roundCode, 기대 판정)
MEASURED = [
    ("3333", "kbo_ps_sp", POSTSEASON),      # 준플레이오프
    ("4444", "kbo_ps_wd", POSTSEASON),      # 와일드카드
    ("5555", "kbo_ps_po", POSTSEASON),      # 플레이오프
    ("7777", "kbo_ps_ks", POSTSEASON),      # 한국시리즈
    ("6666", "kbo_p", REGULAR),             # 순위결정전. 정규시즌입니다.
]


@pytest.mark.parametrize("pre,round_code,want", MEASURED)
def test_실측한_시리즈_코드대로_판정합니다(pre, round_code, want):
    gid = pre + "1013LGWO02016"
    assert classify(gid) == want, (
        "%s (%s) 은 %s 이어야 합니다" % (pre, round_code, want))


def test_육육육육은_포스트시즌이_아닙니다():
    """생김새에 속지 마십시오.

    `6666` 은 순위결정전입니다. 2021년 1위 결정전(KT-삼성)과 2024년
    5위 결정전(SSG-KT) 두 경기입니다. 네이버가 `kbo_p` 로 주고 KBO 도
    정규시즌 기록에 넣습니다.
    """
    assert "6666" not in POSTSEASON_PREFIXES
    assert classify("66661031KTSS02021") == REGULAR
    assert classify("66661001SKKT02024") == REGULAR


def test_날짜로_시작하면_정규시즌입니다():
    for gid in ["20260415LGSS0", "20150322HHKT0", "20081026OBSK0"]:
        assert classify(gid) == REGULAR


def test_올스타전은_건너뜁니다():
    assert is_skippable("99990718WEEA0")
    assert not is_skippable("20260415LGSS0")
    assert not is_skippable("77771026OBSK0")


def test_값이_이상해도_죽지_않습니다():
    for bad in [None, "", "20", 12345678, float("nan")]:
        assert classify(bad) == REGULAR
        assert not is_skippable(bad)
    assert prefix(None) == ""
    assert prefix("20") == ""


def test_시범경기는_roundCode_로만_걸러집니다():
    """경기 ID 로는 시범경기를 못 걸러냅니다.

    시범경기도 정규시즌처럼 날짜로 시작합니다(`20130309HHHT0`).
    실제로 시범경기 53건이 정규시즌으로 들어가 2013 이 팀당 128경기가
    아니라 139경기로 보였습니다.
    """
    gid = "20130309HHHT0"
    assert classify(gid) == REGULAR                      # ID 만으로는 못 걸름
    assert classify_game(gid, "kbo_e") is None           # roundCode 면 걸림
    assert classify_game(gid, "kbo_r") == REGULAR


def test_정규시즌_roundCode_가_두_가지입니다():
    """`kbo_p` 만 정규시즌으로 보면 안 됩니다.

    2008~2026 열아홉 시즌을 훑어 보니 기본값은 `kbo_r` 이고 2020 만
    `kbo_p` 였습니다. `kbo_p` 만 통과시키면 정규시즌 경기가 거의 다
    사라집니다.
    """
    for rc in ("kbo_r", "kbo_p"):
        assert classify_game("20260415LGSS0", rc) == REGULAR


def test_모르는_roundCode_는_버리지_않습니다():
    """새 코드가 하나 생겼다고 시즌이 통째로 사라지면 안 됩니다."""
    assert classify_game("20260415LGSS0", "kbo_새로운거") == REGULAR
    assert classify_game("77771026OBSK0", "kbo_새로운거") == POSTSEASON
    assert classify_game("20260415LGSS0", None) == REGULAR
    assert classify_game("20260415LGSS0", "") == REGULAR


@pytest.mark.parametrize("round_code,want", [
    ("kbo_ps_wd", POSTSEASON), ("kbo_ps_sp", POSTSEASON),
    ("kbo_ps_po", POSTSEASON), ("kbo_ps_ks", POSTSEASON),
])
def test_포스트시즌_roundCode(round_code, want):
    # 경기 ID 가 날짜여도 roundCode 가 포스트시즌이면 포스트시즌입니다.
    assert classify_game("20261013LGWO0", round_code) == want


def test_올스타는_roundCode_가_없어도_걸러집니다():
    assert classify_game("99990718WEEA0") is None
    assert classify_game("99990718WEEA0", "kbo_r") is None


def test_날짜_컷오프_표가_되살아나지_않았습니다():
    """`PLAYOFF_START` 를 다시 넣지 마십시오.

    매년 사람이 값을 넣어야 하고, 일정이 나오기 전에는 넣을 수도
    없으며, 실제로 아홉 경기를 정규시즌으로 잘못 넣었습니다.
    """
    for name in ["games_from_pbp.py", "load_year_pbp.py",
                 "daily_games_to_d1.py", "old_games_to_d1.py"]:
        path = ROOT / "data_collection" / name
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    assert not (isinstance(t, ast.Name)
                                and t.id == "PLAYOFF_START"), (
                        "%s 에 PLAYOFF_START 가 되살아났습니다. 판정은 "
                        "game_type.py 한 곳에서 합니다." % name)
