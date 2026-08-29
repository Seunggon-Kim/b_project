# -*- coding: utf-8 -*-
"""KBO 팀 순위 수집입니다.

## 왜 필요한가

`games` 표는 2008년부터입니다. 그래서 팀 기록실의 시즌별 표에서
1982~2007 승패·순위가 통째로 빕니다. 공식 기록(타율·ERA)은 1982년부터
있는데 순위만 없어 표가 반쪽이 됩니다.

KBO 기록실이 1982~2026 45시즌을 줍니다.

    Record/TeamRank/TeamRank.aspx  ddlYear 로 시즌 선택

## 양대리그를 놓치면 안 됩니다

1999·2000 은 매직리그·드림리그로 나뉘어 **표가 둘**입니다. 한 표만
읽으면 절반이 조용히 사라집니다. 실제로 첫 시도에서 1999가 4행만
나왔습니다(8팀인데).

    표0   롯데 75-52-5   <- 매직리그
    표1   한화 72-58-2   <- 드림리그

표를 모두 읽습니다. 리그가 하나인 해는 표도 하나입니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from team_ranks import parse_ranks, to_rows  # noqa: E402

HEADER = ('<tr><th>순위</th><th>팀명</th><th>경기</th><th>승</th><th>패</th>'
          '<th>무</th><th>승률</th><th>게임차</th><th>최근10경기</th>'
          '<th>연속</th><th>홈</th><th>방문</th></tr>')


def team_table(rows):
    body = "".join(
        "<tr>%s</tr>" % "".join("<td>%s</td>" % c for c in r) for r in rows)
    return ('<table summary="순위, 팀명" class="tData">%s%s</table>'
            % (HEADER, body))


ONE_LEAGUE = team_table([
    ['1', 'OB', '80', '56', '24', '0', '0.700', '0', '7승0무3패', '2패', '', ''],
    ['2', '삼성', '80', '54', '26', '0', '0.675', '2', '', '', '', ''],
])

TWO_LEAGUE = (
    '<h6>매직리그</h6>'
    + team_table([['1', '롯데', '132', '75', '52', '5', '0.591', '0',
                   '', '', '', '']])
    + '<h6>드림리그</h6>'
    + team_table([['1', '한화', '132', '72', '58', '2', '0.554', '0',
                   '', '', '', '']])
    + '<h6>팀간 승패표</h6>'
    # 세 번째는 팀간 상대전적 표입니다. 순위표가 아닙니다.
    + ('<table summary="팀간" class="tData">'
       '<tr><th>팀명</th><th>한화</th></tr>'
       '<tr><td>한화</td><td>7-10-1</td></tr></table>'))


class TestParseRanks:
    def test_한_리그를_읽습니다(self):
        got = parse_ranks(ONE_LEAGUE)
        assert len(got) == 1                 # 표 하나
        name, rows = got[0]
        assert len(rows) == 2                # 두 팀
        assert rows[0]['team_name'] == 'OB'
        assert rows[0]['rank'] == 1
        assert rows[0]['wins'] == 56
        assert rows[0]['losses'] == 24
        assert rows[0]['draws'] == 0
        assert rows[0]['pct'] == '0.700'

    def test_양대리그는_표가_둘입니다(self):
        got = parse_ranks(TWO_LEAGUE)
        assert len(got) == 2
        assert got[0][1][0]['team_name'] == '롯데'
        assert got[1][1][0]['team_name'] == '한화'

    def test_리그_이름을_표_앞에서_읽습니다(self):
        # KBO 는 표 바로 앞에 제목을 둡니다. 그것이 리그 이름입니다.
        got = parse_ranks(TWO_LEAGUE)
        assert got[0][0] == '매직리그'
        assert got[1][0] == '드림리그'

    def test_리그가_하나면_이름이_없습니다(self):
        got = parse_ranks(ONE_LEAGUE)
        assert got[0][0] is None

    def test_상대전적_표는_버립니다(self):
        # 첫 칸이 숫자가 아니면 순위표가 아닙니다.
        got = parse_ranks(TWO_LEAGUE)
        assert all(r['rank'] for _, rows in got for r in rows)

    def test_표가_없으면_빈_목록입니다(self):
        assert parse_ranks('<html></html>') == []


class TestToRows:
    NAMES = {('OB', 1982): 'OB', ('SS', 1982): 'SS'}

    def test_리그가_하나면_단일로_둡니다(self):
        # 빈 문자열은 안 됩니다. sql_literal 이 빈 값을 NULL 로 바꾸는데
        # league 는 PK 라 NOT NULL 입니다. 실제로 적재가 여기서 실패했습니다.
        tables = parse_ranks(ONE_LEAGUE)
        rows = to_rows(tables, 1982, {'OB': 'OB', '삼성': 'SS'})
        assert len(rows) == 2
        assert rows[0]['league'] == '단일'
        assert rows[0]['franchise_id'] == 'OB'
        assert rows[0]['season'] == 1982

    def test_양대리그는_리그_이름을_붙입니다(self):
        tables = parse_ranks(TWO_LEAGUE)
        rows = to_rows(tables, 1999, {'롯데': 'LT', '한화': 'HH'})
        assert {r['league'] for r in rows} == {'매직리그', '드림리그'}
        assert len(rows) == 2

    def test_모르는_팀은_버리지_않고_남깁니다(self):
        # franchise 를 못 붙여도 이름과 성적은 살립니다. 나중에
        # team_seasons 가 채워지면 이어집니다.
        tables = parse_ranks(ONE_LEAGUE)
        rows = to_rows(tables, 1982, {})
        assert len(rows) == 2
        assert rows[0]['franchise_id'] is None
        assert rows[0]['team_name'] == 'OB'
