# -*- coding: utf-8 -*-
"""play_by_play 원천에서 games 테이블을 보강한다 (전 시즌).

배경: games 가 2025 시즌만 적재돼 있고(2015~2024·2026 비어 있음, pre-2015 백필은
2008~2014 만 채움) 대시보드 순위·경기목록·조인이 비는 문제가 있다. play_by_play 에는
gameID·game_date·home_alias·away_alias·score·stadium 이 모두 있으므로, 이를 gameID 단위로
집계해 games 메타를 도출한다.

정책:
  - 기존 games 행은 보존(INSERT OR IGNORE) — 2025 의 attendance/weather 등 풍부한 값을
    덮어쓰지 않는다. games 에 없는 gameID 만 새로 채운다.
  - home/away_team_id: PBP alias(크롤러가 현재 팀명으로 채움)를 우선, 옛 코드는 프랜차이즈
    매핑으로 보정. 미해결은 LOG 후 raw alias 적재(검토용).
  - game_type: game_date >= 해당 시즌 playoff_start 컷오프면 포스트시즌, 아니면 정규시즌.
  - score: gameID 별 score_home/score_away 의 최댓값(최종 누적).

실행: python data_collection/games_from_pbp.py [db_path] [--dry-run]
"""
import os
import sqlite3
import sys
from collections import Counter

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "database", "kbo_stats.db")

# 프랜차이즈 코드/구명칭 → 현재 team_id (backfill_pre2015.sh 와 동일 기준)
FRANCHISE_TO_TEAM_ID = {
    "HT": "KIA", "KIA": "KIA", "해태": "KIA",
    "OB": "두산", "두산": "두산",
    "SK": "SSG", "SSG": "SSG",
    "WO": "키움", "넥센": "키움", "우리": "키움", "히어로즈": "키움", "키움": "키움",
    "NC": "NC", "LG": "LG",
    "SS": "삼성", "삼성": "삼성",
    "LT": "롯데", "롯데": "롯데",
    "HH": "한화", "한화": "한화",
    "KT": "KT",
}

# download.py 의 playoff_start 와 동일 (game_type 판정용 컷오프, MMDD)
PLAYOFF_START = {
    "2008": 1008, "2009": 920, "2010": 1005, "2011": 1008, "2012": 1008,
    "2013": 1008, "2014": 1019, "2015": 1010, "2016": 1021, "2017": 1010,
    "2018": 1015, "2019": 1003, "2020": 1101, "2021": 1101, "2022": 1013,
    "2023": 1019, "2024": 1002, "2025": 1005,
}


def resolve_team_id(alias, known):
    """alias(현재 팀명 우선)를 team_id 로. teams 에 없으면 프랜차이즈 맵 폴백, 그래도 없으면 None."""
    a = (alias or "").strip()
    if a in known:
        return a
    mapped = FRANCHISE_TO_TEAM_ID.get(a)
    return mapped if mapped in known else None


def derive_games(con, skip_existing=True):
    """PBP 에서 games 행을 도출. (rows, unresolved) 반환."""
    known = {r[0] for r in con.execute("SELECT team_id FROM teams")}
    existing = {r[0] for r in con.execute("SELECT game_id FROM games")} if skip_existing else set()
    raw = con.execute("""
        SELECT gameID,
               MAX(game_date)  AS gd,
               MAX(home_alias) AS halias,
               MAX(away_alias) AS aalias,
               MAX(stadium)    AS stadium,
               MAX(score_home) AS hs,
               MAX(score_away) AS as_
        FROM play_by_play
        WHERE gameID IS NOT NULL AND gameID <> ''
        GROUP BY gameID
    """).fetchall()
    rows, unresolved = [], []
    for gid, gd, halias, aalias, stadium, hs, as_ in raw:
        if gid in existing:
            continue
        try:
            gds = str(int(float(gd)))          # YYYYMMDD
        except (ValueError, TypeError):
            continue
        if len(gds) < 8:
            continue
        season = int(gds[:4])
        mmdd = int(gds[4:8])
        cut = PLAYOFF_START.get(str(season))
        game_type = "포스트시즌" if (cut is not None and mmdd >= cut) else "정규시즌"
        home = resolve_team_id(halias, known)
        away = resolve_team_id(aalias, known)
        if home is None:
            unresolved.append((gid, "home", halias)); home = (halias or "").strip()
        if away is None:
            unresolved.append((gid, "away", aalias)); away = (aalias or "").strip()

        def _int(v):
            try:
                return int(float(v))
            except (ValueError, TypeError):
                return None
        rows.append((gid, gds, season, game_type, home, away, _int(hs), _int(as_),
                     (stadium or "").strip() or None))
    return rows, unresolved


def main(db_path=DEFAULT_DB, dry=False):
    con = sqlite3.connect(db_path, timeout=60)
    try:
        rows, unresolved = derive_games(con, skip_existing=True)
        per = Counter(r[2] for r in rows)
        if not dry and rows:
            con.executemany(
                "INSERT OR IGNORE INTO games "
                "(game_id, game_date, season, game_type, home_team_id, away_team_id, "
                " home_score, away_score, stadium) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", rows)
            con.commit()
        print(f"[games_from_pbp] DB: {db_path} | dry_run={dry}")
        print(f"[games_from_pbp] 신규 games {len(rows)}건: {dict(sorted(per.items()))}")
        if unresolved:
            print(f"[games_from_pbp] 미해결 alias {len(unresolved)}건(검토): {unresolved[:20]}")
        print(f"[games_from_pbp] 적재 후 games 시즌 분포: "
              f"{con.execute('SELECT season, COUNT(*) FROM games GROUP BY season ORDER BY season').fetchall()}")
    finally:
        con.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    main(args[0] if args else DEFAULT_DB, "--dry-run" in sys.argv)
