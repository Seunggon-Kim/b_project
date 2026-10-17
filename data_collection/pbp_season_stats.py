# -*- coding: utf-8 -*-
"""공식 시즌 기록 가운데 네이버 시즌 API 에 없는 칸을 play_by_play 로 셉니다.

KBO 이용약관(2026-10-14 시행)으로 KBO 기록실을 못 읽게 되어, 타석·희생타·
고의4구·병살타·선발·완투·투구 수 같은 칸을 이미 가진 PBP(네이버 문자중계)로
계산합니다. 계획서 docs/superpowers/plans/2026-10-18-naver-official-stats.md
조사 결과 3.

칸마다 2008~2026 의 지금 DB 값(10/14 전에 KBO 에서 받은 값)과 맞춰 보고
**99% 이상 같은 칸만** 씁니다(VERIFIED). 못 미치는 칸은 None 으로 두고 화면에서
숨깁니다(evan 결정 3). 검증 결과는 docs/naver-migration/pbp-columns-verify.md.

## PBP 모양

투구 한 개가 한 행입니다. 타석이 끝난 투구에 pa_result(결과)가 있습니다. 투구가
아닌 일(교체·폭투·보크·도루)은 pitch_number 가 빈 행에 description 으로만
있습니다. inning_topbot '초' 는 원정 공격(홈 투수), '말' 은 홈 공격입니다.

## 정규시즌만

공식 기록은 정규시즌 값입니다. 부르는 쪽이 정규시즌 경기 ID 집합을 줍니다
(games.game_type = '정규시즌').
"""
import collections
import re
from decimal import ROUND_HALF_UP, Decimal

HITS = {"안타": 1, "내야안타": 1, "번트 안타": 1, "2루타": 2, "3루타": 3, "홈런": 4}
BB = {"볼넷"}
IBB = {"자동 고의4구", "고의4구"}
HBP = {"몸에 맞는 볼"}
SH = {"희생번트", "희생번트 실책", "희생번트 야수선택"}
SF = {"희생플라이", "희생플라이 실책"}
INTERFERENCE = {"타격방해"}
GIDP = {"병살타"}
# 타수가 아닌 타석 결과(나머지는 모두 타수입니다).
NOT_AB = BB | IBB | HBP | SH | SF | INTERFERENCE

PH_RE = re.compile(r"대타\s*(\S+)\s*\(으\)로 교체")
INFIELD = ("투수", "포수", "1루수", "2루수", "3루수", "유격수")
# 던지지 않은 투구 행입니다. 자동 고의4구는 '고의 볼' 4행으로 적히고, 피치클락
# 위반은 투구 없이 볼·스트라이크가 됩니다. 투구 수·P/PA 에서 뺍니다.
NOT_THROWN_PREFIX = ("피치클락",)


def batter_clause(row):
    """description 의 첫 마디(타자 몫). '문보경 : 1루수 땅볼 실책으로 출루 (…)'."""
    return (row.get("description") or "").split(";")[0]


def is_fly(row):
    t = batter_clause(row)
    return "플라이" in t or "라인드라이브" in t


def is_ground(row):
    """땅볼 타구(KBO 땅볼 칸). 2025·2015 대조로 정한 규칙입니다.

    설명에 '땅볼'·'병살' 이 있거나, 번트 아웃(희생번트 제외), 야수선택, 뜬공이
    아닌 내야수 실책입니다. 내야안타·번트안타·희생번트는 넣지 않습니다.
    """
    t = batter_clause(row)
    if "땅볼" in t or "병살" in t:
        return True
    res, det = row.get("pa_result"), row.get("pa_result_detail")
    if det == "번트 아웃" or res == "야수 선택":
        return True
    if res == "실책" and not is_fly(row):
        return t.split(":")[-1].strip().startswith(INFIELD)
    return False


