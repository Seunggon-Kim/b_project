#!/bin/bash
# 2008-2014 KBO Play-by-Play(PBP) 과거 백필 (연도별)
# EC2 ~/b_project에서 실행: nohup ./data_collection/backfill_pre2015.sh > /dev/null 2>&1 &
#
# 각 연도 Y에 대해:
#   1) crawler/pbp.py 로 정규시즌+포스트시즌 PBP 크롤링 (Y0101 ~ Y1231)
#   2) 그 해 crawler/save/<Y>/ 에 생성된 게임별 CSV 를 DB 에 idempotent 적재
#      (daily_kbo_pbp.sh 와 동일한 패턴: game_date 별 DELETE 후 append)
#   3) 연도별 재실행 가능(resumable): 크롤러는 이미 받은 CSV 를 SKIP,
#      적재는 game_date 단위 DELETE→INSERT 라 중복 없이 다시 돌려도 안전.
#   로그: logs/backfill_pre2015_<year>.log
#
# ── 데이터 한계(caveat) ────────────────────────────────────────────────
#  * 트래킹 수준은 시즌마다 다릅니다 (2014 파일럿 11경기 검증 기준):
#    - 구종(pitch_type)·구속(speed) 은 2014 에도 존재합니다 (약 97% 채움).
#    - PITCHf/x 위치·물리값(px, pz, pfx_x/z, x0/z0, sz_top/bot, vx0/vy0/vz0,
#      ax/ay/az) 만 2017 이전 경기에서 NULL 로 적재됩니다.
#    - 이벤트/투구결과/타석결과/카운트/주자/수비위치/타자·투수 ID 등 정성 PBP 는
#      정상 수집됩니다. ("텍스트만" 이 아니라 구종·구속 포함.)
#  * pre-2008 (2007 이전) 은 Naver 소스에서 제공되지 않아 백필 불가합니다.
#    (download.py 의 regular_start/playoff_start 도 2008 부터 정의)
#  * 대량 백필은 Naver rate-limit 에 걸릴 수 있습니다. 크롤러에 추가된
#    FETCH_SLEEP_SEC(기본 0.4초, crawler/download.py) throttle 로 완화하되,
#    한 해 안에서도 차단이 의심되면 연도 사이 sleep 을 늘리십시오.
#  * 과거 gameID 포맷 차이(포스트시즌 시즌 suffix 등)는 download.py 의
#    gid_year>3000 분기에서 처리되며, 파싱 불가 경기는 이제 배치를 중단시키지
#    않고 skip+log 됩니다(하드닝 반영).
#
# ── 안전 파일럿(권장: 본 백필 전 1회) ──────────────────────────────────
#  하드닝된 크롤러가 구포맷(2014) 경기에서 동작하는지 DB 쓰기 없이 CSV 로만 검증:
#
#      cd ~/b_project
#      venv/bin/python crawler/pbp.py -f 20140401 -t 20140407 -d crawler/save/
#      ls crawler/save/2014/   # 게임별 csv 가 생성되는지, log.txt 의 요약 확인
#
#  (위 명령은 DB 를 건드리지 않습니다. -j/-p 없이 정규시즌만, 한 주만 받습니다.)
# ──────────────────────────────────────────────────────────────────────

set -e
cd ~/b_project

DB="/home/ubuntu/b_project/database/kbo_stats.db"
LOG_DIR="logs"
mkdir -p "$LOG_DIR"

echo "===== pre-2015 PBP 백필 시작 $(date) ====="

