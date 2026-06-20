#!/bin/bash
# Phase C — 2010~2014 백필(인덱스 재생성)이 끝난 뒤 후속 마무리.
#   [precheck] PBP 인덱스 3개 존재 + 무결성 확인 (재생성 미완이면 중단)
#   [1] 은퇴선수 보강: scrape_missing_players.py MISSING_SEASONS=all (requests, 플래그 세팅)
#   [2] games 보강: games_from_pbp.py (INSERT OR IGNORE — 누락 시즌 보완)
#   [3] 플래그·is_active 재도출: backfill_player_flags.py (신규 선수 포함)
#   [verify] verify_full_backfill.py
# 실행: nohup ./data_collection/phase_c.sh > logs/phase_c.log 2>&1 &
set -u
cd ~/b_project
LOG=logs/phase_c.log
VENV=venv/bin/python
DB=database/kbo_stats.db
log(){ echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }

log "===== Phase C 시작 ====="
# precheck: 인덱스 재생성 완료 확인
NIDX=$($VENV -c "import sqlite3;print(len(sqlite3.connect('$DB',timeout=120).execute(\"SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%'\").fetchall()))" 2>/dev/null)
if [ "${NIDX:-0}" -lt 3 ]; then
  log "⚠️ PBP 인덱스 ${NIDX}개(<3) — 재생성 미완. Phase C 중단(백필 완료 후 재실행)."
  exit 1
fi
log "precheck OK: PBP 인덱스 ${NIDX}개"

log "[1] scrape_missing (MISSING_SEASONS=all) — 은퇴선수 보강"
MISSING_SEASONS=all $VENV data_collection/scrape_missing_players.py 2>&1 | tail -8 | tee -a "$LOG" || log "scrape_missing 실패(부분 가능)"

log "[2] games_from_pbp — 누락 시즌 games 보완"
$VENV data_collection/games_from_pbp.py 2>&1 | tail -4 | tee -a "$LOG" || log "games_from_pbp 실패"

log "[3] backfill_player_flags — 플래그·is_active 재도출(신규 선수 포함)"
$VENV data_collection/backfill_player_flags.py 2>&1 | tail -6 | tee -a "$LOG" || log "backfill_player_flags 실패"

log "[verify] 종합 검증"
$VENV data_collection/verify_full_backfill.py 2>&1 | tee -a "$LOG"
log "===== Phase C 완료 ====="
