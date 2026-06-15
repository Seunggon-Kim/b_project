#!/bin/bash
# 2010~2014 PBP/games 백필 — 인덱스 drop→대량적재→재생성 (크래시-안전판).
#   [A] 2011~2014 크롤 (2010 CSV 보존됨, 크롤러가 기존 SKIP)
#   [B1] PBP 인덱스 3개 DROP → [B2] 2010~2014 고속 적재 → [B3] 인덱스 재생성(순차)
# 안전장치(리뷰 반영):
#   - set -o pipefail: `| tee` 뒤에서도 로더의 실제 종료코드를 PIPESTATUS[0]로 포착
#   - trap recreate_indexes EXIT: DROP 후 어떤 경로로 죽어도(디스크가드 exit/OOM/리부트)
#     인덱스가 영구 드롭된 채 방치되지 않도록 종료 시 반드시 재생성
#   - 적재 성공한 연도의 CSV만 삭제(실패 연도는 보존 — 재크롤 불필요)
# 실행: nohup ./data_collection/backfill_2010_2014.sh > logs/backfill_2010_2014.log 2>&1 &
set -uo pipefail
cd ~/b_project
LOG=logs/backfill_2010_2014.log
VENV=venv/bin/python
DB=database/kbo_stats.db
log(){ echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }
freeguard(){ local m; m=$(df -m / | awk 'NR==2{print $4}'); if [ "${m:-0}" -lt 500 ]; then log "⚠️ 디스크 ${m}MB<500 — 중단(인덱스는 trap이 재생성)"; exit 1; fi; }

INDEXES_DROPPED=0
recreate_indexes(){
  # 인덱스를 드롭한 적이 있을 때만(=B1 이후) 재생성. 어떤 종료 경로에서도 호출됨(trap).
  [ "${INDEXES_DROPPED}" -eq 1 ] || return 0
  log "[B3] 인덱스 재생성 보장 (순차 I/O)"
  $VENV - <<PY 2>&1 | tee -a "$LOG"
import sqlite3, time
c=sqlite3.connect("$DB",timeout=3600)
c.execute("PRAGMA temp_store=MEMORY"); c.execute("PRAGMA cache_size=-80000")
for ix,col in (("idx_pbp_game","gameID"),("idx_pbp_batter","batter_ID"),("idx_pbp_pitcher","pitcher_ID")):
    t=time.time(); c.execute(f"CREATE INDEX IF NOT EXISTS {ix} ON play_by_play({col})"); c.commit()
    print(f"  {ix}: {round(time.time()-t)}s")
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("integrity:", c.execute("PRAGMA quick_check").fetchone()[0])
print("pbp 인덱스:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%'")])
c.close()
PY
  INDEXES_DROPPED=0   # 재생성 완료 → trap 중복 실행 방지
}
trap recreate_indexes EXIT

log "===== 2010~2014 백필 시작 (drop→load→reindex, 크래시-안전) ====="
freeguard

# ── Phase A: 2011~2014 크롤 (네트워크만; 이미 받은 경기는 SKIP) ──
for Y in 2011 2012 2013 2014; do
  freeguard
  log "[A] crawl $Y"
  $VENV crawler/pbp.py -f "${Y}0101" -t "${Y}1231" -p -d crawler/save/ 2>&1 \
    | grep -oE "done=[0-9]+ skipped=[0-9]+ broken=[0-9]+ failed=[0-9]+" | tail -1 | tee -a "$LOG" || true
  sleep 20
done

# ── Phase B-1: PBP 인덱스 DROP (대량 INSERT 시 인덱스 랜덤읽기 쓰래싱 제거) ──
log "[B1] DROP PBP indexes"
$VENV - <<PY 2>&1 | tee -a "$LOG"
import sqlite3
c=sqlite3.connect("$DB",timeout=600)
for ix in ("idx_pbp_game","idx_pbp_batter","idx_pbp_pitcher"):
    c.execute(f"DROP INDEX IF EXISTS {ix}")
c.commit(); print("dropped:", [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%'")])
c.close()
PY
INDEXES_DROPPED=1   # 이제부터 어떤 종료 경로든 trap이 인덱스를 재생성

# ── Phase B-2: 2010~2014 적재 (인덱스 없어 고속 append). 실패 연도는 CSV 보존 ──
LOADED=""
for Y in 2010 2011 2012 2013 2014; do
  freeguard
  log "[B2] load $Y (no-index)"
  $VENV data_collection/load_year_pbp.py "$Y" 2>&1 | tee -a "$LOG"
  rc=${PIPESTATUS[0]}
  if [ "$rc" -eq 0 ]; then
    LOADED="$LOADED $Y"
  else
    log "⚠️ load $Y 실패(rc=$rc) — CSV 보존(재시도 가능)"
  fi
done

# ── Phase B-3: 인덱스 재생성 (정상 경로 명시 호출; trap이 이중 보장) ──
recreate_indexes

# ── CSV 정리: 적재 성공한 연도만 삭제(실패 연도는 보존) ──
for Y in ${LOADED}; do rm -rf "crawler/save/$Y"; log "[cleanup] save/$Y 삭제(적재 완료)"; done
log "===== 2010~2014 백필 완료 (적재 성공:${LOADED:- 없음}) ====="
