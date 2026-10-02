# -*- coding: utf-8 -*-
"""스냅샷과 MySQL 을 대조합니다.

표마다 행 수를, 열마다 '값 있는 칸 수' 와 합계를 양쪽에서 세어 견줍니다.
정수·글자 길이·날짜는 합계가 정확히 같아야 하고, 실수만 덧셈 오차를
허용합니다. 날짜는 YYYYMMDD, 일시는 YYYYMMDD와 초 단위를 내용 합계로
견줍니다. 표마다 무작위 200행을 키로 짝지어 값을 하나하나 견줍니다.
스냅샷 쪽은 적재 때와 같은 규칙으로 ''·'-' 를 값 없음으로 봅니다.
play_by_play 는 경기(gameID) 별 행 수도 견줍니다. 새로 매긴 번호(pbp_id)는
견주지 않습니다.

    py -m migration.mysql.verify --snapshot ~/.bstats/snapshots/d1_20261002.db
"""
import argparse
import datetime as dt
import json
import random
import sqlite3
import sys
from pathlib import Path

from migration.mysql import conn as myconn
from migration.mysql import typemap as tm
from migration.mysql.ddl import OUT_DIR, ROOT, split_sql
from migration.mysql.load import _EXISTS, post_object

REPORT = ROOT / "docs" / "mysql-migration" / "verify-report.md"
SAMPLE = 200
WS = "char(32,9,10,11,12,13,160,12288)"


def sqlite_expr(col, kind):
    """스냅샷의 합계 식을 만듭니다. 공백 처리와 값 종류에 맞춘 합계를 씁니다."""
    c = '"%s"' % col
    present = ("CASE WHEN typeof(%s)='text' AND trim(%s, %s) IN ('','-') "
               "THEN NULL ELSE %s END" % (c, c, WS, c))
    trimmed = "trim(%s, %s)" % (present, WS)
    if kind == "int":
        return "COUNT(%s)" % present, "SUM(CAST(%s AS INTEGER))" % trimmed
    if kind == "double":
        return "COUNT(%s)" % present, "TOTAL(CAST(%s AS REAL))" % trimmed
    if kind == "date":
        return ("COUNT(%s)" % present,
                "SUM(CAST(replace(%s, '-', '') AS INTEGER))" % trimmed)
    if kind == "datetime":
        ymd = "CAST(replace(substr(%s,1,10),'-','') AS INTEGER)" % trimmed
        sec = ("CAST(substr(%s,12,2) AS INTEGER)*3600 + "
               "CAST(substr(%s,15,2) AS INTEGER)*60 + "
               "CAST(substr(%s,18,2) AS INTEGER)" % (trimmed, trimmed, trimmed))
        return "COUNT(%s)" % present, "SUM(%s + %s)" % (ymd, sec)
    return "COUNT(%s)" % c, "SUM(length(%s))" % c


def mysql_expr(col, kind):
    """MySQL 의 합계 식을 만듭니다. SQLite 와 맞춘 합계를 씁니다."""
    c = "`%s`" % col
    if kind in ("int", "double"):
        return "COUNT(%s)" % c, "SUM(%s)" % c
    if kind == "date":
        return "COUNT(%s)" % c, "SUM(CAST(DATE_FORMAT(%s,'%%Y%%m%%d') AS UNSIGNED))" % c
    if kind == "datetime":
        ymd = "CAST(DATE_FORMAT(%s,'%%Y%%m%%d') AS UNSIGNED)" % c
        return "COUNT(%s)" % c, "SUM(%s + TIME_TO_SEC(%s))" % (ymd, c)
    if kind == "blob":
        return "COUNT(%s)" % c, "SUM(LENGTH(%s))" % c
    return "COUNT(%s)" % c, "SUM(CHAR_LENGTH(%s))" % c


def close(a, b):
    """합계가 같은지 봅니다. 실수 덧셈 순서에서 오는 오차만 허용합니다."""
    a, b = float(a or 0), float(b or 0)
    return abs(a - b) <= max(1e-6, 1e-9 * max(abs(a), abs(b)))


def same_sum(a, b, kind):
    """합계가 종류에 맞춰 같은지 봅니다. 실수만 오차를 허용합니다."""
    if kind == "double":
        return close(a, b)
    return int(a or 0) == int(b or 0)


def same_value(expected, actual, kind):
    """값이 종류에 맞춰 같은지 봅니다."""
    if expected is None and actual is None:
        return True
    if expected is None or actual is None:
        return False
    if kind == "double":
        return close(expected, actual)
    if kind == "int":
        return int(expected) == int(actual)
    if kind in ("date", "datetime"):
        return str(expected) == str(actual)
    if kind == "blob":
        return bytes(expected) == bytes(actual)
    return expected == actual


