#!/bin/bash
# 2015-2024 KBO 공식 batter/pitcher 통계 백필
# EC2 ~/b_project에서 실행: nohup ./data_collection/backfill_2015_2024.sh > /dev/null 2>&1 &
#
# 시즌 순서: 최신(2024) → 과거(2015)
# 한 시즌당 batter (10팀×3탭) + pitcher (10팀×4탭) ≈ 1~1.5시간
# 전체 10시즌 ≈ 12~15시간
# t3.micro 911MB RAM 고려, 시즌 사이 sleep으로 메모리 정리

set -e
cd ~/b_project

LOG_DIR="logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/backfill_$(date +%Y%m%d_%H%M%S).log"

echo "===== 백필 시작 $(date) =====" | tee -a "$LOG"

# 최신 → 과거 (중간 중단 시 최신 데이터부터 확보)
for YEAR in 2024 2023 2022 2021 2020 2019 2018 2017 2016 2015; do
  echo "" | tee -a "$LOG"
  echo "########## ${YEAR} 시즌 시작 $(date) ##########" | tee -a "$LOG"

  echo "--- ${YEAR} batter scraper ---" | tee -a "$LOG"
  venv/bin/python data_collection/selenium_batter_scraper.py --year "$YEAR" 2>&1 | tee -a "$LOG" || echo "⚠️ batter scraper ${YEAR} 실패" | tee -a "$LOG"

  echo "--- ${YEAR} batter → DB ---" | tee -a "$LOG"
  venv/bin/python data_collection/kbo_to_db.py --year "$YEAR" 2>&1 | tee -a "$LOG" || echo "⚠️ batter DB ${YEAR} 실패" | tee -a "$LOG"

  sleep 60

  echo "--- ${YEAR} pitcher scraper ---" | tee -a "$LOG"
  venv/bin/python data_collection/selenium_pitcher_scraper.py --year "$YEAR" 2>&1 | tee -a "$LOG" || echo "⚠️ pitcher scraper ${YEAR} 실패" | tee -a "$LOG"

  echo "--- ${YEAR} pitcher → DB ---" | tee -a "$LOG"
  venv/bin/python data_collection/pitcher_to_db.py --year "$YEAR" 2>&1 | tee -a "$LOG" || echo "⚠️ pitcher DB ${YEAR} 실패" | tee -a "$LOG"

  echo "########## ${YEAR} 시즌 완료 $(date) ##########" | tee -a "$LOG"
  sleep 120
done

echo "" | tee -a "$LOG"
echo "===== 백필 종료 $(date) =====" | tee -a "$LOG"
