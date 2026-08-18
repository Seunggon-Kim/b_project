# -*- coding: utf-8 -*-
"""로컬 SQLite 의 play_by_play 를 시즌별 D1 샤드로 넣습니다.

## 왜 나누는가

`play_by_play` 한 표가 D1 한 DB 한도(500MB)를 넘습니다. 12시즌이면 약
1.5GB 입니다. 표를 쪼갤 수는 없으니 DB 를 나눕니다.

## 순서

시즌 하나마다: 로컬에서 뽑기 -> 청크 SQL -> 담당 샤드에 적재.
샤드 하나가 끝나면 인덱스를 만듭니다.

**인덱스를 나중에 만드는 이유가 있습니다.** 행 하나를 넣을 때 D1 의
쓰기 계상은 `1 + 인덱스 수` 입니다. 인덱스 3개를 미리 만들어 두면
270만 행 × 4 = 1,080만 쓰기입니다. 나중에 만들면 270만입니다.

    py migration/shard_load.py --dry-run     # 계획만 봅니다
    py migration/shard_load.py               # 전부
    py migration/shard_load.py --only 2015-2017
"""
import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from migration import shard_plan  # noqa: E402
from migration.export_to_d1 import export_table  # noqa: E402

SHARED_DB = "kbo-stats"

# 샤드에 둘 표입니다.
#
# games 를 복제하는 이유는 `teamrange.js` 가 `play_by_play JOIN games` 를
# 하기 때문입니다. D1 은 DB 를 가로지르는 조인을 못 합니다. 시즌당 15KB 라
# 용량은 문제가 안 됩니다. **공용 DB 의 games 가 정본이고 여기 것은
# 사본입니다.**
#
# teams 가 끼어 있는 이유는 games 가 teams 를 FOREIGN KEY 로 참조하기
# 때문입니다. 없으면 games 를 만들 때 `no such table: main.teams` 로
# 실패합니다. 10행짜리라 부담이 없습니다.
SHARD_TABLES = ["play_by_play", "games", "teams", "meta_table_counts"]

# 샤드를 만들 때 공용 DB 에서 통째로 복사할 표입니다. 시즌으로 자를 수
# 없고 작습니다.
COPY_WHOLE = ["teams"]

# 적재가 끝난 뒤에 만들 인덱스입니다.
DEFER_INDEX_TABLES = {"play_by_play"}

# 파일 하나에 담을 행 수. 기본값 1,000 은 하루 예산을 세기 좋지만
# 파일이 700개가 되어 wrangler 를 700번 띄우게 됩니다. 한 번에 다 넣는
# 지금은 크게 잡는 편이 훨씬 빠릅니다.
ROWS_PER_FILE = 10_000


def run(cmd, timeout=3600):
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout)[-500:])
    return r.stdout


def d1(db, sql=None, file=None, json_out=False):
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", db, "--remote", "--yes"]
    if file:
        cmd += ["--file", str(file)]
    else:
        cmd += ["--command", sql]
    if json_out:
        cmd.append("--json")
    return run(cmd)


def query(db, sql):
    out = d1(db, sql=sql, json_out=True)
    return json.loads(out[out.find("["):])[0]["results"]


def source_ddl():
    """공용 DB 에서 표·인덱스 정의를 그대로 가져옵니다.

    직접 적지 않는 이유는, 스키마가 갈라지면 골든 비교가 통과해도
    다른 표가 되기 때문입니다.
    """
    rows = query(SHARED_DB,
                 "SELECT type, name, tbl_name, sql FROM sqlite_master "
                 "WHERE sql IS NOT NULL ORDER BY type DESC, name;")
    tables, indexes = [], []
    for r in rows:
        if r["tbl_name"] not in SHARD_TABLES:
            continue
        (tables if r["type"] == "table" else indexes).append(r)
    return tables, indexes


def ensure_schema(db, tables, indexes, defer_idx=True):
    """샤드에 표를 만듭니다. 있으면 그대로 둡니다."""
    stmts = []
    for t in tables:
        stmts.append(t["sql"].replace("CREATE TABLE",
                                      "CREATE TABLE IF NOT EXISTS", 1) + ";")
    for i in indexes:
        if defer_idx and i["tbl_name"] in DEFER_INDEX_TABLES:
            continue
        stmts.append(i["sql"].replace("CREATE INDEX",
                                      "CREATE INDEX IF NOT EXISTS", 1) + ";")
    path = ROOT / "migration" / "_shard_schema.sql"
    path.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
    d1(db, file=path)
    return len(stmts)


