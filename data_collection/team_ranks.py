# -*- coding: utf-8 -*-
"""KBO 팀 순위를 1982년부터 받아 Cloud SQL(MySQL)에 넣습니다.

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
    py data_collection/team_ranks.py --current          # daily 가 부릅니다

## 매일 올 시즌을 다시 받습니다

처음엔 1982~2026 을 한 번(2026-08-29)만 받았습니다. 그 뒤 2026 이 8월 말
값(KT 111경기)에 멈춰 팀 기록실 순위·승패가 한 달 넘게 늦었습니다
(2026-10-03 발견). 그래서 daily 가 `--current` 로 올 시즌만 다시 받습니다.
KBO 기록실 한 페이지라 가볍습니다. 그해 순위가 아직 없으면(비시즌)
건너뜁니다.

## 올 시즌은 날짜가 아니라 경기로 정합니다

`--current` 의 올 시즌은 kbo_season.record_season 입니다. 올해 정규시즌
경기가 하나라도 끝났으면 올해, 아니면 지난해입니다. 한국 날짜의 올해로
두면 2027년 1월~개막 사이에 기록실이 2027 을 빈 표로 내놓는 순간 "받은
것이 없습니다" 로 매일 실패합니다. 지난해를 다시 받는 것은 해가 없습니다
(끝난 시즌이라 값이 같습니다).

## 새 시즌의 team_seasons 를 채웁니다

팀 기록실(`/teams/:id`)은 그 시즌 팀 이름을 `team_seasons` 로 프랜차이즈에
잇습니다. 그 표는 1982~2026 을 한 번 만들고(migration/build_franchises.py)
정기 작업이 없었습니다. 그대로면 2027 의 팀 타율·ERA·구장이 팀 기록실에서
조용히 빠집니다. `--current` 로 받은 순위의 (프랜차이즈, 시즌, 팀 이름)
가운데 **없는 줄만** 넣습니다. 이미 있는 줄은 건드리지 않습니다. 이름이
처음 보는 것(구단명 변경)이면 프랜차이즈를 몰라 넣지 않습니다. 그때는
사람이 build_franchises 로 계보를 고칩니다.
"""
import argparse
import datetime
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import query  # noqa: E402
from kbo_http import Session  # noqa: E402
from kbo_season import record_season  # noqa: E402
from mysql_sink import mirror  # noqa: E402

URL = "https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx"
TABLE_CLASS = "tData"

KST = datetime.timezone(datetime.timedelta(hours=9))
KEYS = ["season", "team_name", "league"]

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
    입니다. **빈 문자열은 안 됩니다.** 적재(`mysql_sink.blank`)가 빈 값을
    NULL 로 바꾸는데 league 는 PK 라 NOT NULL 입니다. 실제로 적재가 거기서
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


TEAM_SEASON_COLUMNS = ["franchise_id", "season", "team_name"]
TEAM_SEASON_KEYS = ["franchise_id", "season"]


def team_season_rows(rows):
    """순위 행에서 team_seasons 에 넣을 (프랜차이즈, 시즌, 팀 이름)입니다.

    프랜차이즈를 모르는 행은 뺍니다. 같은 줄은 한 번만 둡니다.
    """
    out, seen = [], set()
    for r in rows:
        fid = r.get("franchise_id")
        if not fid:
            continue
        key = (fid, int(r["season"]))
        if key in seen:
            continue
        seen.add(key)
        out.append({"franchise_id": fid, "season": key[1], "team_name": r["team_name"]})
    return out


def mysql_write_ranks(sink, rows, fill_team_seasons=False):
    """(season, team_name, league) 가 같으면 나머지 열을 덮어씁니다.

    fill_team_seasons 면 team_seasons 에 없는 줄만 넣습니다(맨 위 설명).
    """
    n = sink.upsert("team_season_rank", COLUMNS, KEYS, rows)
    sink.refresh_count("team_season_rank")
    if fill_team_seasons:
        ts = team_season_rows(rows)
        if ts:
            sink.insert_missing("team_seasons", TEAM_SEASON_COLUMNS, TEAM_SEASON_KEYS, ts)
            sink.refresh_count("team_seasons")
    return n


def current_season(now=None):
    """한국 날짜 기준 올해입니다. 러너는 UTC 라 1월 1일 새벽이 어긋납니다."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return now.astimezone(KST).year


def pick_current(seasons, year):
    """그해 순위가 KBO 에 있으면 [그해], 아직 없으면(비시즌) [] 입니다."""
    return [year] if year in seasons else []


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
    ap.add_argument("--current", action="store_true",
                    help="올 시즌만(올해 정규시즌 경기가 아직 없으면 지난 시즌). "
                         "그해 순위가 아직 없으면 건너뜁니다")
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    s = Session(args.delay, table_class=TABLE_CLASS)
    s._fetch(URL)                                     # noqa: SLF001
    seasons = season_list(s)
    if not seasons:
        print("시즌 목록을 못 읽었습니다. 페이지 구조가 바뀌었을 수 있습니다.")
        return 1

    if args.current:
        year = record_season()
        seasons = pick_current(seasons, year)
        if not seasons:
            print("%d 순위가 아직 없습니다(비시즌). 건너뜁니다." % year)
            return 0
    elif args.season:
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

    mirror("team_ranks", lambda sink: mysql_write_ranks(
        sink, rows, fill_team_seasons=args.current))
    return 0


if __name__ == "__main__":
    sys.exit(main())
