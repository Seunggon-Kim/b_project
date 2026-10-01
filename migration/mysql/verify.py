# -*- coding: utf-8 -*-
"""스냅샷과 MySQL 을 대조합니다.

표마다 행 수를, 열마다 '값 있는 칸 수' 와 합계(숫자) 또는 글자 길이 합
(글자·날짜·바이너리)을 양쪽에서 세어 견줍니다. 스냅샷 쪽은 적재 때와
같은 규칙으로 ''·'-' 를 값 없음으로 봅니다. play_by_play 는 경기(gameID)
별 행 수도 견줍니다. 새로 매긴 번호(pbp_id)는 견주지 않습니다.

    py -m migration.mysql.verify --snapshot ~/.bstats/snapshots/d1_20261002.db
"""
import argparse
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

from migration.mysql import conn as myconn
from migration.mysql.ddl import OUT_DIR, ROOT

REPORT = ROOT / "docs" / "mysql-migration" / "verify-report.md"


def sqlite_expr(col, kind):
    c = '"%s"' % col
    present = ("CASE WHEN typeof(%s)='text' AND trim(%s) IN ('','-') "
               "THEN NULL ELSE %s END" % (c, c, c))
    if kind in ("int", "double"):
        return "COUNT(%s)" % present, "TOTAL(CAST(%s AS REAL))" % present
    if kind in ("date", "datetime"):
        return "COUNT(%s)" % present, "TOTAL(length(trim(%s)))" % present
    return "COUNT(%s)" % c, "TOTAL(length(%s))" % c


def mysql_expr(col, kind):
    c = "`%s`" % col
    if kind in ("int", "double"):
        return "COUNT(%s)" % c, "SUM(%s)" % c
    if kind in ("date", "datetime"):
        return "COUNT(%s)" % c, "SUM(CHAR_LENGTH(CAST(%s AS CHAR)))" % c
    if kind == "blob":
        return "COUNT(%s)" % c, "SUM(LENGTH(%s))" % c
    return "COUNT(%s)" % c, "SUM(CHAR_LENGTH(%s))" % c


def close(a, b):
    """합계가 같은지 봅니다. 실수 덧셈 순서에서 오는 오차만 허용합니다."""
    a, b = float(a or 0), float(b or 0)
    return abs(a - b) <= max(1e-6, 1e-9 * max(abs(a), abs(b)))


def verify_table(sq, my, table, spec):
    cols = [(c, k) for c, k in spec["columns"] if c != spec.get("renumber")]
    s_parts, m_parts = ["COUNT(*)"], ["COUNT(*)"]
    for c, k in cols:
        s_parts.extend(sqlite_expr(c, k))
        m_parts.extend(mysql_expr(c, k))
    s = sq.execute('SELECT %s FROM "%s"' % (", ".join(s_parts), table)).fetchone()
    with my.cursor() as cur:
        cur.execute("SELECT %s FROM `%s`" % (", ".join(m_parts), table))
        m = cur.fetchone()
    problems = []
    if s[0] != m[0]:
        problems.append("행 수 %s / %s" % (format(s[0], ","), format(m[0], ",")))
    for i, (c, k) in enumerate(cols):
        sc, ss = s[1 + 2 * i], s[2 + 2 * i]
        mc, ms = m[1 + 2 * i], m[2 + 2 * i]
        if sc != mc:
            problems.append("%s: 값 있는 칸 %s / %s" % (c, sc, mc))
        elif not close(ss, ms):
            problems.append("%s: 합계 %s / %s" % (c, ss, ms))
    return s[0], m[0], problems


def verify_games(sq, my):
    s = dict(sq.execute('SELECT "gameID", COUNT(*) FROM play_by_play GROUP BY 1'))
    with my.cursor() as cur:
        cur.execute("SELECT `gameID`, COUNT(*) FROM `play_by_play` GROUP BY 1")
        m = {k: int(n) for k, n in cur.fetchall()}
    bad = sorted((g for g in set(s) | set(m) if s.get(g) != m.get(g)),
                 key=lambda g: str(g))
    return len(s), bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    sq = sqlite3.connect(Path(args.snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    my = myconn.connect()
    lines = ["# MySQL 대조 보고", "",
             "- 스냅샷: `%s`" % Path(args.snapshot).name,
             "- 대조 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
             "", "| 표 | 스냅샷 행 | MySQL 행 | 결과 |", "|---|---|---|---|"]
    failed = []
    for table, spec in types.items():
        srows, mrows, problems = verify_table(sq, my, table, spec)
        lines.append("| %s | %s | %s | %s |" % (
            table, format(srows, ","), format(mrows, ","),
            "같음" if not problems else "<br>".join(problems)))
        if problems:
            failed.append(table)
        print("%-34s %s" % (table, "같음" if not problems else "; ".join(problems)),
              flush=True)
    if "play_by_play" in types:
        games, bad = verify_games(sq, my)
        lines += ["", "경기별 플레이 수: %s경기 중 다른 경기 %d개%s" % (
            format(games, ","), len(bad),
            "" if not bad else " (" + ", ".join(str(g) for g in bad[:20]) + ")")]
        if bad:
            failed.append("play_by_play(경기별)")
    my.close()
    sq.close()
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("보고서: %s" % REPORT)
    print("결과: %s" % ("모두 같음" if not failed else "다름 - " + ", ".join(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
