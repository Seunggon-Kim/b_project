# -*- coding: utf-8 -*-
"""선수 사진 주소를 최신 연도로 맞춥니다.

## 무슨 일이 있었나

`players.image_url` 은 KBO 이미지 주소를 통째로 담습니다. 그 주소에
**연도 폴더**가 들어 있습니다.

    https://.../KBO_IMAGE/person/middle/2025/66606.jpg
                                        ^^^^

이 값이 한 번 적재된 뒤로 갱신되지 않았습니다. 1,749명 중 625명이
2025년 주소이고 666명은 아예 비어 있었습니다. 그래서 겨울에 이적한
선수는 **전 소속팀 유니폼 사진**이 나옵니다. 최원준(66606)이 KT 로
옮겼는데 NC 사진이었습니다. 그 선수의 2026년 사진은 이미 올라와
있었는데도 그랬습니다.

## 예전 판과 다른 점

이 파일은 원래 EC2 의 로컬 SQLite 를 보고 사진 파일을 내려받아
`dashboard_js/assets/player_photos/` 에 미러하는 스크립트였습니다.
Cloudflare 로 옮긴 뒤로는 한 번도 돌지 않았습니다. 경로가
`/home/ubuntu/...` 로 박혀 있었습니다. 미러 폴더도 비어
있습니다.

이제 **주소만 맞춥니다.** 사진 파일은 KBO CDN 이 직접 보내 줍니다.
파일을 우리가 들고 있을 이유가 없고, Pages 에 1,700장을 올리면 배포가
무거워집니다.

## 요청을 아낍니다

선수 한 명에 요청 두 번을 넘기지 않습니다(`photo_url.probe_years`).
이미 현재 시즌 주소를 들고 있으면 아예 건드리지 않습니다.

    py data_collection/heal_player_photos.py --dry-run
    py data_collection/heal_player_photos.py
"""
import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query  # noqa: E402
from photo_url import photo_url, probe_years, year_of  # noqa: E402
from mysql_sink import mirror  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0"}

# KBO 서버에 대고 두드리는 간격입니다. 예의 차원입니다.
SLEEP_SEC = 0.05

def head_ok(url):
    """그 주소에 사진이 있으면 True 입니다."""
    req = urllib.request.Request(url, headers=UA, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError):
        return False


def current_season():
    """공식 기록이 있는 가장 최근 시즌입니다.

    괄호 안 질의(파생 표)에 `AS t` 별칭을 붙입니다. MySQL 은 별칭 없는
    파생 표를 거절합니다("Every derived table must have its own alias").
    """
    rows = query(
        "SELECT MAX(s) AS s FROM ("
        "SELECT MAX(season) AS s FROM kbo_official_batter_stats"
        " UNION ALL SELECT MAX(season) FROM kbo_official_pitcher_stats) AS t;")
    return int(rows[0]["s"]) if rows and rows[0]["s"] else None


def load_players():
    """선수마다 (id, 현재 주소, 마지막 기록 시즌) 입니다.

    파생 표 별칭(`AS t`)은 current_season 과 같은 이유입니다.
    """
    return query(
        "SELECT p.player_id AS id, p.image_url AS url, ("
        "  SELECT MAX(season) FROM ("
        "    SELECT season FROM kbo_official_batter_stats"
        "     WHERE player_id = p.player_id"
        "    UNION ALL"
        "    SELECT season FROM kbo_official_pitcher_stats"
        "     WHERE player_id = p.player_id"
        "  ) AS t"
        ") AS last_season FROM players p;")


def mysql_write_photos(sink, updates):
    """고친 주소를 MySQL 에 씁니다."""
    for pid, url in updates:
        sink.execute("UPDATE `players` SET `image_url`=%s, `updated_at`=UTC_TIMESTAMP() "
                     "WHERE `player_id`=%s", [url, int(pid)])
    return len(updates)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="찔러 보기만 하고 players 를 고치지 않습니다")
    ap.add_argument("--limit", type=int, default=0,
                    help="이 수만큼만 처리합니다 (0 이면 전부)")
    args = ap.parse_args()

    season = current_season()
    if not season:
        print("현재 시즌을 알 수 없습니다.")
        return 1

    rows = load_players()
    print("선수 %s명, 기준 시즌 %d"
          % (format(len(rows), ","), season), flush=True)

    skipped = fixed = missing = 0
    probes = 0
    all_updates = []

    for i, r in enumerate(rows, 1):
        if args.limit and i > args.limit:
            break
        pid = str(r["id"])
        url = r["url"]
        years = probe_years(season, r["last_season"], url)
        if not years:
            skipped += 1
            continue

        found = None
        for y in years:
            candidate = photo_url(pid, y)
            probes += 1
            if head_ok(candidate):
                found = candidate
                break
            time.sleep(SLEEP_SEC)

        if not found:
            # 어느 해에도 없습니다. 들고 있던 주소를 그대로 둡니다.
            # 지우면 화면이 no-image 로 바뀌는데, 옛 주소가 아직
            # 살아 있을 수 있습니다.
            missing += 1
            continue

        if found != url:
            all_updates.append((pid, found))
            fixed += 1

        if i % 200 == 0:
            print("  [%s/%s] 그대로 %d  고침 %d  못찾음 %d  요청 %d"
                  % (format(i, ","), format(len(rows), ","),
                     skipped, fixed, missing, probes), flush=True)

    if all_updates and not args.dry_run:
        mirror("photos", lambda s: mysql_write_photos(s, all_updates))

    print("%s그대로 %d  고침 %d  못찾음 %d  요청 %d"
          % ("[미리보기] " if args.dry_run else "", skipped, fixed,
             missing, probes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
