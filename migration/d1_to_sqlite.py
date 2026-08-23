# -*- coding: utf-8 -*-
"""D1 을 내려받아 로컬 SQLite 를 만듭니다.

파크팩터·wRC+·RE24 재계산은 `play_by_play` 전체를 훑어야 합니다.
그런 계산을 D1 위에서 할 수는 없습니다. Worker 는 10ms CPU 제한이 있고,
D1 질의로 수십 번 왕복하면 읽기 한도를 태웁니다.

그래서 러너에서 D1 을 통째로 내려받아 SQLite 를 만들고, 기존 파이프라인을
그대로 돌린 뒤, 결과 표만 다시 올립니다. 파이프라인 스크립트들은
`KBO_DB` 환경변수를 보므로 코드를 고칠 필요가 없습니다.

`play_by_play` 는 공용 DB 에 없습니다. 시즌별 D1 네 개에 나뉘어 있어
네 곳에서 받아 한 표로 합칩니다. 배정표는 `migration/shard_plan.json`
이 정본입니다.

**읽기 비용을 알고 쓰십시오.** `play_by_play` 전량이 12시즌이면 약
272만 행입니다. 하루 한도가 500만 행이라 이걸 하루에 두 번 돌리면
위험합니다. 주 1회로 두십시오.

    py migration/d1_to_sqlite.py --out /tmp/kbo.db
    py migration/d1_to_sqlite.py --out /tmp/kbo.db --tables games,teams
"""
import argparse
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migration import shard_plan  # noqa: E402

DB_NAME = "kbo-stats"

# 리스트 + shell=True 는 윈도우와 POSIX 가 다르게 동작합니다. POSIX 는
# 첫 항목만 실행하고 나머지를 버려서, 러너에서는 `npx` 만 돌고 끝납니다.
# 자세한 사정은 data_collection/d1_load.py 의 USE_SHELL 주석에 있습니다.
USE_SHELL = os.name == "nt"

# 이 표들은 공용 DB 에 없고 시즌별 D1 네 개에 나뉘어 있습니다.
# 한 곳만 받으면 조용히 1/4 만 계산됩니다.
SHARDED_TABLES = {"play_by_play"}

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
    # wOBA 가중치입니다. build_woba_weights.py 가 다시 만들지만,
    # 만들기 전에 표가 있어야 롤링 백업(_bak)을 뜰 수 있습니다.
    "kbo_woba_weights_by_season",
    "wrc_plus_comparison",
    "weighted_pf_by_batter_season",
    # RE24 산출물입니다. build_re24_run_values.py 가 다시 만들지만,
    # 만들기 전에 롤링 백업(_bak)을 뜨느라 표가 먼저 있어야 합니다.
    # 이것을 빠뜨려 주간 워크플로가 `no such table` 로 죽었습니다.
    "kbo_run_values_by_season",
    "re24_matrix_by_season",
]


def export_table(table, out_dir, db_name=DB_NAME, tag=None):
    """표 하나를 한 D1 에서 SQL 로 내려받습니다."""
    dst = out_dir / ("%s.sql" % (tag or table))
    cmd = ["npx", "--yes", "wrangler@4", "d1", "export", db_name,
           "--remote", "--table", table, "--output", str(dst)]
    t0 = time.time()
    r = subprocess.run(cmd, capture_output=True, text=True, shell=USE_SHELL,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("%s(%s) 내려받기 실패: %s"
                           % (table, db_name, (r.stderr or r.stdout)[-400:]))
    return dst, time.time() - t0


# 나뉜 표는 파일 네 개를 같은 SQLite 에 이어 넣습니다. 두 번째 파일부터
# CREATE 가 "already exists" 로 죽으므로 IF NOT EXISTS 를 붙입니다.
#
# **줄 첫머리에 있는 CREATE 만 바꿉니다.** 처음에는 아무 데나 바꾸게
# 짰는데, 그러면 `INSERT ... VALUES ('CREATE TABLE x')` 처럼 값 안에
# 든 글자까지 바꿔 데이터를 조용히 망가뜨립니다. 테스트가 잡았습니다.
# wrangler 덤프는 문마다 줄을 새로 시작하므로 줄머리로 한정하면 값은
# 안전합니다. 실측으로도 확인했습니다. `play_by_play` 74개 컬럼
# 272만 행 가운데 'CREATE' 가 든 값 0건, 줄바꿈이 든 값 0건입니다.
_CREATE = re.compile(
    r"^([ \t]*)CREATE\s+(TABLE|VIEW|TRIGGER|(?:UNIQUE\s+)?INDEX)\s+"
    r"(?!IF\s+NOT\s+EXISTS)",
    re.IGNORECASE | re.MULTILINE)


def idempotent_ddl(sql):
    return _CREATE.sub(
        lambda m: "%sCREATE %s IF NOT EXISTS " % (m.group(1), m.group(2)), sql)


def export_jobs(tables):
    """(표, D1 이름, 파일이름) 목록입니다. 나뉜 표는 샤드마다 하나씩.

    샤드는 하나의 원본 표를 시즌으로 갈라 담았고 `pbp_id` 를 그대로
    옮겼습니다. 그래서 샤드끼리 번호가 겹치지 않고, 합쳐도 PK 가
    부딪히지 않습니다. 나중에 지난 시즌을 샤드에 새로 넣으면 그 샤드가
    자기 최대값 다음 번호를 붙이므로 겹칠 수 있습니다. 그때는 아래
    executescript 가 UNIQUE 위반으로 시끄럽게 실패합니다. 조용히
    덮어써서 행을 잃는 것보다 낫습니다.
    """
    jobs = []
    for t in tables:
        if t in SHARDED_TABLES:
            for s in shard_plan.shards():
                jobs.append((t, s["database"], "%s__%s" % (t, s["binding"])))
        else:
            jobs.append((t, DB_NAME, t))
    return jobs


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
        jobs = export_jobs(tables)
        for i, (t, db, tag) in enumerate(jobs, start=1):
            path, secs = export_table(t, work, db_name=db, tag=tag)
            size = path.stat().st_size
            total_bytes += size
            sql = idempotent_ddl(
                path.read_text(encoding="utf-8", errors="replace"))
            # executescript 는 하나의 트랜잭션으로 돌립니다. 중간에
            # 실패하면 그 조각은 통째로 안 들어갑니다. 부분 적재보다
            # 낫습니다.
            conn.executescript(sql)
            conn.commit()
            n = conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
            label = t if db == DB_NAME else "%s <- %s" % (t, db)
            print("[%2d/%d] %-38s %9s행(누적)  %6.1fMB  %.0f초"
                  % (i, len(jobs), label, format(n, ","),
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
