"""
v2: player_info_scraper.py의 검증된 함수 import해 KBO ASP.NET ID 셀렉터 재사용

대상: PBP에 등장하지만 players 테이블 미등록인 player_id (2025·2026 합집합)
"""
import sys
sys.path.insert(0, "/home/ubuntu/b_project/data_collection")
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


def get_missing_players():
    con = sqlite3.connect(DB, timeout=60)
    cur = con.cursor()
    pbp_ids = set()
    for r in cur.execute(
        "SELECT DISTINCT batter_ID FROM play_by_play "
        "WHERE substr(gameID,1,4) IN ('2025','2026') "
        "AND batter_ID IS NOT NULL AND batter_ID<>''"
    ):
        pbp_ids.add(r[0])
    for r in cur.execute(
        "SELECT DISTINCT pitcher_ID FROM play_by_play "
        "WHERE substr(gameID,1,4) IN ('2025','2026') "
        "AND pitcher_ID IS NOT NULL AND pitcher_ID<>''"
    ):
        pbp_ids.add(r[0])
    registered = {r[0] for r in cur.execute("SELECT player_id FROM players")}
    con.close()
    return sorted(pbp_ids - registered)


def main():
    missing = get_missing_players()
    logger.info(f"missing players: {len(missing)}")
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
