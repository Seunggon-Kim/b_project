# -*- coding: utf-8 -*-
"""시즌 -> D1 배정을 읽습니다.

정본은 `migration/shard_plan.json` 입니다. Worker 쪽 사본은
`src/lib/shard.js` 이고 `test/shard.test.js` 가 둘이 같은지 강제합니다.
**여기에 배정을 다시 적지 마십시오.** 두 곳에 적으면 언젠가 어긋나고,
어긋나면 넣은 데이터가 화면에서 사라집니다.
"""
import json
from pathlib import Path

PLAN_PATH = Path(__file__).resolve().parent / "shard_plan.json"

# play_by_play 의 시즌은 gameID 가 아니라 game_date 로 봅니다.
# 포스트시즌 gameID 는 앞 4자리가 연도가 아니라 시리즈 코드입니다
# (3333=PO, 4444=준PO, 6666=WC). 자세한 설명은 export_season.py 에
# 적어 두었습니다.
PBP_SEASON_WHERE = "game_date >= {y}0000 AND game_date < {n}0000"


def load():
    return json.loads(PLAN_PATH.read_text(encoding="utf-8"))


def shards():
    """[{binding, database, database_id, seasons}] 을 돌려줍니다."""
    return load()["shards"]


def shared_db():
    return load()["shared"]["database"]


def db_of(season):
    """시즌 하나를 담당하는 D1 이름입니다. 배정에 없으면 None 입니다."""
    y = int(season)
    for s in shards():
        if y in s["seasons"]:
            return s["database"]
    return None


def all_seasons():
    return sorted(y for s in shards() for y in s["seasons"])


def pbp_where(season):
    y = int(season)
    return PBP_SEASON_WHERE.format(y=y, n=y + 1)


def check():
    """배정이 성립하는지 봅니다. 문제 목록을 돌려줍니다."""
    problems = []
    seen = {}
    for s in shards():
        for y in s["seasons"]:
            if y in seen:
                # 한 시즌이 두 DB 에 들어가는 것이 가장 흔한 실수입니다.
                problems.append(
                    "%d 이 %s 와 %s 에 겹칩니다" % (y, seen[y], s["database"]))
            seen[y] = s["database"]
    years = sorted(seen)
    for a, b in zip(years, years[1:]):
        if b != a + 1:
            problems.append("%d 과 %d 사이가 비었습니다" % (a, b))
    return problems


if __name__ == "__main__":
    import sys
    bad = check()
    for s in shards():
        print("%-20s %s" % (s["database"],
                            ", ".join(str(y) for y in s["seasons"])))
    print()
    if bad:
        for b in bad:
            print("문제: %s" % b)
        sys.exit(1)
    print("배정 이상 없음 (시즌 %d개: %d~%d)"
          % (len(all_seasons()), all_seasons()[0], all_seasons()[-1]))
