# -*- coding: utf-8 -*-
"""퓨처스(2군) 시즌 기록을 KBO 기록실에서 받아 D1 에 넣습니다.

## 왜 필요한가

퓨처스 선수 화면에 올 시즌 기록만 나옵니다. KBO 선수 상세 페이지가
올 시즌 요약과 최근 경기만 주기 때문입니다. 1군 화면에는 연도별 표가
있는데 2군은 "올 시즌 퓨처스 기록이 없습니다" 한 줄만 남습니다.

기록실 쪽에는 **2010년부터** 있습니다. 1군과 같은 ASP.NET 구조라
`kbo_http.Session` 을 그대로 씁니다. 표 클래스만 다릅니다.

    1군      <table class="tData01 tt">
    퓨처스   <table class="tbl tt mb30">

## 팀을 골라야 다 나옵니다

필터 없이 보면 규정 타석 이상 29명만 나옵니다. **팀을 고르면 규정
미달까지 나옵니다.** 2020 두산은 43명(2페이지)이었습니다. 팀을 안
고르면 2군에 잠깐 나온 선수가 통째로 빠집니다.

## 규모

    12팀 x 17시즌 x 2(타자·투수) = 408 조합, 약 12분, 약 17,000행

지난 시즌은 다시 바뀌지 않습니다. 한 번 쌓고 나면 올 시즌만 갱신하면
됩니다.

    py data_collection/futures_records.py --season 2020 --dry-run
    py data_collection/futures_records.py --from 2010 --to 2026
"""
import argparse
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "data_collection"))

from d1_load import run_d1_file, sql_literal  # noqa: E402
from kbo_http import Session  # noqa: E402

BASE = "https://www.koreabaseball.com/Futures/Player/"
TABLE_CLASS = "tbl tt"

PAGES = {"batter": "Hitter.aspx", "pitcher": "Pitcher.aspx"}

# 컬럼 이름에 그대로 못 쓰는 것들입니다. SQLite 는 따옴표로 감싸면
# 되지만, 숫자로 시작하는 이름은 다루기 번거롭습니다.
COLUMN_ALIAS = {"2B": "double_hit", "3B": "triple_hit"}

# 표에 있지만 담지 않는 칸입니다. 순위는 필터에 따라 달라집니다.
SKIP_COLUMNS = ("순위",)

SQL_TMP = ROOT / "migration" / "_futures_records.sql"

# 한 파일에 담는 INSERT 행 수입니다. D1 문 상한(100,000바이트)에
# 걸리지 않게 잡습니다.
BATCH = 400


def column_name(header):
    """표 머리를 컬럼 이름으로 바꿉니다."""
    if header == "선수명":
        return "player_name"
    if header == "팀명":
        return "team"
    return COLUMN_ALIAS.get(header, header)


def to_record(player_id, header, cells, season, kind):
    """표 한 줄을 적재용 dict 로 바꿉니다. 선수 ID 가 없으면 None 입니다."""
    if not player_id:
        return None
    row = {"player_id": str(player_id), "season": int(season), "kind": kind}
    for h, v in zip(header, cells):
        if h in SKIP_COLUMNS:
            continue
        row[column_name(h)] = v
    return row


def row_key(record):
    """한 줄을 가리키는 열쇠입니다. 같은 선수·시즌·구분은 한 줄입니다."""
    return (record["player_id"], record["season"], record["kind"])


def season_list(session):
    """기록실이 주는 시즌 목록입니다. 하드코딩하지 않습니다."""
    m = re.search(r'ddlSeason_ddlSeason"[^>]*>(.*?)</select>',
                  session.html, re.S)
    if not m:
        return []
    return [v for v in re.findall(r'<option[^>]*value="(\d+)"', m.group(1))]


def team_list(session):
    """그 화면이 주는 팀 코드입니다. 빈 값(전체)은 뺍니다."""
    m = re.search(r'ddlTeam"[^>]*>(.*?)</select>', session.html, re.S)
    if not m:
        return []
    return [v for v in re.findall(r'<option[^>]*value="([^"]*)"', m.group(1))
            if v]


