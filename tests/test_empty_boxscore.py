# -*- coding: utf-8 -*-
"""박스스코어가 빈 옛 경기를 버리지 않습니다.

## 무슨 일이 있었나

2008 플레이오프·한국시리즈 7경기가 이 오류로 통째로 버려졌습니다.

    AttributeError: 'DataFrame' object has no attribute 'pcode'

네이버 record API 의 `battersBoxscore` 가 비어 있는 경기가 있습니다.
`statusCode` 가 `ENDED` 인 옛 포스트시즌에서 나옵니다.

    55551016SSOB0 (ENDED)   batters away=0  home=0    <- 빈 표
    55551021OBSS0 (RESULT)  batters away=10 home=13

빈 리스트로 `pd.DataFrame([])` 를 만들면 **컬럼이 하나도 없는** 표가
됩니다. 다음 줄에서 `ap.pcode` 를 읽다 터집니다.

## 왜 버릴 일이 아닌가

없는 것은 타순별 집계값(타수·안타·타점)뿐입니다. 투구 하나하나는
relay 에 그대로 있습니다. 같은 경기의 relay 를 보면 타자 12명,
투수 5명이 멀쩡합니다. 집계값은 PBP 로 다시 계산할 수 있으니 표를
컬럼만 갖춰 비워 두고 넘어가면 됩니다.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler"))

from download import BOXSCORE_COLUMNS, boxscore_frame  # noqa: E402


SAMPLE = [
    {'name': '이종욱', 'pos': '중', 'pcode': '76290', 'ab': 4, 'run': 1,
     'hit': 2, 'rbi': 0, 'hr': 0, 'bb': 1, 'k': 0},
    {'name': '고영민', 'pos': '二', 'pcode': '78168', 'ab': 3, 'run': 0,
     'hit': 1, 'rbi': 1, 'hr': 0, 'bb': 0, 'k': 1},
]


class TestBoxscoreFrame:
    def test_값이_있으면_그대로_담깁니다(self):
        df = boxscore_frame(SAMPLE)
        assert len(df) == 2
        assert list(df.name) == ['이종욱', '고영민']
        assert list(df.pcode) == [76290, 78168]
        assert list(df.hit) == [2, 1]

    def test_비어도_컬럼은_남습니다(self):
        # 이것이 핵심입니다. 예전에는 컬럼이 없어 .pcode 가 터졌습니다.
        df = boxscore_frame([])
        assert len(df) == 0
        for col in BOXSCORE_COLUMNS:
            assert col in df.columns
        df.pcode  # AttributeError 가 나면 안 됩니다

    def test_None_도_빈_표로_받습니다(self):
        # record API 가 키 자체를 안 주는 경우입니다.
        df = boxscore_frame(None)
        assert len(df) == 0
        assert 'pcode' in df.columns

    def test_빈_표를_라인업과_병합할_수_있습니다(self):
        # 실제로 하는 일입니다. dtype 이 어긋나면 여기서 터집니다.
        lineup = pd.DataFrame({
            'pcode': [76290, 78168, 79192],
            'name': ['이종욱', '고영민', '김현수'],
        })
        merged = pd.merge(lineup, boxscore_frame([]), on='pcode', how='outer')
        assert len(merged) == 3
        # 집계값은 비고, 이름은 라인업 쪽이 살아 있어야 합니다.
        assert merged.hit.isnull().all()
        assert set(merged.name_x) == {'이종욱', '고영민', '김현수'}

    def test_값이_있는_표도_병합됩니다(self):
        lineup = pd.DataFrame({
            'pcode': [76290, 78168],
            'name': ['이종욱', '고영민'],
        })
        merged = pd.merge(lineup, boxscore_frame(SAMPLE), on='pcode', how='outer')
        assert len(merged) == 2
        assert list(merged.sort_values('pcode').hit) == [2, 1]


class TestStartPosition:
    """선발 포지션 보정입니다.

    `pos` 는 박스스코어의 '경기 종료 시점' 포지션, `posName` 은 라인업
    메타의 '경기 시작 시점' 포지션입니다. 선발로 나온 선수는 시작 시점
    포지션이 맞아서 `pos` 로 덮어씁니다.

    문제는 박스스코어가 통째로 빈 경기였습니다. `pos` 가 전부 NaN 이라
    `pos_dict.get(NaN)` 이 None 을 돌려주고, **posName 이 전부
    지워졌습니다.** 파싱이 '포수' 를 못 찾아 KeyError 로 경기가
    버려졌습니다. 2008 플레이오프 4경기, 한국시리즈 3경기입니다.
    """

    POS_DICT = {'중': '중견수', '좌': '좌익수', '우': '우익수',
                '유': '유격수', '포': '포수', '지': '지명타자',
                '一': '1루수', '二': '2루수', '三': '3루수'}

    def test_선발은_시작_포지션으로_바뀝니다(self):
        from download import start_position
        df = pd.DataFrame({'pos': ['포', '중'],
                           'posName': ['1루수', '우익수']})
        got = list(start_position(df, self.POS_DICT))
        assert got == ['포수', '중견수']

    def test_교체는_메타_포지션을_지킵니다(self):
        from download import start_position
        df = pd.DataFrame({'pos': ['교'], 'posName': ['대타']})
        assert list(start_position(df, self.POS_DICT)) == ['대타']

    def test_박스스코어가_비면_메타를_지킵니다(self):
        # 핵심입니다. 예전에는 전부 None 이 됐습니다.
        from download import start_position
        df = pd.DataFrame({'pos': [None, None, None],
                           'posName': ['포수', '중견수', '유격수']})
        got = list(start_position(df, self.POS_DICT))
        assert got == ['포수', '중견수', '유격수']

    def test_일부만_비어도_각각_처리합니다(self):
        from download import start_position
        df = pd.DataFrame({'pos': ['포', None, '교'],
                           'posName': ['1루수', '중견수', '대타']})
        got = list(start_position(df, self.POS_DICT))
        assert got == ['포수', '중견수', '대타']