# 과거 → 최신 (2008 부터 순차). 중간 중단 시 연도 단위로 이어서 재실행 가능.
for YEAR in 2008 2009 2010 2011 2012 2013 2014; do
  LOG="$LOG_DIR/backfill_pre2015_${YEAR}.log"
  echo "" | tee -a "$LOG"
  echo "########## ${YEAR} 시즌 PBP 시작 $(date) ##########" | tee -a "$LOG"

  # 1) 크롤링: 정규시즌(-j join) + 포스트시즌(-p). 이미 받은 경기는 크롤러가 SKIP.
  echo "--- ${YEAR} PBP 크롤링 ---" | tee -a "$LOG"
  venv/bin/python crawler/pbp.py -f "${YEAR}0101" -t "${YEAR}1231" -j -p -d crawler/save/ 2>&1 \
    | tee -a "$LOG" || echo "⚠️ ${YEAR} 크롤링 일부 실패(개별 경기 skip 로그 확인)" | tee -a "$LOG"

  # 2) 그 해 게임별 CSV → DB idempotent 적재 (daily_kbo_pbp.sh 와 동일 패턴)
  #    + games 테이블도 동시 upsert (standings/경기목록/조인 등 downstream 반영).
  #    games upsert 는 csv_to_db_2025.py 의 매핑을 그대로 재사용합니다
  #    (home_alias/away_alias = 현재 team_id, score = 누적 최종 점수, season=int(year)).
  echo "--- ${YEAR} CSV → DB 적재 (play_by_play + games) ---" | tee -a "$LOG"
  venv/bin/python - "$YEAR" <<'PY' 2>&1 | tee -a "$LOG" || echo "⚠️ ${YEAR} DB 적재 실패" | tee -a "$LOG"
import sys, sqlite3, pandas as pd, pathlib

year = sys.argv[1]
DB = "/home/ubuntu/b_project/database/kbo_stats.db"
csv_dir = pathlib.Path(f"/home/ubuntu/b_project/crawler/save/{year}")

if not csv_dir.is_dir():
    print(f"  {year}: save dir 없음 ({csv_dir}). 크롤링 결과 없음, skip.")
    raise SystemExit(0)

# ── 포스트시즌 컷오프(YYYYMMDD) ────────────────────────────────────────
# game_type 판정 기준. download.py 의 playoff_start 와 동일한 값을 사용합니다.
# 저장된 게임별 CSV 의 gameID 는 포스트시즌도 실제 연도로 재작성되어
# (download.py 의 gid_for_save) 시드(5555 등)로는 구분 불가하므로,
# 크롤러가 정규/포스트시즌을 가르는 것과 동일하게 game_date >= 컷오프 로 판정합니다.
# 컷오프 이상 & 연내 = 포스트시즌, 그 외(또는 미정의 연도) = 정규시즌(기본값).
PLAYOFF_START = {
    "2008": 1008, "2009": 920,  "2010": 1005, "2011": 1008,
    "2012": 1008, "2013": 1008, "2014": 1019, "2015": 1010,
    "2016": 1021, "2017": 1010, "2018": 1015, "2019": 1003,
    "2020": 1101, "2021": 1101, "2022": 1013, "2023": 1019,
    "2024": 1002, "2025": 1005,
}

# ── 프랜차이즈 코드 → 현재 team_id 보강 매핑(폴백/검증용) ──────────────
# 크롤러(game_parse.py)가 이미 home_alias/away_alias 에 현재 팀명을 채워
# 줍니다(예: HT→KIA). csv_to_db_2025.py 도 그 alias 를 그대로 team_id 로 씁니다.
# 다만 과거(2008-2014) 경기에서 alias 가 비거나 teams 에 없는 값이 들어올 경우를
# 대비해, 파일명 프랜차이즈 코드(home/away 컬럼) 기준 폴백 맵을 둡니다.
# teams 에 없는 alias 는 crash 시키지 않고 LOG 만 남겨 owner 검토용으로 둡니다.
FRANCHISE_TO_TEAM_ID = {
    "HT": "KIA",  "KIA": "KIA",
    "OB": "두산", "두산": "두산",
    "SK": "SSG",  "SSG": "SSG",
    "WO": "키움", "넥센": "키움", "우리": "키움", "히어로즈": "키움", "키움": "키움",
    "NC": "NC",
    "LG": "LG",
    "SS": "삼성", "삼성": "삼성",
    "LT": "롯데", "롯데": "롯데",
    "HH": "한화", "한화": "한화",
    "KT": "KT",
}

con = sqlite3.connect(DB)
cur = con.cursor()
known_team_ids = {r[0] for r in cur.execute("SELECT team_id FROM teams")}


