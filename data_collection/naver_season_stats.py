# -*- coding: utf-8 -*-
"""공식 시즌 기록 가운데 네이버 시즌 API 가 주는 칸을 만듭니다.

KBO 이용약관 제14조 차항(2026-10-14 시행)으로 KBO 기록실(official_stats_http.py)을
더 읽지 않습니다. kbo_official_batter_stats·kbo_official_pitcher_stats 를
세 원천으로 채웁니다. 이 모듈은 그 첫째입니다.

    1. 네이버 시즌 기록 API (이 모듈)
    2. 이미 가진 play_by_play(네이버 문자중계)로 계산 (pbp_season_stats.py)
    3. 네이버 박스스코어 (naver_boxscore.py, 결승타·선발승·구원승)

## 받는 법

    GET /statistics/categories/kbo/seasons/{y}/players
        ?playerType=HITTER|PITCHER&pageSize=400&teamCode={팀}

- 2008~ 만 있습니다. 2007 이전은 400 입니다.
- 한 번에 400명까지이고 page 는 무시됩니다. 그래서 팀별로 받습니다.
- 트레이드 선수는 두 팀 목록에 다 나올 수 있습니다(2025). 새 팀 행이 시즌
  합계입니다. **선수마다 경기 수가 가장 큰 행**을 씁니다. 2008~2026 을 지금
  DB 와 대조해 이 규칙이 맞았습니다(계획서 조사 결과 2).

## 반올림

KBO 표기처럼 반을 올립니다(0.3125 → 0.313). 파이썬 round 는 짝수 쪽으로
보내 0.312 가 됩니다. 비율은 Decimal ROUND_HALF_UP 으로 맞춥니다.

## 이닝

네이버는 '149 1/3', 1이닝 미만은 '0 1/3' 입니다. DB(KBO 표기)는 '1/3' 입니다.
"""
import json
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

import naver_http  # noqa: E402

FIRST_SEASON = 2008
KINDS = ("HITTER", "PITCHER")


def r(v, places):
    """반올림(반 올림). None·빈 값은 None."""
    if v is None or v == "":
        return None
    q = Decimal(1).scaleb(-places)
    return float(Decimal(str(v)).quantize(q, ROUND_HALF_UP))


def fmt2(v):
    """k_bb·go_ao 처럼 글자로 두는 칸('2.61')."""
    if v is None:
        return None
    return str(Decimal(str(v)).quantize(Decimal("0.01"), ROUND_HALF_UP))


def ip_text(s):
    """'0 1/3' → '1/3', '172' → '172', None → None."""
    if s is None:
        return None
    s = str(s).strip()
    return s[2:] if s.startswith("0 ") else s


def ip_outs(s):
    """이닝 글자를 아웃 수로. '149 1/3' → 448, '1/3' → 1."""
    if not s:
        return 0
    whole, frac = 0, 0
    for part in str(s).split():
        if "/" in part:
            a, b = part.split("/")
            frac = int(a) * 3 // int(b)
        else:
            whole = int(part)
    return whole * 3 + frac


def teams_of(season, cl=None):
    cl = cl or naver_http.client()
    d = cl.get("/statistics/categories/kbo/seasons/%d/teams" % season)
    return [t["teamId"] for t in ((d.get("result") or {}).get("seasonTeamStats") or [])]


def fetch_season(season, cl=None, cache=None):
    """{'HITTER': [...], 'PITCHER': [...]} 팀별로 받은 선수 행 전부(중복 포함).

    cache 폴더에 <season>.json 이 있으면 그것을 읽습니다(byteam 모양, 조사 때
    받은 원자료와 같음). 없으면 받아서 거기 씁니다.
    """
    if cache:
        p = Path(cache) / ("%d.json" % season)
        if p.exists():
            raw = json.loads(p.read_text(encoding="utf-8"))
            return {k: [x for t in raw["byteam"][k].values()
                        for x in ((t.get("result") or {}).get("seasonPlayerStats") or [])]
                    for k in KINDS}
    cl = cl or naver_http.client()
    byteam = {}
    for kind in KINDS:
        for tm in teams_of(season, cl):
            byteam.setdefault(kind, {})[tm] = cl.get(
                "/statistics/categories/kbo/seasons/%d/players" % season,
                {"playerType": kind, "pageSize": 400, "teamCode": tm})
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
        (Path(cache) / ("%d.json" % season)).write_text(
            json.dumps({"byteam": byteam}, ensure_ascii=False), encoding="utf-8")
    return {k: [x for t in byteam[k].values()
                for x in ((t.get("result") or {}).get("seasonPlayerStats") or [])]
            for k in KINDS}


def pick(rows, games_key):
    """선수마다 경기 수가 가장 큰 행(트레이드 선수는 새 팀 행이 시즌 합계)."""
    best = {}
    for x in rows:
        pid = int(x["playerId"])
        g = x.get(games_key) or 0
        if pid not in best or g > (best[pid].get(games_key) or 0):
            best[pid] = x
    return best


