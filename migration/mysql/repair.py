# -*- coding: utf-8 -*-
"""스냅샷의 알려진 데이터 오류를 고칩니다.

포스트시즌 일부 경기(경기 코드가 3333·5555·7777 로 시작)의 play_by_play.game_date 에
날짜(YYYYMMDD 정수) 대신 경기 코드 일부(예: 'TOB00929')가 글자로 들어 있습니다.
같은 경기의 games.game_date 는 정수로 맞게 들어 있으므로 그 값으로 되돌립니다.
game_date 열은 정수 그대로 둡니다. 복구한 행 수와 경기 수는
docs/mysql-migration/repair-report.md 에 남깁니다.

고치는 곳은 내려받아 둔 로컬 스냅샷 복사본뿐이며, D1 은 건드리지 않습니다.
Task 3(스냅샷 만들기) 뒤, Task 5(스키마 만들기) 앞에 한 번 실행합니다.
games 에서 정수 날짜를 찾지 못한 글자 날짜가 남으면 종료 코드 1 로 알립니다.
그 행들은 사람이 판단합니다.

    py -m migration.mysql.repair --snapshot ~/.bstats/snapshots/d1_YYYYMMDD.db
"""
import argparse
import sqlite3
import sys
from pathlib import Path

from migration.mysql.ddl import ROOT

REPORT = ROOT / "docs" / "mysql-migration" / "repair-report.md"

# games 에 정수 날짜가 있는 경기만 고칩니다.
_RESTORABLE = ("typeof(p.game_date) = 'text' AND EXISTS ("
               "SELECT 1 FROM games g WHERE g.game_id = p.gameID "
               "AND typeof(g.game_date) = 'integer')")


def _count_text(con):
    return con.execute("SELECT COUNT(*) FROM play_by_play "
                       "WHERE typeof(game_date) = 'text'").fetchone()[0]


def fix_postseason_dates(con):
    """글자로 깨진 play_by_play.game_date 를 games.game_date 로 되돌립니다.

    한 트랜잭션 안에서 세고 고칩니다(커밋은 호출한 쪽이 합니다).
    (복구한 행 수, 복구한 경기 수, 아직 글자로 남은 행 수)를 돌려줍니다.
    두 번 실행해도 안전하며, 두 번째는 (0, 0, 남은 행 수) 입니다.
    """
    if not con.in_transaction:
        con.execute("BEGIN")
    try:
        before = _count_text(con)
        fixed_games = con.execute(
            "SELECT COUNT(DISTINCT p.gameID) FROM play_by_play p WHERE " + _RESTORABLE
        ).fetchone()[0]
        cur = con.execute(
            "UPDATE play_by_play SET game_date = ("
            "SELECT g.game_date FROM games g WHERE g.game_id = play_by_play.gameID) "
            "WHERE typeof(game_date) = 'text' AND EXISTS ("
            "SELECT 1 FROM games g WHERE g.game_id = play_by_play.gameID "
            "AND typeof(g.game_date) = 'integer')")
        fixed_rows = cur.rowcount
        left_rows = _count_text(con)
        if before - fixed_rows != left_rows:
            raise RuntimeError("보정 뒤 글자 날짜 수가 맞지 않습니다: 전 %d, 고침 %d, 후 %d"
                               % (before, fixed_rows, left_rows))
    except BaseException:
        con.rollback()
        raise
    return fixed_rows, fixed_games, left_rows


def render_report(snapshot_name, fixed_rows, fixed_games, left_rows):
    """보정 보고서(마크다운)를 만듭니다."""
    lines = [
        "# 스냅샷 보정 보고",
        "",
        "- 스냅샷: `%s`" % snapshot_name,
        "- play_by_play.game_date 포스트시즌 날짜 복구: %s행 (%d경기)"
        % (format(fixed_rows, ","), fixed_games),
        "- 남은 글자 날짜: %s행" % format(left_rows, ","),
        "",
        "올바른 날짜는 `games.game_date` 에서 가져왔습니다.",
    ]
    return "\n".join(lines) + "\n"


def main():
    """스냅샷을 보정하고 보고서를 씁니다. 글자 날짜가 남으면 1, 없으면 0 을 돌려줍니다."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    args = ap.parse_args()
    path = Path(args.snapshot).expanduser()
    con = sqlite3.connect(str(path))
    try:
        fixed_rows, fixed_games, left_rows = fix_postseason_dates(con)
        con.commit()
    finally:
        con.close()
    text = render_report(path.name, fixed_rows, fixed_games, left_rows)
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(text, encoding="utf-8", newline="\n")
    print("play_by_play.game_date 포스트시즌 날짜 복구: %s행 (%d경기)"
          % (format(fixed_rows, ","), fixed_games))
    print("남은 글자 날짜: %s행" % format(left_rows, ","))
    print("보고서: %s" % REPORT)
    if left_rows:
        print("글자 날짜가 남았습니다. games 에서 날짜를 찾지 못한 행이니 evan 이 판단합니다.")
    return 0 if left_rows == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