def key_part(value, kind):
    """키 값을 양쪽 표현으로 맞춥니다."""
    if value is None:
        return None
    if kind in ("date", "datetime"):
        return str(value)
    if kind == "int":
        return int(value)
    if kind == "double":
        return float(value)
    if kind == "blob":
        return bytes(value)
    return value if isinstance(value, str) else str(value)


def compare_rows(expected, actual, names, kinds):
    """예상 행 집합과 실제 행 집합의 차이를 찾습니다.

    expected, actual 는 {key_tuple: value_tuple} 딕셔너리입니다.
    차이를 설명하는 문자열 목록을 돌려줍니다. 20건을 초과하면 뒤에 요약을 붙입니다.
    """
    problems = []
    for key in expected:
        if key not in actual:
            problems.append("키 %r 가 MySQL 에 없습니다" % (key,))
        else:
            exp_vals = expected[key]
            act_vals = actual[key]
            for name, exp, act, kind in zip(names, exp_vals, act_vals, kinds):
                if not same_value(exp, act, kind):
                    problems.append("키 %r 의 %s: %r / %r" % (key, name, exp, act))
    if len(problems) > 20:
        rest = len(problems) - 20
        problems = problems[:20]
        problems.append("그 밖에 %d건" % rest)
    return problems


def primary_key(my, table):
    """MySQL 표의 기본키 열을 돌려줍니다."""
    with my.cursor() as cur:
        cur.execute(
            "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND "
            "CONSTRAINT_NAME = 'PRIMARY' ORDER BY ORDINAL_POSITION",
            (table,))
        return [row[0] for row in cur.fetchall()]


def verify_table(sq, my, table, spec):
    """표를 대조합니다. (스냅샷행, MySQL행, 문제들)을 돌려줍니다."""
    # 스냅샷에 있는 열을 확인합니다.
    snap_cols = sq.execute('PRAGMA table_info("%s")' % table).fetchall()
    snap_col_names = {row[1] for row in snap_cols}
    missing = [c for c, k in spec["columns"] if c != spec.get("renumber")
               and c not in snap_col_names]
    if missing:
        snap_rows = sq.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        return snap_rows, None, ["스냅샷에 없는 열: " + ", ".join(missing)]

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
        elif not same_sum(ss, ms, k):
            problems.append("%s: 합계 %s / %s" % (c, ss, ms))
    return s[0], m[0], problems


