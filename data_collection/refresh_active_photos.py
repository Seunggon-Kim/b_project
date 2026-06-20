# -*- coding: utf-8 -*-
"""현역(is_active=1)인데 image_url 결측인 선수만 대상으로 KBO 프로필을 재스크레이프해
image_url 만 채운다(다른 컬럼·플래그는 일절 건드리지 않음, idempotent).

실행: (cwd=~/b_project) venv/bin/python data_collection/refresh_active_photos.py
"""
import sys
import sqlite3
import time
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # data_collection
import player_registry_sync as prs  # noqa: E402

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
con = sqlite3.connect(DB, timeout=120)
con.execute("PRAGMA busy_timeout=120000")
ids = [r[0] for r in con.execute(
    "SELECT player_id FROM players WHERE is_active=1 AND (image_url IS NULL OR image_url='')")]
print(f"target active no-image: {len(ids)}", flush=True)

session = prs.make_session()
filled = miss = err = 0
for i, pid in enumerate(ids, 1):
    try:
        info = prs.scrape_player_profile(session, pid)
        img = (info or {}).get("image_url")
        if img:
            con.execute(
                "UPDATE players SET image_url=?, updated_at=datetime('now') "
                "WHERE player_id=? AND (image_url IS NULL OR image_url='')", (img, pid))
            con.commit()
            filled += 1
        else:
            miss += 1
    except Exception as e:
        err += 1
        print(f"  err pid={pid}: {e}", flush=True)
    time.sleep(0.4)
    if i % 20 == 0:
        print(f"  [{i}/{len(ids)}] filled={filled} miss={miss} err={err}", flush=True)

print(f"[done] filled={filled} miss={miss} err={err}", flush=True)
con.close()
