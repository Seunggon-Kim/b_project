# -*- coding: utf-8 -*-
"""2008~2014 PBP 를 하루 예산만큼씩 D1 에 밀어 넣습니다.

## 왜 나눠 넣나

D1 무료는 **하루 10만 행 쓰기**입니다. 그런데 한 행을 넣을 때 계상되는
쓰기는 `1 + 인덱스 수` 입니다. `play_by_play` 는 인덱스가 셋이라
**행당 4** 입니다. 실측했습니다.

    50행 INSERT -> rows_written 201   (4.02배)

2008~2014 는 약 120만 행이라 계상 쓰기가 480만입니다. 하루 한도로는
한 번에 못 넣습니다. 약 51일 걸립니다.

## 인덱스를 나중에 만들 수는 없습니다

"인덱스 없이 넣고 마지막에 만들면 되지 않나" 는 막힙니다. 1,000행
표에 `CREATE INDEX` 하나를 돌리면 `rows_written` 이 1,001 입니다.
120만 행이면 단일 DDL 하나가 하루 한도를 그 자체로 넘는데, DDL 은
며칠에 나눠 실행할 수 없습니다. 먼저 만들어 두면 같은 비용이 행
단위로 쪼개져 여러 날에 나뉩니다.

## 어떻게 이어 가나

진행 위치는 D1 `kbo-stats` 의 `meta_backfill` 에 날짜로 남습니다.
파일이 아니라 D1 에 두는 이유는 GitHub Actions 러너가 매번 새로
시작해 로컬 파일이 안 남기 때문입니다.

한 번 돌 때마다 이렇게 합니다.

    1. 커서(마지막으로 끝낸 날짜) 다음 날짜들을 games 에서 읽습니다
    2. 예산에 맞는 만큼만 고릅니다 (경기 수 x 310행으로 어림)
    3. 그 날짜들을 크롤러로 받습니다 (이미 있으면 건너뜁니다)
    4. 해당 시즌 샤드에 넣습니다
    5. 커서를 옮깁니다

중간에 끊겨도 커서가 안 옮겨져 다음 날 같은 자리에서 다시 합니다.
이미 들어간 경기는 gameID 로 걸러 두 번 넣지 않습니다.

    py migration/shard_backfill.py --dry-run
    py migration/shard_backfill.py --budget 23000
"""
import argparse
import csv
import datetime
import io
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query, run_d1, run_d1_file  # noqa: E402

PLAN = json.loads((ROOT / "migration" / "shard_plan.json")
                  .read_text(encoding="utf-8"))

FIRST, LAST = 2008, 2014

# 한 경기 평균 행 수입니다. 2008 표본 15경기에서 310.0 이었습니다.
# 예산을 넘기지 않으려고 넉넉히 잡습니다.
ROWS_PER_GAME = 330

# D1 무료 한도는 하루 10만 **계상 쓰기** 입니다. 인덱스 3개라 실제
# 행 하나가 4로 계상됩니다. daily 수집이 하루 3,000 쯤 쓰므로 그만큼
# 비워 둡니다.
#
#     (100,000 - 8,000) / 4 = 23,000
DEFAULT_BUDGET_ROWS = 23000

# 한 문의 상한은 100,000바이트입니다. 50행이 약 20,000바이트였으니
# 200행이면 한도에 닿습니다. 절반만 씁니다.
MAX_STATEMENT_BYTES = 45000


def shard_for(season):
    """그 시즌 PBP 가 들어갈 D1 이름입니다."""
    for s in PLAN["shards"]:
        if int(season) in s["seasons"]:
            return s["database"]
    return None


def ensure_cursor_table():
    run_d1("CREATE TABLE IF NOT EXISTS meta_backfill ("
           "name TEXT PRIMARY KEY, last_date INTEGER NOT NULL, "
           "rows_loaded INTEGER NOT NULL DEFAULT 0, updated_at TEXT);")


