# -*- coding: utf-8 -*-
"""기존 players 전체에 분류 플래그(국적/외국인/아시아쿼터/현역)를 1회 백필.

실행:
  python data_collection/backfill_player_flags.py [db_path] [--dry-run]

순서:
  1) migrate_add_player_flags.ensure_columns() 로 컬럼 보장 (멱등)
  2) career 로 nationality/is_foreign/player_type 도출 (player_flags.classify_player)
  3) is_active 산출:
       - 우선 player_registry_sync.refresh_is_active(con, session) (현 로스터 스크레이프, 정확)
       - 실패 시 DB 프록시(2026 공식스탯/PBP 출현)로 폴백 (방출 선수가 다음 동기화 전까지 1로 보일 수 있음)
  4) 요약 + 검토대상(국내 분류 but 한국학교 흔적 없음) 출력

운영 적용 전 DB 백업 필수. --dry-run 은 UPDATE 없이 집계만.
"""

import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "database"))

import player_flags as pf
from migrate_add_player_flags import ensure_columns

DEFAULT_DB = os.path.join(os.path.dirname(__file__), "..", "database", "kbo_stats.db")
CURRENT_SEASON = 2026


def _db_proxy_active_ids(con):
    """현 로스터 스크레이프 불가 시 폴백: 2026 공식스탯/PBP 에 출현한 선수 = 현역 근사."""
    ids = set()
    for sql in (
        "SELECT player_id FROM kbo_official_batter_stats WHERE season=?",
        "SELECT player_id FROM kbo_official_pitcher_stats WHERE season=?",
    ):
        try:
            ids |= {str(r[0]) for r in con.execute(sql, (CURRENT_SEASON,))}
        except sqlite3.OperationalError:
            pass
    try:
        ids |= {str(r[0]) for r in con.execute(
            "SELECT DISTINCT batter_ID FROM play_by_play WHERE substr(CAST(game_date AS TEXT),1,4)=?",
            (str(CURRENT_SEASON),))}
        ids |= {str(r[0]) for r in con.execute(
            "SELECT DISTINCT pitcher_ID FROM play_by_play WHERE substr(CAST(game_date AS TEXT),1,4)=?",
            (str(CURRENT_SEASON),))}
    except sqlite3.OperationalError:
        pass
    ids.discard("None"); ids.discard("")
    return ids


def _official_2026_ids(con):
    """2026 공식스탯(타자/투수) 출현 선수 id 집합. 소형 테이블이라 빠름.
    로스터 합집합 보강용 — PBP 풀스캔(느림)을 피하려 fallback 프록시와 분리한다."""
    ids = set()
    for sql in (
        "SELECT player_id FROM kbo_official_batter_stats WHERE season=?",
        "SELECT player_id FROM kbo_official_pitcher_stats WHERE season=?",
    ):
        try:
            ids |= {str(r[0]) for r in con.execute(sql, (CURRENT_SEASON,))}
        except sqlite3.OperationalError:
            pass
    ids.discard("None")
    ids.discard("")
    return ids


def _set_is_active(con, dry):
    """is_active 산출. (산출방식, 현역수) 반환.

    현역 = 현 로스터 스크레이프 ∪ 2026 공식스탯 출현.
    로스터 스크레이프는 1군 엔트리만 잡아 2군/말소 중인 '등록' 선수를 거짓 비현역으로
    떨굴 수 있어, 2026 출전 선수를 합집합으로 보강한다(예: 황성빈).
    이적·은퇴로 2026 미출전이면 합집합에도 안 들어가 정상적으로 비현역(예: 폰세)."""
    method = None
    # 1순위: 레지스트리 현 로스터 스크레이프
    try:
        import player_registry_sync as prs
        if hasattr(prs, "refresh_is_active"):
            n = prs.refresh_is_active(con, dry_run=dry)
            # n==0 은 로스터 스크레이프 전면 실패(0팀) → 프록시 폴백
            if n and n > 0:
                method = "roster_scrape"
            else:
                print("[backfill] refresh_is_active 0명 반환 → 로스터 스크레이프 전면 실패, DB 프록시 폴백")
    except Exception as e:  # noqa: BLE001
        print(f"[backfill] refresh_is_active 사용 불가 → DB 프록시 폴백 ({e})")

    if method == "roster_scrape":
        # 로스터 ∪ 2026 공식스탯 출현: 스크레이프가 놓친 출전 등록선수를 현역으로 보강(빠름)
        appeared = _official_2026_ids(con)
        if not dry and appeared:
            con.executemany(
                "UPDATE players SET is_active=1 WHERE player_id=? AND (is_active IS NULL OR is_active=0)",
                [(i,) for i in appeared])
            con.commit()
        n_total = con.execute("SELECT COUNT(*) FROM players WHERE is_active=1").fetchone()[0]
        return ("roster_scrape+2026출전", n_total)
    # 2순위(폴백): DB 프록시(공식스탯+PBP, 로스터 전면 실패 시에만)
    active = _db_proxy_active_ids(con)
    if not dry:
        con.execute("UPDATE players SET is_active=0")
        con.executemany("UPDATE players SET is_active=1 WHERE player_id=?",
                        [(i,) for i in active])
        con.commit()
    return ("db_proxy_2026", len(active))


def main(db_path=DEFAULT_DB, dry=False):
    # timeout: 05:40 cron 등과 겹쳐도 'database is locked' 로 즉시 죽지 않게 여유
    con = sqlite3.connect(db_path, timeout=60)
    try:
        added = ensure_columns(con)
        print(f"[backfill] DB: {db_path} | 컬럼 추가: {added or '이미 적용'} | dry_run={dry}")

        rows = con.execute("SELECT player_id, player_name, team_id, career FROM players").fetchall()
        from collections import Counter
        ptype, nat = Counter(), Counter()
        review = []
        updates = []
        for pid, name, team, career in rows:
            career = career or ""
            n, isf, pt = pf.classify_player(pid, career, CURRENT_SEASON)
            updates.append((n, isf, pt, str(pid)))
            ptype[pt] += 1
            if isf:
                nat[n or "(국적미상)"] += 1
            if pf.is_review_suspect(pid, career, CURRENT_SEASON):
                review.append((pid, name, team, (career or "")[:30]))

        if not dry:
            con.executemany(
                "UPDATE players SET nationality=?, is_foreign=?, player_type=? WHERE player_id=?",
                updates)
            con.commit()

        method, active_n = _set_is_active(con, dry)

        print(f"[backfill] 총 {len(rows)}명 | player_type={dict(ptype)} | is_active={active_n} ({method})")
        print("[backfill] 국적(외국인):", dict(nat))
        print(f"[backfill] 검토대상(국내 but 한국학교 흔적 없음) {len(review)}명:")
        for x in review:
            print("   ", x)
    finally:
        con.close()


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    main(args[0] if args else DEFAULT_DB, dry)
