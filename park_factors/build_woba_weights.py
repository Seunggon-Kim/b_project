# -*- coding: utf-8 -*-
"""`kbo_woba_weights_by_season` 을 play_by_play 에서 만듭니다.

## 왜 이 스크립트가 생겼는가

이 표는 원래 **손으로 채우던 것**이었습니다(column_descriptions.json 의
update_freq: "시즌/연간 갱신 수동 (자동 갱신 아님; 수작업으로 입력)").
값의 출처는 Statiz 캡처였습니다. `statiz_yearly_constants` 의 source 가
'Statiz' 이고 captured_at 이 전 행 동일한 한 시각(2026-05-07)입니다.

그런데 아티클(dashboard_js/pages/article.html #wrc-plus)은 이렇게
약속하고 있습니다.

  "이 대시보드의 wRC+ 는 Statiz 같은 외부 수치를 그대로 가져다 쓰지 않고,
   KBO play-by-play 원천 데이터에서 처음부터 다시 계산합니다."

문서와 데이터가 어긋나 있었습니다. 게다가 표가 D1 으로 넘어오지 않아
주간 파이프라인이 첫 질의에서 죽었고, 2026 wOBA·wRC+ 가 비었습니다.

이 스크립트가 그 표를 원천 데이터로 만듭니다. 사람이 넣을 값이
없습니다.

## 산식

`database/column_descriptions.json` 에 컬럼마다 적혀 있는 것 그대로입니다.

    fg_wX       = (raw_RV_X - avg_out_RV) x wOBA_scale
    wOBA_scale  = 리그 OBP / raw_lg_wOBA
    raw_lg_wOBA = 스케일 전 가중치를 리그 합계에 적용한 값

`raw_RV_*` 는 RE24 기대득점 변화의 사건별 평균입니다. 계산은
`build_re24_run_values.py` 와 같은 함수를 씁니다. 두 곳에서 따로 세면
언젠가 갈라집니다.

## 검증

  - Statiz 공개 상수와 대조: 2026 1루타 0.4910 vs 0.493,
    홈런 1.4184 vs 1.411, 볼넷 0.3528 vs 0.364
  - 2025 저장값 재현: 선수별 wOBA 평균오차 0.00066
  - 시즌별 가중치가 통합 가중치보다 잘 맞습니다(RMSE 0.00136 vs 0.00162).
    아티클이 말하는 "통합" 은 RE24 산출물 쪽이고, wOBA 는 "시즌별
    가중치 표" 를 읽는다고 같은 문단에 적혀 있습니다.

    py park_factors/build_woba_weights.py            # 미리보기
    py park_factors/build_woba_weights.py --write    # 반영
"""
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_re24_run_values as R  # noqa: E402

DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db")

# 아웃의 기준선입니다. 타수에서 안타를 뺀 아웃, 곧 삼진과 인플레이
# 아웃입니다. 희생번트·희생플라이는 타수에 들어가지 않으므로 뺍니다.
OUT_EVENTS = ("SO", "OutInPlay")

COLS = [
    "season", "PA", "AB", "H", "BB", "HBP", "SF", "OBP",
    "raw_RV_1B", "raw_RV_2B", "raw_RV_3B", "raw_RV_HR",
    "raw_RV_uBB", "raw_RV_HBP", "avg_out_RV",
    "raw_lg_wOBA", "wOBA_scale",
    "fg_w1B", "fg_w2B", "fg_w3B", "fg_wHR", "fg_wBB", "fg_wHBP",
]

DDL = ('CREATE TABLE IF NOT EXISTS kbo_woba_weights_by_season ('
       'season INTEGER PRIMARY KEY, '
       + ', '.join('"%s" REAL' % c for c in COLS[1:]) + ')')


def run_values(con, season):
    """그 시즌 사건별 평균 득점가치입니다. 없으면 None 입니다."""
    df = R.load_year(con, season)
    if len(df) == 0:
        return None
    _re, pa = R.compute_season(df)
    g = pa.groupby("event_type").rv.agg(rv="mean", n="count")
    return {e: (float(g.loc[e, "rv"]), int(g.loc[e, "n"])) for e in g.index}


def league_totals(con):
    """시즌별 리그 타격 합계입니다. 공식 기록에서 가져옵니다."""
    q = """SELECT season,
             SUM(plate_appearance) PA, SUM(at_bat) AB, SUM(single) H,
             SUM(double) D2, SUM(triple) D3, SUM(home_run) HR,
             SUM(base_on_balls) BB, SUM(hit_by_pitch) HBP,
             SUM(sacrifice_fly) SF
           FROM kbo_official_batter_stats GROUP BY season"""
    out = {}
    for r in con.execute(q):
        # NULL 이 하나라도 있으면 그 시즌은 계산하지 않습니다. 조용히
        # 0 으로 세면 가중치가 통째로 어긋납니다. 2021 NC 49명이 실제로
        # 그랬습니다(크롤러가 Basic2 페이지를 못 넘어갔습니다).
        if any(v is None for v in r[1:]):
            continue
        out[r[0]] = dict(zip(
            ["season", "PA", "AB", "H", "D2", "D3", "HR", "BB", "HBP", "SF"],
            r))
    return out


