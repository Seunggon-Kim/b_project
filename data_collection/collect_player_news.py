# -*- coding: utf-8 -*-
"""선수별 뉴스를 모아 D1 적재용 SQL 을 만듭니다.

왜 Actions 에서 도는가
----------------------
구글 뉴스 RSS 는 Cloudflare 엣지에서 막힙니다. 다섯 번에 한 번만 200 이 오고
나머지는 Google 의 `Sorry...` 봇 차단 페이지입니다. 엣지 IP 를 전 세계가
공유해 이미 한도가 차 있기 때문입니다. 같은 URL 을 GitHub Actions 러너에서
부르면 다섯 번 모두 정상 응답합니다(설계 문서 §7 위험 2 판정).

그래서 Worker 가 요청 때마다 구글을 부르는 대신, Actions 가 하루 한 번 모아
D1 에 넣고 Worker 는 D1 만 읽습니다. 응답도 빨라집니다.

정확도
------
검색 결과에는 이름이 제목에 없는 기사, 같은 이름의 다른 선수 기사가 섞입니다.
`player_news_filter` 가 그것을 거릅니다. 실측에서 112건 중 34건을 걸렀습니다.

대상 범위
--------
등록 선수 585명 전체가 아니라 **해당 시즌 출전 기록이 있는 선수**만 봅니다
(타자 50타석 이상 또는 투수 10경기 이상, 약 389명). 뉴스가 날 만한 선수는
모두 들어오면서 구글에 보내는 요청은 3분의 2로 줄어듭니다.

사용법
------
    py data_collection/collect_player_news.py --limit 5 --dry-run   # 맛보기
    py data_collection/collect_player_news.py                       # 전체
    npx wrangler d1 execute kbo-stats --remote --file=migration/out/news.sql
"""
import argparse
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_collection.player_news_filter import (  # noqa: E402
    clean_title, dedupe, is_news_source, is_relevant, team_tokens)

DB = os.environ.get("KBO_DB") or str(
    Path(__file__).resolve().parent.parent / "database" / "kbo_stats.db")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0 Safari/537.36")

# 선수 한 명당 남길 기사 수입니다. 원본 api/main.py 가 5건을 보여 줍니다.
KEEP = 5

# 요청 간격입니다. 구글이 자동화 트래픽을 탐지하지 않도록 여유를 둡니다.
DELAY_SEC = 1.5

# 대상 선수를 고르는 기준입니다.
#
# 처음에는 타석 50 이상 또는 등판 10경기 이상으로 잡아 389명이었습니다.
# 그러다 LG 김민수(타석 13)가 빠지는 것을 발견했습니다. 사생활 논란으로
# 기사가 12건이나 나오는 선수인데도요. **출전이 적은 것과 뉴스가 없는 것은
# 다릅니다.** 부상·논란·이적처럼 경기 밖 소식이 오히려 많은 경우가 있습니다.
#
# 확인해 보니 등록 선수 585명 전원이 출전 기록을 갖고 있어, 하한을 둘 이유가
# 없었습니다. 전원을 봅니다. 585명 x 1.5초 = 약 15분이라 Actions 에서 감당
# 가능합니다.
MIN_PA = 0
MIN_GAMES = 0


def kst_now():
    return datetime.now(timezone.utc) + timedelta(hours=9)


# --- 선수 목록 원천 -------------------------------------------------------
#
# 로컬에서는 SQLite 를 읽고, GitHub Actions 에서는 D1 을 읽습니다.
#
# 러너에는 `database/kbo_stats.db` 가 없습니다. 127MB 라 git 에 두지 않기
# 때문입니다. 처음에 이 사실을 놓쳐 워크플로가 `unable to open database file`
# 로 죽었습니다. D1 에 같은 표가 이미 적재돼 있으므로 그쪽을 읽습니다.


