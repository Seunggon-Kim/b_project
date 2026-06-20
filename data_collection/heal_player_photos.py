# -*- coding: utf-8 -*-
"""선수 사진 자가복구 미러러(idempotent, 주기 실행 가능).

각 선수(image_url 보유)에 로컬 미러가 없으면:
  1) 현재 image_url 시도 → 200이면 미러 저장(URL 변경 없음)
  2) 404면 연도폴더 프로빙(마지막 PBP 시즌 → 2024 → 2025 → 2023..2008) → 첫 200을
     로컬 저장하고 players.image_url을 그 URL로 교정
  3) 어느 연도에도 없으면 stillbad(복구 불가)
로컬 미러가 이미 있으면 skip → 재실행/cron 안전.
실행: (cwd=~/b_project) venv/bin/python data_collection/heal_player_photos.py
"""
import sqlite3
import time
import pathlib
import urllib.request

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
OUT = pathlib.Path("/home/ubuntu/b_project/dashboard_js/assets/player_photos")
OUT.mkdir(parents=True, exist_ok=True)
BASE = "https://6ptotvmi5753.edge.naverncp.com/KBO_IMAGE/person/middle/{y}/{p}.jpg"
DESC = [2024, 2025, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016,
        2015, 2014, 2013, 2012, 2011, 2010, 2009, 2008]
# 어느 연도에도 이미지가 없는 선수는 KBO 공식 no-Image 를 미러로 둔다(재프로빙 방지 + 플레이스홀더 표시)
NOIMG = pathlib.Path("/home/ubuntu/b_project/dashboard_js/assets/player_no_image.png")
NOIMG_BYTES = NOIMG.read_bytes() if NOIMG.exists() else None

con = sqlite3.connect(DB, timeout=120)
con.execute("PRAGMA busy_timeout=120000")
# image_url 유무와 무관하게 로컬 미러가 없는 모든 선수를 대상으로(=null 인 선수도 연도폴더 프로빙)
rows = con.execute("SELECT player_id, image_url FROM players").fetchall()
targets = [(p, u) for p, u in rows if not (OUT / f"{p}.jpg").exists()]
print(f"targets(no local mirror): {len(targets)}", flush=True)


def fetch(url):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=20)
        d = r.read()
        return d if (r.status == 200 and d and len(d) > 100) else None
    except Exception:
        return None


def last_season(pid):
    r = con.execute(
        "SELECT MAX(substr(CAST(game_date AS TEXT),1,4)) FROM play_by_play "
        "WHERE batter_ID=? OR pitcher_ID=?", (pid, pid)).fetchone()[0]
    try:
        return int(r) if r else None
    except (ValueError, TypeError):
        return None


saved = urlfixed = stillbad = 0
for i, (p, u) in enumerate(targets, 1):
    data = fetch(u) if u else None   # 1) 현재 URL(없으면 바로 프로빙)
    goodurl = u if data else None
    if not data:              # 2) 프로빙
        ls = last_season(p)
        order = ([ls] if ls else []) + DESC
        seen = set()
        order = [y for y in order if not (y in seen or seen.add(y))]
        for y in order:
            url = BASE.format(y=y, p=p)
            data = fetch(url)
            if data:
                goodurl = url
                break
    if data:
        (OUT / f"{p}.jpg").write_bytes(data)
        saved += 1
        if goodurl != u:
            con.execute("UPDATE players SET image_url=?, updated_at=datetime('now') "
                        "WHERE player_id=?", (goodurl, p))
            con.commit()
            urlfixed += 1
    else:
        # 어느 연도에도 이미지 없음 → no-Image 를 미러로 둬 다음 실행 때 재프로빙 안 하도록
        if NOIMG_BYTES:
            (OUT / f"{p}.jpg").write_bytes(NOIMG_BYTES)
        stillbad += 1
    time.sleep(0.08)
    if i % 100 == 0:
        print(f"  [{i}/{len(targets)}] saved={saved} urlfixed={urlfixed} stillbad={stillbad}", flush=True)

print(f"[done] saved={saved} urlfixed={urlfixed} stillbad={stillbad} targets={len(targets)}", flush=True)
con.close()
