# -*- coding: utf-8 -*-
"""프랜차이즈와 시즌별 팀 이름 표를 만듭니다.

## 왜 필요한가

1982년까지 선수 기록을 받으면 소속이 **그때 이름**으로 들어옵니다.

    1982 김우열  player_team = OB      (지금 두산)
    1990 선동열  player_team = 해태     (지금 KIA)
    1985 장명부  player_team = 청보     (해체)

지금 `teams` 표는 현재 10팀만 담고 시간 개념이 없습니다. 그래서
옛 이름으로는 팀 정보를 못 찾습니다. 화면에는 그 시즌 실제 이름이
나와야 하고(사실이 그렇습니다), 동시에 팀 색·엠블럼·프랜차이즈
통산은 이어져야 합니다.

표 둘로 나눕니다.

    franchises    변하지 않는 정체성 12개
    team_seasons  그 시즌 표기명 (1982~2026, 약 380행)

    player_team='OB' + season=1982
        -> team_seasons -> franchise_id='OB'
        -> franchises   -> current_name='두산'

## 값의 출처

**KBO 기록실의 시즌별 팀 드롭다운입니다.** 손으로 적지 않았습니다.
`--refresh` 를 주면 사이트에서 다시 읽어 옵니다. 기억에 의존하면
1985년 청보 같은 것을 놓칩니다.

## 기존 teams 는 건드리지 않습니다

`games` 가 FK 로 참조하고 현재 화면이 전부 이 표를 씁니다. 새 표를
옆에 두고, 옛 시즌만 그쪽을 보게 합니다.

    py migration/build_franchises.py            # 미리보기
    py migration/build_franchises.py --write    # 로컬 DB 반영
    py migration/build_franchises.py --refresh  # 사이트에서 다시 읽기
"""
import argparse
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

DB = os.environ.get("KBO_DB") or str(ROOT / "database" / "kbo_stats.db")
CACHE = ROOT / "migration" / "teams_by_season.json"

FIRST_SEASON = 1982

# 프랜차이즈 -> 현재 teams.team_id. 해체팀은 None 입니다.
# 코드 자체는 사이트가 주지만, "지금 어느 팀인가" 는 사이트가 알려
# 주지 않아 여기서 잇습니다. 근거는 KBO 가 인정하는 프랜차이즈
# 승계입니다(구단 매각·이름 변경은 같은 프랜차이즈로 봅니다).
CURRENT = {
    "OB": "두산", "SS": "삼성", "LG": "LG", "HT": "KIA", "LT": "롯데",
    "HH": "한화", "SK": "SSG", "WO": "키움", "NC": "NC", "KT": "KT",
    "HD": None,   # 삼미 -> 청보 -> 태평양 -> 현대, 2007 해체
    "SB": None,   # 쌍방울, 1999 마지막
}

NOTE = {
    "HD": "삼미 슈퍼스타즈로 창단, 2007 시즌 후 해체. 선수단은 히어로즈로",
    "SB": "쌍방울 레이더스, 1999 시즌 마지막. 이듬해 SK 가 자리를 이음",
}

DDL = """
CREATE TABLE IF NOT EXISTS franchises (
  franchise_id    TEXT PRIMARY KEY,
  current_name    TEXT,
  first_season    INTEGER NOT NULL,
  last_season     INTEGER,
  note            TEXT
);
CREATE TABLE IF NOT EXISTS team_seasons (
  franchise_id TEXT NOT NULL,
  season       INTEGER NOT NULL,
  team_name    TEXT NOT NULL,
  PRIMARY KEY (franchise_id, season)
);
CREATE INDEX IF NOT EXISTS idx_team_seasons_name
  ON team_seasons(season, team_name);
"""


