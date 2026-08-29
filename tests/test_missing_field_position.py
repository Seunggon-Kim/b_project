# -*- coding: utf-8 -*-
"""수비 위치 하나가 비어도 경기를 버리지 않습니다.

## 무슨 일이 있었나

2008 플레이오프 2경기가 이 오류로 통째로 버려졌습니다.

    KeyError: '3루수'
      at save_row['pos_5'] = self.fields[self.top_bot]['3루수'].get('name')

네이버 라인업 메타에 타순 하나가 빠진 경기가 있습니다. 55551019OBSS0
의 홈팀 9번 타순은 교체 선수(seqno 2)만 있고 선발(seqno 1)이 없습니다.

    order=8 seq=1 pos=좌익수 name=강봉규
    order=9 seq=2 pos=유격수 name=김재걸    <- seq=1 이 없습니다

그래서 선발 아홉 자리에 유격수가 둘이 되고 3루수가 아무도 없습니다.
`fields['3루수']` 에서 KeyError 가 나 경기 511행이 전부 사라졌습니다.

## 왜 버릴 일이 아닌가

빠진 것은 수비수 이름 한 칸입니다. 투구 하나하나, 타석 결과, 주자
상황은 모두 멀쩡합니다. 한 칸을 비우고 나머지를 살리는 편이 낫습니다.
원천이 불완전한 것이라 우리가 채울 방법도 없습니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler"))

from game_parse import FIELD_POSITIONS, field_player  # noqa: E402


class TestFieldPlayer:
    def test_있으면_그대로_돌려줍니다(self):
        side = {'포수': {'name': '진갑용', 'code': 60123}}
        assert field_player(side, '포수').get('name') == '진갑용'
        assert field_player(side, '포수').get('code') == 60123

    def test_없으면_빈_값입니다(self):
        # KeyError 가 나면 안 됩니다.
        assert field_player({}, '3루수').get('name') is None
        assert field_player({}, '3루수').get('code') is None

    def test_None_이_들어_있어도_빈_값입니다(self):
        assert field_player({'3루수': None}, '3루수').get('name') is None

    def test_아홉_수비_위치가_모두_정의돼_있습니다(self):
        assert FIELD_POSITIONS == ['투수', '포수', '1루수', '2루수', '3루수',
                                   '유격수', '좌익수', '중견수', '우익수']


class TestChangeCreatesSlot:
    """교체 선수가 빈 자리에 들어올 수 있어야 합니다.

    라인업 메타에 3루수가 없던 경기에서, 9회초 교체로 3루수가 처음
    등장하자 `fields[top_bot]['3루수']['code'] = ...` 가 KeyError 를
    냈습니다. 자리가 없으면 만들어 주면 됩니다.
    """

    def _gs(self):
        from game_parse import game_status
        gs = game_status()
        gs.fields = [{}, {}]
        gs.top_bot = 0
        gs.lineups = [[], []]
        # 대타 처리가 마지막 주자를 바꿉니다. 자리를 하나 둡니다.
        gs.runner_bases = [['이종욱', 76290, 0, [None]]]
        return gs

    def test_없던_자리도_교체로_만들어집니다(self):
        gs = self._gs()
        gs.handle_change_stack(
            [('3루수', '3루수', None, '조동찬', 61234, '우투우타')])
        assert gs.fields[0]['3루수']['name'] == '조동찬'
        assert gs.fields[0]['3루수']['code'] == 61234

    def test_있던_자리는_덮어씁니다(self):
        gs = self._gs()
        gs.fields[0]['포수'] = {'name': '진갑용', 'code': 1, 'hitType': None}
        gs.handle_change_stack(
            [('포수', '포수', None, '현재윤', 2, '우투우타')])
        assert gs.fields[0]['포수']['name'] == '현재윤'
        assert gs.fields[0]['포수']['code'] == 2

    def test_대타는_수비_자리를_건드리지_않습니다(self):
        gs = self._gs()
        gs.handle_change_stack(
            [('좌익수', '대타', None, '이성열', 3, '좌투좌타')])
        assert '대타' not in gs.fields[0]
        assert gs.fields[0] == {}
