# -*- coding: utf-8 -*-
"""2008~2014 PBP 를 시즌별로 모읍니다.

## 왜 따로 두나

`crawler/pbp.py` 는 날짜 구간을 받습니다. 일곱 시즌을 한 번에 부르면
중간에 끊겼을 때 어디까지 됐는지 알 수 없고, 처음부터 다시 받게
됩니다. 세 시간짜리 작업을 두 번 하고 싶지 않습니다.

그래서 시즌 단위로 나눠 부르고, 끝난 시즌은 `.done` 으로 표시합니다.
다시 돌리면 안 끝난 시즌부터 이어집니다.

`crawler/pbp.py` 자체도 이미 받은 경기는 건너뜁니다(`skipped`). 그래서
시즌 중간에 끊겨도 그 시즌을 다시 부르면 남은 것만 받습니다.

## 구간

시작·종료일은 `games` 표에서 그대로 읽습니다. 손으로 적으면 개막일이
바뀐 해에 어긋납니다. 포스트시즌까지 받으므로 `-p` 를 붙입니다.

    py data_collection/collect_old_pbp.py --from 2008 --to 2014
    py data_collection/collect_old_pbp.py --year 2008 --dry-run
"""
import argparse
import datetime
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from d1_load import query  # noqa: E402

FIRST, LAST = 2008, 2014


def all_ranges(tries=4):
    """시즌별 (첫 경기, 마지막 경기) 를 **한 번에** 읽습니다.

    시즌마다 따로 물으면 D1 호출이 일곱 번이 되고, 그중 한 번만
    실패해도 세 시간짜리 수집이 중간에 죽습니다. 실제로 2010 에서
    죽었습니다(`7403 not authorized`, 일시적 오류).

    한 번으로 줄이고, 그 한 번도 재시도합니다.
    """
    last = None
    for i in range(tries):
        try:
            rows = query(
                "SELECT season, MIN(game_date) AS lo, MAX(game_date) AS hi "
                "FROM games WHERE season BETWEEN %d AND %d "
                "GROUP BY season ORDER BY season;" % (FIRST, LAST))
            return {int(r["season"]): (str(r["lo"]), str(r["hi"])) for r in rows}
        except Exception as e:                       # noqa: BLE001
            last = e
            wait = 5 * (i + 1)
            print("  구간 조회 실패(%d/%d). %d초 뒤 다시 시도합니다: %s"
                  % (i + 1, tries, wait, str(e)[:80]), flush=True)
            time.sleep(wait)
    raise RuntimeError("시즌 구간을 못 읽었습니다: %s" % last)


def collect(season, save_root, ranges, dry_run=False):
    lo_hi = ranges.get(int(season))
    if not lo_hi:
        print("  %d: games 에 그 시즌이 없습니다" % season)
        return False
    lo, hi = lo_hi
    out = save_root / str(season)
    done = save_root / ("%d.done" % season)
    if done.exists():
        n = len(list(out.glob("*.csv"))) if out.is_dir() else 0
        print("  %d: 이미 끝났습니다 (%d경기). 건너뜁니다." % (season, n))
        return True

    print("  %d: %s ~ %s" % (season, lo, hi), flush=True)
    if dry_run:
        return True

    t0 = datetime.datetime.now()
    cmd = [sys.executable, str(ROOT / "crawler" / "pbp.py"),
           "-f", lo, "-t", hi, "-d", str(save_root) + "/", "-p"]
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    secs = (datetime.datetime.now() - t0).total_seconds()

    # 진행 막대가 아니라 요약 줄만 봅니다.
    tail = ""
    for line in (r.stdout or "").splitlines():
        if "download_pbp_files" in line:
            tail = line.strip()
    got = len(list(out.glob("*.csv"))) if out.is_dir() else 0

    if r.returncode != 0:
        print("  %d: 실패 (종료코드 %d, %d경기까지 받음, %.0f분)"
              % (season, r.returncode, got, secs / 60))
        print("     " + (r.stderr or "")[-300:])
        return False

    print("  %d: %d경기, %.0f분  %s" % (season, got, secs / 60, tail), flush=True)
    # 다시 돌릴 때 건너뛰도록 표시합니다.
    done.write_text("%s~%s %d경기\n" % (lo, hi, got), encoding="utf-8")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int)
    ap.add_argument("--from", dest="start", type=int, default=FIRST)
    ap.add_argument("--to", dest="end", type=int, default=LAST)
    ap.add_argument("--save-dir", default="crawler/save")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    save_root = Path(args.save_dir)
    if not save_root.is_absolute():
        save_root = ROOT / save_root
    save_root.mkdir(parents=True, exist_ok=True)

    years = [args.year] if args.year else list(range(args.start, args.end + 1))
    print("저장 위치: %s" % save_root)
    # D1 은 여기서 딱 한 번 부릅니다. 나머지는 네이버만 씁니다.
    ranges = all_ranges()
    t0 = datetime.datetime.now()
    bad = []
    for y in years:
        if not collect(y, save_root, ranges, args.dry_run):
            bad.append(y)
    mins = (datetime.datetime.now() - t0).total_seconds() / 60

    total = sum(len(list((save_root / str(y)).glob("*.csv")))
                for y in years if (save_root / str(y)).is_dir())
    print()
    print("합계 %d경기, %.0f분" % (total, mins))
    if bad:
        print("못 끝낸 시즌: %s" % bad)
        print("같은 명령을 다시 돌리면 이어서 받습니다.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
