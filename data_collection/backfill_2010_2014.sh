#!/bin/bash
# 2010~2014 PBP/games 백필 — 인덱스 drop→대량적재→재생성.
# t3.micro EBS 인덱스 랜덤읽기 쓰래싱 회피용 표준 대량로드 기법.
#   [A] 2011~2014 크롤 (2010 은 CSV 보존됨)
#   [B] PBP 인덱스 3개 DROP → 2010~2014 고속 적재(append) → 인덱스 일괄 재생성(순차)
# 재생성 중 PBP 쿼리(arsenal 등)는 풀스캔으로 느려짐 — 단독 사용자라 무방.
# 실행: nohup ./data_collection/backfill_2010_2014.sh > logs/backfill_2010_2014.log 2>&1 &
set -u
cd ~/b_project
LOG=logs/backfill_2010_2014.log
VENV=venv/bin/python
DB=database/kbo_stats.db
log(){ echo "$(date -u +%H:%M:%S) $*" | tee -a "$LOG"; }
freeguard(){ local m; m=$(df -m / | awk 'NR==2{print $4}'); if [ "${m:-0}" -lt 500 ]; then log "⚠️ 디스크 ${m}MB<500 — 중단"; exit 1; fi; }

log "===== 2010~2014 백필 시작 (drop→load→reindex) ====="
freeguard

# ── Phase A: 2011~2014 크롤 (네트워크만, 이미 받은 경기는 SKIP) ──
for Y in 2011 2012 2013 2014; do
  freeguard
  log "[A] crawl $Y"
  $VENV crawler/pbp.py -f "${Y}0101" -t "${Y}1231" -p -d crawler/save/ 2>&1 \
    | grep -oE "done=[0-9]+ skipped=[0-9]+ broken=[0-9]+ failed=[0-9]+" | tail -1 | tee -a "$LOG" \
    || log "crawl $Y 일부 실패(개별 skip)"
  sleep 20
done

# ── Phase B-1: PBP 인덱스 DROP ──
log "[B1] DROP PBP indexes"
$VENV - <<PY 2>&1 | tee -a "$LOG"
import sqlite3
c=sqlite3.connect("$DB",timeout=600)
for ix in ("idx_pbp_game","idx_pbp_batter","idx_pbp_pitcher"):
    c.execute(f"DROP INDEX IF EXISTS {ix}")
c.commit()
print("남은 pbp 인덱스:", c.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%'").fetchall())
c.close()
PY

# ── Phase B-2: 2010~2014 적재 (인덱스 없어 고속 append) ──
for Y in 2010 2011 2012 2013 2014; do
  freeguard
  log "[B2] load $Y (no-index)"
  $VENV data_collection/load_year_pbp.py "$Y" 2>&1 | tee -a "$LOG" || log "load $Y 실패"
done

# ── Phase B-3: 인덱스 재생성 (순차 I/O) ──
log "[B3] CREATE indexes (recreate, 순차 — 시간 소요)"
$VENV - <<PY 2>&1 | tee -a "$LOG"
import sqlite3, time
c=sqlite3.connect("$DB",timeout=3600)
c.execute("PRAGMA temp_store=MEMORY"); c.execute("PRAGMA cache_size=-80000")
for ix,col in (("idx_pbp_game","gameID"),("idx_pbp_batter","batter_ID"),("idx_pbp_pitcher","pitcher_ID")):
    t=time.time(); c.execute(f"CREATE INDEX IF NOT EXISTS {ix} ON play_by_play({col})"); c.commit()
    print(f"  {ix}: {round(time.time()-t)}s")
c.execute("PRAGMA wal_checkpoint(TRUNCATE)")
print("integrity:", c.execute("PRAGMA quick_check").fetchone()[0])
print("PBP<2015:", c.execute("SELECT substr(CAST(game_date AS TEXT),1,4) y,COUNT(*) FROM play_by_play WHERE game_date<20150000 GROUP BY y ORDER BY y").fetchall())
print("games seasons:", c.execute("SELECT COUNT(DISTINCT season) FROM games").fetchone()[0])
c.close()
PY

# ── CSV 정리 (디스크) ──
for Y in 2010 2011 2012 2013 2014; do rm -rf "crawler/save/$Y"; done
log "===== 2010~2014 백필 완료 ====="
