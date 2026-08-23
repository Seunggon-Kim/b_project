# -*- coding: utf-8 -*-
"""표를 gzip CSV 로 떠서 GitHub Releases 에 올릴 파일을 만듭니다.

## 왜 필요한가

원본 사이트는 `/db/table/{name}/csv` 로 표 전체를 스트리밍했습니다.
Workers 에서는 못 합니다. 실측하면 **오류 없이 조용히 끊깁니다**
(229,667행 요청이 80,000행에서 멈추고, 끊기는 지점이 매번 다릅니다).
잘린 파일을 전량으로 알고 분석에 쓰는 것이 제일 나쁩니다.

그래서 지금은 20,000행을 넘으면 스트림을 열지 않고 413 과 안내를
냅니다. `play_by_play` 는 136번 나눠 받아야 합니다. 실행 가능한
안내이긴 하지만 쓸 만하지는 않습니다.

설계 문서는 R2 사전 생성본을 답으로 적었는데, R2 는 결제수단 등록이
필요해 예산 조건에 걸립니다. 공개 저장소의 Releases 는 무료이고
자산 하나에 2GB 까지 됩니다. 저장소 용량에도 잡히지 않습니다.

## 무엇을 만드는가

20,000행을 넘는 표만 대상입니다. 지금은 `play_by_play` 하나입니다.
나머지는 전부 2만 행 미만이라 화면에서 바로 받아집니다.

`play_by_play` 는 **시즌별로 나눕니다.** 한 덩어리 208MB 보다
18MB 짜리 열두 개가 쓰기 좋습니다.

    play_by_play_2015.csv.gz  ...  play_by_play_2026.csv.gz

실측(2025 시즌 229,667행): gzip 17.6MB, 원본 79MB, 7.6초.
12시즌이면 gzip 208MB, 원본 939MB 입니다.

    py migration/export_csv.py --out dist/csv
    py migration/export_csv.py --out dist/csv --table play_by_play
"""
import argparse
import csv
import gzip
import io
import os
import sqlite3
import sys
import time
from pathlib import Path

DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db")

# 화면이 한 번에 내주는 상한입니다. src/routes/dbexplorer.js 의
# CSV_MAX_ROWS 와 같아야 합니다. 이 값을 넘는 표만 여기서 만듭니다.
CSV_MAX_ROWS = 20000

# 시즌으로 쪼갤 표입니다. 한 파일이 너무 크면 받다가 지칩니다.
BY_SEASON = {
    # 표 이름: 시즌을 뽑는 식
    "play_by_play": "game_date / 10000",
}

# 롤링 백업과 내부 표는 내보내지 않습니다.
SKIP = ("_bak", "_cf_KV", "sqlite_")


def tables(con):
    out = []
    for (t,) in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "ORDER BY name"):
        if any(s in t for s in SKIP):
            continue
        out.append(t)
    return out


def write_gz(path, cursor):
    """커서를 gzip CSV 로 씁니다. 쓴 행 수를 돌려줍니다.

    **TextIOWrapper 를 반드시 flush 하고 detach 해야 합니다.**
    처음에는 이름 없이 `csv.writer(io.TextIOWrapper(gz, ...))` 로 썼는데,
    `with` 를 빠져나갈 때 gz 가 먼저 닫히고 래퍼의 텍스트 버퍼가
    그대로 사라졌습니다. 파일마다 **끝 4~18행이 조용히 잘렸습니다.**
    형식은 멀쩡하고(모든 행이 74필드) 행 수만 모자라서, 읽어 보기
    전에는 알 수 없었습니다. 이 기능이 막으려던 바로 그 고장입니다.

    detach 는 래퍼가 gz 를 두 번 닫지 않게 합니다. 순서가 중요합니다.
    """
    n = 0
    cols = [d[0] for d in cursor.description]
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wb", compresslevel=6) as gz:
        text = io.TextIOWrapper(gz, encoding="utf-8", newline="")
        w = csv.writer(text)
        w.writerow(cols)
        for row in cursor:
            w.writerow(["" if v is None else v for v in row])
            n += 1
        text.flush()
        text.detach()
    return n