def scrape(last_season):
    """기록실 드롭다운에서 시즌별 팀 목록을 읽습니다."""
    from kbo_http import Session
    out = {}
    s = Session(delay=0.3)
    s.open("HitterBasic/Basic1.aspx")
    for y in range(FIRST_SEASON, last_season + 1):
        s.post("ddlSeason$ddlSeason", {"ddlSeason$ddlSeason": str(y)})
        m = re.search(r'ddlTeam_ddlTeam"[^>]*>(.*?)</select>', s.html, re.S)
        opts = re.findall(r'value="([^"]*)"[^>]*>([^<]*)<', m.group(1)) if m else []
        teams = [(v, t.strip()) for v, t in opts if v]
        if not teams:
            print("  %d: 팀 목록을 못 읽었습니다" % y)
            continue
        out[str(y)] = teams
        print("  %d: %d팀" % (y, len(teams)), flush=True)
    return out


def spans(by_season):
    """{코드: [(이름, 시작, 끝), ...]} 입니다."""
    hist = {}
    for y in sorted(by_season, key=int):
        for code, name in by_season[y]:
            hist.setdefault(code, {})[int(y)] = name
    out = {}
    for code, m in hist.items():
        ys = sorted(m)
        rows, start = [], ys[0]
        for i, y in enumerate(ys):
            last = i == len(ys) - 1
            if last or m[ys[i + 1]] != m[y]:
                rows.append((m[y], start, y))
                if not last:
                    start = ys[i + 1]
        out[code] = rows
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--refresh", action="store_true",
                    help="사이트에서 팀 목록을 다시 읽습니다")
    ap.add_argument("--last-season", type=int, default=2026)
    args = ap.parse_args()

    if args.refresh or not CACHE.exists():
        print("기록실에서 시즌별 팀 목록을 읽습니다...")
        by_season = scrape(args.last_season)
        CACHE.write_text(json.dumps(by_season, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        print("저장: %s" % CACHE)
    else:
        by_season = json.loads(CACHE.read_text(encoding="utf-8"))
        print("캐시를 씁니다: %s (--refresh 로 다시 읽습니다)" % CACHE.name)

    sp = spans(by_season)

    # 사이트에 있는데 CURRENT 에 없는 코드가 있으면 멈춥니다. 새 팀이
    # 생겼는데 조용히 빠지면 그 팀 선수가 프랜차이즈에 안 붙습니다.
    unknown = sorted(set(sp) - set(CURRENT))
    if unknown:
        print("CURRENT 에 없는 코드: %s" % ", ".join(unknown))
        print("migration/build_franchises.py 의 CURRENT 에 추가하십시오.")
        return 1

    fr_rows, ts_rows = [], []
    print("\n%-4s %-9s %s" % ("코드", "현재", "이름 변천"))
    print("-" * 66)
    for code in sorted(sp, key=lambda c: sp[c][0][1]):
        rows = sp[code]
        first = rows[0][1]
        last = rows[-1][2]
        alive = last >= args.last_season
        fr_rows.append((code, CURRENT[code], first,
                        None if alive else last, NOTE.get(code)))
        for name, a, b in rows:
            for y in range(a, b + 1):
                ts_rows.append((code, y, name))
        print("%-4s %-9s %s" % (
            code, CURRENT[code] or "(해체)",
            "  ".join("%s %d~%d" % (n, a, b) for n, a, b in rows)))

    print("\n프랜차이즈 %d개, 시즌별 이름 %d행" % (len(fr_rows), len(ts_rows)))
    if not args.write:
        print("[미리보기] 반영하지 않았습니다. --write 를 주십시오.")
        return 0

    con = sqlite3.connect(DB)
    con.executescript(DDL)
    con.execute("DELETE FROM franchises")
    con.execute("DELETE FROM team_seasons")
    con.executemany(
        "INSERT INTO franchises (franchise_id, current_name, first_season,"
        " last_season, note) VALUES (?,?,?,?,?)", fr_rows)
    con.executemany(
        "INSERT INTO team_seasons (franchise_id, season, team_name)"
        " VALUES (?,?,?)", ts_rows)
    con.commit()
    n1 = con.execute("SELECT COUNT(*) FROM franchises").fetchone()[0]
    n2 = con.execute("SELECT COUNT(*) FROM team_seasons").fetchone()[0]
    con.close()
    print("반영 완료: franchises %d행, team_seasons %d행" % (n1, n2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
