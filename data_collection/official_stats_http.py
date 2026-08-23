# -*- coding: utf-8 -*-
"""KBO 공식 기록을 브라우저 없이 수집해 CSV 로 씁니다.

`selenium_batter_scraper.py` / `selenium_pitcher_scraper.py` 를 대신합니다.
결과 CSV 는 같은 경로·같은 컬럼이라 뒤 단계(csv_to_d1.py)는 그대로입니다.

## 왜 바꾸는가

  - 매일 13분을 브라우저에 씁니다. 이쪽은 1분 안팎입니다.
  - 브라우저에서만 나는 고장이 있습니다. 상단 고정 메뉴바가 '다음'
    링크를 가려 2021 NC 49명의 볼넷·사구·삼진이 통째로 비었습니다.
    **오류는 로그에만 남고 CSV 는 정상적으로 만들어졌습니다.**
    좌표도 겹침도 없는 HTTP 에서는 이런 종류가 생기지 않습니다.
  - Chrome·chromedriver 설치가 필요 없어 러너가 가볍습니다.

    py data_collection/official_stats_http.py --kind batter
    py data_collection/official_stats_http.py --kind pitcher --year 2021
    py data_collection/official_stats_http.py --kind both --check
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from kbo_http import fetch_table  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SAVE_DIR = ROOT / "crawler" / "save" / "official_stats"

TEAM_CODES = ["LG", "HH", "SK", "SS", "NC", "KT", "LT", "HT", "OB", "WO"]

# 화면 머리글 -> DB 컬럼. selenium 쪽 COLUMN_MAPPING 과 같은 표입니다.
BATTER_MAP = {
    "선수명": "player_name", "팀명": "player_team", "AVG": "batting_average",
    "G": "games", "PA": "plate_appearance", "AB": "at_bat", "R": "run",
    "H": "single", "2B": "double", "3B": "triple", "HR": "home_run",
    "TB": "total_bases", "RBI": "run_batted_in", "SAC": "sacrifice_bunts",
    "SF": "sacrifice_fly", "BB": "base_on_balls",
    "IBB": "intentional_base_on_balls", "HBP": "hit_by_pitch",
    "SO": "strikeout", "GDP": "ground_into_double_play",
    "SLG": "slugging_percentage", "OBP": "on_base_percentage",
    "OPS": "on_base_plus_slugging", "MH": "multi_hits",
    "RISP": "runners_in_scoring_position",
    "PH-BA": "pinch_hit_batting_average", "XBH": "extra_base_hits",
    "GO": "ground_outs", "AO": "air_outs", "GO/AO": "go_ao",
    "GW RBI": "gw_rbi", "BB/K": "bb_k", "P/PA": "p_pa", "ISOP": "isop",
    "XR": "extended_runs", "GPA": "gross_production_average",
}

# selenium_pitcher_scraper.py 의 COLUMN_MAPPING 과 같아야 합니다.
# 컬럼 이름이 하나라도 어긋나면 그 값이 D1 에서 조용히 NULL 로 남습니다
# (csv_to_d1.py 가 "D1 에 없어 뺀 컬럼" 으로 넘깁니다).
# `wild_pitch`·`balk` 는 단수입니다. D1 스키마가 그렇습니다.
PITCHER_MAP = {
    "선수명": "player_name", "팀명": "player_team",
    "ERA": "earned_run_average", "G": "games", "W": "wins", "L": "losses",
    "SV": "save", "HLD": "hold", "WPCT": "winning_percentage",
    "IP": "innings_pitched", "H": "hits", "HR": "home_run",
    "BB": "base_on_balls", "HBP": "hit_by_pitch", "SO": "strikeout",
    "R": "run", "ER": "earned_run",
    "WHIP": "walks_plus_hits_per_inning_pitched",
    "CG": "complete_game", "SHO": "shutout", "QS": "quality_start",
    "BSV": "blown_save", "TBF": "total_batters_faced",
    "NP": "number_of_pitchers", "AVG": "batting_average", "2B": "double",
    "3B": "triple", "SAC": "sacrifice_bunts", "SF": "sacrifice_fly",
    "IBB": "intentional_base_on_balls", "WP": "wild_pitch", "BK": "balk",
    "GS": "games_started", "Wgs": "wins_game_started",
    "Wgr": "wins_game_relieved", "GF": "games_finished",
    "SVO": "save_opportunity", "TS": "total_saves",
    "GDP": "ground_into_double_play", "GO": "ground_outs",
    "AO": "air_outs", "GO/AO": "go_ao",
    "BABIP": "batting_average_on_balls_in_play",
    "P/G": "p_g", "P/IP": "p_ip", "K/9": "k_9", "BB/9": "bb_9",
    "K/BB": "k_bb",
    "OBP": "on_base_percentage", "SLG": "slugging_percentage",
    "OPS": "on_base_plus_slugging",
}

# 세부기록은 `Detail.aspx` 가 아니라 **`Detail1.aspx`** 입니다.
# 화면에서는 '세부기록' 링크로 들어가서 주소가 눈에 안 띕니다.
# 틀린 주소를 넣으면 3KB 짜리 빈 페이지가 오고, 표를 못 찾아
# 세부 컬럼(GO/AO, ISOP 등)이 조용히 비게 됩니다.
# 투수는 세부기록이 **두 쪽**입니다. Detail2 를 빠뜨리면 BABIP·P/G·
# P/IP·K/9·BB/9·OBP·SLG·OPS 가 통째로 빕니다. 타자는 Detail1 이 끝입니다.
PAGES = {
    "batter": ["HitterBasic/Basic1.aspx", "HitterBasic/Basic2.aspx",
               "HitterBasic/Detail1.aspx"],
    "pitcher": ["PitcherBasic/Basic1.aspx", "PitcherBasic/Basic2.aspx",
                "PitcherBasic/Detail1.aspx", "PitcherBasic/Detail2.aspx"],
}
MAPS = {"batter": BATTER_MAP, "pitcher": PITCHER_MAP}

# 머리글에 있지만 DB 로 넘기지 않는 것들입니다.
SKIP_HEADERS = {"순위", ""}


def collect(kind, year, delay=None):
    """한 시즌 전 팀을 모아 {player_id: {컬럼: 값}} 으로 돌려줍니다."""
    colmap = MAPS[kind]
    out = {}
    unknown = set()
    for team in TEAM_CODES:
        for page in PAGES[kind]:
            kw = {} if delay is None else {"delay": delay}
            header, rows = fetch_table(page, year, team, **kw)
            if not header:
                print("  [경고] %s %s: 표를 찾지 못했습니다" % (team, page))
                continue
            for pid, cells in rows.items():
                if not pid:
                    continue
                rec = out.setdefault(pid, {"player_id": pid})
                for h, v in zip(header, cells):
                    if h in SKIP_HEADERS:
                        continue
                    col = colmap.get(h)
                    if col is None:
                        unknown.add(h)
                        continue
                    # 페이지마다 선수명·팀명이 겹칩니다. 처음 값을 지킵니다.
                    rec.setdefault(col, v)
        print("  %s %d명 누적" % (team, len(out)), flush=True)
    if unknown:
        # 조용히 버리면 새 컬럼이 생겨도 아무도 모릅니다.
        print("  [알림] 매핑에 없는 머리글 %d개: %s"
              % (len(unknown), ", ".join(sorted(unknown))))
    return out


def write_csv(kind, year, data):
    cols = ["player_id"] + [c for c in dict.fromkeys(MAPS[kind].values())]
    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    path = SAVE_DIR / ("%s_stats_%d.csv" % (kind, year))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for pid in sorted(data, key=lambda x: int(x) if x.isdigit() else 0):
            w.writerow(data[pid])
    return path


def holes(kind, data):
    """핵심 컬럼이 빈 선수 수입니다. 2021 NC 같은 결손을 잡습니다."""
    keys = (["plate_appearance", "at_bat", "base_on_balls", "hit_by_pitch",
             "strikeout"] if kind == "batter"
            else ["games", "innings_pitched", "base_on_balls", "strikeout"])
    bad = 0
    for rec in data.values():
        if any(not str(rec.get(k, "")).strip() or rec.get(k) == "-"
               for k in keys):
            bad += 1
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["batter", "pitcher", "both"],
                    default="both")
    ap.add_argument("--year", type=int, default=None,
                    help="기본값은 KST 기준 올해")
    ap.add_argument("--delay", type=float, default=None,
                    help="요청 간격(초). 기본값은 kbo_http 의 값")
    ap.add_argument("--check", action="store_true",
                    help="CSV 를 쓰지 않고 결과만 봅니다")
    args = ap.parse_args()

    kst = datetime.timezone(datetime.timedelta(hours=9))
    year = args.year or datetime.datetime.now(kst).year
    kinds = ["batter", "pitcher"] if args.kind == "both" else [args.kind]

    rc = 0
    for kind in kinds:
        print("=== %s %d ===" % (kind, year))
        t0 = datetime.datetime.now()
        data = collect(kind, year, args.delay)
        secs = (datetime.datetime.now() - t0).total_seconds()
        bad = holes(kind, data)
        print("  선수 %d명, 결손 %d명, %.0f초" % (len(data), bad, secs))
        if not data:
            print("  [실패] 한 명도 모으지 못했습니다.")
            rc = 1
            continue
        if bad:
            # 여기서 멈춥니다. 결손 CSV 를 그대로 넘기면 D1 에 NULL 이
            # 들어가고, 그 뒤 계산이 조용히 어긋납니다.
            print("  [실패] 핵심 컬럼이 빈 선수가 있습니다. 적재하지 않습니다.")
            rc = 1
            continue
        if args.check:
            print("  [check] CSV 를 쓰지 않았습니다.")
            continue
        print("  -> %s" % write_csv(kind, year, data))
    return rc


if __name__ == "__main__":
    sys.exit(main())
