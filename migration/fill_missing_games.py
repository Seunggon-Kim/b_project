# -*- coding: utf-8 -*-
"""처음 수집 때 빠진 정규시즌 경기를 다시 받아 넣습니다.

## 무엇이 빠졌나

네이버 일정과 `games` 를 맞대 보니 정규시즌 6경기가 없었습니다
(2026-10-03, 올스타전은 원래 넣지 않음). 그 경기들은 PBP 부터 없어서
games 도 만들어지지 않았습니다. 팀 승패가 공식 순위표와 1경기씩 어긋난
원인입니다.

    다시 받을 수 있음   20150612LTSK0, 20200725LTWO02020,
                        20200726NCKT02020, 20210429HHHT02021
    받을 수 없음        20250628HHSK02025  원천 기록이 깨져 있습니다(크롤러 broken)
                        20210627LTOB02021  크롤러 목록에 나오지 않습니다

다시 받은 네 경기는 9회 이상 기록이 있고, 플레이 득점 합이 최종 점수와
같습니다.

## 어떻게 넣나

그날을 통째로 지우고 다시 넣는 daily 와 달리 **그 경기 행만** 넣습니다.
같은 날 다른 경기는 건드리지 않습니다. 이미 MySQL 에 그 경기가 있으면
아무것도 쓰지 않고 멈춥니다.

    py migration/fill_missing_games.py            # 미리보기(받기만)
    py migration/fill_missing_games.py --write    # MySQL 에 넣기
"""
import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query  # noqa: E402
from daily_games_to_d1 import GAME_COLS, memory_db  # noqa: E402
from daily_pbp_to_d1 import read_csv_rows, wrong_dates  # noqa: E402
from games_from_pbp import derive_games  # noqa: E402
from mysql_sink import mirror  # noqa: E402

GAMES = ["20150612LTSK0", "20200725LTWO02020", "20200726NCKT02020", "20210429HHHT02021"]


def crawl(gid, out_dir):
    day = gid[:8]
    subprocess.run([sys.executable, str(ROOT / "crawler" / "pbp.py"),
                    "-f", day, "-t", day, "-d", str(out_dir) + "/"],
                   cwd=str(ROOT), check=True, capture_output=True)
    f = out_dir / gid[:4] / (gid + ".csv")
    if not f.exists():
        raise SystemExit("%s 를 받지 못했습니다." % gid)
    rows = read_csv_rows(f)
    bad = wrong_dates(rows, day)
    if bad or any(r.get("gameID") != gid for r in rows):
        raise SystemExit("%s CSV 의 날짜나 gameID 가 다릅니다: %s" % (gid, bad[:3]))
    return rows


def already_has(gid):
    """MySQL 에 그 경기의 PBP·games 행이 몇 개 있는지 셉니다(gameID 인덱스 범위)."""
    pbp = query("SELECT COUNT(*) AS n FROM play_by_play WHERE gameID >= '%s' AND gameID < '%s~';"
                % (gid, gid))[0]["n"]
    games = query("SELECT COUNT(*) AS n FROM games WHERE game_id = '%s';" % gid)[0]["n"]
    return pbp, games


def season_names(game_rows):
    """팀을 그 시즌 이름으로 바꿉니다(2015 'SSG' -> 'SK').

    derive_games 는 현재 이름을 줍니다. games 는 그 시즌 이름을 씁니다
    (migration/fix_game_team_names.py 와 같은 규칙).
    """
    for g in game_rows:
        for col in ("home_team_id", "away_team_id"):
            got = query(
                "SELECT ts.team_name FROM franchises f JOIN team_seasons ts "
                "ON ts.franchise_id = f.franchise_id AND ts.season = %d "
                "WHERE f.current_name = '%s';" % (int(g["season"]), g[col]))
            if got:
                g[col] = got[0]["team_name"]


def mysql_write(sink, by_game, game_rows):
    cols = [c for c in sink.columns("play_by_play") if c != "pbp_id"]
    for gid, rows in by_game.items():
        if sink.query("SELECT 1 FROM `play_by_play` WHERE `gameID` = %s LIMIT 1", [gid]):
            raise RuntimeError("MySQL 에 이미 %s 가 있습니다" % gid)
        sink.insert("play_by_play", cols, rows)
    sink.upsert("games", GAME_COLS, ["game_id"], game_rows)
    sink.refresh_count("play_by_play")
    sink.refresh_count("games")
    return len(game_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    by_game = {}
    with tempfile.TemporaryDirectory() as tmp:
        for gid in GAMES:
            by_game[gid] = crawl(gid, Path(tmp))
            print("%s %d행" % (gid, len(by_game[gid])))

    teams = [r["team_id"] for r in query("SELECT team_id FROM teams;")]
    con = memory_db([r for rows in by_game.values() for r in rows], teams)
    derived, unresolved = derive_games(con, skip_existing=False)
    if unresolved or len(derived) != len(GAMES):
        raise SystemExit("games 행을 만들지 못했습니다: %s" % unresolved)
    game_rows = [dict(zip(GAME_COLS, r)) for r in derived]
    season_names(game_rows)
    for g in game_rows:
        print("  %s %s %s %s:%s %s" % (g["game_id"], g["game_type"], g["away_team_id"],
                                       g["away_score"], g["home_score"], g["home_team_id"]))

    for gid in GAMES:
        n_pbp, n_games = already_has(gid)
        if n_pbp or n_games:
            raise SystemExit("MySQL 에 이미 %s 가 있습니다(PBP %d, games %d)" % (gid, n_pbp, n_games))

    if not args.write:
        print("[미리보기] 쓰지 않았습니다.")
        return 0

    mirror("fill_missing_games", lambda s: mysql_write(s, by_game, game_rows), required=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