def make_indexes(db, indexes):
    made = []
    for i in indexes:
        if i["tbl_name"] not in DEFER_INDEX_TABLES:
            continue
        t0 = time.time()
        d1(db, sql=i["sql"].replace("CREATE INDEX",
                                    "CREATE INDEX IF NOT EXISTS", 1) + ";")
        made.append((i["name"], time.time() - t0))
    return made


def copy_whole_table(conn, db, table):
    """작은 표를 공용 DB 내용 그대로 샤드에 넣습니다.

    로컬 SQLite 를 원천으로 씁니다. 공용 D1 에서 읽으면 읽기 한도를
    쓰는데, 로컬이 같은 내용이고 공짜입니다.
    """
    sys.path.insert(0, str(ROOT / "data_collection"))
    from d1_load import build_inserts  # noqa: E402

    cols = [r[1] for r in conn.execute('PRAGMA table_info("%s")' % table)]
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute('SELECT * FROM "%s"' % table)]
    conn.row_factory = None
    lines = ['DELETE FROM "%s";' % table] + build_inserts(table, cols, rows)
    path = ROOT / "migration" / ("_copy_%s.sql" % table)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    d1(db, file=path)
    return len(rows)


def export_season(conn, season, out_dir, rows_per_file):
    """한 시즌의 play_by_play + games 를 청크로 뽑습니다."""
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    manifest = {"season": season, "files": []}
    total = 0
    # games 를 먼저 넣습니다. 참조 순서를 지킵니다.
    for order, (table, where) in enumerate([
        ("games", "season = %d" % season),
        ("play_by_play", shard_plan.pbp_where(season)),
    ], start=1):
        n = conn.execute('SELECT COUNT(*) FROM "%s" WHERE %s'
                         % (table, where)).fetchone()[0]
        if not n:
            continue
        pairs = export_table(conn, table, out_dir, rows_per_file=rows_per_file,
                             order=order, where=where)
        for path, rows in pairs:
            manifest["files"].append({
                "name": path.name, "table": table, "rows": rows,
                "bytes": path.stat().st_size,
            })
        total += n
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return total, manifest