def d1_query(sql, db_name="kbo-stats"):
    """`wrangler d1 execute --json` 으로 D1 에 질의합니다.

    출력에 진행 메시지가 섞이므로 첫 `[` 부터 잘라 파싱합니다.
    한글은 wrangler 가 UTF-8 로 내보내므로 인코딩을 명시해 읽습니다.
    """
    cmd = ('npx wrangler d1 execute %s --remote --command "%s" --yes --json'
           % (db_name, sql.replace('"', '\\"')))
    r = subprocess.run(cmd, capture_output=True, shell=True)
    out = r.stdout.decode("utf-8", "replace")
    if r.returncode != 0:
        err = r.stderr.decode("utf-8", "replace")
        raise RuntimeError((err or out)[:600])
    i = out.find("[")
    if i < 0:
        raise RuntimeError("JSON 을 찾지 못했습니다: %s" % out[:300])
    data = json.loads(out[i:])
    rows = []
    for item in data:
        if isinstance(item, dict):
            rows.extend(item.get("results", []))
    return rows


class D1Source:
    """D1 을 SQLite 커넥션처럼 쓰기 위한 얇은 껍데기입니다."""

    def __init__(self, db_name="kbo-stats"):
        self.db_name = db_name

    def query(self, sql):
        return d1_query(sql, self.db_name)


class SqliteSource:
    def __init__(self, path):
        self.conn = sqlite3.connect(
            "file:%s?mode=ro" % path.replace("\\", "/"), uri=True)
        self.conn.row_factory = sqlite3.Row

    def query(self, sql):
        return [dict(r) for r in self.conn.execute(sql)]

    def close(self):
        self.conn.close()


def target_players(source, season, limit=None):
    """뉴스를 모을 선수 목록을 돌려줍니다.

    해당 시즌 출전 기록이 있는 선수를 봅니다. MIN_PA·MIN_GAMES 가 0 이면
    한 번이라도 나온 선수 전원입니다. 기준을 왜 0 으로 두는지는 그 상수의
    주석을 보십시오.

    D1 과 SQLite 를 함께 쓰려고 바인딩 대신 값을 문자열에 넣습니다. 세 값
    모두 이 파일 안에서 정한 정수라 외부 입력이 섞이지 않습니다.
    """
    sql = """
        SELECT p.player_id, p.player_name, p.team_id, t.team_name
        FROM players p
        LEFT JOIN teams t ON p.team_id = t.team_id
        WHERE p.player_id IN (
            SELECT player_id FROM kbo_official_batter_stats
            WHERE season = %d AND plate_appearance >= %d
            UNION
            SELECT player_id FROM kbo_official_pitcher_stats
            WHERE season = %d AND games >= %d
        )
        ORDER BY p.player_name, p.player_id
    """ % (int(season), int(MIN_PA), int(season), int(MIN_GAMES))
    rows = source.query(" ".join(sql.split()))
    return rows[:limit] if limit else rows


def ambiguous_names(source):
    """이름이 겹치는 선수 이름 집합입니다. 585명 중 20조가 있습니다."""
    rows = source.query(
        "SELECT player_name FROM players GROUP BY player_name "
        "HAVING COUNT(*) > 1")
    return {r["player_name"] for r in rows}


def latest_season(source):
    rows = source.query(
        "SELECT MAX(season) AS s FROM kbo_official_batter_stats")
    if rows and rows[0].get("s"):
        return rows[0]["s"]
    return kst_now().year


def fetch_rss(query, timeout=20, retries=2):
    """구글 뉴스 RSS 를 가져옵니다. 일시 실패는 한 번 더 시도합니다."""
    url = ("https://news.google.com/rss/search?q=%s&hl=ko&gl=KR&ceid=KR:ko"
           % urllib.parse.quote(query))
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = r.read().decode("utf-8", "replace")
            if "<rss" not in body[:600]:
                last = "차단 페이지로 보입니다"
            else:
                return body, None
        except Exception as exc:
            last = "%s: %s" % (type(exc).__name__, exc)
        if attempt < retries:
            time.sleep(2 + attempt * 2)
    return None, last


def parse_items(xml):
    """RSS 에서 (제목, 링크, 언론사, 발행일) 을 뽑습니다."""
    out = []
    for block in re.findall(r"<item[^>]*>([\s\S]*?)</item>", xml):
        def tag(name):
            m = re.search(r"<%s[^>]*>([\s\S]*?)</%s>" % (name, name), block)
            if not m:
                return ""
            v = re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1))
            return v.strip()

        raw_title = tag("title")
        body, press_from_title = clean_title(raw_title)
        out.append({
            "title": body,
            "link": tag("link"),
            # <source> 가 있으면 그쪽이 정확합니다. 없으면 제목 꼬리를 씁니다.
            "press": tag("source") or press_from_title or "Google News",
            "pub_date": tag("pubDate"),
        })
    return out


