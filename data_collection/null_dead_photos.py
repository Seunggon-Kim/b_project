# -*- coding: utf-8 -*-
"""복구 불가(어느 연도폴더에도 이미지 없음) 선수의 죽은 image_url을 NULL 처리.
안전장치: 로컬 미러가 없는 선수만 후보로 보고, 현재 image_url이 *확정 404*일 때만 NULL.
(일시적 네트워크 오류는 건너뜀 → 잘못된 삭제 방지)
실행: (cwd=~/b_project) venv/bin/python data_collection/null_dead_photos.py
"""
import sqlite3
import time
import pathlib
import urllib.request
import urllib.error

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
OUT = pathlib.Path("/home/ubuntu/b_project/dashboard_js/assets/player_photos")

con = sqlite3.connect(DB, timeout=120)
con.execute("PRAGMA busy_timeout=120000")
rows = con.execute(
    "SELECT player_id, image_url FROM players WHERE image_url IS NOT NULL AND image_url<>''").fetchall()
cand = [(p, u) for p, u in rows if not (OUT / f"{p}.jpg").exists()]
print(f"candidates(no local mirror): {len(cand)}", flush=True)


def http_status(url):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)
        s = r.status
        r.close()
        return s
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


nulled = kept = 0
for p, u in cand:
    st = http_status(u)
    if st == 404:
        con.execute("UPDATE players SET image_url=NULL, updated_at=datetime('now') WHERE player_id=?", (p,))
        con.commit()
        nulled += 1
    else:
        kept += 1
        print(f"  keep pid={p} status={st} (404 아님 → 보존)", flush=True)
    time.sleep(0.1)

print(f"[done] nulled(404 확정)={nulled} kept(비404/일시오류)={kept}", flush=True)
con.close()
