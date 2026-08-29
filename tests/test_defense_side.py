# -*- coding: utf-8 -*-
"""초/말이 깨진 경기에서도 수비측을 알아냅니다.

## 무슨 일이 있었나

2011년 정규시즌 5경기가 이 오류로 버려졌습니다.

    IndexError: index 0 is out of bounds for axis 0 with size 0
      at self.home_alias = pdf[pdf.homeaway == 'h'].team_name.unique()[0]

네이버 relay 의 `homeOrAway` 가 경기 내내 한 값만 오는 경기가 있습니다.

    20110413WOHT0   102개 반이닝이 전부 '1'
    20110414WOHT0   전부 '0'
    20110419LTHH0   전부 '0'
    20110422SSWO0   전부 '0'
    20110512HHLG0   전부 '0'

이 경기들은 라인업 메타와 박스스코어의 투수가 둘 다 비어 있어서
relay 에서 투수를 되살려야 하는데, 수비측을 `homeOrAway` 로 갈랐습니다.
값이 한쪽뿐이니 한쪽 투수만 모이고 반대쪽은 0명이 되어 라인업을 만들
수 없었습니다.

## 어떻게 알아내나

**타자가 어느 라인업에 있는지로 봅니다.** 원정 타자가 치고 있으면
수비는 홈입니다. 정상 경기 세 개 166타석에서 `homeOrAway` 와 100%
일치했습니다(불일치 0, 판정불가 0).

반이닝 순서로 초/말을 번갈아 매기는 방법도 해 봤는데 30~46% 가
어긋났습니다. `textRelays` 한 항목이 반이닝이 아니기 때문입니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "crawler"))

from download import defense_side  # noqa: E402

AWAY = {'76290', '78168', '79192'}
HOME = {'60123', '61234', '62345'}


class TestDefenseSide:
    def test_원정_타자가_치면_수비는_홈입니다(self):
        assert defense_side('76290', AWAY, HOME, None) == 'h'

    def test_홈_타자가_치면_수비는_원정입니다(self):
        assert defense_side('60123', AWAY, HOME, None) == 'a'

    def test_초_말이_깨져도_타자로_가립니다(self):
        # 이것이 핵심입니다. homeOrAway 가 전부 '1' 이어도 갈립니다.
        assert defense_side('76290', AWAY, HOME, '1') == 'h'
        assert defense_side('60123', AWAY, HOME, '1') == 'a'

    def test_타자를_모르면_초_말로_돌아갑니다(self):
        assert defense_side(None, AWAY, HOME, '0') == 'h'
        assert defense_side(None, AWAY, HOME, '1') == 'a'
        assert defense_side('', AWAY, HOME, '0') == 'h'

    def test_라인업에_없는_타자도_초_말로_돌아갑니다(self):
        # 교체로 들어온 선수가 라인업 메타에 없을 수 있습니다.
        assert defense_side('99999', AWAY, HOME, '0') == 'h'
        assert defense_side('99999', AWAY, HOME, '1') == 'a'

    def test_양쪽에_다_있으면_초_말로_돌아갑니다(self):
        both = {'55555'}
        assert defense_side('55555', both, both, '0') == 'h'

    def test_라인업이_비면_초_말_그대로입니다(self):
        assert defense_side('76290', set(), set(), '0') == 'h'
        assert defense_side('76290', set(), set(), '1') == 'a'

    def test_숫자로_와도_받습니다(self):
        # currentGameState.batter 가 int 로 오는 경우가 있습니다.
        assert defense_side(76290, AWAY, HOME, None) == 'h'
