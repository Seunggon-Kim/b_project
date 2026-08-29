# -*- coding: utf-8 -*-
"""퓨처스 시즌 기록 수집입니다.

## 왜 필요한가

퓨처스 선수 화면에 올 시즌 기록만 나옵니다. KBO 선수 상세 페이지가
올 시즌 요약과 최근 경기만 주기 때문입니다. 1군 화면에는 연도별 표가
있는데 2군은 "올 시즌 퓨처스 기록이 없습니다" 한 줄만 남습니다.

기록실 쪽에는 2010년부터 있습니다. 1군과 같은 ASP.NET 구조라
`kbo_http.Session` 을 그대로 씁니다. 표 클래스만 다릅니다.

    1군      <table class="tData01 tt">
    퓨처스   <table class="tbl tt mb30">

## 팀을 골라야 다 나옵니다

필터 없이 보면 규정 타석 이상 29명만 나옵니다. 팀을 고르면 규정
미달까지 나옵니다. 2020 두산은 43명이었습니다.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import kbo_http  # noqa: E402
from futures_records import row_key, to_record  # noqa: E402

FUTURES_HTML = """
<html><body>
<table class="tbl tt mb30">
  <thead><tr>
    <th>순위</th><th>선수명</th><th>팀명</th><th>AVG</th><th>G</th>
    <th>PA</th><th>AB</th><th>R</th><th>H</th>
  </tr></thead>
  <tbody>
    <tr><td>1</td>
      <td><a href="/Futures/Player/HitterDetail.aspx?playerId=65040">김태훈</a></td>
      <td>KT</td><td>0.367</td><td>64</td><td>249</td><td>229</td><td>40</td><td>84</td></tr>
    <tr><td>2</td>
      <td><a href="/Futures/Player/HitterDetail.aspx?playerId=64101">한석현</a></td>
      <td>LG</td><td>0.345</td><td>65</td><td>254</td><td>206</td><td>35</td><td>71</td></tr>
  </tbody>
</table>
<a id="cphContents_cphContents_cphContents_ucPager_btnNo1">1</a>
<a id="cphContents_cphContents_cphContents_ucPager_btnNo2">2</a>
</body></html>"""


class TestSessionTableClass:
    def test_퓨처스_표를_읽습니다(self):
        s = kbo_http.Session(delay=0, table_class="tbl tt")
        s.html = FUTURES_HTML
        assert s.header()[:4] == ['순위', '선수명', '팀명', 'AVG']
        rows = s.rows()
        assert len(rows) == 2
        assert rows[0][0] == '65040'
        assert rows[0][1][1] == '김태훈'

    def test_1군_표는_예전_그대로입니다(self):
        # 표 클래스를 안 주면 1군 것을 봅니다. 기존 수집이 안 바뀝니다.
        s = kbo_http.Session(delay=0)
        s.html = FUTURES_HTML
        assert s.rows() == []

    def test_페이지_수를_셉니다(self):
        s = kbo_http.Session(delay=0, table_class="tbl tt")
        s.html = FUTURES_HTML
        assert s.page_count() == 2


class TestRecord:
    HEADER = ['순위', '선수명', '팀명', 'AVG', 'G', 'PA', 'AB', 'R', 'H']
    CELLS = ['1', '김태훈', 'KT', '0.367', '64', '249', '229', '40', '84']

    def test_한_줄을_적재용_dict_로_바꿉니다(self):
        r = to_record('65040', self.HEADER, self.CELLS, 2020, 'batter')
        assert r['player_id'] == '65040'
        assert r['season'] == 2020
        assert r['kind'] == 'batter'
        assert r['player_name'] == '김태훈'
        assert r['team'] == 'KT'
        assert r['AVG'] == '0.367'
        assert r['G'] == '64'
        # 순위는 그때그때 달라지는 값이라 담지 않습니다.
        assert '순위' not in r

    def test_선수_ID_가_없으면_None_입니다(self):
        # 링크가 없으면 우리 화면에서 열 수가 없습니다.
        assert to_record('', self.HEADER, self.CELLS, 2020, 'batter') is None

    def test_같은_선수_같은_시즌은_한_줄입니다(self):
        a = to_record('65040', self.HEADER, self.CELLS, 2020, 'batter')
        b = to_record('65040', self.HEADER, self.CELLS, 2020, 'batter')
        assert row_key(a) == row_key(b)

    def test_시즌이_다르면_다른_줄입니다(self):
        a = to_record('65040', self.HEADER, self.CELLS, 2020, 'batter')
        b = to_record('65040', self.HEADER, self.CELLS, 2021, 'batter')
        assert row_key(a) != row_key(b)

    def test_타자와_투수는_다른_줄입니다(self):
        a = to_record('65040', self.HEADER, self.CELLS, 2020, 'batter')
        b = to_record('65040', self.HEADER, self.CELLS, 2020, 'pitcher')
        assert row_key(a) != row_key(b)
