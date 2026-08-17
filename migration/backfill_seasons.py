# -*- coding: utf-8 -*-
"""여러 시즌의 play-by-play 를 순차로 수집합니다.

`crawler/pbp.py` 는 날짜 범위를 받으므로 시즌마다 따로 부르면 됩니다.
한 번에 다 넣지 않고 나누는 이유는, 중간에 죽어도 끝난 시즌은 남기
위해서입니다. 이미 받은 경기는 `download.py` 가 건너뛰므로 다시 돌려도
낭비가 없습니다.

실측: 한 시즌 약 20~25분(경기당 2.4초 × 720경기 안팎).
2015~2024 열 시즌이면 3.5~4시간입니다.

    py migration/backfill_seasons.py 2015 2024
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

SAVE_ROOT = "crawler/save_backfill"


def collect(year, save_root, timeout_sec):
    """한 시즌을 수집합니다. (성공 여부, 걸린 초) 를 돌려줍니다."""
    # 개막이 3월 하순, 포스트시즌이 11월 초까지입니다. 넉넉히 잡아도
    # 경기가 없는 날은 그냥 넘어가므로 비용이 들지 않습니다.
    cmd = [
        sys.executable, "crawler/pbp.py",
        "-f", "%d0301" % year,
        "-t", "%d1130" % year,
        "-d", save_root + "/",
    ]
    t0 = time.time()
    try:
        r = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace",
                           timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return False, time.time() - t0, "제한 시간을 넘겼습니다"
    except Exception as exc:
        return False, time.time() - t0, "%s: %s" % (type(exc).__name__, exc)

    summary = ""
    for line in reversed((r.stdout or "").strip().splitlines()):
        if "download_pbp_files" in line:
            summary = line.strip()
            break

    # 종료 코드가 0 이어도 실제로 못 받았을 수 있습니다. 처음 이 스크립트를
    # 돌렸을 때 2017 이 34경기에서 멈췄는데 "성공"으로 찍혔습니다.
    # **오류를 삼키면 실패를 성공으로 착각합니다.** 실패하면 stderr 를
    # 남깁니다. 원인을 모르면 고칠 수 없습니다.
    if r.returncode != 0:
        err = (r.stderr or "").strip().splitlines()
        # 경고는 빼고 진짜 오류만 봅니다.
        real = [x for x in err
                if "Warning" not in x and x.strip() and not x.startswith("  ")]
        detail = " | ".join(real[-3:]) if real else (
            err[-1] if err else "출력 없음")
        return False, time.time() - t0, "종료코드 %d :: %s" % (
            r.returncode, detail[:300])

    return True, time.time() - t0, summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--save-root", default=SAVE_ROOT)
    # 한 시즌이 25분이면 넉넉합니다. 이보다 오래 걸리면 무언가 잘못된
    # 것이니 다음 시즌으로 넘어가는 편이 낫습니다.
    ap.add_argument("--timeout", type=int, default=5400)
    args = ap.parse_args()

    years = list(range(args.start, args.end + 1))
    print("수집할 시즌: %s (%d개)" % (
        ", ".join(str(y) for y in years), len(years)))
    print()

    done, failed = [], []
    t_all = time.time()
    for i, y in enumerate(years, start=1):
        print("[%d/%d] %d 시즌 수집 시작" % (i, len(years), y), flush=True)
        ok, secs, summary = collect(y, args.save_root, args.timeout)
        n = len(list((Path(args.save_root) / str(y)).glob("*.csv"))) \
            if (Path(args.save_root) / str(y)).is_dir() else 0
        print("      %s  %.1f분  경기 %d개  %s" % (
            "완료" if ok else "실패", secs / 60, n, summary), flush=True)
        (done if ok else failed).append(y)
        # 한 시즌이 실패해도 멈추지 않습니다. 이미 받은 경기는 다음
        # 실행에서 건너뛰므로 나중에 이어서 채울 수 있습니다.

    print()
    print("전체 %.1f분" % ((time.time() - t_all) / 60))
    print("성공 %d시즌: %s" % (len(done), done))
    if failed:
        print("실패 %d시즌: %s" % (len(failed), failed))
        print("같은 명령으로 다시 돌리면 받은 경기는 건너뜁니다.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
