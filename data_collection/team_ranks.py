# -*- coding: utf-8 -*-
"""KBO 팀 순위를 1982년부터 받아 D1 에 넣습니다.

## 왜 필요한가

`games` 표는 2008년부터입니다. 그래서 팀 기록실의 시즌별 표에서
1982~2007 승패·순위가 통째로 빕니다. 공식 기록(타율·ERA)은 1982년부터
있는데 순위만 없어 표가 반쪽이 됩니다.

KBO 기록실이 45시즌을 그대로 줍니다.

    Record/TeamRank/TeamRank.aspx   ddlYear 로 시즌 선택

## 양대리그를 놓치면 안 됩니다

1999·2000 은 매직리그·드림리그로 나뉘어 **표가 둘**입니다. 한 표만
읽으면 절반이 조용히 사라집니다. 첫 시도에서 1999가 4행만 나왔습니다
(8팀인데). 표를 모두 읽습니다.

    표0   롯데 75-52-5   <- 매직리그
    표1   한화 72-58-2   <- 드림리그
    표2   팀간 상대전적   <- 순위표가 아닙니다

세 번째 표는 팀간 상대전적입니다. 첫 칸이 숫자가 아닌 것으로 거릅니다.

## 팀 이름을 프랜차이즈에 잇습니다

그 시즌 표기명(`OB`, `해태`)을 `team_seasons` 로 franchise_id 에
맞춥니다. 못 찾으면 NULL 로 두고 이름은 남깁니다. 나중에 표가 채워지면
이어집니다. 버리면 그 시즌이 통째로 사라집니다.

    py data_collection/team_ranks.py --dry-run
    py data_collection/team_ranks.py --from 1982 --to 2026
    py data_collection/team_ranks.py --season 2026      # 올 시즌만
"""
import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query, run_d1_file, sql_literal  # noqa: E402
from kbo_http import Session  # noqa: E402

URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx"
TABLE_CLASS = "tData"

SQL_TMP = ROOT / "migration" / "_team_ranks.sql"

_TAG = re.compile(r"<[^>]+>")
_TABLE = re.compile(r'<table[^>]*class="tData[^"]*"[^>]*>([\s\S]*?)</table>')
_TR = re.compile(r"<tr[^>]*>([\s\S]*?)</tr>")
_TD = re.compile(r"<td[^>]*>([\s\S]*?)</td>")


def _text(s):
    return _TAG.sub("", s).replace("&nbsp;", " ").strip()


def _int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def _league_before(html, pos):
    """그 표 바로 앞의 제목입니다. 양대리그 이름이 거기 있습니다.

        ... 매직리그 <table class="tData"> ...
        ... 드림리그 <table class="tData"> ...

    리그가 하나인 해에는 리그 이름이 없습니다. 그때는 None 입니다.
    """
    before = _TAG.sub(" ", html[max(0, pos - 400):pos])
    words = re.findall(r"(\S*리그)", before)
    return words[-1] if words else None


def parse_ranks(html):
    """순위표들입니다. `[(리그이름, 행들), ...]` 입니다.

    양대리그면 둘, 아니면 하나입니다. 팀간 상대전적 표는 첫 칸이 팀
    이름이라 걸러집니다.
    """
    out = []
    for m in re.finditer(r'<table[^>]*class="tData[^"]*"[^>]*>([\s\S]*?)</table>',
                         html):
        body = m.group(1)
        rows = []
        for tr in _TR.findall(body):
            tds = [_text(x) for x in _TD.findall(tr)]
            if len(tds) < 7:
                continue
            rank = _int(tds[0])
            if rank is None:
                # 순위표가 아닙니다(상대전적 표).
                continue
            rows.append({
                "rank": rank,
                "team_name": tds[1],
                "games": _int(tds[2]),
                "wins": _int(tds[3]),
                "losses": _int(tds[4]),
                "draws": _int(tds[5]),
                # 승률·게임차는 '0.700', '2.5' 처럼 표기 그대로 둡니다.
                "pct": tds[6],
                "gb": tds[7] if len(tds) > 7 else None,
            })
        if rows:
            out.append((_league_before(html, m.start()), rows))
    return out


