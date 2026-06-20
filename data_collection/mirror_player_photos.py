# -*- coding: utf-8 -*-
"""players.image_url(KBO CDN) 이미지를 EC2 로컬로 미러링.
저장: dashboard_js/assets/player_photos/{player_id}.jpg  (nginx /kbo/assets/... 로 서빙)
용도: CDN 경로 변경/404 대비 폴백. idempotent(기존 파일 skip) → 주기 실행 가능.
실행: (cwd=~/b_project) venv/bin/python data_collection/mirror_player_photos.py
"""
import sqlite3
import time
import pathlib
import urllib.request

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
OUT = pathlib.Path("/home/ubuntu/b_project/dashboard_js/assets/player_photos")
OUT.mkdir(parents=True, exist_ok=True)

con = sqlite3.connect(DB, timeout=60)
rows = con.execute(
    "SELECT player_id, image_url FROM players WHERE image_url IS NOT NULL AND image_url<>''").fetchall()
con.close()
print(f"targets: {len(rows)}", flush=True)

ok = skip = err = 0
for i, (pid, url) in enumerate(rows, 1):
    dest = OUT / f"{pid}.jpg"
    if dest.exists() and dest.stat().st_size > 0:
        skip += 1
        continue
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=20).read()
        if data and len(data) > 100:
            dest.write_bytes(data)
            ok += 1
        else:
            err += 1
    except Exception as e:
        err += 1
        if err <= 5:
            print(f"  err pid={pid}: {e}", flush=True)
    time.sleep(0.1)
    if i % 200 == 0:
        print(f"  [{i}/{len(rows)}] ok={ok} skip={skip} err={err}", flush=True)

print(f"[done] ok={ok} skip={skip} err={err} total={len(rows)}", flush=True)