def read_cursor():
    """마지막으로 끝낸 날짜입니다. 시작 전이면 0 입니다."""
    rows = query("SELECT last_date, rows_loaded FROM meta_backfill "
                 "WHERE name='pbp_2008_2014';")
    if not rows:
        return 0, 0
    return int(rows[0]["last_date"] or 0), int(rows[0]["rows_loaded"] or 0)


def write_cursor(last_date, rows_loaded):
    run_d1("INSERT INTO meta_backfill (name, last_date, rows_loaded, updated_at) "
           "VALUES ('pbp_2008_2014', %d, %d, datetime('now')) "
           "ON CONFLICT(name) DO UPDATE SET last_date=excluded.last_date, "
           "rows_loaded=excluded.rows_loaded, updated_at=excluded.updated_at;"
           % (int(last_date), int(rows_loaded)))


def pending_dates(cursor):
    """아직 안 넣은 날짜와 그날 경기 수입니다."""
    return query(
        "SELECT game_date AS d, season, COUNT(*) AS games FROM games "
        "WHERE season BETWEEN %d AND %d AND game_date > %d "
        "GROUP BY game_date, season ORDER BY game_date;"
        % (FIRST, LAST, int(cursor)))


def pick_window(rows, budget):
    """예산에 맞는 만큼만 앞에서 잘라 옵니다.

    한 시즌 안에서만 자릅니다. 시즌이 바뀌면 샤드도 바뀌어 한 번에
    처리하면 어느 DB 에 넣을지 갈립니다.
    """
    if not rows:
        return [], 0
    season = rows[0]["season"]
    picked, est = [], 0
    for r in rows:
        if r["season"] != season:
            break
        cost = int(r["games"]) * ROWS_PER_GAME
        if picked and est + cost > budget:
            break
        picked.append(r)
        est += cost
        if est >= budget:
            break
    return picked, est


def crawl(lo, hi, save_root):
    """그 구간 경기를 받습니다. 이미 있는 것은 크롤러가 건너뜁니다."""
    cmd = [sys.executable, str(ROOT / "crawler" / "pbp.py"),
           "-f", str(lo), "-t", str(hi), "-d", str(save_root) + "/", "-p"]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    for line in (r.stdout or "").splitlines():
        if "download_pbp_files" in line:
            print("  " + line.strip())
    if r.returncode != 0:
        print("  수집 실패 (종료코드 %d)" % r.returncode)
        print("  " + (r.stderr or "")[-300:])
        return False
    return True


def read_csv_rows(path):
    """cp949 로 먼저, 안 되면 utf-8 로 읽습니다."""
    for enc in ("cp949", "utf-8"):
        try:
            with io.open(path, encoding=enc) as f:
                return list(csv.DictReader(f))
        except (UnicodeDecodeError, LookupError):
            continue
    return []


def lit(v):
    if v is None or v == "":
        return "NULL"
    s = str(v)
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return s
    return "'" + s.replace("'", "''") + "'"


def build_inserts(cols, rows):
    """INSERT 문 여러 개로 나눕니다. 한 문이 상한을 넘지 않게 합니다."""
    head = 'INSERT INTO "play_by_play" (%s) VALUES ' % (
        ",".join('"%s"' % c for c in cols))
    out, buf, size = [], [], 0
    for r in rows:
        piece = "(%s)" % ",".join(lit(r.get(c)) for c in cols)
        if buf and size + len(piece) + 1 > MAX_STATEMENT_BYTES:
            out.append(head + ",".join(buf) + ";")
            buf, size = [], 0
        buf.append(piece)
        size += len(piece) + 1
    if buf:
        out.append(head + ",".join(buf) + ";")
    return out


