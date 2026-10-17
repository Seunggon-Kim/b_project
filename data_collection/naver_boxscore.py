# -*- coding: utf-8 -*-
"""네이버 경기 기록(박스스코어)을 받아 로컬 파일로 둡니다.

KBO 이용약관(2026-10-14 시행)으로 KBO 기록실을 못 읽게 되어, 공식 기록 가운데
네이버 시즌 API 에 없는 칸(결승타·선발승·구원승)을 박스스코어로 채웁니다
(계획서 docs/superpowers/plans/2026-10-18-naver-official-stats.md 결정 4).

    GET /schedule/games/{game_id}/record

경기 ID 는 DB games.game_id 와 같습니다(옛 경기 13자 `20100701LTSS0`, 최근
17자 `20160701HTWO02016`). 응답에서 쓰는 부분만 남깁니다(KEEP).

한 경기에 한 번 부르고, 이미 받은 경기는 건너뜁니다. 끊겨도 다시 돌리면
이어 받습니다. 2008~2026 정규시즌 약 12,400경기, 1.1초 간격이라 약 3.8시간
걸립니다.

    py data_collection/naver_boxscore.py --games-csv games.csv --from 2008 --to 2026
    py data_collection/naver_boxscore.py --game 20100701LTSS0

파일: <out>/<시즌>/<game_id>.json.gz (기본 out = ~/.bstats/naver_boxscore)
"""
import argparse
import csv
import gzip
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import naver_http  # noqa: E402

KEEP = ("gameInfo", "pitchersBoxscore", "battersBoxscore", "pitchingResult",
        "etcRecords", "scoreBoard")
DEFAULT_OUT = Path(os.path.expanduser("~")) / ".bstats" / "naver_boxscore"
REGULAR = "정규시즌"


def season_of(game_id):
    return int(str(game_id)[:4])


def path_of(out, game_id):
    return Path(out) / str(season_of(game_id)) / ("%s.json.gz" % game_id)


def slim(body):
    """응답에서 KEEP 부분만 남깁니다. recordData 가 없으면 ValueError 입니다."""
    rd = ((body or {}).get("result") or {}).get("recordData")
    if not isinstance(rd, dict):
        raise ValueError("recordData 가 없습니다")
    return {k: rd.get(k) for k in KEEP}


def save(out, game_id, data):
    p = path_of(out, game_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    tmp.replace(p)


def load(out, game_id):
    p = path_of(out, game_id)
    if not p.exists():
        return None
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return json.load(f)


def games_from_csv(path, first, last):
    """games 표 CSV(공개 /db/table/games/csv)에서 정규시즌 경기 ID 들입니다."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    return sorted(r["game_id"] for r in rows
                  if r.get("game_type") == REGULAR and first <= int(r["season"]) <= last)


def fetch_all(game_ids, out, cl=None, log=print):
    """받지 않은 경기만 받습니다. (받음, 건너뜀, 실패 목록) 을 돌려줍니다."""
    cl = cl or naver_http.client()
    got = skipped = 0
    failed = []
    t0 = time.time()
    for i, gid in enumerate(game_ids, 1):
        if path_of(out, gid).exists():
            skipped += 1
            continue
        try:
            save(out, gid, slim(cl.get("/schedule/games/%s/record" % gid)))
            got += 1
        except (naver_http.NaverError, ValueError) as e:
            failed.append((gid, str(e)[:120]))
        if i % 200 == 0:
            log("  %d/%d (받음 %d·건너뜀 %d·실패 %d, %.0f분)"
                % (i, len(game_ids), got, skipped, len(failed), (time.time() - t0) / 60))
    return got, skipped, failed


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--games-csv")
    ap.add_argument("--from", dest="first", type=int, default=2008)
    ap.add_argument("--to", dest="last", type=int, default=2026)
    ap.add_argument("--game", action="append", default=[])
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    a = ap.parse_args(argv)
    ids = list(a.game)
    if a.games_csv:
        ids += games_from_csv(a.games_csv, a.first, a.last)
    if not ids:
        ap.error("--games-csv 나 --game 이 필요합니다")
    print("경기 %d개, 저장 %s" % (len(ids), a.out))
    got, skipped, failed = fetch_all(ids, a.out)
    print("끝: 받음 %d · 건너뜀 %d · 실패 %d" % (got, skipped, len(failed)))
    if failed:
        fl = Path(a.out) / "failed.txt"
        fl.write_text("\n".join("%s\t%s" % x for x in failed), encoding="utf-8")
        print("실패 목록: %s" % fl)
    return 0


if __name__ == "__main__":
    sys.exit(main())
