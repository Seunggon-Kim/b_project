# -*- coding: utf-8 -*-
"""프로필 수집 대상 고르기입니다.

## 무슨 일이 있었나

`player_info_scraper.py` 가 **이미 `players` 에 있는 선수를 통째로
건너뛰었습니다.**

    remaining_ids = [pid for pid in all_player_ids if pid not in existing_ids]

그래서 한 번 적재된 선수의 프로필은 그 뒤로 영원히 갱신되지 않습니다.
2026-08-28 monthly 로그를 보면 1,749명 중 **4명**만 처리했습니다.

    [1/4] 선수 ID: 56168
    ...
    크롤링 완료 - 성공: 4명, 실패: 0명

그 결과 이적한 선수의 소속·연봉·경력이 옛 값으로 남습니다. 최원준이
KT 로 옮겼는데 화면에는 연봉 4억에 경력이 `...-KIA-상무-KIA` 였습니다.
사진 주소도 같은 이유로 낡았습니다(별도로 `heal_player_photos.py` 가
맞춥니다).

## 어떻게 고치나

`--refresh` 를 주면 이미 있는 선수도 다시 봅니다. 대상은 올 시즌 기록이
있는 선수 567명이라 30분쯤 걸립니다. monthly 는 한도가 300분이고
저장소가 공개라 Actions 시간이 무료입니다.

기본값은 그대로 둡니다. 손으로 돌릴 때 1,700명을 훑고 싶지 않을 때가
있습니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from player_info_scraper import pick_targets  # noqa: E402

ALL = ['1', '2', '3', '4']
HAVE = {'1', '3'}


class TestPickTargets:
    def test_기본은_없는_선수만_봅니다(self):
        assert pick_targets(ALL, HAVE, refresh=False) == ['2', '4']

    def test_refresh_면_전부_다시_봅니다(self):
        assert pick_targets(ALL, HAVE, refresh=True) == ALL

    def test_순서를_지킵니다(self):
        # 시즌 기록 순서대로 돌아야 중간에 끊겨도 이어 하기 좋습니다.
        assert pick_targets(['9', '8', '7'], set(), refresh=False) == ['9', '8', '7']

    def test_이미_다_있으면_기본은_빈_목록입니다(self):
        assert pick_targets(ALL, set(ALL), refresh=False) == []

    def test_이미_다_있어도_refresh_면_전부입니다(self):
        assert pick_targets(ALL, set(ALL), refresh=True) == ALL

    def test_대상이_없으면_빈_목록입니다(self):
        assert pick_targets([], HAVE, refresh=True) == []
