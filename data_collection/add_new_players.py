# -*- coding: utf-8 -*-
"""`players` 에 없는 새 선수를 KBO 선수 검색으로 찾아 넣습니다.

## 왜 필요한가

홈 화면 경기 카드와 등말소 칸의 선수 이름은 `players` 에 있어야 링크가
걸립니다. 그런데 새 선수는 한참 동안 `players` 에 없습니다.

    monthly 선수 프로필 수집   올 시즌 **기록이 있는** 선수만 받습니다
    sync_players_from_roster   이미 있는 선수의 소속·등번호만 고칩니다

그래서 시즌 중에 영입된 외국인 선수는 첫 등판 날 선발로 나와도 글자로만
보였습니다(2026-09-27 NC 클레빈저). 기록이 생기고 다음 달 monthly 가
돌아야 비로소 링크가 걸립니다. 신인·육성선수도 같습니다.

## 어디서 이름을 모으나

선수 ID 가 비어 있는 이름을 셋에서 모읍니다.

    kbo_roster          지금 1군 명단
    kbo_roster_moves    최근 등말소
    /schedule           오늘·내일 선발 투수

## 어떻게 찾나

`Player/Search.aspx?searchWord=이름` 은 로그인 없이 표 한 장을 줍니다.
선수 ID·팀·포지션·등번호·생년월일·체격·출신교가 다 있습니다. 선수 상세
페이지처럼 Selenium 이 필요 없습니다.

    이름이 같고 팀이 같은 행이 하나면 그 선수
    둘 이상이면 등번호로 좁힙니다. 그래도 둘 이상이면 넣지 않습니다.

찍지 않습니다. 남의 기록으로 보내는 링크보다 링크 없는 글자가 낫습니다.

## 무엇을 쓰나

**없는 선수만 넣습니다.** `INSERT OR IGNORE` 라 이미 있는 선수의
생년월일·경력 같은 값을 덮지 않습니다. 투타(`throw`·`bat`)는 검색 표에
없어 비워 둡니다. 기록이 생기면 monthly 가 `--refresh` 로 채웁니다.

그다음 `kbo_roster`·`kbo_roster_moves` 의 빈 `player_id` 를 채웁니다.
그래야 등말소 칸도 바로 링크가 걸립니다.

    py data_collection/add_new_players.py --dry-run
    py data_collection/add_new_players.py
"""
import argparse
import datetime
import html
import re
import sys
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from d1_load import query, run_d1_file  # noqa: E402
from mysql_sink import mirror  # noqa: E402

SEARCH_URL = "https://www.koreabaseball.com/Player/Search.aspx"
API_BASE = "https://kbo-api.bstats-baseball.workers.dev"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://www.koreabaseball.com/"}

PLAYER_ROLES = ("투수", "포수", "내야수", "외야수")

# src/routes/standings.js 의 KBO_CODE_TO_TEAM 과 같아야 합니다.
CODE_TO_TEAM = {
    "LG": "LG", "KT": "KT", "OB": "두산", "SS": "삼성", "HT": "KIA",
    "LT": "롯데", "SK": "SSG", "NC": "NC", "WO": "키움", "HH": "한화",
}

IMAGE_URL = ("https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/"
             "middle/%d/%s.jpg")


def kst_today():
    return (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).date()


def missing_from_roster():
    """(이름, 팀, 등번호, 포지션) 집합입니다. 모르면 빈 문자열입니다."""
    since = (kst_today() - datetime.timedelta(days=14)).isoformat()
    rows = query(
        "SELECT name AS nm, team AS tm, back_number AS bn, role AS pos "
        "FROM kbo_roster "
        "WHERE player_id IS NULL AND role IN ('투수','포수','내야수','외야수') "
        "UNION SELECT name, team, '', position FROM kbo_roster_moves "
        "WHERE player_id IS NULL AND move_date >= '%s' "
        "AND position IN ('투수','포수','내야수','외야수');" % since)
    return {(r["nm"], r["tm"], str(r["bn"] or ""), r["pos"] or "")
            for r in rows}


