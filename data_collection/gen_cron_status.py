#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cron 작업별 '마지막 실행 시각'을 dashboard_js/cron_status.json으로 출력한다.

데이터 탐색 페이지(pages/database-explorer.html)의 '자동 수집 스케줄(Cron)' 표가
이 JSON을 fetch해 '마지막 업데이트 시간' 컬럼을 채운다.

각 작업의 마지막 실행은 로그 파일의 mtime으로 판정한다.
  - append 로그(>>)  : 파일 mtime = 마지막 실행
  - per-run 로그     : 가장 최근 파일의 mtime = 마지막 실행
서버 타임존이 UTC라도 KST 고정 오프셋(+9)으로 변환하므로 표기는 항상 KST다.

cron 등록(별도 라인):
  */15 * * * * cd ~/b_project && venv/bin/python data_collection/gen_cron_status.py >> /tmp/cron_status.log 2>&1
"""
import os
import json
import glob
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # ~/b_project
LOGS = os.path.join(ROOT, "logs")
OUT = os.path.join(ROOT, "dashboard_js", "cron_status.json")
KST = timezone(timedelta(hours=9))

# 작업 id -> 마지막 실행을 나타내는 로그 경로(glob 허용, 여러 개면 가장 최근 mtime)
SIGNALS = {
    "official_stats": [os.path.join(LOGS, "selenium_batter_*.log"),
                       os.path.join(LOGS, "selenium_pitcher_*.log")],
    "pbp":             [os.path.join(LOGS, "daily_pbp_*.log")],
    "player_detector": ["/tmp/daily_player_detector.log"],
    "cleanup":         ["/tmp/cleanup.log"],
    "park_factors":    ["/tmp/park_factors_pipeline.log"],
    "futures":         ["/tmp/futures_update.log"],
    "player_info":     ["/tmp/monthly_player_full.log"],
    "registry_sync":   ["/tmp/player_registry_sync.log"],
}


def latest_mtime(patterns):
    """patterns(글롭 목록) 중 가장 최근 mtime(epoch) 반환, 없으면 None."""
    best = None
    for pat in patterns:
        for f in glob.glob(pat):
            try:
                m = os.path.getmtime(f)
            except OSError:
                continue
            if best is None or m > best:
                best = m
    return best


def fmt(epoch):
    if epoch is None:
        return None
    return datetime.fromtimestamp(epoch, KST).strftime("%Y-%m-%d %H:%M")


def main():
    jobs = {job: fmt(latest_mtime(pats)) for job, pats in SIGNALS.items()}
    data = {
        "generated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "timezone": "KST",
        "jobs": jobs,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, OUT)  # 원자적 교체(부분 쓰기 노출 방지)
    print(f"wrote {OUT}: {data}")


if __name__ == "__main__":
    main()
