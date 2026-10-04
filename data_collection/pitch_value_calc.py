# -*- coding: utf-8 -*-
"""구종 가치 계산(순수 함수). DB 를 모릅니다.

설계: docs/superpowers/specs/2026-10-04-pitch-run-value-design.md

공 하나의 가치 = RE(바로 다음 행 상태) − RE(이 공 직전 상태) + 이 공 득점.
투수 쪽 부호로 바꿉니다(실점을 막으면 +). 행은 경기 안에서 pbp_id 순이어야 합니다.
"""
from collections import defaultdict

NO_TYPE = (None, "", "-", "null")


def is_pitch(r):
    return r.get("pitch_result") is not None


def has_type(r):
    return r.get("pitch_type") not in NO_TYPE


def state_of(r):
    bases = (1 if r["on_1b"] else 0) + (2 if r["on_2b"] else 0) + (4 if r["on_3b"] else 0)
    return (bases, int(r["outs"]), min(int(r["balls"]), 3), int(r["strikes"]))


def split_halves(rows):
    halves, cur, key = [], None, None
    for r in rows:
        k = (r["gameID"], r["inning"], r["inning_topbot"])
        if k != key:
            cur = []
            halves.append(cur)
            key = k
        cur.append(r)
    return halves


def last_half_index(halves):
    last = {}
    for i, h in enumerate(halves):
        last[h[0]["gameID"]] = i
    return set(last.values())


def build_re(halves, skip=frozenset()):
    sums, n = defaultdict(float), defaultdict(int)
    for i, h in enumerate(halves):
        if i in skip:
            continue
        rem = 0
        for r in reversed(h):
            rem += int(r.get("runs_scored") or 0)
            if is_pitch(r):
                s = state_of(r)
                sums[s] += rem
                n[s] += 1
    return {s: sums[s] / n[s] for s in n}, dict(n)


def expectancy_table(halves):
    re, n = build_re(halves, skip=last_half_index(halves))
    full, full_n = build_re(halves)
    for s, v in full.items():
        if s not in re:
            re[s] = v
            n[s] = full_n[s]
    return re, n


def bat_side(stands, throws):
    if stands == "양":
        return "L" if throws == "우" else "R"
    return "L" if stands == "좌" else "R"


def pitch_values(halves, re):
    out = {}
    for h in halves:
        for i, r in enumerate(h):
            # 투수 ID 가 빈 공(2019 등 원천 누락)은 누구 몫인지 몰라 뺍니다.
            # 기대 득점 표에는 그대로 씁니다.
            if not is_pitch(r) or not has_type(r) or r.get("pitcher_ID") is None:
                continue
            nxt = h[i + 1] if i + 1 < len(h) else None
            after = re.get(state_of(nxt), 0.0) if nxt is not None else 0.0
            delta = after - re[state_of(r)] + int(r.get("runs_scored") or 0)
            key = (r["pitcher_ID"], r["pitch_type"], bat_side(r.get("stands"), r.get("throws")))
            acc = out.setdefault(key, [0, 0.0])
            acc[0] += 1
            acc[1] -= delta
    return out
