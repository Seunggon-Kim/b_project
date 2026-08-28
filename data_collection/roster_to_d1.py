# -*- coding: utf-8 -*-
"""1군 등록 현황과 등말소를 D1 에 넣습니다.

## 하루 한 번 돌립니다

KBO 는 **오늘 것만** 보여 줍니다. 어제 누가 등록됐는지 묻는 화면이
없습니다. 놓친 날은 영영 못 채웁니다.

## 무엇을 넣나

    kbo_roster        지금 1군 명단. 바뀐 것만 갱신합니다.
    kbo_roster_moves  그날 등록·말소. 쌓습니다.

명단을 날마다 통째로 쌓으면 445행 x 365일 = 16만 행입니다. 대부분
어제와 같아서 낭비입니다. 그래서 `kbo_roster` 는 현재 상태만 두고
변화는 `kbo_roster_moves` 에 남깁니다.

## player_id 붙이기

등록 현황 페이지는 이름과 등번호만 줍니다. 선수 ID 가 없습니다.
공식 기록(`kbo_official_*_stats`)에 이름·팀·ID 가 있으므로 그걸로
짝짓습니다.

    1. 이름 + 팀 이 유일하면 그 ID
    2. 겹치면 players.back_number 로 한 번 더
    3. 그래도 모르면 NULL

신인이나 육성선수는 아직 기록이 없어 못 찾습니다. NULL 로 둡니다.
이름은 남으니 화면에 쓸 수 있고, 기록이 생기면 다음 날 채워집니다.

    py data_collection/roster_to_d1.py --dry-run
    py data_collection/roster_to_d1.py
"""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

from d1_load import build_upserts, query, run_d1_file  # noqa: E402
from kbo_register import collect  # noqa: E402

ROSTER_COLS = ["team", "name", "back_number", "role", "player_id", "as_of"]
MOVE_COLS = ["move_date", "kind", "team", "name", "position", "player_id"]

# 선수만 넣습니다. 감독·코치는 경기 기록이 없어 ID 를 못 붙이고,
# 화면에서도 쓸 데가 없습니다.
PLAYER_ROLES = ("투수", "포수", "내야수", "외야수")


def id_index():
    """ID 를 찾는 데 쓸 색인 셋입니다.

    `by_team`  (이름, 팀) -> {player_id}   올해 1군 기록에서
    `nums`     (이름, 등번호) -> {player_id}  players 에서
    `by_name`  이름 -> {player_id}          players 에서

    **올해 기록만으로는 모자랍니다.** 오늘 1군에 올라온 선수는 아직
    1군 기록이 없습니다. 실제로 이재학(NC)이 오늘 등록됐고 2026 투수
    기록에 없습니다. 문상철(KT)도 올해 2군에 있었습니다.

    그런 선수도 `players` 에는 있으므로 등번호로 찾습니다.
    """
    season = query("SELECT MAX(season) AS s FROM kbo_official_batter_stats;"
                   )[0]["s"]
    rows = query(
        "SELECT player_id AS pid, player_name AS nm, player_team AS tm "
        "FROM kbo_official_batter_stats WHERE season=%d "
        "UNION SELECT player_id, player_name, player_team "
        "FROM kbo_official_pitcher_stats WHERE season=%d;" % (season, season))
    by_team = {}
    for r in rows:
        by_team.setdefault((r["nm"], r["tm"]), set()).add(int(r["pid"]))

    nums, by_name = {}, {}
    for r in query("SELECT player_id AS pid, player_name AS nm, "
                   "back_number AS bn FROM players;"):
        pid = int(r["pid"])
        by_name.setdefault(r["nm"], set()).add(pid)
        if r["bn"] is not None:
            nums.setdefault((r["nm"], str(r["bn"])), set()).add(pid)
    return season, by_team, nums, by_name


