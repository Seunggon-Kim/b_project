# -*- coding: utf-8 -*-
"""KBO 퓨처스리그 경기 일정/결과 수집 (koreabaseball.com 공식 GameList.aspx 파싱).

본 리그(/schedule)는 Naver 스포츠 API 프록시지만, Naver는 퓨처스를 제공하지 않으므로
퓨처스는 KBO 공식 페이지를 직접 파싱해 DB(futures_games)에 적재한다.

기초 데이터 계층:
  - futures_teams : 팀 마스터 (코드/표기명/엠블럼/디비전/유형) - 시드값으로 채움
  - futures_games : 경기 일정/결과 - GameList.aspx 파싱 후 upsert

사용:
  py -3 futures_schedule.py            # DB 셋업 + 이번 달 적재
  py -3 futures_schedule.py 2026-04    # 특정 월 적재(백필)
  py -3 futures_schedule.py 2026-04 2026-05 2026-06
  py -3 futures_schedule.py --setup-only
"""
import os
import re
import sys
import html as _html
import sqlite3
import datetime
import urllib.parse
import urllib.request

BASE = "https://www.koreabaseball.com/Futures/Schedule/GameList.aspx"
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "database", "kbo_stats.db")
UA = {"User-Agent": "Mozilla/5.0"}

# ASP.NET 포스트백 컨트롤 이름 (백필용)
_F_YEAR = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlYear"
_F_MONTH = "ctl00$ctl00$ctl00$cphContents$cphContents$cphContents$ddlMonth"

# ===== 퓨처스 팀 마스터 =====
# code        : KBO gameId 2자리 코드
# kbo_name    : KBO 페이지 표기명 (파싱 매칭 키)
# display     : 대시보드 표기명
# emblem      : dashboard_js/assets/logos/{emblem}.png (없으면 None -> UI 텍스트 폴백)
# division    : 북부 / 남부 / 교류
# team_type   : franchise(1군 산하 2군) / independent(독립) / exhibition(교류전)
FUTURES_TEAMS = [
    # 북부
    ("SM", "상무", "상무", "SM", "북부", "independent"),
    ("HH", "한화", "한화", "HH", "북부", "franchise"),
    ("LG", "LG", "LG", "LG", "북부", "franchise"),
    ("WO", "고양", "키움", "WO", "북부", "franchise"),   # 고양 = 키움 2군 홈구장
    ("OB", "두산", "두산", "OB", "북부", "franchise"),
    ("SK", "SSG", "SSG", "SK", "북부", "franchise"),
    # 남부
    ("UL", "울산", "울산", "UL", "남부", "independent"),
    ("LT", "롯데", "롯데", "LT", "남부", "franchise"),
    ("HT", "KIA", "KIA", "HT", "남부", "franchise"),
    ("NC", "NC", "NC", "NC", "남부", "franchise"),
    ("SS", "삼성", "삼성", "SS", "남부", "franchise"),
    ("KT", "KT", "KT", "KT", "남부", "franchise"),
    # 교류전(외부)
    ("SO", "소프트뱅크", "소프트뱅크", "SO", "교류", "exhibition"),
]
# 표기명 -> 코드 (예정 경기 synthetic gameId 생성용)
NAME_TO_CODE = {t[1]: t[0] for t in FUTURES_TEAMS}


