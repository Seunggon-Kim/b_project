# -*- coding: utf-8 -*-
"""네이버 박스스코어(naver_boxscore.py 가 받은 파일)로 공식 기록 칸을 셉니다.

박스스코어는 경기마다 빠짐이 없습니다. PBP(문자중계)는 2008~2011·2013 에
중계가 끊긴 경기가 있어 그 선수들의 개수가 모자랍니다(계획서 조사 결과 3,
docs/naver-migration/pbp-columns-verify.md). 그래서 경기 단위로 셀 수 있는
칸은 박스스코어로 셉니다.

## 타자: 이닝 칸의 기록 약어

battersBoxscore 의 inn1~inn25 는 KBO 기록지 약어입니다. 한 칸에 두 타석이면
'/' 로 나뉩니다. 앞 글자는 수비 위치(투·포·1·2·3·유·좌·중·우), 뒤가 결과입니다.

    삼진·스낫(낫아웃)  4구  고4(고의4구)  사구  타방(타격방해)
    …안·…2·…3·…홈(안타)  …땅(땅볼)  …병(병살)  …비(뜬공)  …직(직선)
    …파(파울 뜬공)  …번(번트 아웃)  …희번·…희실·…희선(희생번트)  …희비(희생플라이)
    …실(실책 출루)  야선(야수선택)

## 투수: 나온 순서와 투구 수

pitchersBoxscore 는 팀마다 나온 순서대로이고 `pa`(상대 타자), `bf`(투구 수)가
있습니다. 첫 투수가 선발, 마지막 투수가 경기를 마친 투수(완투 포함)입니다.

## etcRecords: 이름으로만 나오는 기록

결승타·폭투·보크는 '이름(회)' 목록입니다. 그 경기 박스의 같은 이름 선수 ID 로
잇습니다. 한 팀 안에 같은 이름이 둘이면 잇지 않고 세지 않습니다(unmatched).
"""
import collections
import gzip
import json
import re
from pathlib import Path

POSITIONS = ("투", "포", "1", "2", "3", "유", "좌", "중", "우")
INFIELD = ("투", "포", "1", "2", "3", "유")
NAME_RE = re.compile(r"([^\s(]+?)(\d+)?\(")


def kind(code):
    """기록 약어 하나를 결과 종류로. 모르는 약어는 '?'."""
    c = code.strip()
    if c in ("삼진", "스낫"):
        return "so"
    if c == "4구":
        return "bb"
    if c == "고4":
        return "ibb"
    if c == "사구":
        return "hbp"
    if c == "타방":
        return "ci"
    if c == "야선":
        return "fc"
    if "희비" in c:
        return "sf"
    if "희번" in c or "희실" in c or "희선" in c:
        # 외야수가 받은 '희번'은 2008 기록지의 뜬공(주자 진루)입니다. KBO 는 희생번트로
        # 세지 않습니다(2008 대조: 우희번=우익수 플라이 아웃).
        # 외야 '희실'은 희생플라이 실책이라 희생플라이로 셉니다(2008 이현곤).
        if c[0] in ("좌", "중", "우"):
            return "fly" if "희번" in c else "sf"
        return "sh"
    if c.endswith("홈"):
        return "hr"
    if c.endswith("안"):
        return "h1"
    if c.endswith("병"):
        return "gidp"
    if c.endswith("땅"):
        return "go"
    if c.endswith("번"):
        return "bunt_out"
    if c.endswith("비"):
        return "fly"
    if c.endswith("직"):
        return "liner"
    if c.endswith("파"):
        return "foul_fly"
    if c.endswith("실"):
        return "err_if" if c[0] in INFIELD else "err_of"
    if c.endswith("2"):
        return "h2"
    if c.endswith("3"):
        return "h3"
    return "?"


NOT_AB = {"bb", "ibb", "hbp", "sh", "sf", "ci"}
HITS = {"h1", "h2", "h3", "hr"}


