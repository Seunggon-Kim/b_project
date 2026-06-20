# -*- coding: utf-8 -*-
"""auto-chain 성공 게이트(읽기 전용). 백필 B-3 완료를 프로그램적으로 확인.
조건: PBP 인덱스 3개 + 2010~2014 각 연도 PBP>0 + quick_check=ok -> GATE=PASS.
"""
import sqlite3

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
c = sqlite3.connect(DB, timeout=300)

idx = [r[0] for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_pbp%'")]
ok_idx = len(idx) == 3

years = {}
for y in (2010, 2011, 2012, 2013, 2014):
    n = c.execute(
        "SELECT COUNT(*) FROM play_by_play WHERE game_date>=? AND game_date<?",
        (y * 10000, (y + 1) * 10000)).fetchone()[0]
    years[y] = n
ok_rows = all(v > 0 for v in years.values())

integ = c.execute("PRAGMA quick_check").fetchone()[0]
ok_int = (integ == "ok")
c.close()

print("indexes:", idx, "(ok)" if ok_idx else "(FAIL, !=3)")
print("years:", years, "(ok)" if ok_rows else "(FAIL, 0 in some year)")
print("integrity:", integ)
print("GATE=PASS" if (ok_idx and ok_rows and ok_int) else "GATE=FAIL")
