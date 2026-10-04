# -*- coding: utf-8 -*-
"""PBP 가 없거나 끊긴 정규시즌 경기의 결과를 네이버 경기 정보로 넣습니다.

## 무엇이 남았나

끝내기 득점 수정(fix_games_final_score.py)과 빠진 경기 채우기
(fill_missing_games.py) 뒤에도 2015~2025 팀 승패가 공식 순위표와 7경기만큼
달랐습니다(2026-10-03). 모두 원천 PBP 가 없거나 중간에 끊긴 경기입니다.

    없음   20170923SSHH02017  네이버 상태가 STARTED 로 멈춰 크롤러가 건너뜀
           20190601SSLT02019  〃
           20190605KTLG02019  〃
           20210627LTOB02021  크롤러 목록에 나오지 않음
           20250628HHSK02025  원천 기록이 깨져 있음(크롤러 broken)
    끊김   20240404LTHH02024  9회초에서 끝남. 9회말 끝내기 2점이 없어 승패가 뒤바뀜
           20240724WOOB02024  5회초에서 끝남. 2:2 무승부로 남음

PBP 는 원천에 없어 채울 수 없습니다. 경기 결과만 네이버 경기 정보
(`/schedule/games/<id>`)의 최종 점수로 넣습니다. 넣고 나면 2015~2025 팀별
승·패·무가 공식 순위표와 모두 같습니다.

`fix_games_final_score.py` 는 PBP 로 점수를 다시 셉니다. 끊긴 두 경기를
되돌리지 않게 `PBP_INCOMPLETE` 를 건너뜁니다.

    py migration/fix_games_from_naver.py            # 미리보기
    py migration/fix_games_from_naver.py --write    # MySQL 에 넣기

2026-10-03 에 한 번 돌렸습니다. D1 은 2026-10-04 에 걷어내 이제 MySQL 에만 씁니다.
"""
import argparse
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query  # noqa: E402
from daily_games_to_d1 import GAME_COLS  # noqa: E402
from mysql_sink import mirror  # noqa: E402

GAMES = ["20170923SSHH02017", "20190601SSLT02019", "20190605KTLG02019",
         "20210627LTOB02021", "20250628HHSK02025",
         "20240404LTHH02024", "20240724WOOB02024"]

# PBP 가 중간에 끊긴 경기입니다. PBP 로 점수를 다시 세면 틀린 값이 됩니다.
PBP_INCOMPLETE = {"20240404LTHH02024", "20240724WOOB02024"}

API = "https://api-gw.sports.naver.com/schedule/games/"


def season_name(season, current):
    got = query("SELECT ts.team_name FROM franchises f JOIN team_seasons ts "
                "ON ts.franchise_id = f.franchise_id AND ts.season = %d "
                "WHERE f.current_name = '%s';" % (season, current))
    return got[0]["team_name"] if got else current


def naver_row(gid):
    g = requests.get(API + gid, timeout=20).json()["result"]["game"]
    if g.get("roundCode") not in ("kbo_r", "kbo_p"):
        raise SystemExit("%s 는 정규시즌이 아닙니다: %s" % (gid, g.get("roundCode")))
    away, home = g.get("awayTeamScore"), g.get("homeTeamScore")
    if away is None or home is None:
        raise SystemExit("%s 최종 점수가 없습니다" % gid)
    season = int(gid[:4])
    return {
        "game_id": gid,
        "game_date": int(g["gameDate"].replace("-", "")),
        "season": season,
        "game_type": "정규시즌",
        "home_team_id": season_name(season, g["homeTeamName"]),
        "away_team_id": season_name(season, g["awayTeamName"]),
        "home_score": int(home),
        "away_score": int(away),
        "stadium": g.get("stadium"),
    }


def mysql_write(sink, rows):
    n = sink.upsert("games", GAME_COLS, ["game_id"], rows)
    sink.refresh_count("games")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = [naver_row(gid) for gid in GAMES]
    now = {r["game_id"]: r for r in query(
        "SELECT * FROM games WHERE game_id IN (%s);" % ",".join("'%s'" % g for g in GAMES))}
    for r in rows:
        old = now.get(r["game_id"])
        before = ("%s %s:%s %s" % (old["away_team_id"], old["away_score"], old["home_score"],
                                   old["home_team_id"])) if old else "없음"
        print("%s  %s -> %s %s:%s %s (%s)" % (r["game_id"], before, r["away_team_id"],
                                              r["away_score"], r["home_score"],
                                              r["home_team_id"], r["stadium"]))
        if old and (old["home_team_id"], old["away_team_id"]) != (r["home_team_id"], r["away_team_id"]):
            raise SystemExit("%s 팀이 다릅니다. 멈춥니다." % r["game_id"])
    if not args.write:
        print("[미리보기] 쓰지 않았습니다.")
        return 0

    mirror("fix_games_from_naver", lambda s: mysql_write(s, rows), required=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
