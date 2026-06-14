#!/bin/bash
# 2008-2014 KBO Play-by-Play(PBP) 과거 백필 (연도별)
# EC2 ~/b_project에서 실행: nohup ./data_collection/backfill_pre2015.sh > /dev/null 2>&1 &
#
# 각 연도 Y에 대해:
#   1) crawler/pbp.py 로 정규시즌+포스트시즌 PBP 크롤링 (Y0101 ~ Y1231)
#   2) 그 해 crawler/save/<Y>/ 에 생성된 게임별 CSV 를 DB 에 idempotent 적재
#      (daily_kbo_pbp.sh 와 동일한 패턴: game_date 별 DELETE 후 append)
#   3) 연도별 재실행 가능(resumable): 크롤러는 이미 받은 CSV 를 SKIP,
#      적재는 game_date 단위 DELETE→INSERT 라 중복 없이 다시 돌려도 안전.
#   로그: logs/backfill_pre2015_<year>.log
#
# ── 데이터 한계(caveat) ────────────────────────────────────────────────
#  * 2017 이전 경기는 텍스트 중계(PBP) 만 존재 → 피치 트래킹 컬럼
#    (px, pz, speed, pfx_x/z, x0/z0, sz_top/bot, vx0/vy0/vz0, ax/ay/az 등)
#    은 전부 NULL 로 적재됩니다. 2008-2014 백필은 정성적 PBP(투구결과·타석결과·
#    주자·수비위치) 위주이며 트래킹 수치는 기대하지 마십시오.
#  * pre-2008 (2007 이전) 은 Naver 소스에서 제공되지 않아 백필 불가합니다.
#    (download.py 의 regular_start/playoff_start 도 2008 부터 정의)
#  * 대량 백필은 Naver rate-limit 에 걸릴 수 있습니다. 크롤러에 추가된
#    FETCH_SLEEP_SEC(기본 0.4초, crawler/download.py) throttle 로 완화하되,
#    한 해 안에서도 차단이 의심되면 연도 사이 sleep 을 늘리십시오.
#  * 과거 gameID 포맷 차이(포스트시즌 시즌 suffix 등)는 download.py 의
#    gid_year>3000 분기에서 처리되며, 파싱 불가 경기는 이제 배치를 중단시키지
#    않고 skip+log 됩니다(하드닝 반영).
#
# ── 안전 파일럿(권장: 본 백필 전 1회) ──────────────────────────────────
#  하드닝된 크롤러가 구포맷(2014) 경기에서 동작하는지 DB 쓰기 없이 CSV 로만 검증:
#
#      cd ~/b_project
#      venv/bin/python crawler/pbp.py -f 20140401 -t 20140407 -d crawler/save/
#      ls crawler/save/2014/   # 게임별 csv 가 생성되는지, log.txt 의 요약 확인
#
#  (위 명령은 DB 를 건드리지 않습니다. -j/-p 없이 정규시즌만, 한 주만 받습니다.)
# ──────────────────────────────────────────────────────────────────────

set -e
cd ~/b_project

DB="/home/ubuntu/b_project/database/kbo_stats.db"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

echo "===== pre-2015 PBP 백필 시작 $(date) ====="

# 과거 → 최신 (2008 부터 순차). 중간 중단 시 연도 단위로 이어서 재실행 가능.
for YEAR in 2008 2009 2010 2011 2012 2013 2014; do
  LOG="$LOG_DIR/backfill_pre2015_${YEAR}.log"
  echo "" | tee -a "$LOG"
  echo "########## ${YEAR} 시즌 PBP 시작 $(date) ##########" | tee -a "$LOG"

  # 1) 크롤링: 정규시즌(-j join) + 포스트시즌(-p). 이미 받은 경기는 크롤러가 SKIP.
  echo "--- ${YEAR} PBP 크롤링 ---" | tee -a "$LOG"
  venv/bin/python crawler/pbp.py -f "${YEAR}0101" -t "${YEAR}1231" -j -p -d crawler/save/ 2>&1 \
    | tee -a "$LOG" || echo "⚠️ ${YEAR} 크롤링 일부 실패(개별 경기 skip 로그 확인)" | tee -a "$LOG"

  # 2) 그 해 게임별 CSV → DB idempotent 적재 (daily_kbo_pbp.sh 와 동일 패턴)
  echo "--- ${YEAR} CSV → DB 적재 ---" | tee -a "$LOG"
  venv/bin/python - "$YEAR" <<'PY' 2>&1 | tee -a "$LOG" || echo "⚠️ ${YEAR} DB 적재 실패" | tee -a "$LOG"
import sys, sqlite3, pandas as pd, pathlib

year = sys.argv[1]
DB = "/home/ubuntu/b_project/database/kbo_stats.db"
csv_dir = pathlib.Path(f"/home/ubuntu/b_project/crawler/save/{year}")

if not csv_dir.is_dir():
    print(f"  {year}: save dir 없음 ({csv_dir}). 크롤링 결과 없음, skip.")
    raise SystemExit(0)

# 게임별 CSV 만 (연도 합본 {year}.csv, source/ 하위 원본 등은 제외)
game_csvs = sorted(
    f for f in csv_dir.glob("*.csv")
    if f.stem[:8].isdigit() and not f.name.startswith("~$")
)
print(f"  {year}: 게임별 CSV {len(game_csvs)}개 발견")
if not game_csvs:
    raise SystemExit(0)

con = sqlite3.connect(DB)
cur = con.cursor()

# 이번 백필에 등장하는 game_date 들을 먼저 일괄 삭제(idempotent).
# game_date 는 YYYYMMDD 문자열(game_id[:8]). daily 로더와 동일하게 정수로 매칭.
dates = set()
frames = {}
for f in game_csvs:
    try:
        df = pd.read_csv(f, encoding="cp949")
    except Exception:
        df = pd.read_csv(f, encoding="utf-8")
    frames[f] = df
    if "game_date" in df.columns and len(df) > 0:
        for d in df["game_date"].dropna().unique():
            try:
                dates.add(int(str(d)[:8]))
            except (ValueError, TypeError):
                pass

deleted = 0
for d in dates:
    cur.execute("DELETE FROM play_by_play WHERE game_date=?", (d,))
    deleted += cur.rowcount
print(f"  {year}: 기존 행 삭제 {deleted} (game_date {len(dates)}개)")

total = 0
loaded = 0
for f, df in frames.items():
    if len(df) == 0:
        continue
    df.to_sql("play_by_play", con, if_exists="append", index=False)
    total += len(df)
    loaded += 1
con.commit()

cur.execute(
    "SELECT COUNT(*) FROM play_by_play WHERE CAST(SUBSTR(CAST(game_date AS TEXT),1,4) AS INT)=?",
    (int(year),),
)
print(f"  {year}: {loaded}개 경기, {total}행 적재. DB 내 {year} 시즌 PBP 행: {cur.fetchone()[0]}")
con.close()
PY

  echo "########## ${YEAR} 시즌 PBP 완료 $(date) ##########" | tee -a "$LOG"
  # Naver rate-limit 완화를 위한 연도 사이 휴지(크롤러 throttle 보완)
  sleep 60
done

echo "===== pre-2015 PBP 백필 종료 $(date) ====="