def resolve_team_id(alias, fcode):
    """alias(크롤러가 채운 현재 팀명) 우선, 없으면 파일명 프랜차이즈 코드로 폴백.
    teams 에 없으면 (None, alias) 를 돌려주어 호출부에서 LOG 후 통과시킵니다."""
    a = (alias or "").strip()
    if a in known_team_ids:
        return a, None
    mapped = FRANCHISE_TO_TEAM_ID.get(a) or FRANCHISE_TO_TEAM_ID.get((fcode or "").strip())
    if mapped in known_team_ids:
        return mapped, None
    return None, (a or fcode)  # 미해결 — 검토 대상

# 게임별 CSV 만 (연도 합본 {year}.csv, source/ 하위 원본 등은 제외)
game_csvs = sorted(
    f for f in csv_dir.glob("*.csv")
    if f.stem[:8].isdigit() and not f.name.startswith("~$")
)
print(f"  {year}: 게임별 CSV {len(game_csvs)}개 발견")
if not game_csvs:
    con.close()
    raise SystemExit(0)

# 이번 백필에 등장하는 game_date 들을 먼저 일괄 삭제(idempotent).
# game_date 는 YYYYMMDD 문자열(game_id[:8]). daily 로더와 동일하게 정수로 매칭.
dates = set()
frames = {}
for f in game_csvs:
    try:
        df = pd.read_csv(f, encoding="cp949")
    except Exception:
        df = pd.read_csv(f, encoding="utf-8")
    frames[f] = df
    if "game_date" in df.columns and len(df) > 0:
        for d in df["game_date"].dropna().unique():
            try:
                dates.add(int(str(d)[:8]))
            except (ValueError, TypeError):
                pass

deleted = 0
for d in dates:
    cur.execute("DELETE FROM play_by_play WHERE game_date=?", (d,))
    deleted += cur.rowcount
print(f"  {year}: 기존 행 삭제 {deleted} (game_date {len(dates)}개)")

