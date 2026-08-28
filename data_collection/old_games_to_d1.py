# -*- coding: utf-8 -*-
"""옛 시즌 경기 결과를 네이버에서 받아 `games` 에 넣습니다.

## 왜 필요한가

선수 기록은 1982년까지 넣었는데 경기 결과는 2015년부터였습니다.
1982 백인천의 4할 2리는 보이는데 그 경기가 언제 누구와였는지는
알 수 없었습니다.

## 어디까지 되는가

원천은 네이버 스포츠 API 입니다. **2008년이 하한선**입니다. 그
이전을 요청하면 2008년으로 되돌아옵니다(실측). 1982~2007 은 공개된
경기 단위 원천이 없습니다.

    2006 요청 -> 2008 응답
    2007 요청 -> 2008 응답
    2008 요청 -> 2008 (5월 101경기)

## 팀 이름

**그 시즌 표기명으로 저장합니다.** 네이버는 현재 이름을 주므로
(2014 경기인데 "SSG") `team_seasons` 로 바꿔 넣습니다.

    2008  우리       2009  히어로즈    2010~2018  넥센
    2000~2020  SK    2021~      SSG

`games` 는 `teams` 를 FK 로 참조하므로 그 이름이 표에 있어야 합니다.
없으면 적재가 통째로 막히고, wrangler 는 그 오류를 `D1_RESET_DO` 로
가립니다. 그래서 넣기 전에 먼저 확인합니다.

## 적재 방식

**UPSERT 만 씁니다. DELETE 를 먼저 돌리지 않습니다.** 큰 표를
DELETE + INSERT 로 바꾸다 INSERT 가 막히면 데이터가 사라진 채
남습니다. 실제로 games 가 30분간 절반이 된 적이 있습니다.

    py data_collection/old_games_to_d1.py --year 2014 --dry-run
    py data_collection/old_games_to_d1.py --from 2008 --to 2014
"""
import argparse
import datetime
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from d1_load import build_upserts, d1_columns, query, run_d1_file  # noqa: E402

API = "https://api-gw.sports.naver.com/schedule"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Referer": "https://m.sports.naver.com/"}

# 네이버가 주는 가장 이른 시즌입니다. 더 이르게 요청하면 이 해로
# 되돌아옵니다.
FIRST_SEASON = 2008

# 게임 ID 앞 네 자리가 시리즈 코드입니다. 정규시즌은 날짜(20140718)로
# 시작하고, 포스트시즌과 이벤트 경기는 코드로 시작합니다.
POSTSEASON_CODES = ("3333", "4444", "5555", "6666", "7777")

# 올스타전입니다. 팀이 '나눔'·'드림' 이라 teams 에 없고, 구단 성적도
# 아닙니다. `9999` 로 시작합니다. 넣으면 FK 위반으로 그 시즌 적재가
# 통째로 막힙니다.
SKIP_CODES = ("9999",)

DELAY = 0.25

GAME_COLS = ["game_id", "game_date", "season", "game_type",
             "home_team_id", "away_team_id", "home_score", "away_score",
             "stadium"]


def get(url):
    r = requests.get(url, headers=HEADERS, timeout=30, verify=False)
    r.raise_for_status()
    return r.json()


def month_games(year, month):
    """그 달의 (게임ID, 날짜) 목록입니다."""
    ymd = "%d-%02d-01" % (year, month)
    d = get("%s/calendar?upperCategoryId=kbaseball&categoryIds=kbo&date=%s"
            % (API, ymd))
    out = []
    for x in (d.get("result") or {}).get("dates") or []:
        day = x.get("ymd") or ""
        # 요청한 달이 아니면 버립니다. 없는 연도를 부르면 다른 달이
        # 섞여 돌아옵니다.
        if not day.startswith("%d-%02d" % (year, month)):
            continue
        for gid in (x.get("gameIds") or []):
            out.append((gid, day))
    return out


def game_detail(gid):
    d = get("%s/games/%s" % (API, gid))
    return (d.get("result") or {}).get("game") or {}


