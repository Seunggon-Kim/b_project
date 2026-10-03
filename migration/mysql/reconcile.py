# -*- coding: utf-8 -*-
"""D1 과 MySQL 을 대조합니다. 2단계 이중 적재 동안 매일 돕니다.

    py -m migration.mysql.reconcile               # 다르면 종료 코드 1
    py -m migration.mysql.reconcile --days 7      # 최근 7일 경기는 경기별 행 수까지

- play_by_play 를 뺀 모든 표: 양쪽 행 수.
- players·kbo_roster·kbo_roster_moves·games: 열쇠로 짝지어 값까지 견줍니다. 수집이
  UPDATE 로 고치는 표라 행 수만으로는 어긋남이 안 보입니다. created_at·
  updated_at 은 두 DB 가 따로 시각을 찍으므로 뺍니다.
- play_by_play: D1 샤드별 meta_table_counts 합과 MySQL 행 수. 최근 N일
  경기는 경기별 행 수.

D1 읽기는 하루 약 8만 3천 행입니다(무료 한도 500만의 1.7%). games 값 비교가
약 1만 3천 행입니다. 값 비교 규칙은
적재와 같습니다. ''·'-' 는 값 없음, 정수 열의 '7.0' 은 7 입니다.
"""
import argparse
import datetime
import decimal
import json
import os
import sys

from migration import shard_plan
from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, q

KST = datetime.timezone(datetime.timedelta(hours=9))
PBP = "play_by_play"
FULL = {"players": ["player_id"],
        "games": ["game_id"],
        "kbo_roster": ["team", "name", "back_number"],
        "kbo_roster_moves": ["move_date", "kind", "team", "name"]}
# 두 DB 가 일부러 다르게 쓰는 기록표입니다. meta_table_counts 는 D1 이 샤드별로,
# MySQL 은 표 하나로 play_by_play 행 수를 적습니다(play_by_play 는 따로 견줍니다).
COUNT_SKIP = {PBP, "meta_table_counts"}
# D1 이 29항 UNION 을 "too many terms in compound SELECT" 로 거절했습니다.
# 한 질의에 4항이면 안전합니다.
D1_UNION_MAX = 4
SKIP_COLS = {"created_at", "updated_at"}


def d1_query(sql, db_name=None):
    from data_collection.d1_load import DB_NAME, query
    return query(sql, db_name=db_name or DB_NAME)


def my_query(con, sql, params=None):
    with con.cursor() as cur:
        cur.execute(sql, params)
        names = [d[0] for d in cur.description]
        return [dict(zip(names, r)) for r in cur.fetchall()]


