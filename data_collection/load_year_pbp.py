# -*- coding: utf-8 -*-
"""한 해의 게임별 CSV 를 play_by_play + games 에 적재 (경량, t3.micro EBS 대응).

backfill_pre2015.sh 인라인 로더를 standalone 으로 분리 — 인덱스 drop/재생성 오케스트레이션
(backfill_2010_2014.sh)에서 연도별로 호출한다.

경량화:
  - WAL + synchronous=NORMAL: 커밋당 fsync 없음(checkpoint 에서만 동기화) → IOPS 절감
  - CSV 스트리밍: 한 번에 하나씩 읽고 버림(메모리 절약)
  - 날짜는 파일명(gameID[:8])에서 추출 → CSV 이중 읽기 회피
  - 적재 후 WAL checkpoint(TRUNCATE)
play_by_play 인덱스가 DROP 된 상태에서 호출하면 INSERT 가 순수 append 라 매우 빠르다.

실행: python data_collection/load_year_pbp.py <YEAR> [db_path] [save_root]
"""
import sys
import sqlite3
import pathlib
import pandas as pd

YEAR = sys.argv[1]
DB = sys.argv[2] if len(sys.argv) > 2 else "/home/ubuntu/b_project/database/kbo_stats.db"
SAVE_ROOT = sys.argv[3] if len(sys.argv) > 3 else "/home/ubuntu/b_project/crawler/save"
csv_dir = pathlib.Path(SAVE_ROOT) / YEAR

PLAYOFF_START = {
    "2008": 1008, "2009": 920, "2010": 1005, "2011": 1008, "2012": 1008,
    "2013": 1008, "2014": 1019, "2015": 1010, "2016": 1021, "2017": 1010,
    "2018": 1015, "2019": 1003, "2020": 1101, "2021": 1101, "2022": 1013,
    "2023": 1019, "2024": 1002, "2025": 1005,
}
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

if not csv_dir.is_dir():
    print(f"  {YEAR}: save dir 없음 ({csv_dir}). skip.")
    raise SystemExit(0)

con = sqlite3.connect(DB, timeout=300)
con.execute("PRAGMA journal_mode=WAL")
con.execute("PRAGMA synchronous=NORMAL")
con.execute("PRAGMA cache_size=-40000")
con.execute("PRAGMA temp_store=MEMORY")
cur = con.cursor()
known_team_ids = {r[0] for r in cur.execute("SELECT team_id FROM teams")}


def resolve_team_id(alias, fcode):
    a = (alias or "").strip()
    if a in known_team_ids:
        return a, None
    mapped = FRANCHISE_TO_TEAM_ID.get(a) or FRANCHISE_TO_TEAM_ID.get((fcode or "").strip())
    if mapped in known_team_ids:
        return mapped, None
    return None, (a or fcode)


game_csvs = sorted(
    f for f in csv_dir.glob("*.csv")
    if f.stem[:8].isdigit() and not f.name.startswith("~$")
)
print(f"  {YEAR}: 게임별 CSV {len(game_csvs)}개")
if not game_csvs:
    con.close()
    raise SystemExit(0)

# 날짜는 파일명에서 → CSV 미리 안 읽음. 해당 game_date 선삭제(idempotent).
dates = set()
for f in game_csvs:
    try:
        dates.add(int(f.stem[:8]))
    except ValueError:
        pass
for d in dates:
    cur.execute("DELETE FROM play_by_play WHERE game_date=?", (d,))
print(f"  {YEAR}: 기존 행 삭제 대상 game_date {len(dates)}개")

playoff_cut = PLAYOFF_START.get(str(YEAR))
total = loaded = games_upserted = 0
unresolved = []
for f in game_csvs:   # 스트리밍
    try:
        df = pd.read_csv(f, encoding="cp949")
    except Exception:
        try:
            df = pd.read_csv(f, encoding="utf-8")
        except Exception as e:
            print(f"    read fail {f.name}: {e}")
            continue
    if len(df) == 0:
        continue
    df.to_sql("play_by_play", con, if_exists="append", index=False)
    total += len(df)
    loaded += 1

    def col_max_int(name):
        if name not in df.columns:
            return 0
        s = pd.to_numeric(df[name], errors="coerce").dropna()
        return int(s.max()) if len(s) else 0

    last = df.iloc[-1]
    game_id = last.get("gameID")
    if game_id is None or (isinstance(game_id, float) and pd.isna(game_id)):
        game_id = f.stem
    game_date = last.get("game_date")
    try:
        gd_int = int(str(game_date)[:8]) % 10000
    except (ValueError, TypeError):
        gd_int = None
    game_type = "정규시즌"
    if playoff_cut is not None and gd_int is not None and gd_int >= playoff_cut:
        game_type = "포스트시즌"
    home_id, h_un = resolve_team_id(last.get("home_alias"), last.get("home"))
    away_id, a_un = resolve_team_id(last.get("away_alias"), last.get("away"))
    for u, side in ((h_un, "home"), (a_un, "away")):
        if u:
            unresolved.append((game_id, side, u))
    home_id = home_id or (str(last.get("home_alias") or last.get("home") or "")).strip()
    away_id = away_id or (str(last.get("away_alias") or last.get("away") or "")).strip()
    cur.execute(
        "INSERT OR REPLACE INTO games (game_id, game_date, season, game_type, "
        "home_team_id, away_team_id, home_score, away_score, stadium) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (game_id, str(game_date) if game_date is not None else None, int(YEAR), game_type,
         home_id, away_id, col_max_int("score_home"), col_max_int("score_away"),
         (str(last.get("stadium")).strip() if last.get("stadium") is not None else None)),
    )
    games_upserted += 1
    del df

con.commit()
con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
if unresolved:
    print(f"  ⚠️ {YEAR}: teams 미등록 alias {len(unresolved)}건: {unresolved[:20]}")
cur.execute("SELECT COUNT(*) FROM play_by_play WHERE game_date>=? AND game_date<?",
            (int(YEAR) * 10000, (int(YEAR) + 1) * 10000))
pbp_rows = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM games WHERE season=?", (int(YEAR),))
print(f"  {YEAR}: {loaded}경기 적재 / PBP {total}행 / games {games_upserted}건 "
      f"(DB내 {YEAR} PBP {pbp_rows}, games {cur.fetchone()[0]})")
con.close()