def already_in(db_name, game_ids):
    """샤드에 이미 있는 gameID 집합입니다."""
    if not game_ids:
        return set()
    ids = ",".join("'%s'" % g.replace("'", "''") for g in game_ids)
    rows = query("SELECT DISTINCT gameID AS g FROM play_by_play "
                 "WHERE gameID IN (%s);" % ids, db_name=db_name)
    return {r["g"] for r in rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET_ROWS,
                    help="이번에 넣을 실제 행 수 상한 (계상 쓰기는 4배)")
    ap.add_argument("--save-dir", default="crawler/save")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true",
                    help="이미 받아 둔 CSV 만 씁니다")
    args = ap.parse_args()

    save_root = ROOT / args.save_dir
    ensure_cursor_table()
    cursor, done_rows = read_cursor()

    left = query("SELECT COUNT(*) AS n FROM games WHERE season BETWEEN %d AND %d "
                 "AND game_date > %d;" % (FIRST, LAST, cursor))[0]["n"]
    total = query("SELECT COUNT(*) AS n FROM games WHERE season BETWEEN %d AND %d;"
                  % (FIRST, LAST))[0]["n"]
    print("커서 %s  남은 경기 %s / %s  누적 %s행"
          % (cursor or "(시작 전)", format(left, ","), format(total, ","),
             format(done_rows, ",")))
    if not left:
        print("모두 끝났습니다.")
        return 0

    dates = pending_dates(cursor)
    window, est = pick_window(dates, args.budget)
    if not window:
        print("넣을 날짜가 없습니다.")
        return 0

    lo, hi = window[0]["d"], window[-1]["d"]
    season = window[0]["season"]
    db_name = shard_for(season)
    games = sum(int(r["games"]) for r in window)
    print("이번 구간 %s ~ %s  (%d일, %d경기, 약 %s행 예상)"
          % (lo, hi, len(window), games, format(est, ",")))
    print("대상 D1: %s (%d시즌)" % (db_name, season))
    if not db_name:
        print("배정표에 그 시즌이 없습니다. shard_plan.json 을 보십시오.")
        return 1
    if args.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0

    if not args.skip_crawl and not crawl(lo, hi, save_root):
        return 1

    ydir = save_root / str(season)
    want = {str(r["d"]) for r in window}
    files = sorted(f for f in ydir.glob("*.csv") if f.stem[:8] in want) \
        if ydir.is_dir() else []
    if not files:
        print("CSV 가 없습니다: %s" % ydir)
        return 1

    have = already_in(db_name, [f.stem for f in files])
    files = [f for f in files if f.stem not in have]
    if have:
        print("  이미 들어간 경기 %d개는 건너뜁니다." % len(have))

    rows, cols = [], None
    for f in files:
        rs = read_csv_rows(f)
        if not rs:
            print("  읽기 실패: %s" % f.name)
            continue
        if cols is None:
            cols = [c for c in rs[0] if c]
        rows.extend(rs)

    if not rows:
        print("넣을 행이 없습니다. 커서만 옮깁니다.")
        write_cursor(hi, done_rows)
        return 0

    stmts = build_inserts(cols, rows)
    out = ROOT / "migration" / "_backfill_chunk.sql"
    out.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
    print("  %s행, INSERT 문 %d개, %.1fMB"
          % (format(len(rows), ","), len(stmts), out.stat().st_size / 1048576))

    t0 = datetime.datetime.now()
    run_d1_file(out, db_name=db_name)
    secs = (datetime.datetime.now() - t0).total_seconds()

    write_cursor(hi, done_rows + len(rows))
    print("  적재 완료 %.0f초. 계상 쓰기 약 %s"
          % (secs, format(len(rows) * 4, ",")))

    after = query("SELECT COUNT(*) AS n FROM games WHERE season BETWEEN %d AND %d "
                  "AND game_date > %d;" % (FIRST, LAST, hi))[0]["n"]
    days = (after / max(games, 1))
    print("남은 경기 %s (이 속도면 약 %.0f회 더)" % (format(after, ","), days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
