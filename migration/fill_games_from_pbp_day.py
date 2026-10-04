# -*- coding: utf-8 -*-
"""문자중계는 있는데 경기 결과(games)가 안 만들어진 날을 채웁니다.

2026-09-01 경기 5개가 그랬습니다(2026-10-04 발견). 그날 문자중계 행은
있는데 daily 의 games 단계가 그날 것을 만들지 않았습니다.

MySQL 의 그날 문자중계로 games_from_pbp.derive_games 를 돌려(daily 와 같은
규칙) 없는 경기만 MySQL 에 넣습니다. 이미 있는 경기는 건드리지 않습니다.

    py migration/fill_games_from_pbp_day.py 20260901            # 미리보기
    py migration/fill_games_from_pbp_day.py 20260901 --write    # 넣기
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_collection"))

from daily_games_to_d1 import GAME_COLS, NEEDED, memory_db  # noqa: E402
from games_from_pbp import derive_games  # noqa: E402
from mysql_sink import mirror  # noqa: E402

def pbp_rows(cur, day):
    cols = ", ".join("`%s`" % c for c in NEEDED)
    cur.execute("SELECT %s FROM play_by_play WHERE game_date = %%s ORDER BY pbp_id" % cols, (int(day),))
    return [{c: (None if v is None else str(v)) for c, v in zip(NEEDED, r)} for r in cur.fetchall()]


def mysql_write(sink, rows):
    sink.insert_missing("games", GAME_COLS, ["game_id"], rows)
    sink.refresh_count("games")
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("days", nargs="+", help="YYYYMMDD")
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from migration.mysql import conn
    con = conn.connect()
    try:
        with con.cursor() as cur:
            rows = [r for d in args.days for r in pbp_rows(cur, d)]
            cur.execute("SELECT game_id FROM games WHERE game_date IN (%s)"
                        % ",".join(str(int(d)) for d in args.days))
            have = {r[0] for r in cur.fetchall()}
            cur.execute("SELECT team_id FROM teams")
            teams = [r[0] for r in cur.fetchall()]
    finally:
        con.close()
    if not rows:
        raise SystemExit("그날 문자중계가 없습니다.")

    derived, unresolved = derive_games(memory_db(rows, teams), skip_existing=False)
    if unresolved:
        raise SystemExit("팀을 못 찾았습니다: %s" % unresolved)
    new = [dict(zip(GAME_COLS, r)) for r in derived if r[0] not in have]
    print("문자중계 %d행, 만든 경기 %d개, 이미 있음 %d, 넣을 것 %d개"
          % (len(rows), len(derived), len(have), len(new)))
    for g in new:
        print("  %s %s %s %s:%s %s (%s)" % (g["game_id"], g["game_type"], g["away_team_id"],
                                           g["away_score"], g["home_score"], g["home_team_id"],
                                           g["stadium"]))
    if not args.write or not new:
        print("[미리보기] 쓰지 않았습니다." if not args.write else "넣을 것이 없습니다.")
        return 0

    mirror("fill_games_from_pbp_day", lambda s: mysql_write(s, new), required=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
