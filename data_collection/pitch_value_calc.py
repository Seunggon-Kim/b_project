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


# 공격 존(Tango·Savant Heart/Shadow/Chase/Waste)입니다(2026-10-06). 투구 분포
# 화면(arsenal attackZone)·pitch_trend 의 edge 와 같은 규칙입니다. 폭은 10/12 ft,
# 높이는 그 공의 sz_top·sz_bot(둘 다 있고 top > bot), 아니면 3.5·1.5 ft.
HALF_W = 10 / 12
ZONES = ("heart", "shadow", "chase", "waste")


def zone_of(r):
    """공의 공격 존입니다. px·pz 가 없으면 None(어느 존에도 넣지 않음)."""
    px, pz = r.get("px"), r.get("pz")
    if px is None or pz is None:
        return None
    top, bot = r.get("sz_top"), r.get("sz_bot")
    if top is None or bot is None or not top > bot:
        top, bot = 3.5, 1.5
    rr = max(abs(px) / HALF_W, abs(pz - (top + bot) / 2) / ((top - bot) / 2))
    if rr < 0.67:
        return "heart"
    if rr < 1.33:
        return "shadow"
    if rr < 2:
        return "chase"
    return "waste"


def pitch_deltas(halves, re):
    """가치를 매기는 공마다 (행, 기대 득점 변화+득점)을 냅니다(타자 쪽 부호)."""
    for h in halves:
        for i, r in enumerate(h):
            # 투수 ID 가 빈 공(2019 등 원천 누락)은 누구 몫인지 몰라 뺍니다.
            # 기대 득점 표에는 그대로 씁니다.
            if not is_pitch(r) or not has_type(r) or r.get("pitcher_ID") is None:
                continue
            nxt = h[i + 1] if i + 1 < len(h) else None
            after = re.get(state_of(nxt), 0.0) if nxt is not None else 0.0
            yield r, after - re[state_of(r)] + int(r.get("runs_scored") or 0)


def pitch_values(halves, re):
    out = {}
    for r, delta in pitch_deltas(halves, re):
        key = (r["pitcher_ID"], r["pitch_type"], bat_side(r.get("stands"), r.get("throws")))
        acc = out.setdefault(key, [0, 0.0])
        acc[0] += 1
        acc[1] -= delta
    return out


def zone_values(halves, re):
    """투수 x 공격 존 가치입니다. pitch_values 와 같은 공·같은 값이고, 위치 없는 공은 뺍니다."""
    out = {}
    for r, delta in pitch_deltas(halves, re):
        z = zone_of(r)
        if z is None:
            continue
        acc = out.setdefault((r["pitcher_ID"], z), [0, 0.0])
        acc[0] += 1
        acc[1] -= delta
    return out


# 리그 선구(Plate Discipline) 합계입니다(2026-10-06, /stats/plate_discipline).
# src/routes/pitchTrend.js 의 같은 이름 키와 똑같이 셉니다. 정규시즌은 읽는 질의가
# 이미 거릅니다. n 은 구종 있는 공 전부(결과 무관), 나머지는 선구 집계 공만입니다.
SWING = {"타격", "파울", "헛스윙", "번트파울", "번트헛스윙"}
WHIFF = {"헛스윙", "번트헛스윙"}
CONTACT = {"타격", "파울", "번트파울"}
LOOK = {"스트라이크"}
BALL = {"볼"}
DISCIPLINE = SWING | LOOK | BALL
DISCIPLINE_KEYS = ("n", "pd_n", "sw", "wh", "ct", "cs", "z_n", "o_n", "z_sw", "o_sw",
                   "z_ct", "o_ct", "edge_n", "fp_n", "fp_str", "mb_n", "mb_sw")


def _box(r):
    top, bot = r.get("sz_top"), r.get("sz_bot")
    if top is None or bot is None or not top > bot:
        return 3.5, 1.5
    return top, bot


def discipline_counts(rows):
    d = dict.fromkeys(DISCIPLINE_KEYS, 0)
    for r in rows:
        if not has_type(r):
            continue
        d["n"] += 1
        res = r.get("pitch_result")
        if res not in DISCIPLINE:
            continue
        sw, ct = res in SWING, res in CONTACT
        d["pd_n"] += 1
        d["sw"] += sw
        d["wh"] += res in WHIFF
        d["ct"] += ct
        d["cs"] += res in LOOK
        if r.get("balls") == 0 and r.get("strikes") == 0:
            d["fp_n"] += 1
            d["fp_str"] += res not in BALL
        px, pz = r.get("px"), r.get("pz")
        if px is None or pz is None:
            continue
        top, bot = _box(r)
        inside = abs(px) <= HALF_W and bot <= pz <= top
        side = "z" if inside else "o"
        d[side + "_n"] += 1
        d[side + "_sw"] += sw
        d[side + "_ct"] += ct
        rr = max(abs(px) / HALF_W, abs(pz - (top + bot) / 2) / ((top - bot) / 2))
        d["edge_n"] += 0.67 <= rr < 1.33
        h = top - bot
        if abs(px) <= HALF_W / 3 and bot + h / 3 <= pz <= top - h / 3:
            d["mb_n"] += 1
            d["mb_sw"] += sw
    return d
