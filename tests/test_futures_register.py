# -*- coding: utf-8 -*-
"""퓨처스(2군) 등록 명단입니다.

## 왜 필요한가

소속 판정 기준이 화면마다 달랐습니다.

    1군 화면    올 시즌 기록이 있나      -> 방출돼도 기록은 남습니다
    퓨처스 화면 KBO 등번호가 있나        -> 정확하지만 월 1회만 갱신

그래서 타무라(56218)가 한쪽에선 두산, 한쪽에선 무소속이었습니다.

`kbo_roster`(1군 등록 현황)는 매일 받는 좋은 신호인데 **1군만** 담아
2군 선수가 통째로 빠집니다. 여기에 퓨처스 명단을 더하면 구단에 속한
선수 전체가 됩니다.

    명단 = 1군 등록 현황 + 퓨처스 등록 현황
    소속 = 그 명단의 팀. 없으면 무소속.

## 페이지

`Futures/Player/Register.aspx` 는 한 번에 한 팀만 보여 줍니다. 팀은
hidden `hfSearchTeam` 으로 정하고 `__EVENTTARGET` 을
`btnCalendarSelect` 로 줘야 바뀝니다. 드롭다운이 아닙니다.

표는 감독·코치·투수·포수·내야수·외야수 순입니다. **선수 ID 가 링크에
있습니다.** 1군 명단(이름과 등번호만)과 달라 이름으로 짝지을 필요가
없고 동명이인 문제도 없습니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from futures_register import PLAYER_ROLES, parse_team_page  # noqa: E402

PAGE = """
<html><body>
<table><caption>야구단 선수등록명단 표</caption>
  <thead><tr><th>등번호</th><th>감독</th><th>투타유형</th><th>생년월일</th><th>체격</th></tr></thead>
  <tbody><tr><td>71</td>
    <td><a href="/Futures/Player/HitterDetail.aspx?playerId=93626">이대진</a></td>
    <td>우투우타</td><td>1974-06-09</td><td>180cm, 83kg</td></tr></tbody>
</table>
<table>
  <thead><tr><th>등번호</th><th>코치</th><th>투타유형</th><th>생년월일</th><th>체격</th></tr></thead>
  <tbody><tr><td>70</td>
    <td><a href="/Futures/Player/HitterDetail.aspx?playerId=55770">쓰루오카</a></td>
    <td>우투우타</td><td>1977-05-30</td><td>183cm, 87kg</td></tr></tbody>
</table>
<table>
  <thead><tr><th>등번호</th><th>투수</th><th>투타유형</th><th>생년월일</th><th>체격</th></tr></thead>
  <tbody><tr><td>03</td>
    <td><a href="/Futures/Player/PitcherDetail.aspx?playerId=56703">여현승</a></td>
    <td>우투우타</td><td>2006-02-20</td><td>185cm, 95kg</td></tr></tbody>
</table>
<table>
  <thead><tr><th>등번호</th><th>내야수</th><th>투타유형</th><th>생년월일</th><th>체격</th></tr></thead>
  <tbody><tr><td>2</td>
    <td><a href="/Futures/Player/HitterDetail.aspx?playerId=51764">정민규</a></td>
    <td>우투우타</td><td>2003-01-10</td><td>183cm, 101kg</td></tr></tbody>
</table>
</body></html>"""


class TestParseTeamPage:
    def test_선수만_담습니다(self):
        rows = parse_team_page(PAGE, '한화')
        # 감독과 코치는 선수가 아닙니다.
        names = [r['name'] for r in rows]
        assert names == ['여현승', '정민규']

    def test_역할과_등번호를_담습니다(self):
        rows = parse_team_page(PAGE, '한화')
        assert rows[0]['role'] == '투수'
        assert rows[0]['back_number'] == '03'
        assert rows[1]['role'] == '내야수'
        assert rows[1]['back_number'] == '2'

    def test_등번호_00_을_문자열로_둡니다(self):
        # 정수로 바꾸면 '0' 번과 구분이 사라집니다.
        page = PAGE.replace('<td>03</td>', '<td>00</td>')
        assert parse_team_page(page, '한화')[0]['back_number'] == '00'

    def test_선수_ID_를_링크에서_읽습니다(self):
        rows = parse_team_page(PAGE, '한화')
        assert rows[0]['player_id'] == 56703
        assert rows[1]['player_id'] == 51764

    def test_팀과_리그를_붙입니다(self):
        rows = parse_team_page(PAGE, '한화')
        assert all(r['team'] == '한화' for r in rows)
        assert all(r['league'] == '퓨처스' for r in rows)

    def test_선수_ID_가_없는_줄은_버립니다(self):
        # 눌러도 열 수 없고 우리 표와 이을 수도 없습니다.
        page = PAGE.replace(
            '<a href="/Futures/Player/PitcherDetail.aspx?playerId=56703">여현승</a>',
            '여현승')
        assert [r['name'] for r in parse_team_page(page, '한화')] == ['정민규']

    def test_표가_없으면_빈_목록입니다(self):
        assert parse_team_page('<html></html>', '한화') == []

    def test_선수_역할은_넷입니다(self):
        assert PLAYER_ROLES == ('투수', '포수', '내야수', '외야수')
