# -*- coding: utf-8 -*-
"""`games` 의 팀 이름을 그 시즌 이름으로 바로잡습니다.

## 무엇이 틀렸나

`games` 는 팀을 **현재 이름**으로 담고 있었습니다. 그래서 2015년
경기가 화면에 "한화 vs 키움" 으로 나옵니다. 키움은 2019년에 생긴
이름이고 그때는 넥센이었습니다.

    2015~2018  넥센 경기가 '키움' 으로   290경기
    2015~2020  SK  경기가 'SSG' 로      431경기
    합계 홈 721 · 원정 723

선수 기록은 그때 이름으로 저장합니다(1982 김우열 = OB). 경기만
현재 이름이면 같은 2015년인데 기록실에서는 "넥센", 경기 목록에서는
"키움" 으로 갈립니다.

## 어떻게 고치나

`team_seasons` 가 시즌별 표기명을 압니다.

    현재이름 '키움' + season 2015
      -> franchises  -> franchise_id 'WO'
      -> team_seasons -> '넥센'

바꿀 값이 없거나(모르는 팀) 이미 맞으면 건드리지 않습니다.

**되돌릴 수 있게 백업을 먼저 뜨십시오.**

    npx wrangler d1 export kbo-stats --remote --table games --output games.sql

    py migration/fix_game_team_names.py            # 미리보기
    py migration/fix_game_team_names.py --write    # 반영
"""
import argparse
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = os.environ.get("KBO_DB") or str(ROOT / "database" / "kbo_stats.db")

# 그 시즌 이름을 찾는 조각입니다. 바깥 games 행(g)을 봅니다.
SEASON_NAME = """
  SELECT ts.team_name
  FROM franchises f
  JOIN team_seasons ts
    ON ts.franchise_id = f.franchise_id AND ts.season = g.season
  WHERE f.current_name = g.{col}
"""


def preview(con):
    """바꿀 것들을 (시즌, 지금값, 바꿀값, 건수)로 돌려줍니다."""
    rows = []
    for col in ("home_team_id", "away_team_id"):
        q = """
          SELECT g.season, g.{col} AS now_name, ({sub}) AS want, COUNT(*) AS n
          FROM games g
          WHERE ({sub}) IS NOT NULL AND ({sub}) <> g.{col}
          GROUP BY g.season, g.{col}
          ORDER BY g.season
        """.format(col=col, sub=SEASON_NAME.format(col=col))
        for season, now, want, n in con.execute(q):
            rows.append((col, season, now, want, n))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    con = sqlite3.connect(DB)
    have = {r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    for t in ("franchises", "team_seasons"):
        if t not in have:
            print("%s 표가 없습니다. build_franchises.py --write 를 먼저 "
                  "돌리십시오." % t)
            return 1

    rows = preview(con)
    if not rows:
        print("바꿀 것이 없습니다. 이미 그 시즌 이름입니다.")
        con.close()
        return 0

    total = sum(r[4] for r in rows)
    print("%-14s %-6s %-8s -> %-8s %s" % ("컬럼", "시즌", "지금", "바꿀값", "건수"))
    print("-" * 56)
    for col, season, now, want, n in rows:
        print("%-14s %-6d %-8s -> %-8s %d" % (col, season, now, want, n))
    print("-" * 56)
    print("합계 %d건" % total)

    if not args.write:
        print("\n[미리보기] 반영하지 않았습니다. --write 를 주십시오.")
        con.close()
        return 0

    before = con.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    for col in ("home_team_id", "away_team_id"):
        sub = SEASON_NAME.format(col=col)
        # games 를 g 로 별칭 짓지 못하므로 서브쿼리 안에서 games 를
        # 직접 씁니다. 뜻은 같습니다.
        con.execute("""
          UPDATE games SET {col} = (
            SELECT ts.team_name FROM franchises f
            JOIN team_seasons ts ON ts.franchise_id = f.franchise_id
                                AND ts.season = games.season
            WHERE f.current_name = games.{col}
          )
          WHERE EXISTS (
            SELECT 1 FROM franchises f
            JOIN team_seasons ts ON ts.franchise_id = f.franchise_id
                                AND ts.season = games.season
            WHERE f.current_name = games.{col} AND ts.team_name <> games.{col}
          )
        """.format(col=col))
    con.commit()

    after = con.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    # 행이 줄면 UPDATE 가 NULL 을 넣었다는 뜻입니다. 그러면 안 됩니다.
    if before != after:
        raise RuntimeError("행 수가 %d -> %d 로 바뀌었습니다" % (before, after))
    left = preview(con)
    print("\n반영 완료. 남은 불일치 %d건" % sum(r[4] for r in left))
    nulls = con.execute(
        "SELECT COUNT(*) FROM games WHERE home_team_id IS NULL"
        " OR away_team_id IS NULL").fetchone()[0]
    print("팀 이름이 빈 경기 %d건" % nulls)
    con.close()
    return 1 if (left or nulls) else 0


if __name__ == "__main__":
    sys.exit(main())
