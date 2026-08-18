# -*- coding: utf-8 -*-
"""하루치 경기 메타(games)를 D1 에 넣습니다.

`daily_pbp_to_d1.py` 가 play_by_play 를 채우면 이 스크립트가 같은 날짜의
`games` 행을 만듭니다. **둘 다 해야 합니다.** `games` 는 순위·경기목록에
쓰이고, `src/routes/wrc.js` 의 경기 수 계산도 여기서 읽습니다. PBP 만
넣으면 새 경기가 화면에 안 나오고 경기 수가 어제 값에 멈춥니다.

판정 규칙(팀 별칭 해석, 포스트시즌 컷오프)은 `games_from_pbp.py` 의
`derive_games` 를 그대로 씁니다. 같은 규칙을 두 번 쓰면 언젠가 갈라집니다.
러너에는 로컬 DB 가 없으므로, 그날 CSV 로 메모리 SQLite 를 만들어
그 함수를 먹입니다.

    py data_collection/daily_games_to_d1.py --date 20260816 --dry-run
"""
import argparse
import csv
import datetime
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d1_load import build_upserts, query, refresh_count, run_d1_file  # noqa: E402
from games_from_pbp import PLAYOFF_START, derive_games  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

# derive_games 가 읽는 컬럼입니다.
NEEDED = ["gameID", "game_date", "home_alias", "away_alias", "stadium",
          "score_home", "score_away"]

GAME_COLS = ["game_id", "game_date", "season", "game_type",
             "home_team_id", "away_team_id", "home_score", "away_score",
             "stadium"]


def read_csv_rows(path):
    for enc in ("cp949", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 알 수 없습니다: %s" % path)


def memory_db(rows, teams):
    """그날 CSV 와 D1 의 teams 로 작은 SQLite 를 만듭니다."""
    con = sqlite3.connect(":memory:")
    con.execute("CREATE TABLE teams (team_id TEXT)")
    con.executemany("INSERT INTO teams VALUES (?)", [(t,) for t in teams])
    con.execute("CREATE TABLE games (game_id TEXT)")   # 비어 있음
    con.execute("CREATE TABLE play_by_play (%s)"
                % ",".join('"%s" TEXT' % c for c in NEEDED))
    con.executemany(
        "INSERT INTO play_by_play VALUES (%s)" % ",".join("?" * len(NEEDED)),
        [tuple(r.get(c) for c in NEEDED) for r in rows])
    return con


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYYMMDD, 기본값은 어제")
    ap.add_argument("--save-dir", default="crawler/save_daily")
    ap.add_argument("--out", default="migration/daily_games.sql")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    kst = datetime.timezone(datetime.timedelta(hours=9))
    day = args.date or (datetime.datetime.now(kst).date()
                        - datetime.timedelta(days=1)).strftime("%Y%m%d")
    year = day[:4]
    print("대상 날짜: %s (KST 기준)" % day)

    # **포스트시즌 컷오프가 없는 시즌은 10월부터 오분류됩니다.**
    # 조용히 "정규시즌"으로 넣으면 나중에 찾기 어렵습니다.
    if str(year) not in PLAYOFF_START and int(day[4:6]) >= 10:
        print("%s 시즌의 포스트시즌 시작일이 PLAYOFF_START 에 없습니다." % year)
        print("games_from_pbp.py 와 load_year_pbp.py 두 곳에 넣은 뒤 다시 돌리십시오.")
        return 1

    save_dir = ROOT / args.save_dir
    csvs = sorted((save_dir / year).glob("%s*.csv" % day)) \
        if (save_dir / year).is_dir() else []
    if not csvs:
        print("%s 에 경기가 없습니다. 넣을 것이 없습니다." % day)
        return 0

    rows = []
    for f in csvs:
        rows.extend(read_csv_rows(f))
    print("경기 CSV %d개, 행 %s개" % (len(csvs), format(len(rows), ",")))

    teams = [r["team_id"] for r in query("SELECT team_id FROM teams;")]
    print("teams %d개" % len(teams))

    con = memory_db(rows, teams)
    # skip_existing=False 로 둡니다. 메모리 DB 의 games 가 비어 있어
    # 어차피 전부 새로 나옵니다. 기존 행 보존은 D1 쪽 UPSERT 가 합니다.
    derived, unresolved = derive_games(con, skip_existing=False)
    con.close()

    if unresolved:
        # 별칭을 못 풀면 team_id 자리에 원문이 그대로 들어갑니다.
        # 조인이 깨지므로 눈에 띄게 남깁니다.
        print("미해결 팀 별칭 %d건: %s" % (len(unresolved), unresolved[:10]))
    if not derived:
        print("도출된 경기가 없습니다.")
        return 1

    dicts = [dict(zip(GAME_COLS, r)) for r in derived]
    for d in dicts:
        print("  %s  %s %s:%s %s (%s)" % (
            d["game_id"], d["away_team_id"], d["away_score"],
            d["home_score"], d["home_team_id"], d["game_type"]))

    # 이미 있는 경기는 점수만 갱신합니다. 2025 행에는 관중·날씨 같은
    # 값이 더 들어 있는데 여기서 만들 수 없으므로 덮지 않습니다.
    stmts = build_upserts("games", GAME_COLS, ["game_id"], dicts)
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
    print("SQL %d문 -> %s" % (len(stmts), out))

    if args.dry_run:
        print("[dry-run] 적재하지 않았습니다.")
        return 0

    run_d1_file(out)
    refresh_count("games")
    print("D1 적재 완료 (%d경기)" % len(dicts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
