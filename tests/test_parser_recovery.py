# -*- coding: utf-8 -*-
"""파서가 중계 구멍을 만나도 죽지 않는지 확인합니다.

네이버 중계에 seqno 가 통째로 빠지는 구간이 있습니다. 2008-05-03
두산-LG 전은 114~117 이 없고 그 자리에 '김현수 볼넷' 과 '3번타자
고영민' 이 있어야 합니다. 타석 시작 없이 결과가 나오니 주자 추적이
깨집니다.

전에는 그 지점에서 죽었고, 죽기 전까지만 저장돼 20점짜리 경기가 2회
6점으로 남았습니다. 2008~2013 에 105경기가 그렇게 잘렸습니다.
"""
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'crawler'))

from game_parse import game_status


def make():
    gs = game_status()
    gs.recovered = 0
    gs.recover_reasons = []
    gs.inn = 2
    gs.top_bot = 0
    return gs


def test_recover_counts_and_continues():
    gs = make()
    assert gs._recover('구멍') is True
    assert gs.recovered == 1
    assert '구멍' in gs.recover_reasons[0]


def test_recover_records_the_inning():
    gs = make()
    gs.inn, gs.top_bot = 7, 1
    gs._recover('주자를 찾을 수 없음')
    assert '7회 말' in gs.recover_reasons[0]


def test_recover_gives_up_past_the_limit():
    """너무 많이 어긋나면 그 경기는 믿을 수 없으니 버립니다."""
    gs = make()
    for _ in range(game_status.MAX_RECOVER):
        assert gs._recover('구멍') is True
    assert gs._recover('구멍') is False


def test_limit_is_set():
    # 한 경기에서 열두 번까지는 넘어갑니다. 그보다 많으면 중계 자체가
    # 성한 데가 없다는 뜻입니다.
    assert game_status.MAX_RECOVER == 12
