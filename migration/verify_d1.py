# -*- coding: utf-8 -*-
"""로컬 SQLite 와 D1 의 테이블별 행 수를 대조합니다.

적재가 끝났는지, 중간에 빠진 청크가 없는지 확인하는 용도입니다.
행 수만 봅니다. 내용 일치는 골든 응답 비교(`golden_compare.py`)가 맡습니다.
"""
import argparse
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

# `py migration/verify_d1.py` 로 직접 실행하면 sys.path 에 migration/ 만 들어가고
# 저장소 루트가 빠져 아래 import 가 실패합니다. 루트를 먼저 넣어 둡니다.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from migration.export_to_d1 import TABLE_ORDER  # noqa: E402


def parse_d1_json(raw):
    """`wrangler d1 execute --json` 출력에서 결과 행 목록을 꺼냅니다.

    wrangler 는 결과를 배열로 감싸고, 앞에 진행 메시지를 붙일 때가 있습니다.
    SQL 문을 여러 개 보내면 배열 원소도 문 수만큼 늘어나므로 전부 모읍니다.
    """
    start = raw.find("[")
    if start < 0:
        raise ValueError("JSON 을 찾지 못했습니다: %s" % raw[:200])
    data = json.loads(raw[start:])
    if not isinstance(data, list):
        return []
    rows = []
    for item in data:
        if isinstance(item, dict):
            rows.extend(item.get("results", []))
    return rows


def local_counts(conn, tables):
    """로컬에 실제로 있는 테이블만 세어 돌려줍니다."""
    have = {
        name
        for (name,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    }
    return {
        t: conn.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        for t in tables
        if t in have
    }


def compare_counts(local, remote):
    """다른 것만 (테이블, 로컬, 원격) 목록으로 돌려줍니다."""
    return [
        (t, n, remote.get(t, 0))
        for t, n in local.items()
        if remote.get(t, 0) != n
    ]


# D1 은 UNION ALL 항이 많으면 `too many terms in compound SELECT` 를 냅니다.
# 실측상 17개는 거부되므로 작게 묶어 나눠 보냅니다.
UNION_CHUNK = 5


def remote_counts(db_name, tables):
    """D1 에 테이블별 행 수를 물어 옵니다.

    `--file` 로 여러 문을 보내면 wrangler 가 개별 결과 대신 요약만 돌려줘서
    조회에 쓸 수 없습니다. `--command` 로 보내되, 셸이 따옴표를 먹지 않도록
    테이블 이름에 큰따옴표를 두르지 않습니다(모두 평범한 식별자입니다).
    """
    counts = {}
    for i in range(0, len(tables), UNION_CHUNK):
        group = tables[i:i + UNION_CHUNK]
        sql = " UNION ALL ".join(
            "SELECT '%s' AS t, COUNT(*) AS n FROM %s" % (t, t) for t in group
        )
        cmd = 'npx wrangler d1 execute %s --remote --command "%s" --yes --json' % (
            db_name, sql)
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                                encoding="utf-8", errors="replace")
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or "")[:800])
        for r in parse_d1_json(result.stdout):
            if "t" in r and "n" in r:
                counts[r["t"]] = r["n"]
    return counts


def main():
    ap = argparse.ArgumentParser(description="로컬과 D1 의 행 수를 대조합니다")
    ap.add_argument("--db", default="kbo-stats")
    ap.add_argument("--local-db", default="database/kbo_stats.db")
    args = ap.parse_args()

    conn = sqlite3.connect(args.local_db)
    local = local_counts(conn, TABLE_ORDER)
    conn.close()

    remote = remote_counts(args.db, list(local))

    print("%-32s %12s %12s" % ("테이블", "로컬", "D1"))
    print("-" * 58)
    for t, n in local.items():
        r = remote.get(t, 0)
        mark = "" if r == n else "   <- 다름"
        print("%-32s %12s %12s%s" % (t, format(n, ","), format(r, ","), mark))

    diffs = compare_counts(local, remote)
    print()
    if diffs:
        print("불일치 %d건" % len(diffs))
        for t, a, b in diffs:
            print("  %s: 로컬 %s, D1 %s (차이 %s)" % (
                t, format(a, ","), format(b, ","), format(a - b, ",")))
        return 1
    print("불일치 0건")
    return 0


if __name__ == "__main__":
    sys.exit(main())
