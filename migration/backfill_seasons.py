# -*- coding: utf-8 -*-
"""여러 시즌의 play-by-play 를 순차로 수집합니다.

`crawler/pbp.py` 는 날짜 범위를 받으므로 나눠서 여러 번 부르면 됩니다.
이미 받은 경기는 `download.py` 가 건너뛰므로 다시 돌려도 낭비가 없습니다.

## 시즌이 아니라 달 단위로 부릅니다

처음에는 시즌 하나를 한 번에 불렀는데, 2026-08-17 밤 실행에서
세 가지가 한꺼번에 터졌습니다.

1. 집 네트워크가 끊겼습니다. `pbp.py` 는 맨 처음에 네이버 일정 API 로
   경기 목록을 받는데(`get_game_ids`), 여기서 DNS 가 실패하면 경기를
   한 개도 못 받고 통째로 죽습니다. 그래서 2018~2024 일곱 시즌이
   각각 0.0분 만에 연달아 실패했습니다.
2. 2017 은 90분 제한을 걸어 뒀는데 533분이 지나서야 실패로 잡혔습니다.
   `subprocess.run(timeout=)` 이 자식만 죽이고 손자 프로세스가 파이프를
   쥐고 있으면 `communicate()` 가 계속 기다립니다(윈도우).
3. 실패 사유가 "if sp.exists() & ~(sp.is_dir()):" 로 찍혔습니다. 이건
   파이썬 3.13 의 DeprecationWarning 이 stderr 에 남긴 소스 줄일 뿐,
   진짜 원인이 아닙니다. 진짜 원인은 `log.txt` 에 있었습니다.

셋 다 고쳤습니다. 달 단위로 자르고, 부르기 전에 연결을 확인하고,
제한 시간이 지나면 프로세스 트리째 죽이고, 실패하면 `log.txt` 를 읽습니다.

    py migration/backfill_seasons.py 2017 2024
"""
import argparse
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

SAVE_ROOT = "crawler/save_backfill"
ROOT = Path(__file__).resolve().parent.parent

# 개막이 3월 하순, 포스트시즌이 11월 초까지입니다. 경기가 없는 달은
# 목록이 비어서 금방 끝나므로 넉넉히 잡아도 손해가 없습니다.
MONTHS = list(range(3, 12))

# 크롤러가 맨 처음 부르는 곳입니다. 여기가 안 되면 시작할 이유가 없습니다.
PROBE_HOST = "api-gw.sports.naver.com"


def month_range(year, month):
    """그 달의 첫날과 마지막 날을 YYYYMMDD 로 돌려줍니다."""
    import calendar
    last = calendar.monthrange(year, month)[1]
    return "%d%02d01" % (year, month), "%d%02d%02d" % (year, month, last)


def network_ok():
    try:
        socket.gethostbyname(PROBE_HOST)
        return True
    except OSError:
        return False


def wait_for_network(max_wait_sec, quiet=False):
    """연결이 돌아올 때까지 기다립니다. 돌아왔으면 True 입니다.

    밤새 돌리는 작업이라 몇 분짜리 끊김에 전체를 버리면 안 됩니다.
    """
    if network_ok():
        return True
    t0 = time.time()
    wait = 30
    while time.time() - t0 < max_wait_sec:
        if not quiet:
            print("      네트워크가 끊겼습니다. %d초 뒤 다시 봅니다." % wait,
                  flush=True)
        time.sleep(wait)
        if network_ok():
            print("      네트워크가 돌아왔습니다 (%.1f분 기다림)"
                  % ((time.time() - t0) / 60), flush=True)
            return True
        wait = min(wait * 2, 300)
    return False


def kill_tree(pid):
    """윈도우에서 자식까지 확실히 죽입니다.

    `Popen.kill()` 은 직계 자식만 죽입니다. 크롤러가 손자를 남기면
    파이프가 안 닫혀서 계속 기다리게 됩니다.
    """
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                       capture_output=True, shell=True, timeout=60)
    except Exception:
        pass


def real_cause(log_path, since_pos):
    """log.txt 에서 이번 실행이 남긴 진짜 예외 줄을 찾습니다.

    crawler 는 traceback 을 거꾸로 뒤집어 씁니다(`getTracebackStr`).
    그래서 예외 이름이 위쪽에 옵니다. 예외처럼 보이는 첫 줄을 씁니다.
    """
    try:
        with open(log_path, encoding="cp949", errors="replace") as f:
            f.seek(since_pos)
            fresh = f.read()
    except OSError:
        return ""
    for line in fresh.splitlines():
        s = line.strip()
        if re.match(r"^[A-Za-z_.]+(Error|Exception|Timeout)\b", s):
            return s[:300]
    return ""


