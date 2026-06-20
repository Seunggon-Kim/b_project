#!/bin/bash
# 매일 자동 PBP 수집 + DB 적재 (cron 등록 대상)
# - 어제 일자 PBP 크롤링
# - CSV → DB import
# 로그: ~/b_project/logs/daily_pbp_YYYYMMDD.log

set -e
cd ~/b_project

YESTERDAY=$(date -d 'yesterday' +%Y%m%d)
LOG_DIR="$HOME/b_project/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/daily_pbp_${YESTERDAY}.log"

echo "===== Daily PBP $(date) — target: ${YESTERDAY} =====" | tee -a "$LOG"

# 1. PBP 크롤링 (어제만)
venv/bin/python crawler/pbp.py -f "$YESTERDAY" -t "$YESTERDAY" -d crawler/save/ 2>&1 | tail -5 | tee -a "$LOG"

# 2. CSV → DB import (방금 크롤링한 어제 csv만)
YEAR=${YESTERDAY:0:4}
venv/bin/python - <<PY 2>&1 | tee -a "$LOG"
import sqlite3, pandas as pd, pathlib
DB = "/home/ubuntu/b_project/database/kbo_stats.db"
date_str = "$YESTERDAY"
year = "$YEAR"
csv_dir = pathlib.Path(f"/home/ubuntu/b_project/crawler/save/{year}")
new_csvs = sorted(csv_dir.glob(f"{date_str}*.csv"))
print(f"  found {len(new_csvs)} csv files for {date_str}")

if not new_csvs:
    print("  no games crawled (rest day or future). exit.")
    raise SystemExit(0)

con = sqlite3.connect(DB)
cur = con.cursor()
# delete existing entries for this date (idempotent)
cur.execute("DELETE FROM play_by_play WHERE game_date=?", (int(date_str),))
print(f"  deleted existing rows: {cur.rowcount}")
total = 0
for f in new_csvs:
    df = pd.read_csv(f, encoding="cp949")
    # 선수 ID 정규화: 컬럼에 NaN 1개라도 있으면 pandas가 float64로 읽어 '75847.0'이 적재됨
    # → players(정수문자열)와 조인 끊김. 정수 문자열로 통일(결측은 None).
    for _idc in ("batter_ID", "pitcher_ID"):
        if _idc in df.columns:
            _s = pd.to_numeric(df[_idc], errors="coerce")
            df[_idc] = _s.map(lambda v: str(int(v)) if pd.notna(v) else None)
    df.to_sql("play_by_play", con, if_exists="append", index=False)
    total += len(df)
con.commit()
cur.execute("SELECT COUNT(*) FROM play_by_play WHERE game_date=?", (int(date_str),))
print(f"  imported {total} rows, DB total for date: {cur.fetchone()[0]}")
con.close()
PY

echo "===== Done $(date) =====" | tee -a "$LOG"