def load_dir(db, out_dir):
    """청크 파일을 순서대로 넣습니다. 이미 넣은 것은 건너뜁니다."""
    progress = out_dir / ".progress"
    done = set(progress.read_text(encoding="utf-8").split()) \
        if progress.exists() else set()
    files = sorted(f for f in out_dir.glob("*.sql") if f.name != "manifest.json")
    todo = [f for f in files if f.name not in done]
    for i, f in enumerate(todo, start=1):
        t0 = time.time()
        d1(db, file=f)
        # 한 파일이 끝날 때마다 기록합니다. 중간에 죽어도 다시 넣지
        # 않습니다. 다시 넣으면 행이 두 배가 됩니다.
        with open(progress, "a", encoding="utf-8") as fh:
            fh.write(f.name + "\n")
        print("      [%d/%d] %s  %.0f초" % (i, len(todo), f.name,
                                            time.time() - t0), flush=True)
    return len(todo)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--local-db", default=str(ROOT / "database" / "kbo_stats.db"))
    ap.add_argument("--work", default=str(ROOT / "migration" / "shard_out"))
    ap.add_argument("--rows-per-file", type=int, default=ROWS_PER_FILE)
    ap.add_argument("--only", default=None,
                    help="샤드 이름 일부 (예: 2015-2017)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    problems = shard_plan.check()
    if problems:
        for p in problems:
            print("배정 문제: %s" % p)
        return 1

    conn = sqlite3.connect(args.local_db)
    targets = [s for s in shard_plan.shards()
               if not args.only or args.only in s["database"]]
    if not targets:
        print("해당하는 샤드가 없습니다: %s" % args.only)
        return 1

    print("=== 계획 ===")
    grand = 0
    for s in targets:
        sub = 0
        for y in s["seasons"]:
            n = conn.execute("SELECT COUNT(*) FROM play_by_play WHERE %s"
                             % shard_plan.pbp_where(y)).fetchone()[0]
            sub += n
        grand += sub
        print("  %-20s %s  %10s행  약 %.0fMB"
              % (s["database"], "·".join(str(y) for y in s["seasons"]),
                 format(sub, ","), sub * 571 / 1e6))
    print("  합계 %s행" % format(grand, ","))
    print()

    if args.dry_run:
        print("[dry-run] 넣지 않았습니다.")
        return 0

    tables, indexes = source_ddl()
    print("공용 DB 에서 가져온 정의: 표 %d개, 인덱스 %d개"
          % (len(tables), len(indexes)))

    t_all = time.time()
    work = Path(args.work)
    for s in targets:
        db = s["database"]
        print()
        print("=== %s ===" % db, flush=True)
        n = ensure_schema(db, tables, indexes)
        print("  스키마 %d문 적용 (pbp 인덱스는 나중에)" % n, flush=True)

        # games 의 FK 대상입니다. 시즌 청크보다 먼저 넣어야 참조가
        # 성립합니다.
        for t in COPY_WHOLE:
            copy_whole_table(conn, db, t)
            print("  %s 복사 완료" % t, flush=True)

        for y in s["seasons"]:
            out_dir = work / str(y)
            t0 = time.time()
            if (out_dir / "manifest.json").exists():
                man = json.loads((out_dir / "manifest.json")
                                 .read_text(encoding="utf-8"))
                total = sum(f["rows"] for f in man["files"])
                print("  %d  청크 재사용 (%s행)" % (y, format(total, ",")),
                      flush=True)
            else:
                total, man = export_season(conn, y, out_dir,
                                           args.rows_per_file)
                print("  %d  %s행 -> 파일 %d개  (%.1f분)"
                      % (y, format(total, ","), len(man["files"]),
                         (time.time() - t0) / 60), flush=True)
            t0 = time.time()
            k = load_dir(db, out_dir)
            print("  %d  파일 %d개 적재  %.1f분"
                  % (y, k, (time.time() - t0) / 60), flush=True)

        print("  인덱스를 만듭니다.", flush=True)
        for name, secs in make_indexes(db, indexes):
            print("    %s  %.1f분" % (name, secs / 60), flush=True)

        # 행 수 메타. 탐색기의 페이지 넘기기가 이 값을 씁니다.
        for t in ("play_by_play", "games"):
            d1(db, sql="INSERT OR REPLACE INTO meta_table_counts "
                       "SELECT '%s', COUNT(*), datetime('now') FROM \"%s\";"
                       % (t, t))

        # 대조. **한 시즌이 빠지거나 두 번 들어가는 것이 가장 흔한
        # 실수입니다.** 시즌별로 세어 봅니다.
        print("  대조", flush=True)
        ok = True
        for y in s["seasons"]:
            want = conn.execute("SELECT COUNT(*) FROM play_by_play WHERE %s"
                                % shard_plan.pbp_where(y)).fetchone()[0]
            got = query(db, "SELECT COUNT(*) AS n FROM play_by_play "
                            "WHERE %s;" % shard_plan.pbp_where(y))[0]["n"]
            mark = "일치" if want == got else "!!! 다름 !!!"
            if want != got:
                ok = False
            print("    %d  로컬 %10s / D1 %10s  %s"
                  % (y, format(want, ","), format(got, ","), mark), flush=True)
        tot = query(db, "SELECT COUNT(*) AS n FROM play_by_play;")[0]["n"]
        want_tot = sum(conn.execute(
            "SELECT COUNT(*) FROM play_by_play WHERE %s"
            % shard_plan.pbp_where(y)).fetchone()[0] for y in s["seasons"])
        print("    합계 로컬 %s / D1 %s  %s"
              % (format(want_tot, ","), format(tot, ","),
                 "일치" if tot == want_tot else "!!! 다름 !!!"), flush=True)
        if tot != want_tot:
            ok = False
        if not ok:
            print("  이 샤드는 대조에 실패했습니다. 멈춥니다.")
            conn.close()
            return 1

    conn.close()
    print()
    print("전체 %.1f분" % ((time.time() - t_all) / 60))
    return 0


if __name__ == "__main__":
    sys.exit(main())
