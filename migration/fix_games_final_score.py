# -*- coding: utf-8 -*-
"""`games` 의 최종 점수를 마지막 플레이 득점까지 넣어 바로잡습니다.

## 무엇이 틀렸나

`games` 점수는 PBP 의 score_home/score_away 최댓값이었습니다. 이 값은
플레이 **전** 점수라 끝내기처럼 마지막 플레이에서 난 점수가 빠집니다.

    2015~2025 정규시즌 무승부  games 50~80경기  공식 5~22경기
    2025 LG                    games 83-54-7   공식 85-56-3

또 2026-08-18 뒤 daily 는 점수를 글자로 비교해 두 자리 점수가 한 자리로
들어갔습니다(8/19 SSG-삼성 18점이 7점). 수집기는 `games_from_pbp.py` 에서
고쳤고, 이 스크립트는 이미 들어간 행을 고칩니다.

## 어떻게 고치나

MySQL 의 PBP 로 (플레이 전 점수 + 그 플레이에서 공격 팀이 낸 점수)의
최댓값을 셉니다. 값이 다른 경기만 MySQL 에 씁니다(2026-10-03 에 한 번
돌렸습니다. D1 은 2026-10-04 에 걷어냈습니다).

2008~2014 는 바꾸지 않습니다. 그 시즌 games 는 다른 출처에서 받아 이미
공식 무승부 수와 맞습니다.

    py migration/fix_games_final_score.py            # 미리보기
    py migration/fix_games_final_score.py --write    # 반영

반영 전에 되돌리기 SQL(`migration/_fix_games_final_score.rollback.sql`)을
먼저 씁니다.
"""
import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "data_collection"))

from mysql_sink import mirror  # noqa: E402
from migration.fix_games_from_naver import PBP_INCOMPLETE  # noqa: E402

FIRST_SEASON = 2015
ROLLBACK_SQL = ROOT / "migration" / "_fix_games_final_score.rollback.sql"

# games_from_pbp.derive_games 와 같은 규칙입니다.
FINAL_SCORE = """
SELECT g.game_id, g.season, g.game_type, g.home_score, g.away_score, f.hs, f.as_
FROM games g
JOIN (
  SELECT gameID,
         MAX(score_home + CASE WHEN inning_topbot = '말'
                               THEN COALESCE(runs_scored, 0) ELSE 0 END) AS hs,
         MAX(score_away + CASE WHEN inning_topbot = '초'
                               THEN COALESCE(runs_scored, 0) ELSE 0 END) AS as_
  FROM play_by_play
  WHERE game_date >= %s
  GROUP BY gameID
) f ON f.gameID = g.game_id
WHERE g.season >= %s
  AND (g.home_score <> f.hs OR g.away_score <> f.as_
       OR g.home_score IS NULL OR g.away_score IS NULL)
ORDER BY g.game_id
"""


def changes(cur):
    cur.execute(FINAL_SCORE, (FIRST_SEASON * 10000, FIRST_SEASON))
    return [dict(zip(("game_id", "season", "game_type", "old_home", "old_away",
                      "home", "away"), r)) for r in cur.fetchall()
            if r[5] is not None and r[6] is not None
            # PBP 가 끊긴 경기는 네이버 최종 점수로 넣었습니다(fix_games_from_naver).
            and r[0] not in PBP_INCOMPLETE]


def literal(v):
    """되돌리기 SQL 의 값 하나입니다. 점수는 정수, 경기 ID 는 글자입니다."""
    if v is None:
        return "NULL"
    if isinstance(v, int):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def update_sql(rows, home, away):
    return "\n".join(
        "UPDATE games SET home_score = %s, away_score = %s WHERE game_id = %s;"
        % (literal(r[home]), literal(r[away]), literal(r["game_id"]))
        for r in rows) + "\n"


def mysql_write(sink, rows):
    for r in rows:
        sink.execute("UPDATE games SET home_score = %s, away_score = %s WHERE game_id = %s",
                     (r["home"], r["away"], r["game_id"]))
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    from migration.mysql import conn
    con = conn.connect()
    try:
        with con.cursor() as cur:
            rows = changes(cur)
    finally:
        con.close()

    per = Counter((r["season"], r["game_type"]) for r in rows)
    ties_fixed = sum(1 for r in rows if r["old_home"] == r["old_away"] and r["home"] != r["away"])
    print("바꿀 경기 %d개 (무승부에서 승패로 %d개)" % (len(rows), ties_fixed))
    for (season, kind), n in sorted(per.items()):
        print("  %s %s %d" % (season, kind, n))
    for r in rows[:5]:
        print("  예: %s %s:%s -> %s:%s" % (r["game_id"], r["old_away"], r["old_home"],
                                          r["away"], r["home"]))
    if not args.write or not rows:
        print("[미리보기] 쓰지 않았습니다.")
        return 0

    ROLLBACK_SQL.write_text(update_sql(rows, "old_home", "old_away"),
                            encoding="utf-8", newline="\n")
    print("되돌리기 SQL: %s" % ROLLBACK_SQL)
    mirror("fix_games_final_score", lambda sink: mysql_write(sink, rows), required=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