def team_name(x, season, names):
    return names.get((x.get("teamId"), int(season))) or x.get("teamShortName") or x.get("teamName")


def batter_row(x, season, names):
    h, d2, d3, hr = (x.get(k) or 0 for k in ("hitterHit", "hitterH2", "hitterH3", "hitterHr"))
    ab = x.get("hitterAb") or 0
    # 출루율 분모(타수+볼넷+사구+희플)가 0 이면 KBO 는 비웁니다. 희플은 PBP 에서
    # 오므로 여기서는 희플을 뺀 분모로 먼저 거르고, pbp_season_stats.finish 가
    # 희플까지 보고 다시 맞춥니다.
    on_den = ab + (x.get("hitterBb") or 0) + (x.get("hitterHp") or 0)
    obp = r(x.get("hitterObp"), 3) if on_den else None
    avg = r(x.get("hitterHra"), 3) if ab else None
    slg = r(x.get("hitterSlg"), 3) if ab else None
    return {
        "player_id": int(x["playerId"]),
        "season": int(season),
        "player_name": x.get("playerName"),
        "player_team": team_name(x, season, names),
        "games": x.get("hitterGameCount"),
        "at_bat": x.get("hitterAb"),
        "run": x.get("hitterRun"),
        "single": x.get("hitterHit"),  # 칸 이름은 single 이지만 KBO 의 H(안타 전체)입니다
        "double": x.get("hitterH2"),
        "triple": x.get("hitterH3"),
        "home_run": x.get("hitterHr"),
        "run_batted_in": x.get("hitterRbi"),
        "base_on_balls": x.get("hitterBb"),
        "hit_by_pitch": x.get("hitterHp"),
        "strikeout": x.get("hitterKk"),
        "batting_average": avg,
        "on_base_percentage": obp,
        "slugging_percentage": slg,
        # KBO 는 타수 0 이어도 출루율만 있으면 OPS 를 냅니다(장타율을 0 으로).
        "on_base_plus_slugging": ops(obp, slg),
        # 순수장타율 = (루타 - 안타) / 타수 를 반 올림(2008~ 5,000행 모두 같음).
        "isop": r(Decimal(d2 + 2 * d3 + 3 * hr) / ab, 3) if ab else None,
        "total_bases": h + d2 + 2 * d3 + 3 * hr,
        "extra_base_hits": d2 + d3 + hr,
    }


def ops(obp, slg):
    if obp is None and slg is None:
        return None
    return r((obp or 0) + (slg or 0), 3)


def per9(n, outs):
    return r(Decimal(n or 0) * 27 / outs, 2) if outs else None


def pitcher_row(x, season, names):
    """이닝 0 이면 ERA·WHIP·K/9·BB/9 를, 볼넷 0 이면 K/BB 를 비웁니다(KBO 와 같음).

    비율은 네이버 값을 쓰지 않고 개수에서 다시 셉니다. 네이버 WHIP·K/9 는 소수
    둘째 자리에서 버린 값이라 43행이 0.01 씩 낮았습니다.
    """
    w, l = x.get("pitcherWin") or 0, x.get("pitcherLose") or 0
    outs = ip_outs(ip_text(x.get("pitcherInning")))
    bb, k = x.get("pitcherBb") or 0, x.get("pitcherKk") or 0
    return {
        "player_id": int(x["playerId"]),
        "season": int(season),
        "player_name": x.get("playerName"),
        "player_team": team_name(x, season, names),
        "earned_run_average": per9(x.get("pitcherEr"), outs),
        "games": x.get("pitcherGameCount"),
        "wins": x.get("pitcherWin"),
        "losses": x.get("pitcherLose"),
        "save": x.get("pitcherSave"),
        "hold": x.get("pitcherHold"),
        "winning_percentage": r(w / (w + l), 3) if (w + l) else None,
        "innings_pitched": ip_text(x.get("pitcherInning")),
        "hits": x.get("pitcherHit"),
        "home_run": x.get("pitcherHr"),
        "base_on_balls": x.get("pitcherBb"),
        "hit_by_pitch": x.get("pitcherHp"),
        "strikeout": x.get("pitcherKk"),
        "run": x.get("pitcherR"),
        "earned_run": x.get("pitcherEr"),
        "walks_plus_hits_per_inning_pitched":
            r(Decimal((x.get("pitcherHit") or 0) + bb) * 3 / outs, 2) if outs else None,
        "quality_start": x.get("pitcherQs"),
        "k_9": per9(k, outs),
        "bb_9": per9(bb, outs),
        "k_bb": fmt2(Decimal(k) / bb) if bb else None,
    }


def season_rows(season, names, cl=None, cache=None):
    """(타자 {player_id: 행}, 투수 {player_id: 행}) 네이버 칸만."""
    got = fetch_season(season, cl, cache)
    bat = {pid: batter_row(x, season, names) for pid, x in pick(got["HITTER"], "hitterGameCount").items()}
    pit = {pid: pitcher_row(x, season, names) for pid, x in pick(got["PITCHER"], "pitcherGameCount").items()}
    return bat, pit
