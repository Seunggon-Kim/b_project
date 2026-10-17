# -*- coding: utf-8 -*-
"""KBO 팀 순위를 네이버 스포츠 API 에서 받아 Cloud SQL(MySQL)에 넣습니다.

KBO 이용약관 제14조 차항(2026-10-14 시행)으로 KBO 기록실(team_ranks.py)을
더 읽지 않습니다. 같은 표(team_season_rank)를 네이버 값으로 채웁니다.

    GET /statistics/categories/kbo/seasons/{y}/teams

네이버는 2008 부터 줍니다. 2007 이전 행은 evan 결정(2026-10-18)으로 백업 뒤
지웁니다(migration/naver_swap.py). 이 스크립트는 2008 이후만 씁니다.

## 칸

    ranking→rank  gameCount→games  winGameCount→wins  loseGameCount→losses
    drawnGameCount→draws  wra→pct('0.632')  gameBehind→gb('10.5', 선두 '0')
    teamId→franchise_id  league='단일'(2008 이후 양대리그 없음)

팀 이름은 네이버 teamName 이 **지금 이름**이라 쓰지 않고, team_seasons 의 그
시즌 이름을 붙입니다(2008·2009 히어로즈는 '우리'·'히어로즈'). 그 시즌 줄이
없으면 네이버 teamShortName 을 쓰고 team_seasons 에도 넣습니다(새 시즌).

## 게임차

2009·2010 은 무승부를 패로 셌습니다(승률 = 승/경기). 네이버 게임차는 그
규칙대로 무승부를 패로 셉니다. KBO 기록실은 무승부를 빼고 셌습니다. 2010
다섯 팀이 0.5~1.5 다릅니다. 순위·승률과 같은 규칙인 네이버 값을 씁니다.

    py data_collection/naver_team_ranks.py --from 2008 --to 2026 --dry-run
    py data_collection/naver_team_ranks.py --current          # daily
"""
import argparse
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_http  # noqa: E402

FIRST_SEASON = 2008
LEAGUE = "단일"
COLUMNS = ["franchise_id", "season", "team_name", "league", "rank",
           "games", "wins", "losses", "draws", "pct", "gb"]
KEYS = ["season", "team_name", "league"]
TEAM_SEASON_COLUMNS = ["franchise_id", "season", "team_name"]
TEAM_SEASON_KEYS = ["franchise_id", "season"]


def fetch(season, cl=None):
    cl = cl or naver_http.client()
    d = cl.get("/statistics/categories/kbo/seasons/%d/teams" % season)
    return ((d.get("result") or {}).get("seasonTeamStats")) or []


def fmt_pct(v):
    return None if v is None else str(Decimal(str(v)).quantize(Decimal("0.001"), ROUND_HALF_UP))


def fmt_gb(v):
    """10.0 → '10', 10.5 → '10.5' (KBO 표기와 같게)."""
    if v is None:
        return None
    d = Decimal(str(v))
    return str(d.quantize(Decimal("1"))) if d == d.to_integral_value() else str(d.normalize())


def to_rows(stats, season, names):
    """names: {(franchise_id, season): 그 시즌 팀 이름}."""
    out = []
    for t in stats:
        if (t.get("gameType") or "REGULAR_SEASON") != "REGULAR_SEASON":
            continue
        fid = t["teamId"]
        out.append({
            "franchise_id": fid,
            "season": int(season),
            "team_name": names.get((fid, int(season))) or t.get("teamShortName") or t.get("teamName"),
            "league": LEAGUE,
            "rank": t.get("ranking"),
            "games": t.get("gameCount"),
            "wins": t.get("winGameCount"),
            "losses": t.get("loseGameCount"),
            "draws": t.get("drawnGameCount"),
            "pct": fmt_pct(t.get("wra")),
            "gb": fmt_gb(t.get("gameBehind")),
        })
    return out


def new_team_seasons(rows, names):
    return [{"franchise_id": r["franchise_id"], "season": r["season"], "team_name": r["team_name"]}
            for r in rows if (r["franchise_id"], r["season"]) not in names]


def write(sink, rows, seasons, names):
    """그 시즌 행을 지우고 넣습니다(팀 이름이 바뀐 옛 행이 남지 않게)."""
    for y in seasons:
        sink.execute("DELETE FROM team_season_rank WHERE season = %s", (y,))
    n = sink.insert("team_season_rank", COLUMNS, rows)
    ts = new_team_seasons(rows, names)
    if ts:
        sink.insert_missing("team_seasons", TEAM_SEASON_COLUMNS, TEAM_SEASON_KEYS, ts)
        sink.refresh_count("team_seasons")
    sink.refresh_count("team_season_rank")
    return n


def name_map(rows):
    return {(r["franchise_id"], int(r["season"])): r["team_name"] for r in rows}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--from", dest="first", type=int, default=FIRST_SEASON)
    ap.add_argument("--to", dest="last", type=int, default=None)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    from kbo_season import record_season
    if a.current:
        seasons = [record_season()]
    else:
        last = a.last or record_season()
        seasons = list(range(max(a.first, FIRST_SEASON), last + 1))

    from d1_load import query
    names = name_map(query("SELECT franchise_id, season, team_name FROM team_seasons"))
    rows = []
    for y in seasons:
        got = to_rows(fetch(y), y, names)
        if not got:
            print("  %d 순위가 아직 없습니다. 건너뜁니다." % y)
            continue
        rows.extend(got)
        print("  %d %d팀" % (y, len(got)), flush=True)
    if not rows:
        print("받은 것이 없습니다(비시즌일 수 있습니다).")
        return 0
    done = sorted({r["season"] for r in rows})
    print("총 %d행, 새 team_seasons %d줄" % (len(rows), len(new_team_seasons(rows, names))))
    if a.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0
    from mysql_sink import mirror
    mirror("team_ranks", lambda sink: write(sink, rows, done, names))
    return 0


if __name__ == "__main__":
    sys.exit(main())
