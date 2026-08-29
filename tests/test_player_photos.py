# -*- coding: utf-8 -*-
"""선수 사진 주소를 최신 연도로 맞춥니다.

## 무슨 일이 있었나

`players.image_url` 은 KBO 이미지 주소를 통째로 담습니다. 그 주소에
**연도 폴더**가 들어 있습니다.

    https://.../KBO_IMAGE/person/middle/2025/66606.jpg
                                        ^^^^

이 값이 한 번 적재된 뒤로 갱신되지 않았습니다. 1,749명 중 625명이
2025년 주소입니다. 그래서 겨울에 이적한 선수는 **전 소속팀 유니폼
사진**이 나옵니다. 최원준(66606)이 KT 로 옮겼는데 NC 사진이었습니다.

같은 선수의 2026년 사진은 이미 올라와 있었습니다.

    2026:200  2025:200  2024:200

## 어떻게 고치나

현재 시즌 주소부터 찔러 보고, 있으면 그 주소로 바꿉니다. 없으면 그
선수가 마지막으로 기록을 남긴 시즌을 봅니다. 은퇴 선수는 그 해 사진이
마지막입니다.

**선수 한 명에 요청 두 번을 넘기지 않습니다.** 1,749명에게 2008년까지
훑게 하면 최악 3만 번이 됩니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from photo_url import photo_url, probe_years, year_of  # noqa: E402


class TestPhotoUrl:
    def test_주소를_만듭니다(self):
        assert photo_url(66606, 2026) == (
            'https://6ptotvmi5753.edge.naverncp.com'
            '/KBO_IMAGE/person/middle/2026/66606.jpg')

    def test_문자열_아이디도_받습니다(self):
        assert photo_url('66606', 2026).endswith('/2026/66606.jpg')


class TestYearOf:
    def test_주소에서_연도를_읽습니다(self):
        assert year_of(photo_url(1, 2025)) == 2025

    def test_모양이_다르면_None_입니다(self):
        assert year_of('https://example.com/a.jpg') is None
        assert year_of(None) is None
        assert year_of('') is None


class TestProbeYears:
    def test_현재_시즌부터_봅니다(self):
        assert probe_years(2026, None, None) == [2026]

    def test_마지막_기록_시즌을_뒤에_둡니다(self):
        assert probe_years(2026, 2019, None) == [2026, 2019]

    def test_이미_현재_시즌_주소면_찌를_것이_없습니다(self):
        # 아무것도 안 하고 넘어갑니다. 요청을 아끼는 것이 핵심입니다.
        url = photo_url(1, 2026)
        assert probe_years(2026, 2024, url) == []

    def test_옛_주소면_현재_시즌을_먼저_봅니다(self):
        url = photo_url(1, 2025)
        assert probe_years(2026, 2025, url) == [2026]

    def test_마지막_시즌이_현재와_같으면_한_번만_봅니다(self):
        assert probe_years(2026, 2026, None) == [2026]

    def test_요청은_두_번을_넘지_않습니다(self):
        for last in [None, 1982, 2008, 2025, 2026, 2030]:
            assert len(probe_years(2026, last, None)) <= 2

    def test_마지막_시즌이_미래면_무시합니다(self):
        # 자료가 어긋난 경우입니다. 없는 연도를 찌를 이유가 없습니다.
        assert probe_years(2026, 2030, None) == [2026]
