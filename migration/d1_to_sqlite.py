# -*- coding: utf-8 -*-
"""D1 을 내려받아 로컬 SQLite 를 만듭니다.

파크팩터·wRC+·RE24 재계산은 `play_by_play` 전체를 훑어야 합니다.
그런 계산을 D1 위에서 할 수는 없습니다. Worker 는 10ms CPU 제한이 있고,
D1 질의로 수십 번 왕복하면 읽기 한도를 태웁니다.

그래서 러너에서 D1 을 통째로 내려받아 SQLite 를 만들고, 기존 파이프라인을
그대로 돌린 뒤, 결과 표만 다시 올립니다. 파이프라인 스크립트들은
`KBO_DB` 환경변수를 보므로 코드를 고칠 필요가 없습니다.

**읽기 비용을 알고 쓰십시오.** `play_by_play` 전량이 12시즌이면 약
276만 행입니다. 하루 한도가 500만 행이라 이걸 하루에 두 번 돌리면
위험합니다. 주 1회로 두십시오.

    py migration/d1_to_sqlite.py --out /tmp/kbo.db
    py migration/d1_to_sqlite.py --out /tmp/kbo.db --tables games,teams
"""
import argparse
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DB_NAME = "kbo-stats"

# 파크팩터 파이프라인이 읽는 표입니다. 전부 받지 않는 이유는
# player_news(1.26MB)처럼 계산에 쓰이지 않는 표까지 받을 이유가
# 없기 때문입니다.
PIPELINE_TABLES = [
    "play_by_play",
    "games",
    "teams",
    "kbo_official_batter_stats",
    "kbo_official_pitcher_stats",
    "team_stadium_by_season",
    "stadium_dim",
    "statiz_park_factor",
    "statiz_yearly_constants",
    "self_park_factor",
    "wrc_plus_comparison",
    "weighted_pf_by_batter_season",
]


def export_table(table, out_dir):
    """표 하나를 SQL 로 내려받습니다."""
    dst = out_dir / ("%s.sql" % table)
    cmd = ["npx", "--yes", "wrangler@4", "d1", "export", DB_NAME,
           "--remote", "--table", table, "--output", str(dst)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("%s 내려받기 실패: %s"
                           % (table, (r.stderr or r.stdout)[-400:]))
    return dst, time.time() - t0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, help="만들 SQLite 경로")
    ap.add_argument("--tables", default=None,
                    help="쉼표로 구분. 기본값은 파이프라인이 읽는 표 전부")
    ap.add_argument("--keep-sql", action="store_true",
                    help="내려받은 SQL 파일을 지우지 않습니다")
    args = ap.parse_args()

    tables = ([t.strip() for t in args.tables.split(",") if t.strip()]
              if args.tables else PIPELINE_TABLES)

    out = Path(args.out)
    if out.exists():
        # 이어붙이면 이전 실행의 행이 남아 계산이 어긋납니다.
        out.unlink()
    out.parent.mkdir(parents=True, exist_ok=True)

    work = Path(tempfile.mkdtemp(prefix="d1dump_"))
    try:
        conn = sqlite3.connect(str(out))
        total_bytes = 0
        for i, t in enumerate(tables, start=1):
            path, secs = export_table(t, work)
            size = path.stat().st_size
            total_bytes += size
            sql = path.read_text(encoding="utf-8", errors="replace")
            # executescript 는 하나의 트랜잭션으로 돌립니다. 중간에
            # 실패하면 그 표는 통째로 안 들어갑니다. 부분 적재보다
            # 낫습니다.
            conn.executescript(sql)
            conn.commit()
            n = conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            print("[%2d/%d] %-30s %9s행  %6.1fMB  %.0f초"
                  % (i, len(tables), t, format(n, ","),
                     size / 1e6, secs), flush=True)
            if not args.keep_sql:
                path.unlink()
        conn.close()
    finally:
        if not args.keep_sql:
            shutil.rmtree(work, ignore_errors=True)
        else:
            print("SQL 남김: %s" % work)

    print()
    print("만든 DB: %s (%.1fMB)" % (out, out.stat().st_size / 1e6))
    print("내려받은 SQL 합계 %.1fMB" % (total_bytes / 1e6))
    print("파이프라인 실행: KBO_DB=%s 로 두고 park_factors/*.py 를 부르십시오."
          % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