# ===== DB 셋업 =====
def setup_db(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_teams (
            code         TEXT PRIMARY KEY,
            kbo_name     TEXT NOT NULL,
            display_name TEXT NOT NULL,
            emblem_code  TEXT,
            division     TEXT,
            team_type    TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS futures_games (
            game_id    TEXT PRIMARY KEY,   -- KBO gameId (예정 경기는 동일 포맷 synthetic)
            game_date  TEXT NOT NULL,      -- YYYY-MM-DD
            game_time  TEXT,              -- HH:MM
            season     INTEGER NOT NULL,
            series_id  INTEGER DEFAULT 0,  -- 0=정규 퓨처스, 10=교류전
            away_code  TEXT NOT NULL,
            home_code  TEXT NOT NULL,
            away_name  TEXT NOT NULL,
            home_name  TEXT NOT NULL,
            away_score INTEGER,            -- NULL=미실시/예정
            home_score INTEGER,
            stadium    TEXT,
            status     TEXT,              -- scheduled / final / canceled
            updated_at TEXT
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_futures_games_date ON futures_games(game_date)")
    # 팀 마스터 시드 (표기명/엠블럼 갱신 가능하도록 REPLACE)
    cur.executemany(
        "INSERT OR REPLACE INTO futures_teams "
        "(code, kbo_name, display_name, emblem_code, division, team_type) "
        "VALUES (?,?,?,?,?,?)",
        FUTURES_TEAMS,
    )
    conn.commit()


# ===== 파싱 =====
def _txt(s):
    return re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def _cell(row, cls):
    """row HTML에서 class=cls 인 첫 td의 내부 HTML."""
    m = re.search(r'<td[^>]*class="%s"[^>]*>(.*?)</td>' % cls, row, re.S)
    return m.group(1) if m else ""


def parse_gamelist(html_text, year):
    """GameList.aspx HTML -> 경기 dict 리스트."""
    m = re.search(r'udpRecord".*?<tbody>(.*?)</tbody>', html_text, re.S)
    tbody = m.group(1) if m else html_text
    rows = re.findall(r"<tr[^>]*>.*?</tr>", tbody, re.S)

    games = []
    cur_date = None
    seq = {}  # (date,away,home) -> 더블헤더 시퀀스
    for row in rows:
        dm = re.search(r'lblGameDate[^>]*>(.*?)</span>', row, re.S)
        if dm:
            dt = _txt(dm.group(1))            # "06.01(월)"
            mo = re.match(r"(\d{2})\.(\d{2})", dt)
            if mo:
                cur_date = "%d-%s-%s" % (year, mo.group(1), mo.group(2))
        if cur_date is None:
            continue

        play = _cell(row, "play")
        if "vs" not in play:
            continue

        # 점수(em 내부 숫자, 순서 = away,home). 예정 경기는 숫자 없음.
        em = re.search(r"<em>(.*?)</em>", play, re.S)
        nums = re.findall(r"<span[^>]*>(\d+)</span>", em.group(1)) if em else []
        # 팀명: em 제거 후 남는 span 2개 = away, home
        no_em = re.sub(r"<em>.*?</em>", "|", play, flags=re.S)
        names = [_txt(x) for x in re.findall(r"<span[^>]*>(.*?)</span>", no_em, re.S)]
        names = [n for n in names if n]
        if len(names) < 2:
            continue
        away_name, home_name = names[0], names[1]
        away_score = int(nums[0]) if len(nums) >= 2 else None
        home_score = int(nums[1]) if len(nums) >= 2 else None

        time_ = _txt(_cell(row, "time"))
        stadium = _txt(_cell(row, "ballpark"))
        if stadium == "-":
            stadium = ""

        # gameId: relay 셀 href. 없으면 synthetic (KBO 동일 포맷).
        relay = _cell(row, "relay")
        gm = re.search(r"gameId=([0-9A-Z]+)", relay)
        ac = NAME_TO_CODE.get(away_name, away_name[:2].upper())
        hc = NAME_TO_CODE.get(home_name, home_name[:2].upper())
        if gm:
            game_id = gm.group(1)
            ac, hc = game_id[8:10], game_id[10:12]
        else:
            ymd = cur_date.replace("-", "")
            key = (ymd, ac, hc)
            n = seq.get(key, 0)
            seq[key] = n + 1
            game_id = "%s%s%s%d" % (ymd, ac, hc, n)

        # 시리즈: 소프트뱅크(SO) 관여 = 교류전(10)
        series_id = 10 if ("SO" in (ac, hc)) else 0
        # 상태
        cancel = ("취소" in _cell(row, "etc")) or ("취소" in stadium)
        if cancel:
            status = "canceled"
        elif away_score is not None:
            status = "final"
        else:
            status = "scheduled"

        games.append({
            "game_id": game_id, "game_date": cur_date, "game_time": time_,
            "season": year, "series_id": series_id,
            "away_code": ac, "home_code": hc,
            "away_name": away_name, "home_name": home_name,
            "away_score": away_score, "home_score": home_score,
            "stadium": stadium, "status": status,
        })
    return games


# ===== 수집(현재월 GET / 임의월 포스트백) =====
def _get(url, data=None):
    req = urllib.request.Request(url, data=data, headers=UA)
    return urllib.request.urlopen(req, timeout=25).read().decode("utf-8", "replace")


def _hidden(html_text, name):
    m = re.search(r'name="%s"[^>]*value="([^"]*)"' % re.escape(name), html_text)
    return m.group(1) if m else ""


def fetch_month(year, month):
    """(year, month) 퓨처스 일정 HTML. 현재월은 기본 GET, 그 외는 ASP.NET 포스트백."""
    today = datetime.date.today()
    page = _get(BASE)
    if year == today.year and month == today.month:
        return page
    form = {
        "__EVENTTARGET": _F_MONTH,
        "__EVENTARGUMENT": "",
        "__VIEWSTATE": _hidden(page, "__VIEWSTATE"),
        "__VIEWSTATEGENERATOR": _hidden(page, "__VIEWSTATEGENERATOR"),
        "__EVENTVALIDATION": _hidden(page, "__EVENTVALIDATION"),
        _F_YEAR: str(year),
        _F_MONTH: str(month),
    }
    body = urllib.parse.urlencode(form).encode("utf-8")
    return _get(BASE, data=body)


def load_to_db(conn, games):
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO futures_games
          (game_id, game_date, game_time, season, series_id,
           away_code, home_code, away_name, home_name,
           away_score, home_score, stadium, status, updated_at)
        VALUES
          (:game_id, :game_date, :game_time, :season, :series_id,
           :away_code, :home_code, :away_name, :home_name,
           :away_score, :home_score, :stadium, :status, :updated_at)
        ON CONFLICT(game_id) DO UPDATE SET
          game_date=excluded.game_date, game_time=excluded.game_time,
          series_id=excluded.series_id,
          away_score=excluded.away_score, home_score=excluded.home_score,
          stadium=excluded.stadium, status=excluded.status,
          updated_at=excluded.updated_at
    """, [dict(g, updated_at=now) for g in games])
    conn.commit()
    return len(games)


def ingest_month(conn, year, month):
    games = parse_gamelist(fetch_month(year, month), year)
    n = load_to_db(conn, games) if games else 0
    return n, games


def main(argv):
    conn = sqlite3.connect(DB_PATH)
    setup_db(conn)
    print("[setup] futures_teams seeded: %d teams; futures_games ready" %
          conn.execute("SELECT COUNT(*) FROM futures_teams").fetchone()[0])

    if "--setup-only" in argv:
        conn.close()
        return

    months = [a for a in argv if re.match(r"^\d{4}-\d{2}$", a)]
    if not months:
        t = datetime.date.today()
        months = ["%d-%02d" % (t.year, t.month)]

    total = 0
    for ym in months:
        y, m = int(ym[:4]), int(ym[5:7])
        n, games = ingest_month(conn, y, m)
        sched = sum(1 for g in games if g["status"] == "scheduled")
        final = sum(1 for g in games if g["status"] == "final")
        total += n
        print("[%s] %d games (final=%d, scheduled=%d)" % (ym, n, final, sched))
    print("[done] upserted %d rows -> %s" % (total, DB_PATH))
    conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
