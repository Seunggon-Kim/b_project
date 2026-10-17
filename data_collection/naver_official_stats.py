# -*- coding: utf-8 -*-
"""공식 시즌 기록(kbo_official_batter_stats·kbo_official_pitcher_stats)을 네이버
값으로 만들어 Cloud SQL(MySQL)에 넣습니다.

KBO 이용약관 제14조 차항(2026-10-14 시행)으로 KBO 기록실(official_stats_http.py)을
더 읽지 않습니다. 세 원천을 합칩니다(계획서
docs/superpowers/plans/2026-10-18-naver-official-stats.md).

    1. 네이버 시즌 기록 API   naver_season_stats.py  타율·홈런·ERA 같은 기본 칸
    2. 네이버 박스스코어       naver_box_stats.py     타석·희생타·고의4구·병살·
                                                       선발·완투·투구 수·폭투·보크·결승타
    3. play_by_play(네이버)   pbp_season_stats.py    득점권·대타 타율, 투수의 피안타율·
                                                       땅볼/뜬공 같은 타석 단위 칸

## 검증한 칸만 씁니다

칸마다 2008~2026 의 지금 DB 값(10/14 전에 KBO 에서 받은 값)과 맞춰 보고(migration/
naver_verify.py) 시즌마다 99% 이상 같은 (칸, 시즌)만 씁니다. 결과는
database/naver_verified.json 이고 표는 docs/naver-migration/official-verify.md 입니다.
못 미치는 칸·시즌은 None 으로 두고 화면에서 숨깁니다(evan 결정 3). 검증한 마지막
시즌보다 뒤(새 시즌)는 그 마지막 시즌이 통과한 칸만 씁니다. 네이버 시즌 API 가 바로
주는 기본 칸(BASE_COLUMNS)은 늘 씁니다.

PBP 로 세는 칸은 그 선수 시즌의 PBP 가 온전할 때만 씁니다. 중계가 끊긴 경기가
있으면(2008~2011·2013 에 많음) 개수가 모자라 틀린 값이 되기 때문입니다. 온전함은
PBP 로 센 타수·안타(타자), 상대 타자·안타·삼진(투수)이 네이버·박스와 같은지로
봅니다.

    py data_collection/naver_official_stats.py --season 2025 --dry-run
    py data_collection/naver_official_stats.py --current            # daily
"""
import argparse
import collections
import os
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))
sys.path.insert(0, str(ROOT))

import naver_box_stats as nbx  # noqa: E402
import naver_season_stats as nss  # noqa: E402
import pbp_season_stats as pss  # noqa: E402

FIRST_SEASON = 2008
DEFAULT_BOX_DIR = Path(os.path.expanduser("~")) / ".bstats" / "naver_boxscore"

VERIFIED_PATH = ROOT / "database" / "naver_verified.json"
_verified = None


