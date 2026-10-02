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
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

from d1_load import (  # noqa: E402
    build_inserts, d1_columns, query, refresh_count, run_d1_file,
)
from migration import shard_plan  # noqa: E402
from mysql_sink import mirror  # noqa: E402


def read_csv_rows(path):
    # 크롤러가 cp949 로 씁니다. utf-8 로 저장된 것도 있어 둘 다 봅니다.
    for enc in ("cp949", "utf-8"):
        try:
            with open(path, encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError("인코딩을 알 수 없습니다: %s" % path)


DATE_LIKE = re.compile(r"\d{8}(\.0+)?")


def wrong_dates(rows, day):
    """그날(day)이 아닌 game_date 값들입니다(정렬, 중복 없음).

    날짜가 틀린 행이 들어가면 다음 재실행의 `DELETE … WHERE game_date =
    그날` 이 그 행을 못 지워 같은 경기가 두 번 쌓입니다. 포스트시즌 날짜
    버그(game_date='TOB00929')가 실제로 그런 행을 만들었습니다.
    """
    bad = set()
    for r in rows:
        s = str(r.get("game_date") or "").strip()
        if not (DATE_LIKE.fullmatch(s) and s[:8] == day):
            bad.add(s)
    return sorted(bad)


def mysql_write_pbp(sink, day, rows):
    """MySQL 에 하루치를 씁니다. 표 하나라 샤드를 고르지 않습니다.

    D1 과 같이 그날 행을 지우고 다시 넣어, 다시 돌려도 결과가 같습니다.
    idx_pbp_game_date 가 있어야 이 DELETE 가 400만 행을 훑지 않습니다.
    pbp_id 는 넣지 않습니다. AUTO_INCREMENT 가 이어 붙이고, 받은 순서대로
    넣으므로 경기 안 순서(RE24 의 ORDER BY pbp_id)가 지켜집니다.
    """
    cols = [c for c in sink.columns("play_by_play") if c != "pbp_id"]
    sink.execute("DELETE FROM `play_by_play` WHERE `game_date` = %s", [int(day)])
    n = sink.insert("play_by_play", cols, rows)
    sink.refresh_count("play_by_play")
    return n


def d1_day_rows(day, pbp_db):
    """D1 에 이미 들어간 그날 행입니다. 따라잡기(--mysql-only)용입니다.

    D1 샤드의 game_date 에는 인덱스가 없어 날짜로 고르면 샤드 전체(약 70만
    행)를 읽습니다. 날짜 인덱스가 있는 games 에서 그날 경기를 찾고, gameID
    인덱스로 고릅니다. 읽는 양은 그날 행 수와 같습니다.
    """
    games = [r["g"] for r in query(
        "SELECT game_id AS g FROM games WHERE game_date = %d;" % int(day))]
    if not games:
        return []
    ids = ",".join("'%s'" % str(g).replace("'", "''") for g in games)
    return query("SELECT * FROM play_by_play WHERE gameID IN (%s) ORDER BY pbp_id;" % ids,
                 db_name=pbp_db)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", default=None, help="YYYYMMDD, 기본값은 어제")
    ap.add_argument("--save-dir", default="crawler/save_daily")
    ap.add_argument("--out", default="migration/daily_pbp.sql")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--skip-crawl", action="store_true",
                    help="이미 받아 둔 CSV 로만 SQL 을 만듭니다")
    ap.add_argument("--mysql-only", action="store_true",
                    help="크롤링·D1 쓰기 없이, D1 에 이미 있는 그날 행을 MySQL 에 넣습니다(따라잡기)")
    args = ap.parse_args()

    # 러너는 UTC 라 그냥 어제를 잡으면 한국 날짜가 하루 어긋납니다.
    kst = datetime.timezone(datetime.timedelta(hours=9))
    day = args.date or (datetime.datetime.now(kst).date()
                        - datetime.timedelta(days=1)).strftime("%Y%m%d")
    year = day[:4]
    print("대상 날짜: %s (KST 기준)" % day)

    # `play_by_play` 는 시즌별 D1 네 개에 나뉘어 있습니다. 공용
    # DB(kbo-stats)에는 이 표가 없습니다. 예전처럼 공용 DB 에 넣으면
    # 워커가 읽지 않아 **오류 없이 화면만 어제에 멈춥니다.** 그게 제일
    # 찾기 어려운 고장이라 배정에 없으면 여기서 멈춥니다.
    pbp_db = shard_plan.db_of(year)
    if not pbp_db:
        print("%s 시즌을 담당하는 D1 이 배정표에 없습니다." % year)
        print("migration/shard_plan.json 에 시즌을 넣고 D1 을 만든 뒤")
        print("src/lib/shard.js 사본까지 맞춘 다음 다시 돌리십시오.")
        return 1
    print("대상 D1: %s" % pbp_db)

    if args.mysql_only:
        rows = d1_day_rows(day, pbp_db)
        print("D1 에서 읽은 행 %s개" % format(len(rows), ","))
        if not rows:
            print("%s 에 D1 행이 없습니다. 넣을 것이 없습니다." % day)
            return 0
        bad = wrong_dates(rows, day)
        if bad:
            print("game_date 가 %s 이 아닌 행이 있습니다: %s" % (day, ", ".join(bad[:5])))
            return 1
        if args.dry_run:
            print("[dry-run] MySQL 에 넣지 않았습니다.")
            return 0
        n = mirror("pbp", lambda s: mysql_write_pbp(s, day, rows), required=True)
        print("MySQL 적재 완료 (%s행)" % format(n, ","))
        return 0

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

    bad = wrong_dates(rows, day)
    if bad:
        # 넣으면 재실행 때 지워지지 않는 행이 생깁니다. 아무것도 쓰지 않고 멈춥니다.
        print("game_date 가 %s 이 아닌 행이 있습니다: %s" % (day, ", ".join(bad[:5])))
        print("crawler/gameid.py 의 game_date_of 와 CSV 를 확인하십시오.")
        return 1

    columns = d1_columns("play_by_play", db_name=pbp_db)
    # pbp_id 는 넣지 않습니다. 샤드가 이미 70만 행 안팎을 갖고 있어 CSV 의
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

    run_d1_file(out, db_name=pbp_db)
    print("D1 적재 완료 (%s)" % pbp_db)

    # 행 수 메타를 갱신합니다. 이것을 빠뜨리면 화면이 어제 숫자를
    # 계속 보여 줍니다(src/lib/counts.js). 나뉜 표라서 **샤드마다**
    # 따로 적어 두고, 화면은 네 값을 더해 보여 줍니다.
    refresh_count("play_by_play", db_name=pbp_db)
    print("행 수 메타 갱신 완료")
    mirror("pbp", lambda s: mysql_write_pbp(s, day, rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
