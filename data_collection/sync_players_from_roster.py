# -*- coding: utf-8 -*-
"""`kbo_roster` 의 최신 소속·등번호를 `players` 에 반영합니다.

## 왜 필요한가

`players.team_id` 와 `back_number` 가 낡았습니다. 실측하면 337명 중
**소속 98명, 등번호 58명**이 실제와 다릅니다.

    최용준   KBO SSG 67번   /   DB KT 92번
    로건     KBO KT  43번   /   DB NC 12번
    이태양   KBO KIA        /   DB 한화

이적과 등번호 변경이 반영이 안 됩니다. monthly 의 선수 프로필 수집은
**새 선수만** 받습니다(이미 있으면 건너뜀). 그래서 기존 선수의 소속이
바뀌어도 영영 안 고쳐집니다.

## 무엇을 고치나

`kbo_roster` 는 매일 KBO 등록 현황에서 새로 받으므로 가장 최신입니다.
그중 `player_id` 가 붙은 행만 반영합니다.

**바뀐 것만 씁니다.** 337명을 매일 통째로 갱신하면 인덱스까지 쳐서
하루 1,000 쓰기가 그냥 나갑니다. 실제로 바뀌는 것은 이적·번호 변경이
있는 날뿐입니다.

## 1군에 없는 선수는 건드리지 않습니다

`kbo_roster` 는 **1군 등록 선수만** 담습니다. 2군에 있거나 은퇴한
선수는 여기 없습니다. 그들의 소속을 지우면 안 되므로 명단에 있는
선수만 손댑니다.

    py data_collection/sync_players_from_roster.py --dry-run
    py data_collection/sync_players_from_roster.py
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from d1_load import query, run_d1_file  # noqa: E402


def same_number(db_value, kbo_value):
    """등번호가 같은지 봅니다.

    **`players.back_number` 는 INTEGER 입니다.** `'00'` 을 넣어도 SQLite
    가 정수 `0` 으로 바꿉니다. 그래서 DB 안에서는 `0` 번과 `00` 번이
    구분되지 않습니다. 실제로 다섯 명이 이 번호를 씁니다.

        권혁빈 키움 00   강민균 LG 00
        황성빈 롯데 0    곽도규 KIA 0   디아즈 삼성 0

    컬럼 타입을 TEXT 로 바꾸면 갈리지만, 그 컬럼을 읽는 화면과 API 가
    여럿이라 타입을 바꾸는 편이 위험합니다. 여기서는 **숫자로 견줍니다.**
    `0` 과 `00` 을 같다고 보면 이 다섯 명이 매일 "바뀜"으로 잡혀 쓸데없이
    UPDATE 가 나갑니다.

    등번호가 실제로 갈려야 하는 곳(같은 팀 동명이인 투수)은 `kbo_roster`
    를 봅니다. 그 표는 TEXT 라 `00` 이 그대로 남습니다.
    """
    if db_value is None:
        return False
    try:
        return int(db_value) == int(kbo_value)
    except (TypeError, ValueError):
        return str(db_value) == str(kbo_value)


def diffs():
    """(player_id, 이름, 새 소속, 새 등번호, 옛 소속, 옛 등번호) 목록."""
    rows = query(
        "SELECT r.player_id AS pid, r.name AS nm, r.team AS rt, "
        "r.back_number AS rb, p.team_id AS pt, p.back_number AS pb "
        "FROM kbo_roster r JOIN players p ON p.player_id = r.player_id;")
    out = []
    for r in rows:
        same_team = (r["pt"] or "") == r["rt"]
        if not (same_team and same_number(r["pb"], r["rb"])):
            out.append(r)
    return out


def sql_str(v):
    return "'" + str(v).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = diffs()
    if not rows:
        print("바꿀 것이 없습니다. players 가 최신입니다.")
        return 0

    team = sum(1 for r in rows if (r["pt"] or "") != r["rt"])
    num = sum(1 for r in rows if str(r["pb"] or "") != str(r["rb"]))
    print("바뀐 선수 %d명 (소속 %d, 등번호 %d)" % (len(rows), team, num))
    for r in rows[:10]:
        print("   %-8s %-5s %-4s  <-  %-6s %s"
              % (r["nm"], r["rt"], r["rb"], r["pt"] or "없음", r["pb"] or "없음"))
    if len(rows) > 10:
        print("   ... 그 외 %d명" % (len(rows) - 10))

    if args.dry_run:
        print("\n[미리보기] 반영하지 않았습니다.")
        return 0

    # UPDATE 를 행마다 씁니다. players 는 UPSERT 하면 안 됩니다.
    # 생년월일·신장·경력 같은 다른 컬럼을 덮어쓸 위험이 있습니다.
    lines = []
    for r in rows:
        lines.append(
            "UPDATE players SET team_id=%s, back_number=%s, "
            "updated_at=datetime('now') WHERE player_id=%d;"
            % (sql_str(r["rt"]), sql_str(r["rb"]), int(r["pid"])))
    out = ROOT / "migration" / "players_sync.sql"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    run_d1_file(out)
    print("반영 완료 (%d문)" % len(lines))

    left = diffs()
    print("남은 불일치 %d명" % len(left))
    return 0


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    sys.exit(main())