def season_names(season):
    """{현재이름: 그시즌이름} 입니다. team_seasons 에서 읽습니다."""
    rows = query(
        "SELECT f.current_name AS cur, ts.team_name AS then_name "
        "FROM team_seasons ts "
        "JOIN franchises f ON f.franchise_id = ts.franchise_id "
        "WHERE ts.season = %d;" % int(season))
    return {r["cur"]: r["then_name"] for r in rows if r["cur"]}


def collect(season, delay=DELAY):
    """한 시즌 경기 전부입니다."""
    names = season_names(season)
    if not names:
        print("  %d: team_seasons 에 그 시즌이 없습니다" % season)
        return []
    rows, seen = [], set()
    for month in range(3, 12):
        try:
            ids = month_games(season, month)
        except Exception as e:
            print("  %d-%02d 일정 실패: %s" % (season, month, str(e)[:60]))
            continue
        for gid, day in ids:
            if gid in seen or gid[:4] in SKIP_CODES:
                continue
            seen.add(gid)
            try:
                g = game_detail(gid)
            except Exception:
                continue
            time.sleep(delay)
            hs, aws = g.get("homeTeamScore"), g.get("awayTeamScore")
            if g.get("statusCode") != "RESULT" or hs is None or aws is None:
                continue  # 취소·미실시
            home = g.get("homeTeamName")
            away = g.get("awayTeamName")
            rows.append({
                "game_id": gid,
                "game_date": int(day.replace("-", "")),
                "season": season,
                # 포스트시즌 판별은 gameID 앞자리가 시리즈 코드인지로
                # 봅니다(3333=PO, 4444=준PO, 6666=WC, 7777=KS).
                "game_type": ("포스트시즌" if gid[:4] in POSTSEASON_CODES
                              else "정규시즌"),
                # 네이버는 현재 이름을 줍니다. 그 시즌 이름으로 바꿉니다.
                "home_team_id": names.get(home, home),
                "away_team_id": names.get(away, away),
                "home_score": hs,
                "away_score": aws,
                "stadium": g.get("stadium"),
            })
        print("  %d-%02d  누적 %d경기" % (season, month, len(rows)), flush=True)
    return rows


def check_teams(rows):
    """teams 에 없는 팀 이름을 돌려줍니다.

    FK 위반은 적재를 통째로 막고 wrangler 가 진짜 원인을 가립니다.
    넣기 전에 확인하는 편이 낫습니다.
    """
    have = {r["team_id"] for r in query("SELECT team_id FROM teams;")}
    used = {r["home_team_id"] for r in rows} | {r["away_team_id"] for r in rows}
    return sorted(used - have)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--from", dest="start", type=int, default=FIRST_SEASON)
    ap.add_argument("--to", dest="end", type=int, default=2014)
    ap.add_argument("--delay", type=float, default=DELAY)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    years = [args.year] if args.year else list(range(args.start, args.end + 1))
    bad = [y for y in years if y < FIRST_SEASON]
    if bad:
        print("네이버는 %d년부터만 줍니다. 요청한 %s 는 받을 수 없습니다."
              % (FIRST_SEASON, bad))
        return 1

    cols = d1_columns("games")
    rc = 0
    for year in years:
        print("=== %d ===" % year)
        t0 = datetime.datetime.now()
        rows = collect(year, args.delay)
        secs = (datetime.datetime.now() - t0).total_seconds()
        if not rows:
            print("  경기가 없습니다.")
            rc = 1
            continue
        missing = check_teams(rows)
        if missing:
            print("  [실패] teams 에 없는 팀: %s" % ", ".join(missing))
            print("  그대로 넣으면 FK 위반으로 적재가 막힙니다.")
            rc = 1
            continue
        teams = sorted({r["home_team_id"] for r in rows})
        print("  %d경기, %d팀 (%s), %.0f초"
              % (len(rows), len(teams), " ".join(teams), secs))
        if args.dry_run:
            continue

        # UPSERT 만 씁니다. DELETE 를 먼저 돌리지 않습니다.
        stmts = build_upserts("games", cols, ["game_id"], rows,
                              max_bytes=20000)
        out = ROOT / "migration" / ("old_games_%d.sql" % year)
        out.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
        run_d1_file(out)
        print("  적재 완료 (%d문)" % len(stmts))
    return rc


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    sys.exit(main())
