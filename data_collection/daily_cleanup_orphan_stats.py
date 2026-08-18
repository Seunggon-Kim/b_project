"""
매일 자동 cleanup: official stats에 row 있지만 PBP 0회인 시범경기·잘못 분류 row 삭제

조건:
  - season >= 2024
  - created_at이 그 시즌 종료 후 ((season+1)-11-01 이후 또는 시즌+11/01 이후)
  - PBP에 그 (player_id, season) 등장 0회
  - 단, 진행 중 시즌(current year)은 정규시즌 시작 한 달 후부터 검증

매일 19:30 UTC cron (PBP 18:30 + detector 19:00 후)
"""
import os
import sqlite3
from datetime import date
from pathlib import Path

# DB 경로: 환경변수 KBO_DB 우선, 없으면 저장소 기준 상대경로.
# EC2 절대경로(/home/ubuntu/...)는 윈도우와 GitHub Actions 러너에서
# 동작하지 않습니다. 그 서버는 2026-07-14 에 없어졌습니다.
DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db")
TODAY = date.today()
CURR_YEAR = TODAY.year

con = sqlite3.connect(DB, timeout=60)
cur = con.cursor()

# Stage 1: created_at 기반 1차 후보 — 그 시즌 종료 후 created
cur.execute("""
    SELECT 'pitcher' AS kind, player_id, season FROM kbo_official_pitcher_stats
    WHERE season >= 2024
      AND season < ?
      AND created_at > (season || '-11-01')
      AND innings_pitched IS NOT NULL AND innings_pitched <> '0'
    UNION ALL
    SELECT 'batter' AS kind, player_id, season FROM kbo_official_batter_stats
    WHERE season >= 2024
      AND season < ?
      AND created_at > (season || '-11-01')
      AND plate_appearance > 0
""", (CURR_YEAR, CURR_YEAR))
candidates = cur.fetchall()
print(f"  candidates (post-season created, prior years): {len(candidates)}")

# Stage 2: PBP 0건 검증 → 삭제
deleted = 0
for kind, pid, season in candidates:
    if kind == "pitcher":
        n = cur.execute(
            "SELECT COUNT(*) FROM play_by_play WHERE pitcher_ID = ? AND substr(gameID,1,4) = ?",
            (pid, str(season))
        ).fetchone()[0]
        if n == 0:
            cur.execute("DELETE FROM kbo_official_pitcher_stats WHERE player_id=? AND season=?", (pid, season))
            deleted += 1
    else:
        n = cur.execute(
            "SELECT COUNT(*) FROM play_by_play WHERE batter_ID = ? AND substr(gameID,1,4) = ?",
            (pid, str(season))
        ).fetchone()[0]
        if n == 0:
            cur.execute("DELETE FROM kbo_official_batter_stats WHERE player_id=? AND season=?", (pid, season))
            deleted += 1

con.commit()
print(f"  deleted orphan rows: {deleted}")
con.close()
