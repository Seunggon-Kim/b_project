"""
v2: player_info_scraper.py의 검증된 함수 import해 KBO ASP.NET ID 셀렉터 재사용

대상: PBP에 등장하지만 players 테이블 미등록인 player_id (2025·2026 합집합)
"""
import sys
sys.path.insert(0, "/home/ubuntu/b_project/data_collection")
import os
import sqlite3
import time
import logging
from datetime import datetime

from player_info_scraper import setup_driver, scrape_player_info, save_to_db

DB = "/home/ubuntu/b_project/database/kbo_stats.db"
LOG = "/tmp/scrape_missing_players_v2.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def get_missing_players(seasons=("2025", "2026")):
    """PBP 에 등장하나 players 미등록인 player_id 목록.

    seasons: 시즌(gameID 앞 4자리) 튜플로 제한. None 이면 전체 시즌 스캔
             (pre-2015 백필 시 은퇴 선수까지 잡기 위해 MISSING_SEASONS=all 로 호출).
    """
    con = sqlite3.connect(DB, timeout=60)
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
    return sorted(pbp_ids - registered)


def main():
    # MISSING_SEASONS: 미설정=현행(2025·2026) / "all"=전체 시즌 / "2008,2009,..."=지정
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

    driver = setup_driver()
    collected = []
    for i, pid in enumerate(missing, 1):
        try:
            data = scrape_player_info(driver, pid)
            if data:
                collected.append(data)
                logger.info(f"  [{i}/{len(missing)}] ✅ {pid} {data.get('player_name')}")
            else:
                logger.info(f"  [{i}/{len(missing)}] ❌ {pid} not found on KBO")
        except Exception as e:
            logger.error(f"  [{i}/{len(missing)}] error {pid}: {e}")
        time.sleep(0.5)

    driver.quit()

    if collected:
        save_to_db(collected)
        logger.info(f"saved to DB: {len(collected)}")
    logger.info(f"done")


if __name__ == "__main__":
    main()