playoff_cut = PLAYOFF_START.get(str(year))
total = 0
loaded = 0
games_upserted = 0
unresolved = []  # owner 검토용: 매핑 실패 alias 목록
for f, df in frames.items():
    if len(df) == 0:
        continue

    # 2-1) play_by_play append (기존 로직 그대로, idempotent: 위에서 DELETE 완료)
    df.to_sql("play_by_play", con, if_exists="append", index=False)
    total += len(df)
    loaded += 1

    # 2-2) games upsert (csv_to_db_2025.py 매핑 재사용 + 보강)
    #   game_id   = gameID (마지막 행 기준, 한 CSV = 한 경기)
    #   game_date = YYYYMMDD (game_date 컬럼)
    #   season    = int(year)
    #   game_type = game_date >= playoff_cut 이면 '포스트시즌', 아니면 '정규시즌'(기본)
    #   home/away_score = 경기 전체 누적 점수의 최댓값(max) — 마지막 행이 누락/0 일
    #     가능성을 막기 위해 csv_to_db_2025.py 의 "마지막 행" 대신 max 를 사용
    #   home/away_team_id = home_alias/away_alias(현재 team_id) → resolve_team_id
    #   stadium = stadium 컬럼. attendance/weather/temperature/game_time_minutes 는
    #     과거 PBP 소스에 없어 NULL 로 둡니다(스키마상 NULL 허용).
    def col_max_int(name):
        if name not in df.columns:
            return 0
        s = pd.to_numeric(df[name], errors="coerce").dropna()
        return int(s.max()) if len(s) else 0

    last = df.iloc[-1]
    game_id = last.get("gameID")
    if game_id is None or (isinstance(game_id, float) and pd.isna(game_id)):
        game_id = f.stem  # 폴백: 파일명(=gameID)
    game_date = last.get("game_date")
    try:
        gd_int = int(str(game_date)[:8]) % 10000  # MMDD 부분
    except (ValueError, TypeError):
        gd_int = None
    game_type = "정규시즌"
    if playoff_cut is not None and gd_int is not None and gd_int >= playoff_cut:
        game_type = "포스트시즌"

    home_id, h_unres = resolve_team_id(last.get("home_alias"), last.get("home"))
    away_id, a_unres = resolve_team_id(last.get("away_alias"), last.get("away"))
    for u, side in ((h_unres, "home"), (a_unres, "away")):
        if u:
            unresolved.append((game_id, side, u))

    # team_id 미해결 시에도 crash 금지: 원본 alias 라도 그대로 적재(검토 후 정정)
    home_id = home_id or (str(last.get("home_alias") or last.get("home") or "")).strip()
    away_id = away_id or (str(last.get("away_alias") or last.get("away") or "")).strip()

    cur.execute(
        """
        INSERT OR REPLACE INTO games (
            game_id, game_date, season, game_type, home_team_id,
            away_team_id, home_score, away_score, stadium
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            game_id,
            str(game_date) if game_date is not None else None,
            int(year),
            game_type,
            home_id,
            away_id,
            col_max_int("score_home"),
            col_max_int("score_away"),
            (str(last.get("stadium")).strip() if last.get("stadium") is not None else None),
        ),
    )
    games_upserted += 1

con.commit()

if unresolved:
    print(f"  ⚠️ {year}: teams 미등록 alias {len(unresolved)}건 — owner 검토 필요:")
    for gid, side, u in unresolved[:50]:
        print(f"      {gid} {side}={u!r}")
    if len(unresolved) > 50:
        print(f"      ... 외 {len(unresolved) - 50}건")

cur.execute(
    "SELECT COUNT(*) FROM play_by_play WHERE CAST(SUBSTR(CAST(game_date AS TEXT),1,4) AS INT)=?",
    (int(year),),
)
pbp_rows = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM games WHERE season=?", (int(year),))
games_rows = cur.fetchone()[0]
print(
    f"  {year}: {loaded}개 경기, PBP {total}행 적재 / games {games_upserted}건 upsert. "
    f"DB 내 {year} 시즌 PBP 행: {pbp_rows}, games: {games_rows}"
)
con.close()
PY

  # 3) (선택) 신규 등장 은퇴 선수 master 보강 — 기본 OFF.
  #    2008-2014 PBP 에 처음 나타난 batter_ID/pitcher_ID 중 players 미등록 선수를
  #    KBO 프로필에서 긁어 players 테이블에 추가합니다(scrape_missing_players.py).
  #    명시적으로 켜야만 실행됩니다:  SCRAPE_MISSING=1 ./data_collection/backfill_pre2015.sh
  #
  #    주의(comment-only, 실행 전 숙지):
  #     (a) 네트워크가 필요하며(Selenium + KBO 사이트), 새로 추가된 선수에 플래그가
  #         붙으려면 player flags 마이그레이션이 선행·성공해야 합니다.
  #     (b) 아주 오래된 선수는 KBO 프로필 페이지 자체가 없을 수 있습니다
  #         (best-effort; 못 찾은 선수는 스크립트가 "not found" 로 로그만 남기고 통과).
  #     (c) 핵심 백필을 결정론적으로 유지하기 위해 기본 OFF 입니다. 네트워크 변동·
  #         사이트 차단의 영향을 PBP/games 적재(2번)와 분리하려는 의도입니다.
  #     (d) scrape_missing_players.py 는 MISSING_SEASONS 환경변수로 대상 연도를 받습니다
  #         (미설정=2025·2026 / "all"=전체 / "YYYY"=지정). 아래 단계는 그 해(YEAR)에
  #         처음 등장한 선수만 보강하도록 MISSING_SEASONS="$YEAR" 로 호출합니다.
  if [ "${SCRAPE_MISSING:-0}" = "1" ]; then
    echo "--- ${YEAR} 신규 선수 master 보강 (SCRAPE_MISSING=1, MISSING_SEASONS=${YEAR}, best-effort) ---" | tee -a "$LOG"
    MISSING_SEASONS="$YEAR" venv/bin/python data_collection/scrape_missing_players.py 2>&1 | tee -a "$LOG" \
      || echo "⚠️ ${YEAR} 선수 보강 실패(네트워크/프로필 없음 가능, 백필 계속)" | tee -a "$LOG"
  else
    echo "--- 신규 선수 master 보강 skip (SCRAPE_MISSING 미설정, 기본 OFF) ---" | tee -a "$LOG"
  fi

  echo "########## ${YEAR} 시즌 PBP 완료 $(date) ##########" | tee -a "$LOG"
  # Naver rate-limit 완화를 위한 연도 사이 휴지(크롤러 throttle 보완)
  sleep 60
done

echo "===== pre-2015 PBP 백필 종료 $(date) ====="