def thrown(row, ibb_pas):
    """실제로 던진 투구인가."""
    if not is_pitch(row):
        return False
    pr = row.get("pitch_result") or ""
    if pr.startswith(NOT_THROWN_PREFIX):
        return False
    if pr == "고의 볼" and (row["gameID"], row["pa_number"]) in ibb_pas:
        return False
    return True


def auto_ibb_pas(rows):
    return {(x["gameID"], x["pa_number"]) for x in rows if x.get("pa_result") == "자동 고의4구"}


def r(v, places):
    if v is None:
        return None
    return float(Decimal(str(v)).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP))


def fmt2(v):
    return None if v is None else str(Decimal(str(v)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def pitching_side(row):
    """그 투구에서 수비(투수) 팀: 초=홈, 말=원정."""
    return "home" if row.get("inning_topbot") == "초" else "away"


def is_pitch(row):
    return row.get("pitch_number") not in (None, "")


def plate_appearances(rows):
    """타석 끝 행들(한 경기·한 타석 번호에 하나). 행 순서는 그대로 둡니다."""
    out, seen = [], set()
    for x in rows:
        res = x.get("pa_result")
        if not res:
            continue
        key = (x["gameID"], x["pa_number"])
        if key in seen:
            continue
        seen.add(key)
        out.append(x)
    return out


def pas_by_game_batter(rows):
    """{(경기, 타자 ID): [타석 끝 행 ...]} 순서대로."""
    out = collections.defaultdict(list)
    for x in plate_appearances(rows):
        if x.get("batter_ID"):
            out[(x["gameID"], int(x["batter_ID"]))].append(x)
    return out


def pinch_hit_pas(rows):
    """대타로 나온 첫 타석들의 (경기, 타석 번호) 집합.

    교체 행 `대타 X (으)로 교체` 다음에 X 가 처음 치는 타석입니다. 이름으로만
    나오므로 그 경기에서 그 뒤 처음 나오는 같은 이름 타자의 타석으로 잇습니다.
    """
    want = collections.defaultdict(list)  # gameID → [이름 ...] (아직 못 이은 대타)
    out = set()
    for x in rows:
        g = x["gameID"]
        d = x.get("description") or ""
        if not is_pitch(x) and "대타" in d:
            for name in PH_RE.findall(d):
                want[g].append(name)
            continue
        if x.get("pa_result") and want[g]:
            nm = x.get("batter")
            if nm in want[g]:
                want[g].remove(nm)
                out.add((g, x["pa_number"]))
    return out


def team_pitchers(rows):
    """(경기, 수비 쪽) → 나온 투수 ID 순서(중복 없이)."""
    seq = collections.defaultdict(list)
    for x in rows:
        if not is_pitch(x) or not x.get("pitcher_ID"):
            continue
        k = (x["gameID"], pitching_side(x))
        pid = int(x["pitcher_ID"])
        if pid not in seq[k]:
            seq[k].append(pid)
    return seq


def count_events(rows, words):
    """description 에 words 가운데 하나가 있는 행 수를 그때 투수에게 줍니다.

    폭투는 투구 아닌 행(`1루주자 X : 폭투로 2루까지 진루`)에도, 타석이 끝난 투구
    행(`볼넷; 3루주자 Y : 폭투로 홈인`, `스트라이크 낫아웃 폭투`)에도 적힙니다. 한
    행에 주자 여러 명이 같이 움직여도 한 번입니다. 행에 투수 ID 가 없으면 그 경기·
    그 수비 쪽의 바로 앞 투구 투수에게 줍니다.

    `폭투사이 진루실패아웃`(주자가 폭투 때 뛰다 잡힘)은 KBO 가 폭투로 세지 않아
    부르는 쪽이 '폭투로'·'낫아웃 폭투' 만 넘깁니다(2025 대조로 확인).
    """
    out = collections.Counter()
    last = {}
    for x in rows:
        side = (x["gameID"], pitching_side(x))
        if is_pitch(x) and x.get("pitcher_ID"):
            last[side] = int(x["pitcher_ID"])
        d = x.get("description") or ""
        if any(w in d for w in words):
            pid = x.get("pitcher_ID") or last.get(side)
            if pid:
                out[int(pid)] += 1
    return out


def batter_counts(rows):
    """타자별 PBP 개수와 비율 재료."""
    pas = plate_appearances(rows)
    ph = pinch_hit_pas(rows)
    c = collections.defaultdict(collections.Counter)
    game_hits = collections.defaultdict(collections.Counter)
    pitches = collections.Counter()
    ibb_pas = auto_ibb_pas(rows)
    for x in rows:
        if thrown(x, ibb_pas) and x.get("batter_ID"):
            pitches[int(x["batter_ID"])] += 1
    for x in pas:
        if not x.get("batter_ID"):
            continue
        b = int(x["batter_ID"])
        res = x["pa_result"]
        k = c[b]
        k["pa"] += 1
        ab = res not in NOT_AB
        hit = res in HITS
        k["ab"] += ab
        k["h"] += hit
        k["sh"] += res in SH
        k["sf"] += res in SF
        k["ibb"] += res in IBB
        k["gidp"] += res in GIDP
        k["go"] += is_ground(x)
        k["ao"] += is_fly(x) and not hit
        if hit:
            game_hits[b][x["gameID"]] += 1
        # 득점권은 타석이 끝난 투구 때 주자입니다(첫 투구 때로 보면 2025 에 119/276,
        # 끝날 때로 보면 276/276 이 KBO 값과 같았습니다).
        if x.get("on_2b_id") or x.get("on_3b_id") or x.get("on_2b") or x.get("on_3b"):
            k["risp_ab"] += ab
            k["risp_h"] += hit
        if (x["gameID"], x["pa_number"]) in ph:
            k["ph_ab"] += ab
            k["ph_h"] += hit
            k["ph_pa"] += 1
    for b, gh in game_hits.items():
        c[b]["multi"] = sum(1 for n in gh.values() if n >= 2)
    for b, n in pitches.items():
        c[b]["pitches"] = n
    return c


def pitcher_counts(rows, final_scores):
    """투수별 PBP 개수. final_scores: {gameID: (원정 점수, 홈 점수)}."""
    pas = plate_appearances(rows)
    c = collections.defaultdict(collections.Counter)
    ibb_pas = auto_ibb_pas(rows)
    for x in rows:
        if thrown(x, ibb_pas) and x.get("pitcher_ID"):
            c[int(x["pitcher_ID"])]["np"] += 1
    for x in pas:
        if not x.get("pitcher_ID"):
            continue
        p = int(x["pitcher_ID"])
        res = x["pa_result"]
        k = c[p]
        k["tbf"] += 1
        ab = res not in NOT_AB
        k["ab"] += ab
        k["h"] += res in HITS
        k["d2"] += res == "2루타"
        k["d3"] += res == "3루타"
        k["hr"] += res == "홈런"
        k["tb"] += HITS.get(res, 0)
        k["bb"] += res in BB
        k["ibb"] += res in IBB
        k["hbp"] += res in HBP
        k["sh"] += res in SH
        k["sf"] += res in SF
        k["so"] += res in ("삼진", "낫아웃 출루")
        k["gidp"] += res in GIDP
        k["go"] += is_ground(x)
        k["ao"] += is_fly(x) and res not in HITS
    for (g, side), seq in team_pitchers(rows).items():
        c[seq[0]]["gs"] += 1
        c[seq[-1]]["gf"] += 1  # 완투도 경기를 마친 투수입니다(KBO 와 같음)
        if len(seq) == 1:
            c[seq[0]]["cg"] += 1
            sc = final_scores.get(g)
            if sc is not None:
                allowed = sc[0] if side == "home" else sc[1]
                c[seq[0]]["sho"] += allowed == 0
    for p, n in count_events(rows, ("폭투로", "낫아웃 폭투")).items():
        c[p]["wp"] += n
    for p, n in count_events(rows, ("보크",)).items():
        c[p]["bk"] += n
    return c