def verified():
    """{'batter': {칸: [시즌]}, 'pitcher': {...}}. 파일이 없으면 빈 사전(기본 칸만 씀)."""
    global _verified
    if _verified is None:
        import json
        try:
            _verified = json.loads(VERIFIED_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            _verified = {"batter": {}, "pitcher": {}}
    return _verified


def allowed(kind, column, season, table=None):
    """이 칸을 이 시즌에 써도 되는가(검증 통과). 새 시즌은 검증한 마지막 시즌을 따릅니다."""
    v = table if table is not None else verified()
    seasons = set(v.get(kind, {}).get(column, []))
    if season in seasons:
        return True
    last = max((y for ys in v.get(kind, {}).values() for y in ys), default=None)
    return last is not None and season > last and last in seasons

# 네이버 시즌 API 가 통째로 뺀 투수(2013~2021, 10명 27행)를 박스 투수 줄 합계로 넣을지.
# evan 결정 대기(결정 2 의 투수 쪽). 켜면 docs/naver-migration/missing-pitchers.md 의
# 방법(가)입니다.
INCLUDE_BOX_ONLY_PITCHERS = False

# 늘 None 인 칸(evan 결정 3: 네이버에 없고 만들면 애매함).
NEVER = {
    "pitcher": ("blown_save", "save_opportunity", "total_saves"),
}

BATTER_COLUMNS = [
    "player_id", "season", "player_name", "player_team", "batting_average", "games",
    "plate_appearance", "at_bat", "run", "single", "double", "triple", "home_run",
    "total_bases", "run_batted_in", "sacrifice_bunts", "sacrifice_fly", "base_on_balls",
    "intentional_base_on_balls", "hit_by_pitch", "strikeout", "ground_into_double_play",
    "slugging_percentage", "on_base_percentage", "on_base_plus_slugging", "multi_hits",
    "runners_in_scoring_position", "pinch_hit_batting_average", "extra_base_hits",
    "ground_outs", "air_outs", "go_ao", "gw_rbi", "strikeout_per_pa",
    "base_on_balls_per_pa", "bb_k", "p_pa", "isop", "extended_runs",
    "gross_production_average",
]
PITCHER_COLUMNS = [
    "player_id", "season", "player_name", "player_team", "earned_run_average", "games",
    "wins", "losses", "save", "hold", "winning_percentage", "innings_pitched", "hits",
    "home_run", "base_on_balls", "hit_by_pitch", "strikeout", "run", "earned_run",
    "walks_plus_hits_per_inning_pitched", "complete_game", "shutout", "quality_start",
    "blown_save", "total_batters_faced", "number_of_pitchers", "batting_average", "double",
    "triple", "sacrifice_bunts", "sacrifice_fly", "intentional_base_on_balls", "wild_pitch",
    "balk", "games_started", "wins_game_started", "wins_game_relieved", "games_finished",
    "save_opportunity", "total_saves", "ground_into_double_play", "ground_outs", "air_outs",
    "go_ao", "batting_average_on_balls_in_play", "p_g", "p_ip", "k_9", "bb_9",
    "strikeout_per_pa", "base_on_balls_per_pa", "k_bb", "on_base_percentage",
    "slugging_percentage", "on_base_plus_slugging",
]


def div(a, b, places):
    return nss.r(Decimal(a) / b, places) if b else None


def batter_extra(nv, box, pbp, pbp_ok, sb, cs):
    """네이버 행 nv 에 박스·PBP 칸을 더한 값들(검증 전, 모든 후보)."""
    ab = nv.get("at_bat") or 0
    h = nv.get("single") or 0
    d2, d3, hr = (nv.get(k) or 0 for k in ("double", "triple", "home_run"))
    bb = nv.get("base_on_balls") or 0
    so = nv.get("strikeout") or 0
    hbp = nv.get("hit_by_pitch") or 0
    sf, sh, ibb, gidp = box["sf"], box["sh"], box["ibb"], box["gidp"]
    out = {
        # 경기 수는 박스 출장 수입니다. 네이버 시즌 API 는 타석 없이 나온 선수(대주자·
        # 대수비)의 경기 수를 1 로 줍니다(2011 4명·2018·2021, 박스·KBO 는 2~5).
        "games": box["games"] or nv.get("games"),
        # 타석 = 타수+볼넷(고의4구 포함)+사구+희생번트+희생플라이+타격방해. 박스 칸 수를
        # 그대로 세는 것보다 KBO 값과 잘 맞았습니다(2008 271/273, 박스 칸 수는 270).
        "plate_appearance": ab + bb + hbp + sh + sf + box["ci"],
        "sacrifice_bunts": sh,
        "sacrifice_fly": sf,
        "intentional_base_on_balls": ibb,
        "ground_into_double_play": gidp,
        "multi_hits": box["multi"],
        "ground_outs": box["GO"],
        "air_outs": box["AO"],
        "go_ao": nss.fmt2(Decimal(box["GO"]) / box["AO"]) if box["AO"] else None,
        "gw_rbi": box["gw"],
        "bb_k": nss.fmt2(Decimal(bb) / so) if so else None,
    }
    # 출루율: 분모(타수+볼넷+사구+희플) 0 이면 None, 희플만 있으면 0.
    if nv.get("on_base_percentage") is None and ab + bb + hbp + sf > 0:
        out["on_base_percentage"] = 0.0
        out["on_base_plus_slugging"] = nss.ops(0.0, nv.get("slugging_percentage"))
    obp = out.get("on_base_percentage", nv.get("on_base_percentage"))
    slg = nv.get("slugging_percentage")
    # GPA 는 출루율·장타율이 없으면 0 으로 셉니다(KBO 와 같음: 타석 없는 투수 행도 0.0).
    out["gross_production_average"] = nss.r(
        (Decimal(str(obp or 0)) * Decimal("1.8") + Decimal(str(slg or 0))) / 4, 3)
    s1 = h - d2 - d3 - hr
    xr = (Decimal("0.5") * s1 + Decimal("0.72") * d2 + Decimal("1.04") * d3 + Decimal("1.44") * hr
          + Decimal("0.34") * (hbp + bb - ibb) + Decimal("0.25") * ibb + Decimal("0.18") * sb
          - Decimal("0.32") * cs - Decimal("0.09") * (ab - h - so) - Decimal("0.098") * so
          - Decimal("0.37") * gidp + Decimal("0.37") * sf + Decimal("0.04") * sh)
    out["extended_runs"] = nss.r(xr, 1)
    if pbp_ok:
        out["runners_in_scoring_position"] = div(pbp["risp_h"], pbp["risp_ab"], 3) or 0.0
        out["pinch_hit_batting_average"] = div(pbp["ph_h"], pbp["ph_ab"], 3) or 0.0
        out["p_pa"] = div(pbp["pitches"], box["pa"], 2)
    return out


def pitcher_extra(nv, box, pbp, pbp_ok):
    g = nv.get("games") or 0
    outs = nss.ip_outs(nv.get("innings_pitched"))
    out = {
        "total_batters_faced": box["tbf"],
        "number_of_pitchers": box["np"],
        "games_started": box["gs"],
        "games_finished": box["gf"],
        "complete_game": box["cg"],
        "shutout": box["sho"],
        "wins_game_started": box["w_start"],
        "wins_game_relieved": box["w_relief"],
        "wild_pitch": box["wp"],
        "balk": box["bk"],
        "p_g": div(box["np"], g, 1),
        "p_ip": div(box["np"] * 3, outs, 1),
    }
    if pbp_ok:
        k = pbp
        ab = k["ab"]
        on_den = ab + k["bb"] + k["ibb"] + k["hbp"] + k["sf"]
        obp = div(k["h"] + k["bb"] + k["ibb"] + k["hbp"], on_den, 3)
        slg = div(k["tb"], ab, 3)
        bden = ab - k["so"] - k["hr"] + k["sf"]
        out.update({
            "double": k["d2"], "triple": k["d3"], "sacrifice_bunts": k["sh"],
            "sacrifice_fly": k["sf"], "intentional_base_on_balls": k["ibb"],
            "ground_into_double_play": k["gidp"], "ground_outs": k["go"], "air_outs": k["ao"],
            "go_ao": nss.fmt2(Decimal(k["go"]) / k["ao"]) if k["ao"] else None,
            "batting_average": div(k["h"], ab, 3), "on_base_percentage": obp,
            "slugging_percentage": slg, "on_base_plus_slugging": nss.ops(obp, slg),
            "batting_average_on_balls_in_play": div(k["h"] - k["hr"], bden, 3),
        })
    return out


def gate(row, season, columns, kind):
    """검증을 통과하지 못한 (칸, 시즌)은 None. 기본 칸(네이버 시즌 API)은 그대로."""
    base = BASE_COLUMNS[kind]
    out = {}
    for c in columns:
        v = row.get(c)
        if c in NEVER.get(kind, ()):
            v = None
        elif c not in base and not allowed(kind, c, season):
            v = None
        out[c] = v
    return out


BASE_COLUMNS = {
    "batter": {"player_id", "season", "player_name", "player_team", "batting_average", "games",
               "at_bat", "run", "single", "double", "triple", "home_run", "total_bases",
               "run_batted_in", "base_on_balls", "hit_by_pitch", "strikeout",
               "slugging_percentage", "on_base_percentage", "on_base_plus_slugging",
               "extra_base_hits", "isop"},
    "pitcher": {"player_id", "season", "player_name", "player_team", "earned_run_average",
                "games", "wins", "losses", "save", "hold", "winning_percentage",
                "innings_pitched", "hits", "home_run", "base_on_balls", "hit_by_pitch",
                "strikeout", "run", "earned_run", "walks_plus_hits_per_inning_pitched",
                "quality_start", "k_9", "bb_9", "k_bb"},
}


def box_pitcher_row(pid, k, season, name, team):
    """박스 투수 줄 합계(nbx.pitcher_lines) → 네이버 시즌 API 와 같은 칸의 행."""
    outs = k["outs"]
    w, l = k["w"], k["l"]
    ip = "%d" % (outs // 3) if outs % 3 == 0 else (
        "%d/3" % outs if outs < 3 else "%d %d/3" % (outs // 3, outs % 3))
    return {
        "player_id": pid, "season": season, "player_name": name, "player_team": team,
        "earned_run_average": nss.per9(k["er"], outs), "games": k["games"], "wins": w, "losses": l,
        "save": k["sv"], "hold": k["hld"], "winning_percentage": nss.r(w / (w + l), 3) if w + l else None,
        "innings_pitched": ip, "hits": k["h"], "home_run": k["hr"], "base_on_balls": k["bb"],
        "hit_by_pitch": k["hbp"], "strikeout": k["so"], "run": k["r"], "earned_run": k["er"],
        "walks_plus_hits_per_inning_pitched": nss.r(Decimal(k["h"] + k["bb"]) * 3 / outs, 2) if outs else None,
        "quality_start": k["qs"], "k_9": nss.per9(k["so"], outs), "bb_9": nss.per9(k["bb"], outs),
        "k_bb": nss.fmt2(Decimal(k["so"]) / k["bb"]) if k["bb"] else None,
    }


def stolen(season_raw_hitters):
    """{player_id: 도루} 네이버 시즌 API(경기 수 큰 행)."""
    best = nss.pick(season_raw_hitters, "hitterGameCount")
    return {pid: (x.get("hitterSb") or 0) for pid, x in best.items()}


def caught_stealing(files):
    cs = collections.Counter()
    for f in files:
        box = nbx.load(f)
        sides = nbx.names_by_side(box)
        for n in nbx.etc_names(box, "도루자"):
            pid = nbx.resolve(n, sides)
            if pid:
                cs[pid] += 1
    return cs


def build_season(season, names, pbp_rows, box_files, naver_cache=None, cl=None, gated=True):
    """(타자 행 목록, 투수 행 목록, 메모) — 모든 칸을 가진 dict.

    gated=False 면 FROM_SEASON 을 적용하지 않은 후보 값 전부(검증용)입니다.
    """
    raw = nss.fetch_season(season, cl, naver_cache)
    nv_bat = {pid: nss.batter_row(x, season, names) for pid, x in nss.pick(raw["HITTER"], "hitterGameCount").items()}
    nv_pit = {pid: nss.pitcher_row(x, season, names) for pid, x in nss.pick(raw["PITCHER"], "pitcherGameCount").items()}
    sb = stolen(raw["HITTER"])
    pbg = pss.pas_by_game_batter(pbp_rows)
    box_bat, box_pit, unmatched = nbx.season(box_files, pbg)
    cs = caught_stealing(box_files)
    pb_bat = pss.batter_counts(pbp_rows)
    pb_pit = pss.pitcher_counts(pbp_rows, {})
    note = {"unmatched_names": dict(unmatched), "pbp_incomplete_batters": 0, "pbp_incomplete_pitchers": 0}
    bats = []
    for pid, nv in nv_bat.items():
        box = box_bat.get(pid, collections.Counter())
        pb = pb_bat.get(pid, collections.Counter())
        ok = pb["ab"] == (nv.get("at_bat") or 0) and pb["h"] == (nv.get("single") or 0)
        note["pbp_incomplete_batters"] += not ok
        row = dict(nv)
        row.update(batter_extra(nv, box, pb, ok, sb.get(pid, 0), cs.get(pid, 0)))
        bats.append(gate(row, season, BATTER_COLUMNS, "batter") if gated else row)
    if INCLUDE_BOX_ONLY_PITCHERS:
        seen = set(box_pit)
        lines, bnames, bteams = nbx.pitcher_lines(box_files, only=seen - set(nv_pit))
        for pid, k in lines.items():
            nv_pit[pid] = box_pitcher_row(pid, k, season, bnames.get(pid),
                                          names.get((bteams.get(pid), season)) or bteams.get(pid))
        note["box_only_pitchers"] = sorted(lines)
    pits = []
    for pid, nv in nv_pit.items():
        box = box_pit.get(pid, collections.Counter())
        pb = pb_pit.get(pid, collections.Counter())
        ok = (pb["tbf"] == box["tbf"] and pb["h"] == (nv.get("hits") or 0)
              and pb["so"] == (nv.get("strikeout") or 0))
        note["pbp_incomplete_pitchers"] += not ok
        row = dict(nv)
        row.update(pitcher_extra(nv, box, pb, ok))
        pits.append(gate(row, season, PITCHER_COLUMNS, "pitcher") if gated else row)
    return bats, pits, note


# ---------------------------------------------------------------- MySQL

PBP_COLUMNS = ("gameID,game_date,pa_number,pitch_number,inning,inning_topbot,pitcher_ID,batter_ID,"
               "pitcher,batter,pitch_result,pa_result,pa_result_detail,on_1b_id,on_2b_id,on_3b_id,"
               "on_1b,on_2b,on_3b,description")


def load_pbp(query, season, regular_ids):
    rows = query("SELECT %s FROM play_by_play WHERE game_date BETWEEN %d AND %d ORDER BY pbp_id"
                 % (PBP_COLUMNS, season * 10000, season * 10000 + 9999))
    return [r for r in rows if r["gameID"] in regular_ids]


def regular_game_ids(query, season):
    rows = query("SELECT game_id FROM games WHERE season = %d AND game_type = '정규시즌'" % season)
    return {r["game_id"] for r in rows}


def write(sink, season, bats, pits):
    """그 시즌 두 표를 지우고 넣습니다(한 트랜잭션, mysql_sink.mirror 안)."""
    sink.execute("DELETE FROM kbo_official_batter_stats WHERE season = %s", (season,))
    sink.execute("DELETE FROM kbo_official_pitcher_stats WHERE season = %s", (season,))
    sink.insert("kbo_official_batter_stats", BATTER_COLUMNS, bats)
    sink.insert("kbo_official_pitcher_stats", PITCHER_COLUMNS, pits)
    sink.refresh_count("kbo_official_batter_stats")
    sink.refresh_count("kbo_official_pitcher_stats")
    return len(bats) + len(pits)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--season", type=int)
    ap.add_argument("--current", action="store_true")
    ap.add_argument("--box-dir", default=str(DEFAULT_BOX_DIR))
    ap.add_argument("--fetch-box", action="store_true",
                    help="그 시즌 정규시즌 경기 가운데 박스가 없는 경기를 먼저 받습니다")
    ap.add_argument("--naver-cache")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    from d1_load import query
    from kbo_season import record_season
    season = record_season() if a.current else a.season
    if not season or season < FIRST_SEASON:
        ap.error("--season(2008 이후) 이나 --current 가 필요합니다")
    reg = regular_game_ids(query, season)
    if a.fetch_box:
        import naver_boxscore
        got, skipped, failed = naver_boxscore.fetch_all(sorted(reg), a.box_dir, workers=3)
        print("박스: 받음 %d · 있음 %d · 실패 %d" % (got, skipped, len(failed)))
        if failed:
            print("박스를 못 받은 경기가 있어 멈춥니다: %s" % failed[:5])
            return 1
    files = [f for f in nbx.season_files(a.box_dir, season) if f.name.split(".")[0] in reg]
    if len(files) < len(reg):
        print("박스가 %d/%d 경기뿐입니다. --fetch-box 로 먼저 받으십시오." % (len(files), len(reg)))
        return 1
    names = {(r["franchise_id"], int(r["season"])): r["team_name"]
             for r in query("SELECT franchise_id, season, team_name FROM team_seasons")}
    bats, pits, note = build_season(season, names, load_pbp(query, season, reg), files, a.naver_cache)
    print("%d: 타자 %d · 투수 %d · %s" % (season, len(bats), len(pits), note))
    if a.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0
    from mysql_sink import mirror
    mirror("official_stats", lambda sink: write(sink, season, bats, pits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