def to_rows(tables, season, franchise_by_name):
    """적재용 행입니다.

    `league` 는 양대리그면 그 이름(매직리그·드림리그), 아니면 '단일'
    입니다. **빈 문자열은 안 됩니다.** `sql_literal` 이 빈 값을 NULL 로
    바꾸는데 league 는 PK 라 NOT NULL 입니다. 실제로 적재가 거기서
    멈췄습니다.
    """
    many = len(tables) > 1
    out = []
    for i, (league, rows) in enumerate(tables, start=1):
        name = (league or str(i)) if many else "단일"
        for r in rows:
            out.append({
                "franchise_id": franchise_by_name.get(r["team_name"]),
                "season": int(season),
                "team_name": r["team_name"],
                "league": name,
                "rank": r["rank"],
                "games": r["games"],
                "wins": r["wins"],
                "losses": r["losses"],
                "draws": r["draws"],
                "pct": r["pct"],
                "gb": r["gb"],
            })
    return out


COLUMNS = ["franchise_id", "season", "team_name", "league", "rank",
           "games", "wins", "losses", "draws", "pct", "gb"]


def create_table():
    return (
        'CREATE TABLE IF NOT EXISTS team_season_rank ('
        ' franchise_id TEXT, season INTEGER NOT NULL, team_name TEXT NOT NULL,'
        " league TEXT NOT NULL DEFAULT '',"
        ' rank INTEGER, games INTEGER, wins INTEGER, losses INTEGER,'
        ' draws INTEGER, pct TEXT, gb TEXT,'
        ' PRIMARY KEY (season, team_name, league));')


def insert_sql(rows):
    head = ('INSERT INTO team_season_rank (%s) VALUES '
            % ",".join('"%s"' % c for c in COLUMNS))
    tail = (' ON CONFLICT(season, team_name, league) DO UPDATE SET %s;'
            % ",".join('"%s"=excluded."%s"' % (c, c) for c in COLUMNS
                       if c not in ("season", "team_name", "league")))
    values = ",".join(
        "(%s)" % ",".join(sql_literal(r.get(c)) for c in COLUMNS)
        for r in rows)
    return head + values + tail


def name_map():
    """그 시즌 표기명 -> franchise_id 입니다."""
    rows = query("SELECT team_name, franchise_id FROM team_seasons;")
    return {r["team_name"]: r["franchise_id"] for r in (rows or [])}


def season_list(session):
    m = re.search(r'ddlYear"[^>]*>([\s\S]*?)</select>', session.html)
    if not m:
        return []
    return [int(v) for v in re.findall(r'<option[^>]*value="(\d{4})"',
                                       m.group(1))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="year_from", type=int, default=None)
    ap.add_argument("--to", dest="year_to", type=int, default=None)
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = Session(args.delay, table_class=TABLE_CLASS)
    s._fetch(URL)                                     # noqa: SLF001
    seasons = season_list(s)
    if not seasons:
        print("시즌 목록을 못 읽었습니다. 페이지 구조가 바뀌었을 수 있습니다.")
        return 1

    if args.season:
        seasons = [args.season]
    else:
        lo = args.year_from or min(seasons)
        hi = args.year_to or max(seasons)
        seasons = [y for y in seasons if lo <= y <= hi]

    names = name_map()
    print("시즌 %d개, 팀 이름 매핑 %d개" % (len(seasons), len(names)),
          flush=True)

    t0 = time.time()
    rows = []
    for y in sorted(seasons):
        s.post("ddlYear", {"ddlYear": str(y)})
        tables = parse_ranks(s.html)
        got = to_rows(tables, y, names)
        if not got:
            print("  %d 순위를 못 읽었습니다." % y, flush=True)
            continue
        rows.extend(got)
        note = (" (%s)" % ", ".join(t[0] or "?" for t in tables)
                if len(tables) > 1 else "")
        unmatched = sum(1 for r in got if not r["franchise_id"])
        print("  %d %d팀%s%s"
              % (y, len(got), note,
                 "  프랜차이즈 못 찾음 %d" % unmatched if unmatched else ""),
              flush=True)

    if not rows:
        print("받은 것이 없습니다.")
        return 1

    print("총 %s행, %.0f초" % (format(len(rows), ","), time.time() - t0))
    if args.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0

    SQL_TMP.parent.mkdir(parents=True, exist_ok=True)
    SQL_TMP.write_text(create_table() + "\n" + insert_sql(rows) + "\n",
                       encoding="utf-8", newline="\n")
    run_d1_file(SQL_TMP)
    print("적재 완료 %s행" % format(len(rows), ","))
    return 0


if __name__ == "__main__":
    sys.exit(main())