def verify_sample(sq, my, table, spec):
    """표의 무작위 표본을 비교합니다. (확인한 행 수, 문제들, 사유)을 돌려줍니다."""
    cols = [(c, k) for c, k in spec["columns"] if c != spec.get("renumber")]
    names = [c for c, k in cols]
    kinds = [k for c, k in cols]
    renumber = spec.get("renumber")

    # 재번호 열이 있으면 스냅샷 rowid 와 MySQL 의 재번호 열을 비교합니다.
    if renumber:
        row_data = sq.execute(
            'SELECT COUNT(*), MAX(rowid) FROM "%s"' % table).fetchone()
        snap_count, snap_max = row_data
        with my.cursor() as cur:
            cur.execute("SELECT COUNT(*), MAX(`%s`) FROM `%s`" % (renumber, table))
            my_count, my_max = cur.fetchone()

        # 두 쪽 다 비어있으면 건너뜁니다.
        if snap_count == 0 and my_count == 0:
            return 0, [], "빈 표"

        if snap_count != my_count or snap_max != my_max:
            return (0, [
                "번호 대응이 맞지 않아 표본 비교를 못 했습니다"
                "(스냅샷 %s/%s, MySQL %s/%s)" % (snap_count, snap_max, my_count, my_max)], None)

        k = min(SAMPLE, snap_count)
        sample_ids = random.sample(range(1, snap_max + 1), k=k)

        # 스냅샷에서 표본을 읽습니다.
        placeholders = ",".join("?" * k)
        sq_cols = ["rowid"] + names
        snap_rows = sq.execute(
            'SELECT %s FROM "%s" WHERE rowid IN (%s)' % (
                ", ".join('"%s"' % c for c in sq_cols), table, placeholders),
            sample_ids).fetchall()
        snap_dict = {}
        for row in snap_rows:
            snap_id = int(row[0])
            values = tuple(tm.normalize(row[i+1], kinds[i]) for i in range(len(names)))
            snap_dict[(snap_id,)] = values

        # MySQL 에서 표본을 읽습니다.
        placeholders = ", ".join(["%s"] * k)
        my_cols = [renumber] + names
        with my.cursor() as cur:
            cur.execute(
                "SELECT %s FROM `%s` WHERE `%s` IN (%s)" % (
                    ", ".join("`%s`" % c for c in my_cols), table, renumber, placeholders),
                sample_ids)
            my_rows = cur.fetchall()
        my_dict = {}
        for row in my_rows:
            my_id = int(row[0])
            values = row[1:]
            my_dict[(my_id,)] = values

        return k, compare_rows(snap_dict, my_dict, names, kinds), None

    # 기본키가 있으면 키를 맞춰 비교합니다.
    pk_names = primary_key(my, table)
    if not pk_names:
        return 0, [], "기본키 없음"

    pk_kinds = {c: k for c, k in spec["columns"] if c in pk_names}
    # 비교할 열들은 PK가 아닌 열입니다.
    value_cols = [(c, k) for c, k in spec["columns"]
                  if c != spec.get("renumber") and c not in pk_names]
    value_names = [c for c, k in value_cols]
    value_kinds = [k for c, k in value_cols]

    # 스냅샷에서 무작위 표본을 읽습니다.
    sq_cols = pk_names + value_names
    snap_count_row = sq.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()
    snap_count = snap_count_row[0] if snap_count_row else 0

    if snap_count == 0:
        return 0, [], "빈 표"

    snap_rows = sq.execute(
        'SELECT %s FROM "%s" ORDER BY random() LIMIT ?' % (
            ", ".join('"%s"' % c for c in sq_cols), table),
        (min(SAMPLE, snap_count),)
    ).fetchall()

    snap_dict = {}
    my_sample_keys = []
    for row in snap_rows:
        # 스냅샷 키는 적재 때와 같은 규칙(normalize)을 먼저 거칩니다.
        # '78513.0' → 78513, ' 2026-09-30 ' → '2026-09-30' 로 저장된 값과 같아집니다.
        pk_vals = tuple(key_part(tm.normalize(row[i], pk_kinds[pk_names[i]]),
                                 pk_kinds[pk_names[i]])
                        for i in range(len(pk_names)))
        values = tuple(tm.normalize(row[len(pk_names) + i], value_kinds[i])
                       for i in range(len(value_names)))
        snap_dict[pk_vals] = values
        my_sample_keys.append(pk_vals)

    if not my_sample_keys:
        return 0, [], "빈 표"

    # MySQL 에서 표본의 키를 가져옵니다.
    if len(pk_names) == 1:
        placeholders = ", ".join(["%s"] * len(my_sample_keys))
        query = "SELECT %s FROM `%s` WHERE `%s` IN (%s)" % (
            ", ".join("`%s`" % c for c in sq_cols), table, pk_names[0], placeholders)
        params = sum(my_sample_keys, ())
    else:
        # 행 생성자 IN 을 씁니다: WHERE (k1, k2) IN ((v1, v2), (v3, v4), ...)
        row_cond = "(" + ", ".join("`%s`" % pn for pn in pk_names) + ")"
        value_rows = ", ".join(
            "(" + ", ".join(["%s"] * len(pk_names)) + ")"
            for _ in range(len(my_sample_keys)))
        query = "SELECT %s FROM `%s` WHERE %s IN (%s)" % (
            ", ".join("`%s`" % c for c in sq_cols), table, row_cond, value_rows)
        params = sum(my_sample_keys, ())

    with my.cursor() as cur:
        cur.execute(query, params)
        my_rows = cur.fetchall()

    my_dict = {}
    for row in my_rows:
        pk_vals = tuple(key_part(row[i], pk_kinds[pk_names[i]])
                        for i in range(len(pk_names)))
        values = row[len(pk_names):]
        my_dict[pk_vals] = values

    return len(my_sample_keys), compare_rows(snap_dict, my_dict, value_names, value_kinds), None


def missing_post_objects(cur, post_sql):
    """schema_post.sql 의 인덱스·외래키 중 MySQL 에 없는 것입니다."""
    missing = []
    for stmt in split_sql(post_sql):
        kind, table, name = post_object(stmt)
        cur.execute(_EXISTS[kind], (table, name))
        if not cur.fetchone()[0]:
            missing.append((kind, table, name))
    return missing


