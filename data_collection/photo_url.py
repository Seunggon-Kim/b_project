# -*- coding: utf-8 -*-
"""선수 사진 주소 규칙입니다.

KBO 이미지 주소에는 **연도 폴더**가 들어 있습니다.

    https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/2026/66606.jpg
                                                                  ^^^^

`players.image_url` 은 이 주소를 통째로 담습니다. 한 번 적재된 뒤로
갱신되지 않아서 1,749명 중 625명이 2025년 주소였습니다. 겨울에 이적한
선수는 **전 소속팀 유니폼 사진**이 나옵니다. 최원준(66606)이 KT 로
옮겼는데 NC 사진이었습니다. 그 선수의 2026년 사진은 이미 올라와
있었는데도 그랬습니다.

규칙만 여기 둡니다. 실제 갱신은 `heal_player_photos.py` 가 합니다.
규칙과 실행을 나눠야 규칙에 테스트를 붙일 수 있습니다.
"""
import re

BASE = ('https://6ptotvmi5753.edge.naverncp.com'
        '/KBO_IMAGE/person/middle/%d/%s.jpg')

# 주소에서 연도를 뽑는 자리입니다.
YEAR_RE = re.compile(r'/person/middle/(\d{4})/')


def photo_url(player_id, year):
    """그 해 선수 사진 주소입니다."""
    return BASE % (int(year), str(player_id))


def year_of(url):
    """주소에 든 연도입니다. 모양이 다르면 None 입니다."""
    if not url:
        return None
    m = YEAR_RE.search(str(url))
    return int(m.group(1)) if m else None


def probe_years(current_season, last_season, current_url):
    """찔러 볼 연도들입니다. 앞에서부터 시도하고 처음 잡히면 멈춥니다.

    **선수 한 명에 두 번을 넘기지 않습니다.** 1,749명에게 2008년까지
    훑게 하면 최악 3만 번이 됩니다. 현역은 현재 시즌에서 잡히고, 은퇴
    선수는 마지막으로 기록을 남긴 시즌에서 잡힙니다.

    이미 현재 시즌 주소를 들고 있으면 빈 목록입니다. 그 선수는 건드릴
    이유가 없습니다.
    """
    have = year_of(current_url)
    if have == current_season:
        return []

    years = [int(current_season)]
    if last_season:
        last = int(last_season)
        # 미래 시즌은 자료가 어긋난 것입니다. 없는 연도를 찌를 이유가
        # 없습니다.
        #
        # 이미 들고 있는 주소의 연도도 뺍니다. 그 주소는 지금 잘 나오는
        # 값입니다. 현재 시즌 사진이 없으면 그대로 두면 됩니다.
        if last < int(current_season) and last != have:
            years.append(last)
    return years
