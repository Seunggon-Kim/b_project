# -*- coding: utf-8 -*-
"""하루치 play-by-play 를 수집해 D1 에 직접 넣습니다.

EC2 의 `daily_kbo_pbp.sh` 를 대신합니다. 그 스크립트는 CSV 를 로컬
SQLite 에 넣는데, GitHub Actions 러너에는 그 파일이 없습니다. DB 가
226MB(12시즌이면 약 1.3GB)라 git 에 둘 수 없기 때문입니다.

하루치는 경기 5개, 약 1,500행이라 로컬 DB 없이도 다룰 수 있습니다.
CSV 를 읽어 SQL 을 만들고 wrangler 로 올립니다.

    py data_collection/daily_pbp_to_d1.py               # 어제
    py data_collection/daily_pbp_to_d1.py --date 20260816
    py data_collection/daily_pbp_to_d1.py --date 20260816 --dry-run

CLOUDFLARE_API_TOKEN 과 CLOUDFLARE_ACCOUNT_ID 가 필요합니다.
"""
import argparse
import csv
import datetime
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_NAME = "kbo-stats"

# D1 문 하나의 상한은 100,000 바이트입니다. 여유를 두고 자릅니다.
MAX_STATEMENT_BYTES = 90_000


def sql_literal(v):
    """CSV 값 하나를 SQL 리터럴로 만듭니다.

    CSV 는 모든 값이 문자열입니다. 빈 칸은 NULL 로, 나머지는 문자열로
    넣습니다. 숫자로 바꾸지 않는 이유가 있습니다. **컬럼 타입은 D1 이
    알고 있고 SQLite 는 문자열을 알아서 변환합니다.** 여기서 추측해
    바꾸면 `007` 같은 값이 7 이 되어 원본과 달라집니다.
    """
    if v is None or v == "":
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def build_inserts(table, columns, rows, max_bytes=MAX_STATEMENT_BYTES):
    """행 목록을 INSERT 문 여러 개로 나눕니다."""
    if not rows:
        return []
    head = 'INSERT INTO "%s" (%s) VALUES ' % (
        table, ",".join('"%s"' % c for c in columns))
    # **문자 수가 아니라 바이트로 세야 합니다.** D1 의 한도는 바이트이고,
    # 이 표에는 선수 이름과 상황 서술이 한글로 들어 있어 UTF-8 로 세 배가
    # 됩니다. 처음에 len() 으로 셌다가 문 하나가 108,774 바이트가 되어
    # 한도 100,000 을 넘었고, wrangler 가 D1_RESET_DO 로 실패했습니다.
    head_bytes = len(head.encode("utf-8"))
    out, batch, size = [], [], 0
    for r in rows:
        piece = "(" + ",".join(sql_literal(r.get(c)) for c in columns) + ")"
        n = len(piece.encode("utf-8"))
        # 한 행이라도 넣고 나서 크기를 봅니다. 빈 배치를 내보내면
        # 문법 오류가 됩니다.
        if batch and size + n + 1 > max_bytes - head_bytes:
            out.append(head + ",".join(batch) + ";")
            batch, size = [], 0
        batch.append(piece)
        size += n + 1
    if batch:
        out.append(head + ",".join(batch) + ";")
    return out