def count_gz(path):
    """만든 파일을 실제로 읽어 행 수를 셉니다(머리글 제외).

    쓴 횟수를 세는 것만으로는 부족합니다. 버퍼가 날아가도 쓴 횟수는
    그대로입니다. 파일을 되읽는 것만이 진짜 검사입니다.
    """
    with gzip.open(path, "rb") as gz:
        r = csv.reader(io.TextIOWrapper(gz, encoding="utf-8", newline=""))
        next(r, None)
        return sum(1 for _ in r)


def export_table(con, table, out_dir):
    """한 표를 파일 하나 또는 시즌별 여러 개로 씁니다."""
    total = con.execute('SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
    if total <= CSV_MAX_ROWS:
        # 화면에서 바로 받아집니다. 만들 이유가 없습니다.
        return []

    made = []
    expr = BY_SEASON.get(table)
    if expr:
        seasons = [r[0] for r in con.execute(
            'SELECT DISTINCT CAST(%s AS INT) s FROM "%s" '
            "WHERE %s IS NOT NULL ORDER BY s" % (expr, table, expr))]
        for s in seasons:
            t0 = time.time()
            cur = con.execute(
                'SELECT * FROM "%s" WHERE CAST(%s AS INT) = ?' % (table, expr),
                (s,))
            p = out_dir / ("%s_%d.csv.gz" % (table, s))
            wrote = write_gz(p, cur)
            check(p, wrote)
            made.append((p, wrote))
            print("  %-32s %9s행  %6.1fMB  %.0f초"
                  % (p.name, format(wrote, ","), p.stat().st_size / 1e6,
                     time.time() - t0), flush=True)
    else:
        t0 = time.time()
        p = out_dir / ("%s.csv.gz" % table)
        wrote = write_gz(p, con.execute('SELECT * FROM "%s"' % table))
        check(p, wrote)
        made.append((p, wrote))
        print("  %-32s %9s행  %6.1fMB  %.0f초"
              % (p.name, format(wrote, ","), p.stat().st_size / 1e6,
                 time.time() - t0), flush=True)

    got = sum(n for _, n in made)
    if got != total:
        # 시즌이 NULL 인 행이 있으면 조용히 빠집니다. 잘린 파일을
        # 전량으로 아는 것이 이 기능에서 제일 나쁜 결과입니다.
        raise RuntimeError(
            "%s: 표에 %s행인데 파일 합계가 %s행입니다"
            % (table, format(total, ","), format(got, ",")))
    return made


def check(path, wrote):
    """만든 파일을 되읽어 쓴 만큼 들어갔는지 봅니다.

    쓴 횟수만 세면 버퍼가 날아가도 모릅니다. 실제로 그렇게 파일마다
    끝 4~18행이 잘린 적이 있습니다.
    """
    got = count_gz(path)
    if got != wrote:
        raise RuntimeError(
            "%s: %s행을 썼는데 파일에는 %s행입니다 (%+d)"
            % (path.name, format(wrote, ","), format(got, ","), got - wrote))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="dist/csv", help="파일을 쓸 폴더")
    ap.add_argument("--table", default=None, help="이 표만")
    ap.add_argument("--list", action="store_true",
                    help="대상만 보고 만들지 않습니다")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    names = [args.table] if args.table else tables(con)
    out_dir = Path(args.out)

    todo = []
    for t in names:
        n = con.execute('SELECT COUNT(*) FROM "%s"' % t).fetchone()[0]
        if n > CSV_MAX_ROWS:
            todo.append((t, n))

    if not todo:
        print("%s행을 넘는 표가 없습니다. 화면에서 바로 받으면 됩니다."
              % format(CSV_MAX_ROWS, ","))
        con.close()
        return 0

    print("대상 %d개 (%s행 초과)" % (len(todo), format(CSV_MAX_ROWS, ",")))
    for t, n in todo:
        print("  %-32s %s행" % (t, format(n, ",")))
    if args.list:
        con.close()
        return 0

    print()
    made = []
    for t, _ in todo:
        made += export_table(con, t, out_dir)
    con.close()

    size = sum(p.stat().st_size for p, _ in made)
    print()
    print("파일 %d개, 합계 %.0fMB -> %s" % (len(made), size / 1e6, out_dir))
    return 0


if __name__ == "__main__":
    sys.exit(main())
