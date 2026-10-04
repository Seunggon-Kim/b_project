# -*- coding: utf-8 -*-
"""구종 가치 표(pitch_run_value)와 기대 득점 표(run_expectancy)를 만듭니다.

MySQL 에서 한 시즌 정규시즌 PBP 를 읽어 계산하고, 그 시즌 행을 한 트랜잭션에서
바꿉니다. D1 은 읽지도 쓰지도 않습니다. 계산 규칙은 pitch_value_calc.py 와
docs/superpowers/specs/2026-10-04-pitch-run-value-design.md 에 있습니다.

    py data_collection/pitch_run_value.py --season 2024 --dry-run
    py data_collection/pitch_run_value.py --current          # daily
    py data_collection/pitch_run_value.py --from 2016 --to 2025
"""
import argparse
import datetime
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data_collection import pitch_value_calc as pv  # noqa: E402

FIRST_SEASON = 2016
NON_REGULAR = ("3333", "4444", "5555", "7777", "9999")
KST = datetime.timezone(datetime.timedelta(hours=9))
COLS = ("gameID", "pbp_id", "inning", "inning_topbot", "outs", "balls", "strikes",
        "on_1b", "on_2b", "on_3b", "pitch_result", "runs_scored",
        "pitcher_ID", "pitch_type", "stands", "throws")


def seasons_from_args(args, today):
    if args.season is not None:
        seasons = [args.season]
    elif args.current:
        seasons = [today.year]
    elif args.from_ is not None and args.to is not None:
        seasons = list(range(args.from_, args.to + 1))
    else:
        raise SystemExit("--season, --current, --from/--to 중 하나가 필요합니다")
    if min(seasons) < FIRST_SEASON:
        raise SystemExit("%d 년부터만 만듭니다" % FIRST_SEASON)
    return seasons


def fetch_sql():
    reg = " AND ".join("gameID NOT LIKE '%s%%%%'" % p for p in NON_REGULAR)
    return ("SELECT gameID, pbp_id, inning, inning_topbot, outs, balls, strikes, "
            "on_1b_id IS NOT NULL AS on_1b, "
            "on_2b_id IS NOT NULL AS on_2b, "
            "on_3b_id IS NOT NULL AS on_3b, "
            "pitch_result, runs_scored, pitcher_ID, pitch_type, stands, throws "
            "FROM play_by_play WHERE game_date >= %s AND game_date < %s AND " + reg +
            " ORDER BY gameID, pbp_id")


def re_rows(season, re, n):
    return [(season, s[0], s[1], s[2], s[3], re[s], n[s]) for s in sorted(re)]


def value_rows(season, vals):
    return [(season, k[0], k[1], k[2], v[0], v[1]) for k, v in sorted(vals.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2]))]


def write_season(con, season, re_list, value_list):
    cur = con.cursor()
    try:
        con.begin()
        cur.execute("DELETE FROM run_expectancy WHERE season = %s", (season,))
        cur.execute("DELETE FROM pitch_run_value WHERE season = %s", (season,))
        cur.executemany("INSERT INTO run_expectancy (season, bases, outs, balls, strikes, re, n) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s)", re_list)
        cur.executemany("INSERT INTO pitch_run_value (season, pitcher_ID, pitch_type, stands, n, rv) "
                        "VALUES (%s, %s, %s, %s, %s, %s)", value_list)
        con.commit()
    except Exception:
        con.rollback()
        raise


def compute(con, season):
    cur = con.cursor()
    cur.execute(fetch_sql(), (season * 10000, (season + 1) * 10000))
    rows = [dict(zip(COLS, r)) for r in cur.fetchall()]
    halves = pv.split_halves(rows)
    re, n = pv.expectancy_table(halves)
    vals = pv.pitch_values(halves, re)
    return rows, re, n, vals


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--from", dest="from_", type=int)
    ap.add_argument("--to", type=int)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    seasons = seasons_from_args(args, datetime.datetime.now(KST).date())

    from migration.mysql import conn as myconn
    con = myconn.connect()
    try:
        for season in seasons:
            t = time.time()
            rows, re, n, vals = compute(con, season)
            if not rows:
                print("%d: 정규시즌 PBP 가 없어 건너뜁니다" % season)
                continue
            total = sum(v[1] for v in vals.values())
            print("%d: PBP %d행, 상태 %d칸(최소 %d공), 가치 %d줄, 리그 합 %+.1f점, %.1f초"
                  % (season, len(rows), len(re), min(n.values()), len(vals), total, time.time() - t))
            if not args.dry_run:
                write_season(con, season, re_rows(season, re, n), value_rows(season, vals))
                print("%d: 썼습니다" % season)
    finally:
        con.close()


if __name__ == "__main__":
    main()
