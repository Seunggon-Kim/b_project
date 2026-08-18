"""
Step 2: 매일 player 변경 감지 + selenium 재크롤 + SCD Type 2 history 갱신

검출 source 3종:
  PBP_team   — 어제 PBP에서 home_alias가 players.team_id와 다른 batter
  KBO_team   — kbo_official_*_stats.player_team이 players.team_id와 다른 player
  KBO_back   — KBO 공식 stats에 등번호 갱신 (있다면)

의심 list → selenium 재크롤 → 변경 확정 시:
  1. player_history: 기존 valid row의 valid_to = today
  2. player_history: 새 row INSERT (valid_from = today)
  3. players: UPDATE current state
"""
import os
import sys
import tempfile
from pathlib import Path

# EC2 절대경로(/home/ubuntu/...)는 윈도우와 GitHub Actions 러너에서
# 동작하지 않습니다. 그 서버는 2026-07-14 에 없어졌습니다.
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import sqlite3
import time
import logging
from datetime import date

# DB 경로: 환경변수 KBO_DB 우선, 없으면 저장소 기준 상대경로.
DB = os.environ.get("KBO_DB") or str(
    _HERE.parent / "database" / "kbo_stats.db")
LOG = os.path.join(tempfile.gettempdir(), "daily_player_detector.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def detect_suspects(con):
    """변경 의심 player_id list 반환 (3 source 합집합)"""
    cur = con.cursor()
    today = date.today().isoformat()
    yday = (date.today().toordinal() - 1)
    yesterday_int = int((date.fromordinal(yday)).strftime("%Y%m%d"))

    suspects = {}  # player_id → (source, new_team_or_field, old_value)

    # Source 1: PBP에서 어제 home 경기 batter의 팀 변경
    # batter가 home/away 어느 쪽인지 정확히 알 수 없으므로, away_alias도 함께 비교
    # 단순 휴리스틱: batter_ID가 yesterday games에서 등장 + 그 게임의 (home_alias, away_alias) 중 어느 한 쪽이 batter 본인팀
    # 우리는 official stats의 player_team을 신뢰하고, PBP는 보조 신호로만 사용
    # (PBP만으론 batter team 정확 추론 불가능 — 대주자 등 케이스)

    # Source 2: KBO official stats team 변경 (가장 신뢰)
    # 현 시즌만 비교한다 — 과거 시즌 row까지 보면 시즌 사이에 이적한 선수가
    # 옛 팀으로 매일 되돌아가는 진동(A↔B)이 생긴다.
    cur.execute("""
        SELECT MAX(s) FROM (
            SELECT MAX(season) AS s FROM kbo_official_batter_stats
            UNION ALL SELECT MAX(season) FROM kbo_official_pitcher_stats)
    """)
    season = cur.fetchone()[0]
    cur.execute("""
        SELECT k.player_id, k.player_team AS new_team, p.team_id AS old_team
        FROM kbo_official_batter_stats k
        JOIN players p ON p.player_id = k.player_id
        WHERE k.season = ?
          AND k.player_team IS NOT NULL
          AND p.team_id IS NOT NULL
          AND k.player_team <> p.team_id
        UNION
        SELECT k.player_id, k.player_team AS new_team, p.team_id AS old_team
        FROM kbo_official_pitcher_stats k
        JOIN players p ON p.player_id = k.player_id
        WHERE k.season = ?
          AND k.player_team IS NOT NULL
          AND p.team_id IS NOT NULL
          AND k.player_team <> p.team_id
    """, (season, season))
    for pid, new_t, old_t in cur.fetchall():
        suspects[pid] = ("KBO_team", new_t, old_t)

    # Source 3: PBP에서 player가 다른 팀의 home 경기에 등장 → 보조 신호
    # 어제만 처리해서 일일 부담 작게
    cur.execute("""
        SELECT DISTINCT pbp.batter_ID, pbp.home_alias, pbp.away_alias
        FROM play_by_play pbp
        WHERE pbp.game_date = ?
          AND pbp.batter_ID IS NOT NULL AND pbp.batter_ID <> ''
    """, (yesterday_int,))
    for pid, ha, aa in cur.fetchall():
        if pid in suspects:
            continue
        old_team = cur.execute("SELECT team_id FROM players WHERE player_id=?", (pid,)).fetchone()
        if old_team and old_team[0] and old_team[0] not in (ha, aa):
            suspects[pid] = ("PBP_team", f"{ha}/{aa}", old_team[0])

    return suspects


def estimate_change_date(con, pid, new_team, last_valid_from):
    """PBP에서 player가 new_team 소속으로 첫 PA(또는 투구)를 가진 game_date.
    batter team = (inning_topbot='말'이면 home_alias, '초'이면 away_alias)
    pitcher team = (inning_topbot='말'이면 away_alias, '초'이면 home_alias)
    """
    if not new_team:
        return None
    cur = con.cursor()
    last_yyyymmdd = (last_valid_from or "1900-01-01").replace("-", "")

    # batter_ID 케이스
    cur.execute("""
        SELECT MIN(game_date) FROM play_by_play
        WHERE batter_ID = ? AND game_date > ?
          AND (CASE WHEN inning_topbot='말' THEN home_alias ELSE away_alias END) = ?
    """, (pid, last_yyyymmdd, new_team))
    r = cur.fetchone()
    candidates = []
    if r and r[0]:
        candidates.append(int(r[0]))

    # pitcher_ID 케이스
    cur.execute("""
        SELECT MIN(game_date) FROM play_by_play
        WHERE pitcher_ID = ? AND game_date > ?
          AND (CASE WHEN inning_topbot='말' THEN away_alias ELSE home_alias END) = ?
    """, (pid, last_yyyymmdd, new_team))
    r = cur.fetchone()
    if r and r[0]:
        candidates.append(int(r[0]))

    if not candidates:
        return None
    d = str(min(candidates))
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def upsert_history(con, pid, new_data, src):
    """변경 확정: history close + new row insert + players update.
    valid_from = PBP 첫 등장 일자 (백트래킹), 없으면 today fallback."""
    cur = con.cursor()
    today = date.today().isoformat()

    # 기존 valid row의 valid_from 조회 (재크롤 경계)
    cur.execute(
        "SELECT valid_from FROM player_history WHERE player_id=? AND valid_to IS NULL",
        (pid,),
    )
    row = cur.fetchone()
    last_valid_from = row[0] if row else None

    # team 변경 시 PBP 백트래킹으로 실제 변경 일자 추정
    estimated = estimate_change_date(con, pid, new_data.get("team_id"), last_valid_from)
    valid_from = estimated if estimated else today

    # 기존 valid row 닫기 (valid_to = 새 valid_from으로 정확히 이음)
    cur.execute(
        "UPDATE player_history SET valid_to = ? WHERE player_id = ? AND valid_to IS NULL",
        (valid_from, pid),
    )

    # 새 row insert
    cur.execute("""
        INSERT INTO player_history
          (player_id, valid_from, valid_to, team_id, back_number, position, throw, bat, height, weight, detection_src)
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (pid, valid_from,
          new_data.get("team_id"), new_data.get("back_number"), new_data.get("position"),
          new_data.get("throw"), new_data.get("bat"),
          new_data.get("height"), new_data.get("weight"),
          f"{src}{'+pbp' if estimated else '+today'}"))

    # players UPDATE
    cur.execute("""
        UPDATE players SET
          team_id = ?, back_number = ?, position = ?,
          throw = ?, bat = ?, height = ?, weight = ?,
          updated_at = datetime('now')
        WHERE player_id = ?
    """, (new_data.get("team_id"), new_data.get("back_number"), new_data.get("position"),
          new_data.get("throw"), new_data.get("bat"),
          new_data.get("height"), new_data.get("weight"), pid))


def main():
    con = sqlite3.connect(DB, timeout=60)
    cur = con.cursor()
    cur.execute("PRAGMA journal_mode = WAL")
    cur.fetchone()

    suspects = detect_suspects(con)
    logger.info(f"detected suspects: {len(suspects)}")
    for pid, (src, new, old) in list(suspects.items())[:20]:
        logger.info(f"  {pid:>8}  {src}  old={old}  new={new}")

    if not suspects:
        logger.info("no changes detected. exit.")
        con.close()
        return

    # 의심 player만 재수집 (requests 기반 — selenium·/tmp 사본 의존 제거)
    from player_registry_sync import make_session, scrape_player_profile

    session = make_session()
    n_changed = 0
    for pid, (src, new, old) in suspects.items():
        try:
            new_data = scrape_player_profile(session, pid)
            if not new_data or not new_data.get("player_name"):
                logger.warning(f"  {pid} scrape fail")
                continue
            # 프로필 페이지에는 팀 표기가 없으므로, 공식 스탯 신호일 때만 새 팀을 반영
            new_data["team_id"] = new if src == "KBO_team" else old
            # 비교: 현재 players와 다른 필드 있나
            cur.execute("SELECT team_id, back_number, position, throw, bat, height, weight FROM players WHERE player_id=?", (pid,))
            old_row = cur.fetchone()
            if old_row:
                fields = ("team_id", "back_number", "position", "throw", "bat", "height", "weight")
                changed_fields = [f for f, ov in zip(fields, old_row) if new_data.get(f) != ov and new_data.get(f) is not None]
                if not changed_fields:
                    logger.info(f"  {pid} {new_data['player_name']}: no actual change despite suspect")
                    continue
                logger.info(f"  {pid} {new_data['player_name']}: changed fields = {changed_fields}")
                # 프로필에서 못 읽은 필드(None)는 기존 값을 유지 — NULL 덮어쓰기 방지
                for f, ov in zip(fields, old_row):
                    if new_data.get(f) is None:
                        new_data[f] = ov

            upsert_history(con, pid, new_data, src)
            con.commit()
            n_changed += 1
        except Exception as e:
            logger.error(f"  {pid} error: {e}")
        time.sleep(0.5)

    con.close()
    logger.info(f"done: changes confirmed = {n_changed}")


if __name__ == "__main__":
    main()