def load(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def codes(b):
    out = []
    for i in range(1, 26):
        v = b.get("inn%d" % i) or ""
        out.extend(p for p in v.split("/") if p.strip())
    return out


def batted_ball(t):
    """박스 약어만으로 정한 땅볼('go')·뜬공('ao') 구분. 실책은 타구 종류가 약어에
    없어 내야 실책=땅볼, 외야 실책=뜬공으로 봅니다(PBP 가 있으면 그쪽을 씁니다)."""
    if t in ("go", "gidp", "bunt_out", "fc", "err_if"):
        return "go"
    if t in ("fly", "liner", "foul_fly", "sf", "err_of"):
        return "ao"
    return None


def batter_game(b, pbp_pas=None):
    """한 경기 타자 한 줄 → Counter.

    pbp_pas 는 같은 경기 같은 타자의 PBP 타석 끝 행들입니다. 타석 수가 박스와 같으면
    땅볼·뜬공을 PBP 문장으로 정합니다(내야 뜬공 실책·외야 앞 땅볼 실책을 가립니다).
    """
    from pbp_season_stats import is_fly, is_ground
    k = collections.Counter()
    cs = codes(b)
    aligned = pbp_pas is not None and len(pbp_pas) == len(cs)
    for i, c in enumerate(cs):
        t = kind(c)
        k["pa"] += 1
        k[t] += 1
        k["ab"] += t not in NOT_AB
        if aligned:
            x = pbp_pas[i]
            bb = "go" if is_ground(x) else ("ao" if is_fly(x) and x.get("pa_result") not in
                                            ("안타", "내야안타", "번트 안타", "2루타", "3루타", "홈런") else None)
        else:
            bb = batted_ball(t)
            # 실책 출루는 약어에 타구 종류가 없어 내야=땅볼·외야=뜬공은 짐작입니다.
            k["bb_guess"] += t in ("err_if", "err_of")
        if bb:
            k[bb.upper()] += 1  # GO·AO (약어 종류 go 와 겹치지 않게 대문자)
    k["hit"] = b.get("hit") or 0
    k["box_ab"] = b.get("ab") or 0
    k["multi"] = 1 if (b.get("hit") or 0) >= 2 else 0
    k["games"] = 1
    return k


def names_by_side(box):
    """{'away': {이름: [ID...]}, 'home': ...} 타자·투수 모두."""
    out = {}
    for side in ("away", "home"):
        m = collections.defaultdict(set)
        for b in (box.get("battersBoxscore") or {}).get(side) or []:
            m[b.get("name")].add(int(b["playerCode"]))
        for p in (box.get("pitchersBoxscore") or {}).get(side) or []:
            m[p.get("name")].add(int(p["pcode"]))
        out[side] = m
    return out


def etc_names(box, how):
    """etcRecords 의 how 줄에서 이름 목록(횟수만큼 되풀이).

    '배영수(5회) 오승환(9회)', 한 경기 두 번이면 '이범석2(3 5회)' 처럼 이름 뒤에
    횟수가 붙습니다.
    """
    out = []
    for e in box.get("etcRecords") or []:
        if e.get("how") != how:
            continue
        text = e.get("result") or ""
        if how == "결승타":
            m = re.match(r"\s*([^\s(]+)\(", text)
            if m:
                out.append(m.group(1))
            continue
        for name, n in NAME_RE.findall(text):
            out.extend([name] * (int(n) if n else 1))
    return out


def resolve(name, sides, prefer=None):
    """이름을 ID 로. prefer 쪽 먼저, 양쪽에 하나뿐일 때만."""
    cands = set()
    for side in ([prefer] if prefer else []) + ["away", "home"]:
        ids = sides.get(side, {}).get(name) or set()
        if len(ids) == 1 and prefer == side:
            return next(iter(ids))
        cands |= ids
    return next(iter(cands)) if len(cands) == 1 else None


def season(files, pbp_by_game_batter=None):
    """박스 파일들 → (타자 {id: Counter}, 투수 {id: Counter}, 못 이은 이름 수).

    pbp_by_game_batter: {(gameID, 타자 ID): [PBP 타석 끝 행...]} (없으면 박스만).
    """
    pbg = pbp_by_game_batter or {}
    bat = collections.defaultdict(collections.Counter)
    pit = collections.defaultdict(collections.Counter)
    unmatched = collections.Counter()
    for f in files:
        box = load(f)
        sides = names_by_side(box)
        # 승리 투수는 pitchingResult 에 있습니다(pitchersBoxscore 의 wls 는 비어 있는 해가 있음).
        winners = {int(x["pCode"]) for x in box.get("pitchingResult") or [] if x.get("wls") == "W"}
        for side in ("away", "home"):
            gid = Path(f).name.split(".")[0]
            for b in (box.get("battersBoxscore") or {}).get(side) or []:
                pid = int(b["playerCode"])
                bat[pid].update(batter_game(b, pbg.get((gid, pid))))
            seq = (box.get("pitchersBoxscore") or {}).get(side) or []
            for i, p in enumerate(seq):
                k = pit[int(p["pcode"])]
                k["games"] += 1
                k["tbf"] += p.get("pa") or 0
                k["np"] += p.get("bf") or 0
                k["gs"] += i == 0
                k["gf"] += i == len(seq) - 1
                if len(seq) == 1:
                    k["cg"] += 1
                    k["sho"] += (p.get("r") or 0) == 0
                if int(p["pcode"]) in winners:
                    k["w_start" if i == 0 else "w_relief"] += 1
        for name in etc_names(box, "결승타"):
            pid = resolve(name, sides)
            if pid:
                bat[pid]["gw"] += 1
            else:
                unmatched["결승타"] += 1
        for how, key in (("폭투", "wp"), ("보크", "bk")):
            for name in etc_names(box, how):
                pid = resolve(name, sides)
                if pid:
                    pit[pid][key] += 1
                else:
                    unmatched[how] += 1
    return bat, pit, unmatched


def season_files(root, year):
    return sorted((Path(root) / str(year)).glob("*.json.gz"))


FRACTION = {"⅓": 1, "⅔": 2}


def inn_outs(text):
    """박스 이닝 글자 → 아웃 수. '4 ⅓' → 13, '0 ⅔' → 2, '6' → 18."""
    outs = 0
    for part in str(text or "").split():
        if part in FRACTION:
            outs += FRACTION[part]
        elif part.isdigit():
            outs += int(part) * 3
    return outs


WLS = {"W": "w", "L": "l", "S": "sv", "H": "hld", "승": "w", "패": "l", "세": "sv", "홀": "hld"}


def pitcher_lines(files, only=None):
    """박스 투수 줄을 선수별로 더합니다(only 가 있으면 그 ID 들만).

    네이버 시즌 기록 API 가 통째로 빼 둔 투수(2013~2021, 10명 27행)의 시즌 기록을
    박스에서 다시 만들 때 씁니다. 경기마다 승·패·세이브·홀드는 pitchingResult 를,
    없으면 투수 줄의 wls 를 봅니다. (합계 {ID: Counter}, 마지막 이름 {ID: 이름},
    마지막 팀 코드 {ID: 'NC'}).
    """
    out = collections.defaultdict(collections.Counter)
    names = {}
    teams = {}
    for f in files:
        box = load(f)
        result = {int(x["pCode"]): x.get("wls") for x in box.get("pitchingResult") or []}
        info = box.get("gameInfo") or {}
        for side in ("away", "home"):
            code = info.get("aCode" if side == "away" else "hCode")
            seq = (box.get("pitchersBoxscore") or {}).get(side) or []
            for i, p in enumerate(seq):
                pid = int(p["pcode"])
                if only is not None and pid not in only:
                    continue
                k = out[pid]
                k["games"] += 1
                k["outs"] += inn_outs(p.get("inn"))
                for key, src in (("h", "hit"), ("hr", "hr"), ("bb", "bb"), ("so", "kk"),
                                 ("r", "r"), ("er", "er"), ("tbf", "pa"), ("np", "bf")):
                    k[key] += p.get(src) or 0
                k["hbp"] += (p.get("bbhp") or 0) - (p.get("bb") or 0)
                w = WLS.get(result.get(pid) or p.get("wls") or "")
                if w:
                    k[w] += 1
                if i == 0:
                    k["gs"] += 1
                    k["qs"] += inn_outs(p.get("inn")) >= 18 and (p.get("er") or 0) <= 3
                k["gf"] += i == len(seq) - 1
                if len(seq) == 1:
                    k["cg"] += 1
                    k["sho"] += (p.get("r") or 0) == 0
                names[pid] = p.get("name")
                teams[pid] = code
    return out, names, teams