def resolve(by_team, nums, by_name, name, team, back_number):
    """못 찾으면 None 입니다. 찍지 않습니다.

    순서가 중요합니다. 올해 1군 기록이 가장 믿을 만하고, 등번호는
    `players` 가 낡아 있을 수 있습니다(이적·번호 변경이 늦게 반영).
    """
    cands = by_team.get((name, team)) or set()
    if len(cands) == 1:
        return next(iter(cands))

    hit = nums.get((name, str(back_number))) or set()
    if cands:
        # 올해 기록에 동명이인이 있습니다. 등번호로 좁힙니다.
        narrowed = cands & hit
        return next(iter(narrowed)) if len(narrowed) == 1 else None

    # 올해 1군 기록이 없는 선수입니다(오늘 콜업·2군·신인).
    if len(hit) == 1:
        return next(iter(hit))
    # 등번호로도 안 되면 이름이 유일할 때만 씁니다. 둘 이상이면
    # 은퇴 선수가 섞였을 수 있어 포기합니다.
    only = by_name.get(name) or set()
    return next(iter(only)) if len(only) == 1 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    d = collect()
    as_of = d["as_of"]
    season, by_team, nums, by_name = id_index()
    print("기준일 %s, ID 원천 %d시즌" % (as_of, season))

    roster = [r for r in d["roster"] if r["role"] in PLAYER_ROLES]
    rows = []
    for r in roster:
        rows.append({
            "team": r["team"], "name": r["name"],
            "back_number": r["back_number"], "role": r["role"],
            "player_id": resolve(by_team, nums, by_name, r["name"], r["team"],
                                 r["back_number"]),
            "as_of": as_of,
        })
    matched = sum(1 for x in rows if x["player_id"])
    print("명단 %d명 (감독·코치 제외), ID 붙은 것 %d명" % (len(rows), matched))

    moves = []
    for m in d["moves"]:
        moves.append({
            "move_date": as_of, "kind": m["kind"], "team": m["team"],
            "name": m["name"], "position": m["position"],
            "player_id": resolve(by_team, nums, by_name, m["name"], m["team"], ""),
        })
    reg = sum(1 for x in moves if x["kind"] == "등록")
    print("등말소 %d건 (등록 %d, 말소 %d)" % (len(moves), reg, len(moves) - reg))

    if not rows:
        print("명단이 비었습니다. 페이지 구조가 바뀌었을 수 있습니다.")
        return 1

    if args.dry_run:
        print("\n[미리보기] 넣지 않았습니다.")
        for x in rows[:5]:
            print("   %-5s %-8s %-4s %-6s id=%s"
                  % (x["team"], x["name"], x["back_number"], x["role"],
                     x["player_id"]))
        for x in moves:
            print("   %-3s %-5s %-8s id=%s"
                  % (x["kind"], x["team"], x["name"], x["player_id"]))
        return 0

    stmts = build_upserts("kbo_roster", ROSTER_COLS,
                          ["team", "name", "back_number"], rows,
                          max_bytes=20000)
    if moves:
        stmts += build_upserts("kbo_roster_moves", MOVE_COLS,
                               ["move_date", "kind", "team", "name"], moves,
                               max_bytes=20000)
    out = ROOT / "migration" / "roster_upsert.sql"
    out.write_text("\n".join(stmts) + "\n", encoding="utf-8", newline="\n")
    run_d1_file(out)
    print("적재 완료 (%d문)" % len(stmts))

    # 1군을 떠난 선수는 명단에서 지웁니다. 남겨 두면 "지금 1군" 이
    # 아니라 "한 번이라도 1군이었던 사람" 이 됩니다.
    keys = ",".join(
        "('%s','%s','%s')" % (x["team"].replace("'", "''"),
                              x["name"].replace("'", "''"),
                              x["back_number"])
        for x in rows)
    gone = ROOT / "migration" / "roster_prune.sql"
    gone.write_text(
        "DELETE FROM kbo_roster WHERE (team, name, back_number) NOT IN (%s);\n"
        % keys, encoding="utf-8", newline="\n")
    run_d1_file(gone)
    left = query("SELECT COUNT(*) AS n FROM kbo_roster;")[0]["n"]
    print("현재 명단 %s명" % left)
    return 0


if __name__ == "__main__":
    import warnings
    warnings.simplefilter("ignore")
    sys.exit(main())