def missing_from_schedule():
    """오늘·내일 선발 중 ID 가 안 붙은 투수입니다.

    선발은 전날 저녁에 발표됩니다. 그 투수가 오늘 처음 1군에 오르면
    아직 등록 현황에도 없습니다. 그래서 일정에서 따로 모읍니다.
    """
    out = set()
    today = kst_today()
    for d in (today, today + datetime.timedelta(days=1)):
        try:
            r = requests.get("%s/schedule" % API_BASE,
                             params={"date": d.isoformat()}, timeout=20)
            r.raise_for_status()
            games = r.json().get("games") or []
        except (requests.RequestException, ValueError) as e:
            print("일정 %s 을 못 받았습니다: %s" % (d, e))
            continue
        for g in games:
            for side in ("home", "away"):
                t = g.get(side) or {}
                team = CODE_TO_TEAM.get(t.get("code") or "")
                if t.get("starter") and team and not t.get("starterId"):
                    out.add((t["starter"], team, "", "투수"))
    return out


def strip_tags(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def search(name):
    """검색 표의 행을 dict 목록으로 돌려줍니다."""
    r = requests.get(SEARCH_URL, params={"searchWord": name},
                     headers=HEADERS, timeout=25)
    r.raise_for_status()
    body = re.search(r"<tbody>(.*?)</tbody>", r.text, re.S)
    if not body:
        return []
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", body.group(1), re.S):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        pid = re.search(r"playerId=(\d+)", tr)
        if len(tds) < 7 or not pid:
            continue
        cells = [strip_tags(t) for t in tds]
        rows.append({
            "player_id": pid.group(1),
            "back_number": cells[0],
            "name": cells[1],
            "team": cells[2],
            "position": cells[3],
            "birthday": cells[4],
            "body": cells[5],
            "career": cells[6],
        })
    return rows


def narrow(rows, name, team, back_number, position):
    """(좁힌 행 목록, 쓴 조건) 입니다. 조건은 'bn'·'pos' 가 들어갑니다.

    등번호가 `#` 인 행은 뺍니다. 은퇴했거나 지금 소속이 없는 선수입니다.
    검색은 역대 선수를 다 주므로 이걸 안 빼면 삼성 김태훈이 셋이 됩니다.
    """
    hit = [r for r in rows if r["name"] == name and r["team"] == team
           and r["back_number"] != "#"]
    used = set()
    if len(hit) > 1 and position:
        hit = [r for r in hit if r["position"] == position]
        used.add("pos")
    if len(hit) > 1 and back_number:
        hit = [r for r in hit if r["back_number"] == back_number]
        used.add("bn")
    return hit, used


def pick(rows, name, team, back_number, position):
    """하나로 좁혀지면 (그 행, 쓴 조건), 아니면 (None, 쓴 조건) 입니다."""
    hit, used = narrow(rows, name, team, back_number, position)
    return (hit[0] if len(hit) == 1 else None), used


def to_int(s):
    return int(s) if s and s.isdigit() else None


def sql_val(v):
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def player_row(r):
    """`players` 한 행입니다. 모르는 칸은 NULL 로 둡니다."""
    birthday = r["birthday"].replace("-", "")
    hw = re.match(r"(\d+)cm,\s*(\d+)kg", r["body"])
    return {
        "player_id": r["player_id"],
        "player_name": r["name"],
        "team_id": r["team"],
        "back_number": to_int(r["back_number"]),
        "position": r["position"] if r["position"] in PLAYER_ROLES else None,
        "birthday": to_int(birthday),
        "height": int(hw.group(1)) if hw else None,
        "weight": int(hw.group(2)) if hw else None,
        "career": r["career"] or None,
        "image_url": IMAGE_URL % (kst_today().year, r["player_id"]),
    }


NEW_PLAYER_COLS = ["player_id", "player_name", "team_id", "back_number", "position",
                   "birthday", "height", "weight", "career", "image_url"]


def id_fill_targets(found):
    """빈 player_id 를 채울 (표, ID, [(열, 값), …]) 목록입니다.

    이름+팀만으로 안 갈렸던 선수는 가를 때 쓴 조건(포지션·등번호)을 똑같이
    붙입니다. 그래야 같은 팀 동명이인의 다른 한 명에게 ID 가 잘못 붙지
    않습니다. 등말소 표에는 등번호가 없어, 등번호로만 갈린 선수는 둘 중
    누구인지 모르니 건드리지 않습니다.
    """
    out, done = [], set()
    for name, team, hit, used in found:
        pid = int(hit["player_id"])
        base = [("name", name), ("team", team)]
        roster = base + ([("role", hit["position"])] if "pos" in used else [])
        if "bn" in used:
            roster = roster + [("back_number", hit["back_number"])]
        targets = [("kbo_roster", pid, roster)]
        if "bn" not in used:
            targets.append(("kbo_roster_moves", pid,
                            base + ([("position", hit["position"])] if "pos" in used else [])))
        for t in targets:
            key = (t[0], t[1], tuple(t[2]))
            if key not in done:
                done.add(key)
                out.append(t)
    return out


def d1_update_sql(table, pid, conds):
    where = " AND ".join("%s=%s" % (c, sql_val(v)) for c, v in conds)
    return "UPDATE %s SET player_id=%d WHERE player_id IS NULL AND %s;" % (table, pid, where)


def mysql_write_new_players(sink, new_rows, targets):
    """새 선수는 없을 때만 넣고(created_at·updated_at 은 MySQL 기본값), 빈 ID 를 채웁니다."""
    if new_rows:
        sink.insert_missing("players", NEW_PLAYER_COLS, ["player_id"], new_rows)
    for table, pid, conds in targets:
        sink.execute(
            "UPDATE `%s` SET `player_id`=%%s WHERE `player_id` IS NULL AND %s"
            % (table, " AND ".join("`%s`=%%s" % c for c, _ in conds)),
            [pid] + [sink.value(table, c, v) for c, v in conds])
    return len(new_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    wanted = missing_from_roster() | missing_from_schedule()
    if not wanted:
        print("ID 가 빈 선수가 없습니다.")
        return 0

    known = {r["pid"] for r in query("SELECT player_id AS pid FROM players;")}
    found, skipped = [], []
    cache = {}
    for name, team, bn, pos in sorted(wanted):
        if name not in cache:
            try:
                cache[name] = search(name)
            except requests.RequestException as e:
                print("검색 실패 %s: %s" % (name, e))
                cache[name] = None
        rows = cache[name]
        hit, used = pick(rows, name, team, bn, pos) if rows else (None, set())
        if hit:
            found.append((name, team, hit, used))
        else:
            skipped.append((name, team))

    new_rows = []
    seen = set()
    for _, _, hit, _ in found:
        if hit["player_id"] not in known and hit["player_id"] not in seen:
            seen.add(hit["player_id"])
            new_rows.append(player_row(hit))

    print("찾음 %d, 못 찾음 %d, 새 선수 %d"
          % (len(found), len(skipped), len(new_rows)))
    for name, team, hit, _ in found:
        mark = "새로" if hit["player_id"] in seen else "있음"
        print("   %-6s %-4s %s  %s" % (name, team, hit["player_id"], mark))
    for name, team in skipped:
        print("   %-6s %-4s 하나로 못 좁힘" % (name, team))

    if args.dry_run or not found:
        if args.dry_run:
            print("\n[미리보기] 반영하지 않았습니다.")
        return 0

    lines = []
    for p in new_rows:
        lines.append(
            "INSERT OR IGNORE INTO players (%s, created_at, updated_at) "
            "VALUES (%s, datetime('now'), datetime('now'));"
            % (", ".join(NEW_PLAYER_COLS), ", ".join(sql_val(p[c]) for c in NEW_PLAYER_COLS)))
    targets = id_fill_targets(found)
    lines += [d1_update_sql(*t) for t in targets]

    out = ROOT / "migration" / "players_add_new.sql"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    run_d1_file(out)
    print("반영 완료 (새 선수 %d명, 문 %d개)" % (len(new_rows), len(lines)))
    mirror("players_new", lambda s: mysql_write_new_players(s, new_rows, targets))
    return 0


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    sys.exit(main())
