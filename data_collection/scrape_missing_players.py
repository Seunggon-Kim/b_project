"""
v3: PBP에 등장하나 players 미등록인 선수를 보강한다 (requests 기반, Selenium 제거).

기존 v2는 player_info_scraper(Selenium/chromedriver)를 썼으나, 대량(수백~천명) 보강 시
크롬드라이버 의존·디스크 사용으로 취약했다. v3는 player_registry_sync 의 정적 HTML
스크레이퍼(scrape_player_profile, requests+BeautifulSoup)와 upsert_player(플래그도 세팅)를
재사용한다.

대상 시즌은 MISSING_SEASONS 환경변수로 제어:
  미설정 = 현행(2025·2026) / "all" = 전체 시즌 / "2008,2009,..." = 지정
team_id 는 프로필에 없으므로 None 으로 INSERT 한다(은퇴 선수 다수 — is_active 는
backfill_player_flags 의 refresh_is_active 에서 현 로스터 기준 0 으로 정리됨).
"""
import sys
sys.path.insert(0, "/home/ubuntu/b_project/data_collection")
import os
import sqlite3
import time
import logging
from datetime import datetime

import player_registry_sync as prs

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
LOG = "/tmp/scrape_missing_players_v3.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def get_missing_players(seasons=("2025", "2026")):
    """PBP 에 등장하나 players 미등록인 player_id 목록.

    seasons: 시즌(gameID 앞 4자리) 튜플로 제한. None 이면 전체 시즌 스캔.
    """
    con = sqlite3.connect(DB, timeout=120)
    cur = con.cursor()
    pbp_ids = set()
    if seasons:
        ph = ",".join("?" * len(seasons))
        where = f"WHERE substr(gameID,1,4) IN ({ph}) AND {{col}} IS NOT NULL AND {{col}}<>''"
        params = tuple(seasons)
    else:
        where = "WHERE {col} IS NOT NULL AND {col}<>''"
        params = ()
    for col in ("batter_ID", "pitcher_ID"):
        q = f"SELECT DISTINCT {col} FROM play_by_play " + where.format(col=col)
        for r in cur.execute(q, params):
            pbp_ids.add(r[0])
    registered = {r[0] for r in cur.execute("SELECT player_id FROM players")}
    con.close()
    # PBP 센티널/비정상 id 제외 (양수 정수만)
    out = []
    for pid in pbp_ids - registered:
        s = str(pid).strip()
        if s.isdigit() and int(s) > 0:
            out.append(s)
    return sorted(out)


def main():
    # MISSING_SEASONS: 미설정=현행(2025·2026) / "all"=전체 / "2008,2009,..."=지정
    env = os.environ.get("MISSING_SEASONS", "").strip()
    if env.lower() == "all":
        seasons = None
    elif env:
        seasons = tuple(s.strip() for s in env.split(",") if s.strip())
    else:
        seasons = ("2025", "2026")

    missing = get_missing_players(seasons)
    logger.info(f"missing players (seasons={seasons or 'ALL'}): {len(missing)}")
    if not missing:
        return

    con = sqlite3.connect(DB, timeout=120)
    session = prs.make_session()
    ok = miss = err = 0
    for i, pid in enumerate(missing, 1):
        try:
            info = prs.scrape_player_profile(session, pid)
            if info:
                prs.upsert_player(con, info, None)   # team_id 미상(은퇴 다수) → None
                con.commit()
                ok += 1
            else:
                miss += 1   # KBO 프로필 없음(아주 오래된 선수 등)
        except Exception as e:  # noqa: BLE001
            err += 1
            logger.error(f"  {pid}: {e}")
        if i % 50 == 0:
            logger.info(f"  [{i}/{len(missing)}] ok={ok} profile_miss={miss} err={err}")
        time.sleep(0.3)

    con.close()
    logger.info(f"done: 등록/갱신 {ok} / 프로필없음 {miss} / 오류 {err}")


if __name__ == "__main__":
    main()