def sql_literal(v):
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def main():
    ap = argparse.ArgumentParser(description="선수 뉴스를 모아 D1 SQL 을 만듭니다")
    ap.add_argument("--db", default=DB)
    ap.add_argument("--source", choices=["sqlite", "d1"], default=None,
                    help="선수 목록을 어디서 읽을지. 기본은 로컬 DB 파일이 "
                         "있으면 sqlite, 없으면 d1 입니다")
    ap.add_argument("--d1-name", default="kbo-stats")
    ap.add_argument("--season", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None,
                    help="앞에서 N 명만 (맛보기용)")
    ap.add_argument("--out", default="migration/out/news.sql")
    ap.add_argument("--delay", type=float, default=DELAY_SEC)
    ap.add_argument("--dry-run", action="store_true",
                    help="SQL 을 쓰지 않고 결과만 출력합니다")
    args = ap.parse_args()

    # 원천을 고릅니다. GitHub Actions 러너에는 로컬 DB 파일이 없어(127MB 라
    # git 에 두지 않습니다) 자동으로 D1 을 씁니다.
    mode = args.source
    if mode is None:
        mode = "sqlite" if os.path.exists(args.db) else "d1"

    if mode == "sqlite":
        source = SqliteSource(args.db)
    else:
        source = D1Source(args.d1_name)

    season = args.season or latest_season(source)
    dupes = ambiguous_names(source)
    players = target_players(source, season, args.limit)
    if hasattr(source, "close"):
        source.close()

    print("원천 %s, 시즌 %s, 대상 선수 %d명, 이름 겹침 %d조" % (
        mode, season, len(players), len(dupes)))
    print()
    if not players:
        print("대상 선수가 없습니다. 원천을 확인하십시오.")
        return 1

    fetched_at = kst_now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    n_ok = n_empty = n_fail = 0
    total_seen = total_kept = 0

    for i, p in enumerate(players, start=1):
        name = p["player_name"]
        tokens = team_tokens(p["team_id"], p["team_name"])
        amb = name in dupes
        query = "%s %s 야구" % (p["team_name"] or p["team_id"] or "", name)

        xml, err = fetch_rss(query)
        if xml is None:
            n_fail += 1
            print("[%d/%d] %-8s 실패 %s" % (i, len(players), name, err))
            time.sleep(args.delay)
            continue

        items = dedupe(parse_items(xml))
        kept = []
        for it in items:
            total_seen += 1
            if not is_news_source(it["press"]):
                continue
            ok, _why = is_relevant(it["title"], "", name, tokens, amb)
            if ok:
                kept.append(it)
                if len(kept) >= KEEP:
                    break
        total_kept += len(kept)

        if kept:
            n_ok += 1
        else:
            n_empty += 1

        for rank, it in enumerate(kept, start=1):
            rows.append((p["player_id"], rank, it["title"], it["link"],
                         it["press"], it["pub_date"], fetched_at))

        if i % 25 == 0 or args.limit:
            print("[%d/%d] %-8s %d건" % (i, len(players), name, len(kept)))
        time.sleep(args.delay)

    print()
    print("선수 %d명: 기사 있음 %d, 없음 %d, 수집 실패 %d" % (
        len(players), n_ok, n_empty, n_fail))
    if total_seen:
        print("검사 %d건 중 %d건 통과 (%.0f%%)" % (
            total_seen, total_kept, 100.0 * total_kept / total_seen))

    if args.dry_run:
        print()
        print("[미리보기] SQL 을 쓰지 않았습니다.")
        for r in rows[:10]:
            print("  %s #%d %s | %s" % (r[0], r[1], r[2][:44], r[4][:12]))
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        # 통째로 갈아 끼웁니다. 선수마다 지우고 넣으면 문이 두 배가 됩니다.
        f.write("DELETE FROM player_news;\n")
        for r in rows:
            f.write("INSERT INTO player_news "
                    "(player_id, rank, title, link, press, pub_date, fetched_at) "
                    "VALUES (%s);\n" % ",".join(sql_literal(v) for v in r))
    print()
    print("%s 에 %d행을 썼습니다 (%.1fKB)" % (
        out, len(rows), out.stat().st_size / 1024))
    return 0


if __name__ == "__main__":
    sys.exit(main())