def read_csv_rows(path):
    # 크롤러가 cp949 로 씁니다. utf-8 로 저장된 것도 있어 둘 다 봅니다.
    for enc in ("cp949", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 알 수 없습니다: %s" % path)


def d1_columns(table):
    """D1 의 실제 컬럼 순서를 읽습니다.

    CSV 헤더를 그대로 믿지 않습니다. 크롤러가 컬럼을 더하거나 순서를
    바꿔도 D1 스키마가 정본입니다. 다른 컬럼을 넣으려 하면 적재가
    통째로 실패합니다.
    """
    out = run_d1('PRAGMA table_info("%s");' % table, json_out=True)
    import json as _json
    data = _json.loads(out[out.find("["):])
    return [r["name"] for r in data[0]["results"]]


def run_d1(sql, json_out=False):
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", DB_NAME,
           "--remote", "--command", sql, "--yes"]
    if json_out:
        cmd.append("--json")
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def run_d1_file(path):
    cmd = ["npx", "--yes", "wrangler@4", "d1", "execute", DB_NAME,
           "--remote", "--file", str(path), "--yes"]
    r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("wrangler 실패: %s" % (r.stderr or r.stdout)[:400])
    return r.stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYYMMDD, 기본값은 어제")
    ap.add_argument("--save-dir", default="crawler/save_daily")
    ap.add_argument("--out", default="migration/daily_pbp.sql")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true",
                    help="이미 받아 둔 CSV 로만 SQL 을 만듭니다")
    args = ap.parse_args()

    day = args.date or (datetime.date.today()
                        - datetime.timedelta(days=1)).strftime("%Y%m%d")
    year = day[:4]
    print("대상 날짜: %s" % day)

    save_dir = ROOT / args.save_dir
    if not args.skip_crawl:
        cmd = [sys.executable, str(ROOT / "crawler" / "pbp.py"),
               "-f", day, "-t", day, "-d", str(save_dir) + "/"]
        r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        for line in (r.stdout or "").splitlines():
            if "download_pbp_files" in line:
                print("  " + line.strip())
        if r.returncode != 0:
            print("수집 실패 (종료코드 %d)" % r.returncode)
            print((r.stderr or "")[-500:])
            return 1

    csvs = sorted((save_dir / year).glob("%s*.csv" % day)) \
        if (save_dir / year).is_dir() else []
    if not csvs:
        # 경기가 없는 날(월요일, 우천 취소)이 정상적으로 있습니다.
        # 실패가 아니므로 0 으로 끝냅니다.
        print("%s 에 경기가 없습니다. 넣을 것이 없습니다." % day)
        return 0
    print("경기 CSV %d개" % len(csvs))

    rows = []
    for f in csvs:
        rows.extend(read_csv_rows(f))
    print("행 %s개" % format(len(rows), ","))

    columns = d1_columns("play_by_play")
    # pbp_id 는 넣지 않습니다. D1 이 이미 229,667행을 갖고 있어 CSV 의
    # 번호와 부딪힙니다. INTEGER PRIMARY KEY 라 빼면 자동으로 붙습니다.
    insert_cols = [c for c in columns if c != "pbp_id"]
    missing = [c for c in insert_cols if c not in (rows[0] or {})]
    if missing:
        print("CSV 에 없는 컬럼 %d개는 NULL 로 들어갑니다: %s"
              % (len(missing), ", ".join(missing[:6])))

    lines = [
        "-- %s 하루치 play_by_play" % day,
        # 같은 날짜를 두 번 넣어도 결과가 같아야 합니다. 재실행이
        # 흔하기 때문입니다. 넣기 전에 그 날짜를 지웁니다.
        "DELETE FROM play_by_play WHERE game_date = %s;" % int(day),
    ]
    lines += build_inserts("play_by_play", insert_cols, rows)

    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("SQL %d문 -> %s" % (len(lines) - 1, out))

    if args.dry_run:
        print("[dry-run] 적재하지 않았습니다.")
        return 0

    # Actions 에서는 토큰이 반드시 있어야 합니다. 로컬에서는 wrangler 가
    # 로그인 세션을 쓰므로 없어도 됩니다. 그래서 막지 않고 알리기만 합니다.
    # 인증이 정말 없으면 아래 wrangler 호출이 실패하며 이유를 보여 줍니다.
    if not os.environ.get("CLOUDFLARE_API_TOKEN"):
        print("CLOUDFLARE_API_TOKEN 이 없습니다. wrangler 로그인 세션으로 시도합니다.")

    run_d1_file(out)
    print("D1 적재 완료")

    # 행 수 메타를 갱신합니다. 이것을 빠뜨리면 화면이 어제 숫자를
    # 계속 보여 줍니다(src/lib/counts.js).
    run_d1("INSERT OR REPLACE INTO meta_table_counts "
           "SELECT 'play_by_play', COUNT(*), datetime('now') "
           "FROM play_by_play;")
    print("행 수 메타 갱신 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
