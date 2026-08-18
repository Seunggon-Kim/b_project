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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d1_load import (  # noqa: E402
    build_inserts, d1_columns, refresh_count, run_d1_file,
)

ROOT = Path(__file__).resolve().parent.parent


def read_csv_rows(path):
    # 크롤러가 cp949 로 씁니다. utf-8 로 저장된 것도 있어 둘 다 봅니다.
    for enc in ("cp949", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 알 수 없습니다: %s" % path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYYMMDD, 기본값은 어제")
    ap.add_argument("--save-dir", default="crawler/save_daily")
    ap.add_argument("--out", default="migration/daily_pbp.sql")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true",
                    help="이미 받아 둔 CSV 로만 SQL 을 만듭니다")
    args = ap.parse_args()

    # 러너는 UTC 라 그냥 어제를 잡으면 한국 날짜가 하루 어긋납니다.
    kst = datetime.timezone(datetime.timedelta(hours=9))
    day = args.date or (datetime.datetime.now(kst).date()
                        - datetime.timedelta(days=1)).strftime("%Y%m%d")
    year = day[:4]
    print("대상 날짜: %s (KST 기준)" % day)

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
    # pbp_id 는 넣지 않습니다. D1 이 이미 40만 행 넘게 갖고 있어 CSV 의
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
    refresh_count("play_by_play")
    print("행 수 메타 갱신 완료")
    return 0


if __name__ == "__main__":
    sys.exit(main())