def run_chunk(start, end, save_root, timeout_sec, tmp_dir):
    """날짜 범위 하나를 수집합니다. (성공, 초, 요약) 을 돌려줍니다."""
    out_f = tmp_dir / "chunk_out.txt"
    err_f = tmp_dir / "chunk_err.txt"
    log_path = ROOT / "log.txt"
    pos = log_path.stat().st_size if log_path.exists() else 0

    cmd = [sys.executable, "crawler/pbp.py",
           "-f", start, "-t", end, "-d", save_root + "/"]
    t0 = time.time()
    # 파이프 대신 파일로 받습니다. 몇 시간짜리 실행에서 파이프 버퍼가
    # 차면 그대로 멈춥니다.
    with open(out_f, "w", encoding="utf-8", errors="replace") as fo, \
         open(err_f, "w", encoding="utf-8", errors="replace") as fe:
        p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=fo, stderr=fe)
        try:
            rc = p.wait(timeout=timeout_sec)
        except subprocess.TimeoutExpired:
            kill_tree(p.pid)
            try:
                p.wait(timeout=30)
            except subprocess.TimeoutExpired:
                pass
            return False, time.time() - t0, "제한 시간 %d분을 넘겨 강제 종료" % (
                timeout_sec // 60)

    secs = time.time() - t0
    stdout = out_f.read_text(encoding="utf-8", errors="replace")
    summary = ""
    for line in reversed(stdout.strip().splitlines()):
        if "download_pbp_files" in line:
            summary = line.strip()
            break

    if rc != 0:
        cause = real_cause(log_path, pos)
        if not cause:
            tail = [x.strip() for x in stdout.strip().splitlines() if x.strip()]
            cause = tail[-1][:300] if tail else "출력 없음"
        return False, secs, "종료코드 %d :: %s" % (rc, cause)

    return True, secs, summary


def csv_count(save_root, year):
    d = Path(save_root) / str(year)
    return len(list(d.glob("*.csv"))) if d.is_dir() else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("start", type=int)
    ap.add_argument("end", type=int)
    ap.add_argument("--save-root", default=SAVE_ROOT)
    # 한 달은 경기가 많아야 120개, 정상 속도면 5분입니다. 30분을 넘기면
    # 무언가 잘못된 것이니 끊고 다시 시도하는 편이 낫습니다.
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--retries", type=int, default=2,
                    help="달 하나가 실패했을 때 다시 시도할 횟수")
    ap.add_argument("--net-wait", type=int, default=3600,
                    help="네트워크가 끊겼을 때 최대 몇 초까지 기다릴지")
    args = ap.parse_args()

    tmp_dir = ROOT / "migration" / "_backfill_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    years = list(range(args.start, args.end + 1))
    print("수집할 시즌: %s (%d개), 달 단위로 나눠 부릅니다"
          % (", ".join(str(y) for y in years), len(years)), flush=True)
    print(flush=True)

    if not wait_for_network(args.net_wait):
        print("네트워크가 없습니다. 시작하지 않습니다.", flush=True)
        return 1

    t_all = time.time()
    year_fail = {}
    for yi, y in enumerate(years, start=1):
        t_y = time.time()
        before = csv_count(args.save_root, y)
        print("[%d/%d] %d 시즌 (이미 %d경기)" % (yi, len(years), y, before),
              flush=True)
        fails = []
        for m in MONTHS:
            s, e = month_range(y, m)
            ok = False
            for attempt in range(args.retries + 1):
                if not wait_for_network(args.net_wait):
                    print("      네트워크 복구 실패, 중단합니다.", flush=True)
                    return 1
                ok, secs, msg = run_chunk(s, e, args.save_root,
                                          args.timeout, tmp_dir)
                if ok:
                    if "done=0 skipped=0" not in msg:
                        print("      %d월  %.1f분  %s" % (m, secs / 60, msg),
                              flush=True)
                    break
                print("      %d월  %.1f분  실패(%d/%d)  %s"
                      % (m, secs / 60, attempt + 1, args.retries + 1, msg),
                      flush=True)
                # 상대 서버가 잠깐 막은 것일 수 있어 조금 쉬고 다시 봅니다.
                time.sleep(20)
            if not ok:
                fails.append(m)
        after = csv_count(args.save_root, y)
        print("      %d 완료  %.1f분  경기 %d개 (+%d)%s"
              % (y, (time.time() - t_y) / 60, after, after - before,
                 "  실패한 달: %s" % fails if fails else ""), flush=True)
        if fails:
            year_fail[y] = fails

    print(flush=True)
    print("전체 %.1f분" % ((time.time() - t_all) / 60), flush=True)
    for y in years:
        print("  %d  경기 %d개%s" % (y, csv_count(args.save_root, y),
                                   "  (실패 달 %s)" % year_fail[y]
                                   if y in year_fail else ""), flush=True)
    if year_fail:
        print("같은 명령으로 다시 돌리면 받은 경기는 건너뜁니다.", flush=True)
    return 1 if year_fail else 0


if __name__ == "__main__":
    sys.exit(main())