def canon(v):
    """견주기 위한 모양입니다. 두 DB 값 모두 이것을 거칩니다."""
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        v = v.decode("utf-8")
    if isinstance(v, str) and v in ("", "-"):
        return None
    if isinstance(v, datetime.datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(v, datetime.date):
        return v.isoformat()
    if isinstance(v, decimal.Decimal):
        v = float(v)
    if isinstance(v, float):
        return int(v) if v.is_integer() else round(v, 9)
    return v


def d1_value(v, kind):
    """D1 값을 MySQL 에 들어갔을 모양으로 바꿉니다(적재와 같은 규칙)."""
    try:
        return canon(tm.normalize(canon(v), kind))
    except ValueError:
        return ("바꿀 수 없음", v)


def compare_counts(d1, my):
    out = []
    for t in sorted(set(d1) | set(my)):
        if d1.get(t) != my.get(t):
            out.append("%s 행 수: D1 %s / MySQL %s" % (t, d1.get(t), my.get(t)))
    return out


def _keyed(rows, cols, keys, conv):
    out = {}
    for r in rows:
        vals = {c: conv(c, r.get(c)) for c in cols}
        out[tuple(vals[k] for k in keys)] = tuple(vals[c] for c in cols)
    return out


def compare_keyed(table, cols, keys, d1_rows, my_rows, kinds):
    a = _keyed(d1_rows, cols, keys, lambda c, v: d1_value(v, kinds[c]))
    b = _keyed(my_rows, cols, keys, lambda c, v: canon(v))
    out = []
    only_a = sorted(set(a) - set(b), key=repr)
    only_b = sorted(set(b) - set(a), key=repr)
    diff = sorted((k for k in set(a) & set(b) if a[k] != b[k]), key=repr)
    if only_a:
        out.append("%s: D1 에만 %d행 (예: %s)" % (table, len(only_a), only_a[:3]))
    if only_b:
        out.append("%s: MySQL 에만 %d행 (예: %s)" % (table, len(only_b), only_b[:3]))
    for k in diff[:5]:
        cols_diff = [c for c, x, y in zip(cols, a[k], b[k]) if x != y]
        out.append("%s %s: 값이 다름 %s" % (table, k, ", ".join(cols_diff)))
    if len(diff) > 5:
        out.append("%s: 값이 다른 행 %d개 더" % (table, len(diff) - 5))
    return out


def count_sql(tables, quote):
    return " UNION ALL ".join("SELECT '%s' AS t, COUNT(*) AS n FROM %s" % (t, quote(t))
                              for t in tables)


def check(my, types, days):
    """다른 곳 목록과 견준 최근 경기 수를 돌려줍니다."""
    tables = [t for t in types if t not in COUNT_SKIP]
    problems = []

    d1c = {}
    for i in range(0, len(tables), D1_UNION_MAX):
        sql = count_sql(tables[i:i + D1_UNION_MAX], lambda t: '"%s"' % t) + ";"
        d1c.update({r["t"]: int(r["n"]) for r in d1_query(sql)})
    myc = {r["t"]: int(r["n"]) for r in my_query(my, count_sql(tables, q))}
    problems += compare_counts(d1c, myc)

    for table, keys in FULL.items():
        kinds = dict(types[table]["columns"])
        cols = [c for c in kinds if c not in SKIP_COLS]
        d1rows = d1_query('SELECT %s FROM "%s";' % (", ".join('"%s"' % c for c in cols), table))
        myrows = my_query(my, "SELECT %s FROM %s" % (", ".join(q(c) for c in cols), q(table)))
        problems += compare_keyed(table, cols, keys, d1rows, myrows, kinds)

    d1_pbp = 0
    for s in shard_plan.shards():
        rows = d1_query("SELECT n FROM meta_table_counts WHERE name='play_by_play';",
                        s["database"])
        if not rows:
            problems.append("%s: meta_table_counts 에 play_by_play 행 수가 없습니다"
                            % s["database"])
            continue
        d1_pbp += int(rows[0]["n"])
    my_pbp = my_query(my, "SELECT COUNT(*) AS n FROM `play_by_play`")[0]["n"]
    if d1_pbp != my_pbp:
        problems.append("play_by_play 전체: D1 샤드 meta 합 %s / MySQL %s "
                        "(D1 meta 가 낡았을 수도 있습니다. 경기별 결과를 함께 보십시오)"
                        % (format(d1_pbp, ","), format(my_pbp, ",")))

    since = int((datetime.datetime.now(KST).date()
                 - datetime.timedelta(days=days)).strftime("%Y%m%d"))
    games = my_query(my, "SELECT game_id AS g, season FROM `games` WHERE game_date >= %s",
                     [since])
    by_db = {}
    for r in games:
        by_db.setdefault(shard_plan.db_of(r["season"]), []).append(r["g"])
    for db, ids in by_db.items():
        if not db:
            continue
        lit = ",".join("'%s'" % str(g).replace("'", "''") for g in ids)
        a = {r["g"]: int(r["n"]) for r in d1_query(
            "SELECT gameID AS g, COUNT(*) AS n FROM play_by_play "
            "WHERE gameID IN (%s) GROUP BY gameID;" % lit, db)}
        b = {r["g"]: int(r["n"]) for r in my_query(
            my, "SELECT gameID AS g, COUNT(*) AS n FROM `play_by_play` "
            "WHERE gameID IN (%s) GROUP BY gameID" % ", ".join(["%s"] * len(ids)), ids)}
        for g in sorted(set(a) | set(b)):
            if a.get(g, 0) != b.get(g, 0):
                problems.append("경기 %s 플레이 수: D1 %s / MySQL %s"
                                % (g, a.get(g, 0), b.get(g, 0)))
    return problems, len(games), len(tables)


def report(problems, n_tables, n_games, days):
    lines = ["## D1·MySQL 대조", "",
             "- 표 %d개 행 수, 값 대조 %s, 최근 %d일 경기 %d개"
             % (n_tables, "·".join(FULL), days, n_games), ""]
    if problems:
        lines += ["다른 곳 %d건:" % len(problems), ""] + ["- %s" % p for p in problems[:50]]
    else:
        lines.append("모두 같습니다.")
    text = "\n".join(lines)
    print(text)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3, help="경기별로 견줄 최근 일수")
    args = ap.parse_args()
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    my = myconn.connect()
    try:
        problems, n_games, n_tables = check(my, types, args.days)
    finally:
        my.close()
    report(problems, n_tables, n_games, args.days)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
