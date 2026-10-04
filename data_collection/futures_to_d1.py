# -*- coding: utf-8 -*-
"""퓨처스(2군) 일정을 수집해 Cloud SQL(MySQL)에 넣습니다.

`futures_schedule.py` 는 로컬 SQLite 에 씁니다. 러너에는 그 파일이
없으므로, 수집·파싱은 그대로 쓰고 쓰는 곳만 MySQL 로 바꿉니다.
파싱 규칙을 복사하지 않는 이유는 같은 규칙이 두 벌이 되면 언젠가
갈라지기 때문입니다. 파일 이름의 `_to_d1` 은 예전 이름이 남은 것입니다.

    py data_collection/futures_to_d1.py                # 이번 달
    py data_collection/futures_to_d1.py 2026-07 2026-08
    py data_collection/futures_to_d1.py --dry-run
"""
import argparse
import datetime
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from futures_schedule import fetch_month, parse_schedule  # noqa: E402
from mysql_sink import mirror  # noqa: E402

COLS = ["game_id", "game_date", "game_time", "season", "series_id",
        "away_code", "home_code", "away_name", "home_name",
        "away_score", "home_score", "stadium", "status", "updated_at"]

# 충돌 시 건드리지 않을 컬럼입니다. `futures_schedule.py` 의 ON CONFLICT
# 절과 같아야 합니다. 팀·시즌은 gameID 에서 나오는 값이라 바뀔 일이 없고,
# 잘못 덮으면 지난 경기의 팀이 뒤바뀝니다.
KEEP = ["season", "away_code", "home_code", "away_name", "home_name"]


def mysql_write_futures(sink, rows):
    """팀·시즌 열(KEEP)은 덮지 않습니다."""
    n = sink.upsert("futures_games", COLS, ["game_id"], rows, touch=None, keep=KEEP)
    sink.refresh_count("futures_games")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("months", nargs="*", help="YYYY-MM, 기본값은 이번 달")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    months = [m for m in args.months if re.match(r"^\d{4}-\d{2}$", m)]
    if not months:
        # 러너는 UTC 입니다. 한국 기준 달을 봐야 월초·월말이 어긋나지
        # 않습니다.
        kst = datetime.timezone(datetime.timedelta(hours=9))
        t = datetime.datetime.now(kst).date()
        months = ["%d-%02d" % (t.year, t.month)]

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows, per_month = [], []
    for ym in months:
        y, m = int(ym[:4]), int(ym[5:7])
        try:
            games = parse_schedule(fetch_month(y, m), y)
        except Exception as exc:
            # 한 달이 실패해도 나머지는 넣습니다. 다만 조용히 넘기지
            # 않습니다. 2026-07 에 2주가 통째로 빈 적이 있습니다.
            print("%s 수집 실패: %s: %s" % (ym, type(exc).__name__, exc))
            per_month.append((ym, None, None))
            continue
        final = sum(1 for g in games if g["status"] == "final")
        sched = sum(1 for g in games if g["status"] == "scheduled")
        per_month.append((ym, final, sched))
        print("[%s] 경기 %d개 (종료 %d, 예정 %d)" % (ym, len(games), final, sched))
        rows.extend(dict(g, updated_at=now) for g in games)

    if not rows:
        print("넣을 경기가 없습니다.")
        # 비시즌에는 정상입니다. 다만 시즌 중이라면 문제이므로 구분합니다.
        # 퓨처스는 9월에 끝납니다. 10월을 시즌 중으로 보면 경기가 없는 게
        # 정상인데도 매일 실패로 남습니다(2026-10-03 발견).
        month_now = int(months[-1][5:7])
        return 1 if 3 <= month_now <= 9 else 0

    print("경기 %d개" % len(rows))

    if args.dry_run:
        print("[dry-run] 적재하지 않았습니다.")
        return 0

    mirror("futures", lambda s: mysql_write_futures(s, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