def collect(kind, season, team, delay):
    """한 시즌·한 팀의 기록입니다(페이지 넘김 포함)."""
    s = Session(delay, table_class=TABLE_CLASS)
    s._fetch(BASE + PAGES[kind])                      # noqa: SLF001
    s.post("ddlSeason$ddlSeason", {"ddlSeason$ddlSeason": str(season)})
    # 시즌을 바꾸면 팀 선택이 초기화됩니다. 나눠 보냅니다.
    s.post("ddlTeam", {"ddlTeam": team})

    header = s.header()
    out = {}
    for page in range(1, s.page_count() + 1):
        if page > 1:
            s.post("ucPager$btnNo%d" % page)
        for pid, cells in s.rows():
            rec = to_record(pid, header, cells, season, kind)
            if rec is None:
                continue
            out.setdefault(row_key(rec), rec)
    return out


def create_table(columns):
    """표가 없으면 만듭니다. 컬럼은 사이트가 주는 그대로입니다."""
    cols = ", ".join('"%s" TEXT' % c for c in columns
                     if c not in ("player_id", "season", "kind"))
    return (
        'CREATE TABLE IF NOT EXISTS futures_season_stats ('
        ' player_id TEXT NOT NULL, season INTEGER NOT NULL,'
        ' kind TEXT NOT NULL, %s,'
        ' PRIMARY KEY (player_id, season, kind));' % cols)


def insert_sql(records, columns):
    """INSERT 문들입니다. 같은 열쇠는 덮어씁니다."""
    head = ('INSERT INTO futures_season_stats (%s) VALUES '
            % ",".join('"%s"' % c for c in columns))
    tail = (' ON CONFLICT(player_id, season, kind) DO UPDATE SET %s;'
            % ",".join('"%s"=excluded."%s"' % (c, c) for c in columns
                       if c not in ("player_id", "season", "kind")))
    out = []
    for i in range(0, len(records), BATCH):
        chunk = records[i:i + BATCH]
        values = ",".join(
            "(%s)" % ",".join(sql_literal(r.get(c)) for c in columns)
            for r in chunk)
        out.append(head + values + tail)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="year_from", type=int, default=None)
    ap.add_argument("--to", dest="year_to", type=int, default=None)
    ap.add_argument("--season", type=int, default=None,
                    help="한 시즌만 합니다")
    ap.add_argument("--kind", choices=["batter", "pitcher", "both"],
                    default="both")
    ap.add_argument("--delay", type=float, default=0.3)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    probe = Session(args.delay, table_class=TABLE_CLASS)
    probe._fetch(BASE + PAGES["batter"])              # noqa: SLF001
    seasons = [int(y) for y in season_list(probe)]
    teams = team_list(probe)
    if not seasons or not teams:
        print("시즌·팀 목록을 못 읽었습니다. 페이지 구조가 바뀌었을 수 있습니다.")
        return 1

    if args.season:
        seasons = [args.season]
    else:
        lo = args.year_from or min(seasons)
        hi = args.year_to or max(seasons)
        seasons = [y for y in seasons if lo <= y <= hi]

    kinds = ["batter", "pitcher"] if args.kind == "both" else [args.kind]
    print("시즌 %d개, 팀 %d개, 구분 %s"
          % (len(seasons), len(teams), ",".join(kinds)), flush=True)

    t0 = time.time()
    records = {}
    for kind in kinds:
        for season in sorted(seasons):
            got = 0
            for team in teams:
                try:
                    part = collect(kind, season, team, args.delay)
                except Exception as e:                # noqa: BLE001
                    print("  %d %s %s 실패: %s" % (season, kind, team, e),
                          flush=True)
                    continue
                records.update(part)
                got += len(part)
            print("  %d %s %d명 (누적 %s, %.0f초)"
                  % (season, kind, got, format(len(records), ","),
                     time.time() - t0), flush=True)

    if not records:
        print("받은 것이 없습니다.")
        return 1

    rows = list(records.values())
    columns = []
    for r in rows:
        for c in r:
            if c not in columns:
                columns.append(c)

    print("총 %s행, 컬럼 %d개" % (format(len(rows), ","), len(columns)))
    if args.dry_run:
        print("[미리보기] 넣지 않았습니다.")
        return 0

    # 없는 컬럼은 NULL 로 채워 문 하나에 넣습니다.
    statements = [create_table(columns)] + insert_sql(rows, columns)
    SQL_TMP.parent.mkdir(parents=True, exist_ok=True)
    SQL_TMP.write_text("\n".join(statements) + "\n",
                       encoding="utf-8", newline="\n")
    run_d1_file(SQL_TMP)
    print("적재 완료 %s행" % format(len(rows), ","))
    return 0


if __name__ == "__main__":
    sys.exit(main())
