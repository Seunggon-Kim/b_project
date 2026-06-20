# -*- coding: utf-8 -*-
"""play_by_play 의 float 표기 선수 ID('75847.0')를 정수 문자열('75847')로 정규화.

원인: 로더(pandas)가 ID 컬럼에 NaN 1개라도 있으면 컬럼 전체를 float64로 읽어 '.0'이 붙음.
효과: PBP의 batter_ID/pitcher_ID 가 players.player_id(정수문자열)와 정상 조인됨 →
      검증 리포트의 '미등록 선수' 허수(568)가 실제값(오기 1건)으로 수렴.
안전: 약 3만 행 한정 UPDATE(인덱스 유지), 단일 트랜잭션, WAL. idempotent(재실행 시 0행).
실행: venv/bin/python data_collection/normalize_pbp_ids.py
"""
import sqlite3
import time

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
c = sqlite3.connect(DB, timeout=600)
c.execute("PRAGMA journal_mode=WAL")
c.execute("PRAGMA synchronous=NORMAL")
c.execute("PRAGMA busy_timeout=600000")
c.execute("PRAGMA cache_size=-80000")


def q1(sql, p=()):
    return c.execute(sql, p).fetchone()[0]


b_before = q1("SELECT COUNT(*) FROM play_by_play WHERE batter_ID LIKE '%.0'")
p_before = q1("SELECT COUNT(*) FROM play_by_play WHERE pitcher_ID LIKE '%.0'")
print(f"[before] float rows: batter={b_before:,} pitcher={p_before:,}", flush=True)

t = time.time()
c.execute("BEGIN")
rb = c.execute("UPDATE play_by_play SET batter_ID=CAST(CAST(batter_ID AS INTEGER) AS TEXT) "
               "WHERE batter_ID LIKE '%.0'").rowcount
rp = c.execute("UPDATE play_by_play SET pitcher_ID=CAST(CAST(pitcher_ID AS INTEGER) AS TEXT) "
               "WHERE pitcher_ID LIKE '%.0'").rowcount
c.execute("COMMIT")
print(f"[update] batter={rb:,} pitcher={rp:,} in {round(time.time()-t)}s", flush=True)

c.execute("PRAGMA wal_checkpoint(TRUNCATE)")

b_after = q1("SELECT COUNT(*) FROM play_by_play WHERE batter_ID LIKE '%.0'")
p_after = q1("SELECT COUNT(*) FROM play_by_play WHERE pitcher_ID LIKE '%.0'")
print(f"[after] float rows: batter={b_after:,} pitcher={p_after:,} (0 이어야 정상)", flush=True)

miss_sql = """SELECT DISTINCT id FROM (
  SELECT batter_ID id FROM play_by_play UNION SELECT pitcher_ID FROM play_by_play)
  WHERE id IS NOT NULL AND id<>'' AND CAST(id AS INTEGER)>0
  AND id NOT IN (SELECT player_id FROM players)"""
rem = [r[0] for r in c.execute(miss_sql)]
print(f"[verify] players 미등록(조인 불일치) 잔여: {len(rem)}", flush=True)
print(f"[verify] 잔여 ID 목록: {rem}", flush=True)
print(f"[verify] integrity: {q1('PRAGMA quick_check')}", flush=True)
c.close()
print("[done] normalize 완료", flush=True)
