#!/bin/bash
# pre-2015 백필 완료를 기다렸다가 후속 단계를 자동 실행한다 (무인 완주).
#   [A] 백필 후 연도별 PBP/경기 수 기록
#   [B] #2: games 전 시즌 보강 (games_from_pbp.py — 2015~2024·2026 채움)
#   [C] #1: 은퇴 선수 보강 (scrape_missing_players.py, MISSING_SEASONS=all)
#   [D] 플래그·is_active 재도출 (신규 선수 포함)
#   [E] 최종 요약
# 실행: nohup ./data_collection/post_backfill.sh > /dev/null 2>&1 &
# 각 단계는 || 가드로 실패해도 다음 단계 진행. 모두 idempotent(재실행 안전).
cd ~/b_project
LOG="logs/post_backfill.log"

echo "$(date -u) post_backfill: backfill_pre2015.sh 종료 대기..." | tee -a "$LOG"
sleep 30
while pgrep -f "backfill_pre2015.sh" >/dev/null 2>&1; do sleep 120; done
echo "$(date -u) 백필 종료 감지. 후속 시작." | tee -a "$LOG"

echo "=== [A] 백필 후 연도별 PBP ===" | tee -a "$LOG"
venv/bin/python - <<'PY' 2>&1 | tee -a "$LOG"
import sqlite3
c=sqlite3.connect('database/kbo_stats.db',timeout=120)
print('PBP rows by year:', c.execute("SELECT substr(CAST(game_date AS TEXT),1,4) y,COUNT(*) FROM play_by_play GROUP BY y ORDER BY y").fetchall())
print('distinct games in PBP by year:', c.execute("SELECT substr(gameID,1,4) y,COUNT(DISTINCT gameID) FROM play_by_play GROUP BY y ORDER BY y").fetchall())
PY

echo "=== [B] #2 games_from_pbp (전 시즌 games 보강) ===" | tee -a "$LOG"
venv/bin/python data_collection/games_from_pbp.py 2>&1 | tee -a "$LOG" || echo "games_from_pbp FAIL" | tee -a "$LOG"

echo "=== [C] #1 scrape_missing_players (MISSING_SEASONS=all) ===" | tee -a "$LOG"
MISSING_SEASONS=all venv/bin/python data_collection/scrape_missing_players.py 2>&1 | tee -a "$LOG" || echo "scrape_missing FAIL" | tee -a "$LOG"

echo "=== [D] 플래그·is_active 재도출 ===" | tee -a "$LOG"
venv/bin/python data_collection/backfill_player_flags.py 2>&1 | tee -a "$LOG" || echo "backfill_player_flags FAIL" | tee -a "$LOG"

echo "=== [E] 최종 요약 ===" | tee -a "$LOG"
venv/bin/python - <<'PY' 2>&1 | tee -a "$LOG"
import sqlite3
c=sqlite3.connect('database/kbo_stats.db',timeout=120)
print('PBP rows by year:', c.execute("SELECT substr(CAST(game_date AS TEXT),1,4) y,COUNT(*) FROM play_by_play GROUP BY y ORDER BY y").fetchall())
print('games by season:', c.execute("SELECT season,COUNT(*) FROM games GROUP BY season ORDER BY season").fetchall())
print('players total:', c.execute("SELECT COUNT(*) FROM players").fetchone()[0])
print('player_type:', c.execute("SELECT player_type,COUNT(*) FROM players GROUP BY 1").fetchall())
print('is_active:', c.execute("SELECT is_active,COUNT(*) FROM players GROUP BY 1").fetchall())
PY
echo "$(date -u) post_backfill COMPLETE" | tee -a "$LOG"
