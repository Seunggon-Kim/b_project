# -*- coding: utf-8 -*-
"""2015년까지의 포스트시즌 gameId 를 다루는 규칙입니다.

## 왜 필요한가

네이버 gameId 는 형식이 둘입니다.

    20080418SKOB0        정규시즌          앞 4자리가 연도
    33331013LGWO02016    2016~ 포스트시즌  뒤 4자리가 연도 (17자)
    33331008SSLT0        ~2015 포스트시즌  **연도가 없습니다** (13자)

크롤러는 연도를 `gid[-4:]` 로만 얻었습니다. 13자에서는 'SLT0' 이 나와
`int()` 가 터지고, 그 예외를 `continue` 로 삼켜 **2015년까지의 모든
포스트시즌이 조용히 버려졌습니다.** 2008~2014 에서 103경기입니다.

`save_game` 도 같은 가정을 해서 `SLT01008SSLT0.csv` 같은 파일명을
만들었습니다.

13자에서 연도를 아는 방법은 하나뿐입니다. 캘린더를 돌 때 이미 알고
있던 연도를 같이 들고 오는 것입니다.
"""
import datetime
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler"))

from gameid import game_id_year, save_stem  # noqa: E402


class TestGameIdYear:
    def test_정규시즌은_앞_네_자리(self):
        assert game_id_year('20080418SKOB0') == 2008
        assert game_id_year('20261231LGOB0') == 2026

    def test_2016년_이후_포스트시즌은_뒤_네_자리(self):
        assert game_id_year('33331013LGWO02016') == 2016
        assert game_id_year('44441002KTOB02024') == 2024
        assert game_id_year('77771026OBSK02020') == 2020

    def test_2015년_이전_포스트시즌은_넘겨받은_연도를_씁니다(self):
        assert game_id_year('33331008SSLT0', 2008) == 2008
        assert game_id_year('55551021OBSS0', 2008) == 2008
        assert game_id_year('77771026OBSK0', 2008) == 2008
        assert game_id_year('33331010WOOB0', 2015) == 2015

    def test_연도를_안_넘기면_None_입니다(self):
        # 버리는 것이 아니라 '모른다' 입니다. 부르는 쪽이 판단합니다.
        assert game_id_year('33331008SSLT0') is None

    def test_뒤_네_자리가_연도여도_넘겨받은_값보다_우선합니다(self):
        # gameId 안의 값이 언제나 정본입니다.
        assert game_id_year('33331013LGWO02016', 2099) == 2016

    def test_올스타는_None_입니다(self):
        # 9999 는 올스타라 games 에 없습니다. 넣으면 FK 가 깨집니다.
        assert game_id_year('99991012ABCD0', 2011) is None
        assert game_id_year('99991012ABCD02019', 2019) is None

    def test_순위결정전은_정규시즌으로_받습니다(self):
        # 6666 은 순위결정전입니다. 포스트시즌이 아니라 정규시즌입니다.
        assert game_id_year('66661001SKKT02024') == 2024
        assert game_id_year('66661002LTSS0', 2013) == 2013


class TestSaveStem:
    """저장 파일명입니다. CSV 안의 gameID 와 **다릅니다.**"""

    def test_정규시즌은_gameId_그대로(self):
        assert save_stem('20080418SKOB0', 2008) == '20080418SKOB0'

    def test_2016년_이후_포스트시즌은_기존_규칙을_지킵니다(self):
        # 이미 저장된 파일이 이 이름입니다. 바꾸면 전부 다시 받습니다.
        assert save_stem('33331013LGWO02016', 2016) == '20161013LGWO02016'

    def test_2015년_이전_포스트시즌은_연도를_앞에_붙입니다(self):
        assert save_stem('33331008SSLT0', 2008) == '20081008SSLT0'
        assert save_stem('55551021OBSS0', 2008) == '20081021OBSS0'

    def test_파일명_앞_여덟_자리는_늘_경기_날짜입니다(self):
        # shard_backfill 이 f.stem[:8] 로 날짜를 고릅니다.
        for gid, year, ymd in [
            ('20080418SKOB0', 2008, '20080418'),
            ('33331008SSLT0', 2008, '20081008'),
            ('33331013LGWO02016', 2016, '20161013'),
        ]:
            assert save_stem(gid, year)[:8] == ymd


class TestDownloadKeepsOldPostseason:
    """`download_pbp_files` 의 루프가 13자 포스트시즌을 버리지 않아야 합니다."""

    def test_2008년_시월_아이디가_전부_살아남습니다(self):
        # 실제로 버려졌던 값들입니다.
        dropped = []
        for gid in ['20081001LGOB0', '33331008SSLT0', '55551021OBSS0',
                    '77771026OBSK0', '99991012ABCD0']:
            y = game_id_year(gid, 2008)
            if y is None:
                dropped.append(gid)
        # 올스타 하나만 빠져야 합니다.
        assert dropped == ['99991012ABCD0']
