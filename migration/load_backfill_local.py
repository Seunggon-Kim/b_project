# -*- coding: utf-8 -*-
"""백필한 시즌 CSV 를 로컬 SQLite 에 넣습니다.

D1 로 바로 넣지 않고 로컬을 거치는 이유가 있습니다.

- `export_season.py` 가 로컬 SQLite 에서 시즌을 뽑습니다.
- 파크팩터·wRC+·RE24 재계산이 로컬 SQLite 를 요구합니다.
- 넣기 전에 시즌별 행 수를 세어 대조할 수 있습니다. D1 에 넣고 나서
  틀린 것을 발견하면 되돌리는 데 쓰기 한도를 또 씁니다.

적재는 `data_collection/load_year_pbp.py` 를 그대로 부릅니다. 팀 별칭
해석과 포스트시즌 판정이 거기 있고, 규칙을 두 벌로 두면 갈라집니다.

**인덱스를 먼저 지웁니다.** play_by_play 에 인덱스가 3개라 행 하나에
쓰기가 4번 일어납니다. 220만 행이면 880만 번입니다. 지우고 넣은 뒤
다시 만드는 편이 훨씬 빠릅니다.

    py migration/load_backfill_local.py 2015 2024
"""
import argparse
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "database" / "kbo_stats.db"
DEFAULT_SAVE = ROOT / "crawler" / "save_backfill"


def indexes_of(conn, table):
    return [(r[0], r[1]) for r in conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' "
        "AND tbl_name=? AND sql IS NOT NULL", (table,))]


def season_counts(conn):
    return {r[0]: r[1] for r in conn.execute(
        "SELECT substr(gameID,1,4) AS s, COUNT(*) FROM play_by_play "
        "GROUP BY s ORDER BY s")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--save-root", default=str(DEFAULT_SAVE))
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    db = Path(args.db)
    years = list(range(args.start, args.end + 1))

    # 몇 시간짜리 대량 작업입니다. 중간에 잘못되면 되돌릴 것이 있어야
    # 합니다. 227MB 복사는 몇 초입니다.
    if not args.no_backup:
        bak = db.with_suffix(".db.bak_beforebackfill")
        if bak.exists():
            print("백업이 이미 있습니다: %s (덮지 않습니다)" % bak.name)
        else:
            t0 = time.time()
            shutil.copy2(db, bak)
            print("백업 %s (%.0fMB, %.0f초)"
                  % (bak.name, bak.stat().st_size / 1e6, time.time() - t0))

    conn = sqlite3.connect(str(db), timeout=300)
    before = season_counts(conn)
    print("적재 전 시즌: %s" % ", ".join(
        "%s(%s)" % (k, format(v, ",")) for k, v in before.items()))

    saved = indexes_of(conn, "play_by_play")
    print("인덱스 %d개를 지웁니다: %s"
          % (len(saved), ", ".join(n for n, _ in saved)))
    for name, _ in saved:
        conn.execute('DROP INDEX IF EXISTS "%s"' % name)
    conn.commit()
    conn.close()

    t_all = time.time()
    failed = []
    for i, y in enumerate(years, start=1):
        print()
        print("[%d/%d] %d 적재" % (i, len(years), y), flush=True)
        t0 = time.time()
        r = subprocess.run(
            [sys.executable, str(ROOT / "data_collection" / "load_year_pbp.py"),
             str(y), str(db), args.save_root],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", errors="replace")
        for line in (r.stdout or "").strip().splitlines():
            print("  " + line.strip(), flush=True)
        if r.returncode != 0:
            print("  실패 (종료코드 %d)" % r.returncode)
            print("  " + (r.stderr or "")[-400:])
            failed.append(y)
        print("  %.1f분" % ((time.time() - t0) / 60), flush=True)

    print()
    print("인덱스를 다시 만듭니다.", flush=True)
    conn = sqlite3.connect(str(db), timeout=3600)
    for name, sql in saved:
        t0 = time.time()
        conn.execute(sql)
        conn.commit()
        print("  %s  %.1f분" % (name, (time.time() - t0) / 60), flush=True)

    after = season_counts(conn)
    print()
    print("전체 %.1f분" % ((time.time() - t_all) / 60))
    print("시즌별 행 수")
    for s in sorted(after):
        mark = "  (새로 들어옴)" if s not in before else ""
        print("  %s  %10s행%s" % (s, format(after[s], ","), mark))
    total = sum(after.values())
    print("  합계 %s행" % format(total, ","))
    conn.close()
    print("DB 크기 %.0fMB" % (db.stat().st_size / 1e6))

    if failed:
        print("실패 시즌: %s" % failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