def season_row(rv, tot):
    """한 시즌의 가중치 한 줄입니다. 재료가 모자라면 None 입니다."""
    num = den = 0.0
    for e in OUT_EVENTS:
        if e in rv:
            num += rv[e][0] * rv[e][1]
            den += rv[e][1]
    if not den:
        return None
    out_rv = num / den

    need = ("1B", "2B", "3B", "HR", "uBB", "HBP")
    if any(e not in rv for e in need):
        return None
    raw = {e: rv[e][0] - out_rv for e in need}

    S1 = tot["H"] - tot["D2"] - tot["D3"] - tot["HR"]
    # 원본 산식대로 BB 는 고의4구를 포함합니다(park_factors/README.md).
    d = tot["AB"] + tot["BB"] + tot["SF"] + tot["HBP"]
    if d <= 0:
        return None
    raw_lg = (raw["uBB"] * tot["BB"] + raw["HBP"] * tot["HBP"]
              + raw["1B"] * S1 + raw["2B"] * tot["D2"]
              + raw["3B"] * tot["D3"] + raw["HR"] * tot["HR"]) / d
    if raw_lg <= 0:
        return None
    obp = (tot["H"] + tot["BB"] + tot["HBP"]) / d
    scale = obp / raw_lg

    r6 = lambda v: round(v, 6)  # noqa: E731
    return [
        tot["season"], tot["PA"], tot["AB"], tot["H"], tot["BB"],
        tot["HBP"], tot["SF"], r6(obp),
        r6(rv["1B"][0]), r6(rv["2B"][0]), r6(rv["3B"][0]), r6(rv["HR"][0]),
        r6(rv["uBB"][0]), r6(rv["HBP"][0]), r6(out_rv),
        r6(raw_lg), r6(scale),
        r6(raw["1B"] * scale), r6(raw["2B"] * scale), r6(raw["3B"] * scale),
        r6(raw["HR"] * scale), r6(raw["uBB"] * scale),
        r6(raw["HBP"] * scale),
    ]


def main(write):
    con = sqlite3.connect(DB)
    totals = league_totals(con)
    rows = []
    for y in R.ALLYEARS:
        if y not in totals:
            print("  %d: 리그 합계가 없거나 결손이 있어 건너뜁니다" % y)
            continue
        rv = run_values(con, y)
        if not rv:
            print("  %d: play_by_play 가 없어 건너뜁니다" % y)
            continue
        row = season_row(rv, totals[y])
        if row is None:
            print("  %d: 사건이 모자라 건너뜁니다" % y)
            continue
        rows.append(row)

    hdr = ("시즌   OBP    scale   w1B    w2B    w3B    wHR    wBB    wHBP")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        d = dict(zip(COLS, r))
        print("%d %.4f %.4f %.3f %.3f %.3f %.3f %.3f %.3f" % (
            d["season"], d["OBP"], d["wOBA_scale"], d["fg_w1B"],
            d["fg_w2B"], d["fg_w3B"], d["fg_wHR"], d["fg_wBB"],
            d["fg_wHBP"]))

    if not write:
        print("\n[DRY RUN] 반영하지 않았습니다. --write 를 주십시오.")
        con.close()
        return 0

    # 시즌 하나도 못 만들었으면 지우지 않습니다. 빈 표를 남기면
    # build_wrc_plus 가 **전 시즌을 지우고 아무것도 넣지 않습니다**
    # (DELETE 는 무조건 돌고, 가중치 없는 시즌은 continue 로 건너뜀).
    if not rows:
        print("만들어진 시즌이 없습니다. 표를 건드리지 않습니다.")
        con.close()
        return 1

    cur = con.cursor()
    cur.execute(DDL)
    cur.execute("DROP TABLE IF EXISTS kbo_woba_weights_by_season_bak")
    cur.execute("CREATE TABLE kbo_woba_weights_by_season_bak AS "
                "SELECT * FROM kbo_woba_weights_by_season")
    cur.execute("DELETE FROM kbo_woba_weights_by_season")
    cur.executemany(
        "INSERT INTO kbo_woba_weights_by_season (%s) VALUES (%s)"
        % (",".join('"%s"' % c for c in COLS), ",".join("?" * len(COLS))),
        rows)
    con.commit()
    n = cur.execute(
        "SELECT COUNT(*) FROM kbo_woba_weights_by_season").fetchone()[0]
    print("\n반영 완료: %d시즌" % n)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main("--write" in sys.argv))
