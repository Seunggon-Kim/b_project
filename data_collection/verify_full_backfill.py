# -*- coding: utf-8 -*-
"""pre-2015 백필 + 플래그 + 선수보강 완료 후 종합 검증(읽기 전용).

실행: python data_collection/verify_full_backfill.py [db_path]
점검: 무결성 / 연도별 PBP·games / games team_id 해소 / 선수·플래그·현역 분포 /
      PBP 선수 id 커버리지(미등록 잔여) / 인덱스 존재.
"""
import sqlite3
import sys

DB = sys.argv[1] if len(sys.argv) > 1 else "/home/ubuntu/b_project/database/kbo_stats.db"
c = sqlite3.connect(DB, timeout=120)


def q(sql, p=()):
    return c.execute(sql, p).fetchall()


print("=" * 60)
print("integrity:", q("PRAGMA quick_check")[0][0])

print("\n[PBP 연도별 행수 / 경기수]")
for y, rows in q("SELECT substr(CAST(game_date AS TEXT),1,4) y, COUNT(*) FROM play_by_play GROUP BY y ORDER BY y"):
    g = q("SELECT COUNT(DISTINCT gameID) FROM play_by_play WHERE substr(gameID,1,4)=?", (y,))[0][0]
    print(f"   {y}: PBP {rows:>8,}  / 경기 {g:>4}")

print("\n[games 시즌별]")
for s, n in q("SELECT season, COUNT(*) FROM games GROUP BY season ORDER BY season"):
    print(f"   {s}: {n}")

bad = q("SELECT season, COUNT(*) FROM games WHERE home_team_id NOT IN (SELECT team_id FROM teams) "
        "OR away_team_id NOT IN (SELECT team_id FROM teams) GROUP BY season ORDER BY season")
print("\n[games team_id 미해소(teams 외)]:", bad if bad else "없음 ✓")

print("\n[players]")
print("   총:", q("SELECT COUNT(*) FROM players")[0][0])
print("   player_type:", dict(q("SELECT player_type, COUNT(*) FROM players GROUP BY 1")))
print("   is_active:", dict(q("SELECT is_active, COUNT(*) FROM players GROUP BY 1")))
print("   국적 상위:", q("SELECT nationality, COUNT(*) FROM players WHERE is_foreign=1 GROUP BY 1 ORDER BY 2 DESC LIMIT 8"))

# PBP 선수 id 커버리지: 전 시즌 PBP에 등장하나 players 미등록인 id 수
miss = q("""SELECT COUNT(DISTINCT id) FROM (
  SELECT batter_ID id FROM play_by_play UNION SELECT pitcher_ID FROM play_by_play)
  WHERE id IS NOT NULL AND id<>'' AND CAST(id AS INTEGER)>0
  AND id NOT IN (SELECT player_id FROM players)""")[0][0]
print("\n[PBP 등장하나 players 미등록 선수 수]:", miss, "(0 이면 #1 보강 완료)")

print("\n[play_by_play 인덱스]")
print("  ", q("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%' ORDER BY name"))
c.close()
print("=" * 60)
