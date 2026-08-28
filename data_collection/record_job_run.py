# -*- coding: utf-8 -*-
"""수집 작업의 실행 결과를 D1 에 남깁니다.

EC2 의 `cron_status.json` 을 대신합니다. 그 파일은 서버가 15분마다
정적 파일로 다시 쓰던 것인데, 이제 서버가 없습니다. Pages 는 정적
호스팅이라 실행 중에 파일을 못 바꿉니다. 그래서 D1 에 씁니다.

데이터 탐색기의 "마지막 업데이트 시간" 칸이 이것을 읽습니다
(`GET /jobs/status`). **기록하지 않으면 화면에 "기록 없음"이 뜹니다.**
성공만 남기지 말고 실패도 남기십시오. 조용히 멈춘 것과 실패한 것을
구분할 수 있어야 합니다.

    py data_collection/record_job_run.py --job pbp --status ok --note "3경기 859행"
    py data_collection/record_job_run.py --job official_stats --status fail
"""
import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from d1_load import run_d1, sql_literal  # noqa: E402

# 화면이 한국 시각을 보여 줍니다. 러너는 UTC 라 그대로 쓰면 아홉 시간
# 어긋납니다.
KST = timezone(timedelta(hours=9))

# 화면의 data-job 값과 같아야 합니다
# (dashboard_js/pages/database-explorer.html).
KNOWN_JOBS = {
    "official_stats", "pbp", "games", "player_detector", "cleanup",
    "park_factors", "registry_sync", "futures", "player_info",
    # 2008~2014 PBP 되채우기입니다. 약 51일 걸리고 끝나면 없앱니다.
    "pbp_backfill",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--status", required=True,
                    choices=["ok", "fail", "skip"])
    ap.add_argument("--note", default=None)
    ap.add_argument("--duration", type=int, default=None, help="초")
    args = ap.parse_args()

    if args.job not in KNOWN_JOBS:
        # 오타로 새 이름이 생기면 화면에는 영영 "기록 없음"이 뜹니다.
        # 그래도 기록은 남기되 눈에 띄게 알립니다.
        print("경고: 화면에 없는 작업 이름입니다: %s" % args.job)
        print("  아는 이름: %s" % ", ".join(sorted(KNOWN_JOBS)))

    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")
    run_d1(
        "INSERT OR REPLACE INTO meta_job_runs "
        "(job, last_run_at, status, note, duration_sec) VALUES (%s,%s,%s,%s,%s);"
        % (sql_literal(args.job), sql_literal(now), sql_literal(args.status),
           sql_literal(args.note),
           "NULL" if args.duration is None else int(args.duration)))
    print("기록: %s  %s  %s" % (args.job, now, args.status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
