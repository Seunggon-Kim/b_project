# -*- coding: utf-8 -*-
"""KBO 기록실을 브라우저 없이 읽습니다.

## 왜 만들었는가

공식 기록 수집이 Selenium 이었습니다. 매일 13분을 브라우저에 쓰고,
브라우저에서만 나는 고장을 겪었습니다.

    element click intercepted: <a class="next"> is not clickable
    at point (1466, 65). Other element would receive the click:
    <div class="wrapping lnb-wrap fixed">

상단 고정 메뉴바가 '다음' 링크를 가려서 2021 NC 49명의 볼넷·사구·
삼진이 통째로 비었습니다. **오류는 로그에만 남고 CSV 는 정상적으로
만들어져** 아무도 몰랐습니다.

브라우저를 걷어내면 이런 종류의 고장이 원천적으로 사라집니다.
화면 좌표도, 겹침도, 렌더링 시점도 없습니다.

## 어떻게 되는가

기록실은 ASP.NET WebForms 입니다. 시즌·팀·페이지를 바꿀 때마다
`__EVENTTARGET` 을 담아 같은 주소로 POST 합니다. `__VIEWSTATE` 를
응답에서 받아 다음 요청에 그대로 실어 보내면 됩니다.

실측(2021 NC)으로 확인했습니다.

    Basic1  1페이지 30행 + 2페이지 19행 = 49행
    Basic2  1페이지 30행 + 2페이지 19행 = 49행   <- 셀레니움이 막히던 곳
    겹치는 선수 0명

## 주의

KBO 가 페이지 구조를 바꾸면 조용히 0행이 나올 수 있습니다. 부르는
쪽에서 행 수를 확인하십시오. `fetch_table` 은 표를 못 찾으면 헤더도
행도 빈 값을 돌려줍니다.
"""
import http.cookiejar
import re
import time
import urllib.parse
import urllib.request

BASE = "https://www.koreabaseball.com/Record/Player/"

# 컨트롤 이름 접두사입니다. 마스터 페이지가 3중이라 이렇게 깁니다.
PREFIX = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# 한 요청과 다음 요청 사이 간격입니다. 사이트에 부담을 주지 않습니다.
DELAY_SEC = 0.4

_HIDDEN = re.compile(
    r'<input type="hidden" name="([^"]+)"[^>]*value="([^"]*)"')
# 1군 기록실의 표입니다. 퓨처스는 클래스가 달라서(`tbl tt mb30`)
# Session 에 넘겨 바꿉니다.
TABLE_CLASS = "tData01 tt"


def _table_re(cls):
    return re.compile(r'<table class="%s[^"]*"[^>]*>(.*?)</table>'
                      % re.escape(cls), re.S)


_TABLE = _table_re(TABLE_CLASS)
_TH = re.compile(r"<th[^>]*>(.*?)</th>", re.S)
_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S)
_TD = re.compile(r"<td[^>]*>(.*?)</td>", re.S)
_TAG = re.compile(r"<.*?>")
_PID = re.compile(r"playerId=(\d+)")
_PAGER = re.compile(r'id="[^"]*ucPager_btnNo(\d+)"')


def _text(s):
    return _TAG.sub("", s).replace("&nbsp;", " ").strip()


class Session:
    """쿠키와 VIEWSTATE 를 들고 다니는 한 번의 수집 세션입니다."""

    def __init__(self, delay=DELAY_SEC, table_class=TABLE_CLASS):
        self._op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.delay = delay
        self.html = ""
        self.url = ""
        # 읽을 표입니다. 퓨처스 기록실은 `tbl tt mb30` 입니다.
        self._table = _table_re(table_class)

    def _fetch(self, url, data=None):
        req = urllib.request.Request(url, data=data, headers={
            "User-Agent": UA,
            "Referer": url,
            "Content-Type": "application/x-www-form-urlencoded",
        })
        with self._op.open(req, timeout=60) as r:
            self.html = r.read().decode("utf-8", "replace")
        self.url = url
        time.sleep(self.delay)
        return self.html

    def open(self, page):
        """`HitterBasic/Basic1.aspx` 같은 상대 경로를 엽니다."""
        return self._fetch(BASE + page)

    def post(self, target, fields=None):
        """포스트백 한 번입니다.

        target 은 접두사를 뺀 컨트롤 이름입니다
        (예: `ddlSeason$ddlSeason`, `ucPager$btnNo2`).
        """
        form = {m.group(1): m.group(2) for m in _HIDDEN.finditer(self.html)}
        form["__EVENTTARGET"] = PREFIX + target
        form["__EVENTARGUMENT"] = ""
        for k, v in (fields or {}).items():
            form[PREFIX + k] = v
        body = urllib.parse.urlencode(form, encoding="utf-8").encode()
        return self._fetch(self.url, body)

    # -------------------------------------------------- 표 읽기

    def header(self):
        m = self._table.search(self.html)
        return [_text(x) for x in _TH.findall(m.group(1))] if m else []

    def rows(self):
        """[(player_id, [셀 문자열...]), ...] 입니다."""
        m = self._table.search(self.html)
        if not m:
            return []
        out = []
        for tr in _TR.findall(m.group(1)):
            tds = _TD.findall(tr)
            if not tds:
                continue
            pid = _PID.search(tr)
            out.append((pid.group(1) if pid else "",
                        [_text(t) for t in tds]))
        return out

    def page_count(self):
        nums = [int(n) for n in _PAGER.findall(self.html)]
        return max(nums) if nums else 1


def fetch_table(page, season, team, delay=DELAY_SEC):
    """한 페이지·한 시즌·한 팀의 표 전체입니다(페이지 넘김 포함).

    돌려주는 값은 (헤더, {player_id: [셀...]}) 입니다. 같은 선수가
    두 번 나오면 뒤엣것으로 덮지 않고 처음 것을 지킵니다. 페이지를
    잘못 넘겨 같은 쪽을 두 번 읽어도 조용히 늘어나지 않습니다.

    **시즌·팀 선택은 Basic1 에서만 합니다.** Basic2·Detail 페이지에서
    시즌을 바꾸면 팀 드롭다운이 갱신되지 않습니다. 1982 를 골라도
    팀 목록은 현재 10팀 그대로라 삼미(HD) 같은 옛 팀을 고를 수 없고,
    **조용히 0행이 나옵니다.** 실제로 HD 는 전 시즌 Basic2 가 비었고,
    2015~2026 에서는 팀이 안 바뀌어 눈에 띄지 않았습니다.

    화면에서도 사람은 Basic1 에서 시작해 '다음' 으로 넘어갑니다.
    같은 순서를 따릅니다. 선택 상태는 세션 쿠키로 이어집니다.
    """
    s = Session(delay)
    entry = page.split("/")[0] + "/Basic1.aspx"
    s.open(entry)
    sel = {"ddlSeason$ddlSeason": str(season), "ddlTeam$ddlTeam": team}
    # 시즌을 바꾸면 팀 선택이 초기화됩니다. 두 번에 나눠 보냅니다.
    s.post("ddlSeason$ddlSeason", {"ddlSeason$ddlSeason": str(season)})
    s.post("ddlTeam$ddlTeam", sel)
    if page != entry:
        # 고른 상태 그대로 목표 페이지로 넘어갑니다.
        s.open(page)

    header = s.header()
    data = {}
    for pid, cells in s.rows():
        data.setdefault(pid, cells)

    for p in range(2, s.page_count() + 1):
        s.post("ucPager$btnNo%d" % p, sel)
        for pid, cells in s.rows():
            data.setdefault(pid, cells)

    return header, data