def verify_games(sq, my):
    """경기별 플레이 수를 대조합니다. (경기 수, 틀린 경기들)을 돌려줍니다."""
    s = dict(sq.execute('SELECT "gameID", COUNT(*) FROM play_by_play GROUP BY 1'))
    with my.cursor() as cur:
        cur.execute("SELECT CAST(`gameID` AS BINARY), COUNT(*) FROM `play_by_play` GROUP BY 1")
        m = {}
        for k, n in cur.fetchall():
            try:
                key = k.decode('utf-8') if isinstance(k, bytes) else (None if k is None else str(k))
            except (UnicodeDecodeError, AttributeError):
                key = None if k is None else str(k)
            m[key] = int(n)

    s_norm = {None if k is None else str(k): v for k, v in s.items()}
    bad = sorted((g for g in set(s_norm.keys()) | set(m.keys())
                  if s_norm.get(g) != m.get(g)),
                 key=lambda g: str(g))
    return len(s), bad


def main():
    """검증 보고서를 생성합니다. 모두 같으면 0, 차이가 있으면 1을 돌려줍니다."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default=None)
    ap.add_argument("--objects-only", action="store_true",
                    help="스냅샷 대조 없이 schema_post.sql 개체가 모두 있는지만 봅니다")
    args = ap.parse_args()
    post = (OUT_DIR / "schema_post.sql").read_text(encoding="utf-8")
    if args.objects_only:
        my = myconn.connect()
        try:
            with my.cursor() as cur:
                missing = missing_post_objects(cur, post)
        finally:
            my.close()
        for kind, table, name in missing:
            print("없음: %s %s.%s" % (kind, table, name))
        print("개체 모두 있음" if not missing else "개체 %d개 없음" % len(missing))
        return 1 if missing else 0
    if not args.snapshot:
        ap.error("--snapshot 이 필요합니다.")
    types = json.loads((OUT_DIR / "schema_types.json").read_text(encoding="utf-8"))
    sq = sqlite3.connect(Path(args.snapshot).resolve().as_uri() + "?mode=ro", uri=True)
    my = myconn.connect()
    try:
        lines = ["# MySQL 대조 보고", "",
                 "- 스냅샷: `%s`" % Path(args.snapshot).name,
                 "- 대조 시각(UTC): %s" % dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M"),
                 "", "| 표 | 스냅샷 행 | MySQL 행 | 표본 | 결과 |", "|---|---|---|---|---|"]
        failed = []
        for table, spec in types.items():
            srows, mrows, problems = verify_table(sq, my, table, spec)

            # 스냅샷에 열이 없으면 표본을 건너뜁니다.
            if mrows is not None:
                try:
                    sample_checked, sample_problems, sample_note = verify_sample(sq, my, table, spec)
                    problems.extend(sample_problems)
                except Exception as e:
                    problems.append("표본 비교 중 오류: %s" % e)
                    sample_checked, sample_note = 0, None
            else:
                sample_checked, sample_note = 0, None

            # 표본 열 포맷합니다.
            if sample_note == "기본키 없음":
                sample_str = "건너뜀(기본키 없음)"
            elif sample_note == "빈 표":
                sample_str = "건너뜀(빈 표)"
            elif sample_checked == 0:
                sample_str = "건너뜀"
            else:
                sample_str = str(sample_checked)

            mrows_str = "-" if mrows is None else format(mrows, ",")
            lines.append("| %s | %s | %s | %s | %s |" % (
                table, format(srows, ","), mrows_str, sample_str,
                "같음" if not problems else "<br>".join(problems)))
            if problems:
                failed.append(table)
            print("%-34s %s" % (table, "같음" if not problems else "; ".join(problems)),
                  flush=True)
            if sample_note == "기본키 없음":
                print("%s: 기본키가 없어 표본 비교를 건너뜁니다" % table, flush=True)

        if "play_by_play" in types:
            games, bad = verify_games(sq, my)
            lines += ["", "경기별 플레이 수: %s경기 중 다른 경기 %d개%s" % (
                format(games, ","), len(bad),
                "" if not bad else " (" + ", ".join(str(g) for g in bad[:20]) + ")")]
            if bad:
                failed.append("play_by_play(경기별)")
        with my.cursor() as cur:
            missing = missing_post_objects(cur, post)
        lines += ["", "인덱스·외래키: %s" % (
            "모두 있음" if not missing else
            "없음 " + ", ".join("%s.%s" % (t, n) for _, t, n in missing))]
        if missing:
            failed.append("인덱스·외래키")
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
        print("보고서: %s" % REPORT)
        print("결과: %s" % ("모두 같음" if not failed else "다름 - " + ", ".join(failed)))
        return 1 if failed else 0
    finally:
        my.close()
        sq.close()


if __name__ == "__main__":
    sys.exit(main())
