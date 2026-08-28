# -*- coding: utf-8 -*-
"""KBO 1군 등록 현황을 받아 옵니다.

## 무엇을 주나

`https://www.koreabaseball.com/Player/RegisterAll.aspx` 한 장에 세 가지가
있습니다.

    표 0~9    구단별 1군 명단. 이름과 **등번호**가 같이 나옵니다.
    표 10     그날 1군에 **등록**된 선수
    표 11     그날 1군에서 **말소**된 선수

## 왜 필요한가

세 가지가 이 하나로 풀립니다.

**동명이인.** 홈 화면 경기 카드에서 투수 이름을 누르면 선수 페이지로
갑니다. 지금은 이름+팀으로 찾는데, 같은 팀에 같은 이름 투수가 둘이면
(2026 삼성 이승현) 링크가 아예 안 걸립니다. 등번호가 있으면 갈립니다.

**소속팀.** `players.team_id` 가 1,749명 중 1,164명이 비어 있습니다.
여기서 채울 수 있습니다.

**등말소 이력.** KBO 는 **오늘 것만** 보여 줍니다. 어제 누가 등록됐는지
묻는 화면이 없습니다. 그래서 매일 받아 우리가 쌓아야 합니다. 오늘
시작하면 오늘부터 쌓입니다. 소급은 안 됩니다.

## 형식

명단 칸은 `고영표(1)스기모토(11)우규민(12)` 처럼 이름과 등번호가
괄호로 붙어 죽 이어집니다. 구분자가 없어 괄호를 기준으로 자릅니다.

등번호에 `00` 이 있습니다(키움 권혁빈). 정수로 바꾸면 `0` 이 되어
`0` 번과 구분이 사라지므로 **문자열로 둡니다.**

    py data_collection/kbo_register.py            # 화면에 요약
    py data_collection/kbo_register.py --json     # JSON 으로
"""
import argparse
import datetime
import json
import re
import sys

import requests

URL = "https://www.koreabaseball.com/Player/RegisterAll.aspx"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://www.koreabaseball.com/"}

# 명단 표의 열 순서입니다. 헤더에 인원수가 붙어 있어(`투수(15)`) 이름만
# 봅니다.
ROLE_ORDER = ["감독", "코치", "투수", "포수", "내야수", "외야수"]

# 등말소 표의 포지션 약어입니다. 명단 표와 표기가 달라 맞춰 둡니다.
POS_FULL = {"투": "투수", "포": "포수", "내": "내야수", "외": "외야수"}


def fetch(timeout=25):
    r = requests.get(URL, headers=HEADERS, timeout=timeout, verify=False)
    r.raise_for_status()
    return r.text


def strip_tags(s):
    return re.sub(r"<[^>]+>", "", s).strip()


def tables(html):
    return re.findall(r"<table([^>]*)>(.*?)</table>", html, re.S)


def parse_names(cell):
    """셀 안의 선수들을 뽑습니다.

    셀은 이렇게 생겼습니다.

        <ul><li>고영표(1)</li><li>스기모토(11)</li>...</ul>

    **`<li>` 를 먼저 잘라야 합니다.** 통째로 정규식을 걸면 이름에
    `</li><li>` 가 붙어 "</li><li>김민수" 같은 값이 나옵니다.

    등번호는 문자열로 둡니다. `00`(키움 권혁빈)과 `0` 은 다른 번호인데
    정수로 바꾸면 같아집니다.
    """
    out = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", cell, re.S):
        m = re.match(r"\s*(.+?)\s*\((\d+)\)\s*$", strip_tags(li))
        if m:
            out.append((m.group(1).strip(), m.group(2)))
    return out


