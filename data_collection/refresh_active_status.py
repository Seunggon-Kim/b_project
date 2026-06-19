#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""players.is_active 보강 — '현재 시즌 출전 기록이 있으면 무조건 현역(1)'을 보장한다.

배경:
  player_registry_sync.refresh_is_active() 는 is_active 를 '로스터(소속선수 명단)
  스크레이프'로 산출한다. 로스터에 잡히면 1, 같은 팀인데 로스터에 없으면 0.
  문제는 로스터 스크레이프가 일부 선수(특히 외국인)를 놓치면, 실제로 뛰고 있는데도
  0(비현역)으로 남는다는 것이다. 실제 사례: 후라도(53375, 삼성 투수, 외국인)는
  현 시즌 등판 기록이 있는데 로스터 매칭에서 빠져 is_active=0 이었다.

해법(promote-only 보강, 합집합):
  '현재 시즌(공식 스탯 기준 MAX season)에 타자/투수 스탯이 있거나 play_by_play 에
  출전한' 선수는 무조건 is_active=1 로 올린다. 절대 0으로 내리지 않는다.
  → 최종 is_active = (로스터에 있음) OR (이번 시즌 출전함).
  로스터 신호(아직 미출전 신인·부상 복귀 등 포착)는 그대로 두고, 로스터가 놓친
  '뛴 선수'만 구제하므로 registry_sync 와 충돌하지 않는다(매일 함께 돌아도 안전).
  매 실행마다 재판정하므로 외국인·이적·표기 불일치와 무관하게 자동으로 풀린다.

안전:
  기본은 dry-run(미적용) — 올릴 대상 요약만 출력. 실제 반영은 --apply.
  '내리는' 동작이 없어 오방출 위험이 없다. 네트워크 없음(로컬 sqlite, 표준 라이브러리).

cron 등록(별도 라인, KST 05:50 — registry_sync(05:40) 직후, 스탯·PBP 적재 뒤):
  50 20 * * * cd ~/b_project && venv/bin/python data_collection/refresh_active_status.py --apply >> /tmp/refresh_active_status.log 2>&1
  (서버 TZ=UTC → 20:50 UTC = KST 05:50. cron_status 노출은 gen_cron_status.py SIGNALS 에
   "active_status": ["/tmp/refresh_active_status.log"] 한 줄 추가.)
초기 1회: 먼저 dry-run 확인 후 --apply.
"""
import argparse
import sqlite3
from datetime import date
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db"

# play_by_play 선수 id 센티널(미상/결손) — 현역 판정에서 제외
PBP_SENTINELS = {"", "-1", "0"}


def _norm_id(pid):
    """선수 id를 문자열로 정규화. REAL로 적재된 '53375.0' 류도 '53375'로 맞춘다."""
    if pid is None:
        return ""
    s = str(pid).strip()
    if s.endswith(".0"):
        s = s[:-2]
    return s


def has_column(cur, table, col):
    return any(r[1] == col for r in cur.execute(f"PRAGMA table_info({table})"))


def current_season(cur):
    """현재 시즌 = 공식 스탯에 적재된 최신 season(연도와 함께 자동 전진)."""
    row = cur.execute("""
        SELECT MAX(season) FROM (
            SELECT MAX(season) AS season FROM kbo_official_batter_stats
            UNION ALL SELECT MAX(season) AS season FROM kbo_official_pitcher_stats)
    """).fetchone()
    return row[0] or date.today().year


def played_player_ids(cur, season, include_pbp=False):
    """현재 시즌 출전 선수 id 집합.

    기본 소스 = 공식 타자/투수 스탯(season 키, 작고 빠름). 경기에 나온 선수는 공식
    스탯에 잡히므로 이것만으로 현역 판정에 충분하다.
    --include-pbp 시 play_by_play 출전까지 합집합(당일 디버 등 공식 집계 지연분까지
    잡지만, 380만 행 substr 풀스캔이라 느리다 — 평소엔 불필요)."""
    ids = set()
    queries = [
        ("SELECT DISTINCT player_id FROM kbo_official_batter_stats WHERE season=?", (season,)),
        ("SELECT DISTINCT player_id FROM kbo_official_pitcher_stats WHERE season=?", (season,)),
    ]
    if include_pbp:
        queries += [
            ("SELECT DISTINCT batter_ID FROM play_by_play WHERE substr(gameID,1,4)=?", (str(season),)),
            ("SELECT DISTINCT pitcher_ID FROM play_by_play WHERE substr(gameID,1,4)=?", (str(season),)),
        ]
    for sql, params in queries:
        for (pid,) in cur.execute(sql, params):
            s = _norm_id(pid)
            if s not in PBP_SENTINELS:
                ids.add(s)
    return ids


def compute_promotions(cur, played, col_exists):
    """현 시즌 출전했는데 is_active 가 1이 아닌(0/NULL) 선수 = 올릴 대상."""
    sel = "is_active" if col_exists else "NULL AS is_active"
    rows = cur.execute(f"SELECT player_id, player_name, {sel} FROM players").fetchall()
    promote = []
    for r in rows:
        pid = _norm_id(r["player_id"])
        if pid in played:
            cur_val = r["is_active"]
            if cur_val is None or int(cur_val) != 1:
                promote.append((r["player_id"], r["player_name"], cur_val))
    return len(rows), promote


def main():
    ap = argparse.ArgumentParser(
        description="players.is_active 보강(현 시즌 출전 ⇒ 현역, promote-only)")
    ap.add_argument("--apply", action="store_true", help="실제 DB 반영(기본은 dry-run)")
    ap.add_argument("--include-pbp", action="store_true",
                    help="공식 스탯 외 play_by_play 출전까지 합집합(느린 풀스캔, 평소 불필요)")
    ap.add_argument("--db", default=str(DB_PATH), help="대상 sqlite 경로")
    args = ap.parse_args()

    con = sqlite3.connect(args.db, timeout=60)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    col_exists = has_column(cur, "players", "is_active")
    season = current_season(cur)
    played = played_player_ids(cur, season, include_pbp=args.include_pbp)
    total, promote = compute_promotions(cur, played, col_exists)

    print(f"[refresh_active_status] db={args.db}")
    print(f"  현재 시즌(파생)={season}  현시즌 출전 선수={len(played)}명  players 총 {total}행")
    print(f"  is_active 컬럼 존재={col_exists}")
    print(f"  현역으로 올릴 대상(출전했는데 0/NULL): {len(promote)}명")
    if promote:
        head = ", ".join(f"{n}({p}, 이전={v})" for p, n, v in promote[:20])
        print(f"  [현역 복구] {head}{' ...' if len(promote) > 20 else ''}")

    if not args.apply:
        print("  DRY-RUN — 변경 미적용. 실제 반영은 --apply.")
        con.close()
        return

    if not col_exists:
        cur.execute("ALTER TABLE players ADD COLUMN is_active INTEGER NOT NULL DEFAULT 0")
        print("  players.is_active 컬럼 생성")

    cur.executemany("UPDATE players SET is_active=1 WHERE player_id=?",
                    [(p,) for p, _, _ in promote])
    con.commit()
    con.close()
    print(f"  반영 완료: 현역(1)으로 올림 {len(promote)}명 (내림 0건 — promote-only)")


if __name__ == "__main__":
    main()
