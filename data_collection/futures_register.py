# -*- coding: utf-8 -*-
"""퓨처스(2군) 등록 명단을 팀별로 받아 옵니다.

## 왜 필요한가

소속 판정 기준이 화면마다 달랐습니다.

    1군 화면    올 시즌 기록이 있나      -> 방출돼도 기록은 남습니다
    퓨처스 화면 KBO 등번호가 있나        -> 정확하지만 월 1회만 갱신

그래서 타무라(56218)가 한쪽에선 두산, 한쪽에선 무소속이었습니다.

`kbo_roster`(1군 등록 현황)는 daily 가 매일 받는 좋은 신호인데
**1군만** 담아 2군 선수가 통째로 빠집니다. 여기에 퓨처스 명단을 더하면
구단에 속한 선수 전체가 됩니다.

    명단 = 1군 등록 현황 + 퓨처스 등록 현황
    소속 = 그 명단의 팀. 어디에도 없으면 무소속.

한화 퓨처스 명단에 1군 등록 선수는 없었습니다. 두 명단이 겹치지 않아
그대로 더하면 됩니다.

## 페이지가 까다롭습니다

`Futures/Player/Register.aspx` 는 한 번에 한 팀만 보여 줍니다. 팀을
고르는 드롭다운이 없습니다. hidden `hfSearchTeam` 에 팀 코드를 넣고
`__EVENTTARGET` 을 **`btnCalendarSelect`** 로 줘야 바뀝니다. 다른
target 으로는 응답의 hidden 값만 바뀌고 명단은 그대로입니다.

표는 감독·코치·투수·포수·내야수·외야수 순입니다. 앞 둘은 선수가
아니라 버립니다.

**선수 ID 가 링크에 있습니다.** 1군 명단(이름과 등번호만)과 달라
이름으로 짝지을 필요가 없고 동명이인 문제도 없습니다.

    py data_collection/futures_register.py
    py data_collection/futures_register.py --json
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import kbo_http  # noqa: E402
from kbo_http import Session  # noqa: E402

URL = "https://www.koreabaseball.com/Futures/Player/Register.aspx"

# 이 표들만 선수입니다. 감독·코치는 뺍니다.
PLAYER_ROLES = ("투수", "포수", "내야수", "외야수")

# 퓨처스 기록실이 주는 팀 코드입니다. 상무(SM)·울산(UL)도 있습니다.
TEAM_CODES = ("HH", "LG", "WO", "OB", "SK", "SM", "LT", "NC", "KT", "HT",
              "SS", "UL")

# 팀 코드 -> 우리가 쓰는 이름입니다. `routes/futuresrecord.js` 의
# FUTURES_TEAM_CODE 를 뒤집은 것입니다.
TEAM_NAME = {
    "LG": "LG", "KT": "KT", "OB": "두산", "SS": "삼성", "HT": "KIA",
    "LT": "롯데", "SK": "SSG", "NC": "NC", "WO": "키움", "HH": "한화",
    "SM": "상무", "UL": "울산",
}

_TAG = re.compile(r"<[^>]+>")
_TABLE = re.compile(r"<table[^>]*>[\s\S]*?</table>")
_TH = re.compile(r"<th[^>]*>([\s\S]*?)</th>")
_TR = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>")
_TD = re.compile(r"<td[^>]*>([\s\S]*?)</td>")
_PID = re.compile(r"playerId=(\d+)")


def _text(s):
    return _TAG.sub("", s).replace("&nbsp;", " ").strip()


def parse_team_page(html, team):
    """한 팀 명단입니다. 감독·코치는 빼고 선수만 돌려줍니다."""
    out = []
    for table in _TABLE.findall(html):
        ths = [_text(x) for x in _TH.findall(table)]
        # 두 번째 머리 칸이 역할입니다: 등번호 | 투수 | 투타유형 | ...
        role = ths[1] if len(ths) > 1 else ""
        if role not in PLAYER_ROLES:
            continue
        for tr in _TR.findall(table):
            tds = _TD.findall(tr)
            if len(tds) < 2:
                continue
            pid = _PID.search(tr)
            if not pid:
                # 링크가 없으면 우리 표와 이을 수 없습니다.
                continue
            out.append({
                "team": team,
                "name": _text(tds[1]),
                # '00' 이 실제로 있습니다. 정수로 바꾸면 '0' 과 같아집니다.
                "back_number": _text(tds[0]),
                "role": role,
                "player_id": int(pid.group(1)),
                "league": "퓨처스",
            })
    return out


def fetch_team(session, code):
    """그 팀 화면으로 넘어가 명단을 읽습니다."""
    import urllib.parse
    form = {m.group(1): m.group(2)
            for m in kbo_http._HIDDEN.finditer(session.html)}  # noqa: SLF001
    form[kbo_http.PREFIX + "hfSearchTeam"] = code
    form["__EVENTTARGET"] = kbo_http.PREFIX + "btnCalendarSelect"
    form["__EVENTARGUMENT"] = ""
    body = urllib.parse.urlencode(form, encoding="utf-8").encode()
    session._fetch(session.url, body)                 # noqa: SLF001
    return parse_team_page(session.html, TEAM_NAME.get(code, code))


def fetch_all(delay=0.3):
    """열두 팀 전부입니다."""
    s = Session(delay)
    s._fetch(URL)                                     # noqa: SLF001
    rows = []
    for code in TEAM_CODES:
        rows.extend(fetch_team(s, code))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--delay", type=float, default=0.3)
    args = ap.parse_args()

    rows = fetch_all(args.delay)
    as_of = datetime.datetime.now(
        datetime.timezone(datetime.timedelta(hours=9))).strftime("%Y-%m-%d")
    for r in rows:
        r["as_of"] = as_of

    if args.json:
        print(json.dumps({"as_of": as_of, "roster": rows}, ensure_ascii=False))
        return 0

    by_team = {}
    for r in rows:
        by_team.setdefault(r["team"], []).append(r)
    print("퓨처스 등록 %s명 (%s)" % (format(len(rows), ","), as_of))
    for team in sorted(by_team):
        print("  %-4s %d명" % (team, len(by_team[team])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