def parse_roster(html):
    """구단별 명단입니다. [{team, role, name, back_number}] 를 돌려줍니다."""
    out = []
    for attrs, body in tables(html):
        if "tDays" not in attrs:
            continue
        heads = [strip_tags(x) for x in
                 re.findall(r"<th[^>]*>(.*?)</th>", body, re.S)]
        cells = [x for x in re.findall(r"<td[^>]*>(.*?)</td>", body, re.S)]
        if not heads or not cells:
            continue
        # **첫 셀은 팀이 아니라 감독입니다.** 첫 열 헤더가 `구단` 이라
        # 팀 이름이 들어 있을 것 같지만, 그 아래 셀에는 `이강철(71)` 이
        # 들어 있습니다. 팀 이름은 헤더 **맨 뒤** 칸에 `KT45명` 형태로
        # 붙어 있습니다.
        m = re.match(r"(.+?)\s*\d+명$", heads[-1])
        team = m.group(1).strip() if m else heads[-1].strip()
        if not team:
            continue
        # 헤더 `감독(1)` 에서 역할 이름만 뽑아 열과 짝지웁니다.
        # 첫 헤더(`구단`)와 마지막(`KT45명`)은 역할이 아닙니다.
        roles = [re.sub(r"\(.*\)$", "", h).strip() for h in heads[1:-1]]
        for role, cell in zip(roles, cells):
            if role not in ROLE_ORDER:
                continue
            for name, num in parse_names(cell):
                out.append({"team": team, "role": role,
                            "name": name, "back_number": num})
    return out


def parse_moves(html):
    """그날 등록·말소입니다. [{kind, name, position, team}] 입니다.

    표가 둘인데 겉모습이 같습니다(선수·포지션·팀). 앞이 등록, 뒤가
    말소인데 순서에만 기대면 페이지가 바뀔 때 조용히 뒤집힙니다.

    `<caption>` 도 못 씁니다. **둘 다 `1군등록현황`** 입니다. 말소 표에도
    그렇게 적혀 있습니다.

    구분되는 것은 `<table>` 의 `summary` 속성입니다.

        summary="...1군등록현황을 보여주고 있습니다."
        summary="...1군말소현황을 보여주고 있습니다."
    """
    out = []
    for attrs, body in tables(html):
        if "tDays" in attrs or "tData" not in attrs:
            continue
        heads = [strip_tags(x) for x in
                 re.findall(r"<th[^>]*>(.*?)</th>", body, re.S)]
        if heads[:3] != ["선수", "포지션", "팀"]:
            continue
        kind = "말소" if "말소" in attrs else "등록"
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", body, re.S):
            tds = [strip_tags(x) for x in
                   re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
            if len(tds) < 3:
                continue
            out.append({"kind": kind, "name": tds[0],
                        "position": POS_FULL.get(tds[1], tds[1]),
                        "team": tds[2]})
    return out


def collect():
    html = fetch()
    kst = datetime.timezone(datetime.timedelta(hours=9))
    return {
        "as_of": datetime.datetime.now(kst).strftime("%Y-%m-%d"),
        "roster": parse_roster(html),
        "moves": parse_moves(html),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    d = collect()
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=1))
        return 0

    roster, moves = d["roster"], d["moves"]
    print("기준일 %s" % d["as_of"])
    print()
    teams = {}
    for r in roster:
        teams.setdefault(r["team"], []).append(r)
    print("=== 구단별 (%d팀, %d명) ===" % (len(teams), len(roster)))
    for t in sorted(teams):
        rs = teams[t]
        by = {}
        for r in rs:
            by[r["role"]] = by.get(r["role"], 0) + 1
        print("  %-5s %3d명  %s" % (
            t, len(rs), " ".join("%s%d" % (k, by[k]) for k in ROLE_ORDER if k in by)))
    print()
    print("=== 오늘 등록·말소 (%d건) ===" % len(moves))
    for m in moves:
        print("  %-3s %-8s %-4s %s" % (m["kind"], m["name"], m["position"], m["team"]))
    print()
    dup = {}
    for r in roster:
        dup.setdefault(r["name"], set()).add(r["team"] + r["back_number"])
    same = {k: v for k, v in dup.items() if len(v) > 1}
    print("=== 현재 1군 안 동명이인 %d명 ===" % len(same))
    for k in sorted(same):
        who = [r for r in roster if r["name"] == k]
        print("  %-8s %s" % (k, ", ".join(
            "%s %s번" % (x["team"], x["back_number"]) for x in who)))
    return 0


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    sys.exit(main())
