"""
KBO Baseball Analytics API
FastAPI backend for JavaScript dashboard - v1.0.7
Fixed: API endpoint for Pitch Usage, encoding issues, and indentation
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
import sqlite3
from pathlib import Path
from typing import Optional, List
import datetime
import traceback
import sys
import csv
import io
import requests
import xml.etree.ElementTree as ET
import urllib.parse

app = FastAPI(title="KBO Analytics API", version="1.0.7")

# CORS Settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB Path
DB_PATH = Path(__file__).parent.parent / 'database' / 'kbo_stats.db'

def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"DB Connection Error: {e}")
        raise

def robust_player_lookup(cur, player_id):
    """Try lookup by string and then int if numeric"""
    cur.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
    row = cur.fetchone()
    if row: return dict(row)
    
    if str(player_id).isdigit():
        cur.execute("SELECT * FROM players WHERE player_id = ?", (int(player_id),))
        row = cur.fetchone()
        if row: return dict(row)
    return None

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "type": type(exc).__name__,
            "traceback": traceback.format_exc()
        }
    )

@app.get("/")
async def root():
    return {"message": "KBO Baseball Analytics API Active", "version": "1.0.7"}

@app.get("/dashboard/stats")
async def get_dashboard_stats():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        def one(q):
            try:
                cur.execute(q)
                r = cur.fetchone()
                return r[0] if r else 0
            except Exception:
                return 0
        games = one("SELECT COUNT(DISTINCT gameID) FROM play_by_play WHERE substr(gameID,1,4) GLOB '20[0-2][0-9]'")
        plays = one("SELECT COUNT(*) FROM play_by_play")
        batters = one("SELECT COUNT(DISTINCT player_id) FROM kbo_official_batter_stats")
        pitchers = one("SELECT COUNT(DISTINCT player_id) FROM kbo_official_pitcher_stats")
        players = one("SELECT COUNT(*) FROM players")
        teams = one("SELECT COUNT(*) FROM teams")
        smin = one("SELECT MIN(substr(gameID,1,4)) FROM play_by_play WHERE substr(gameID,1,4) GLOB '20[0-2][0-9]'")
        smax = one("SELECT MAX(substr(gameID,1,4)) FROM play_by_play WHERE substr(gameID,1,4) GLOB '20[0-2][0-9]'")
        seasons = str(smin) if smin == smax else f"{smin}~{smax}"
        conn.close()
        return {"games": games, "plays": plays, "batters": batters, "pitchers": pitchers,
                "players": players, "teams": teams, "seasons": seasons, "status": "ok"}
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/teams")
async def get_teams():
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams ORDER BY team_name")
    teams = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"teams": teams}

@app.get("/players/search")
async def search_players(q: str):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM players WHERE player_name LIKE ? LIMIT 50", (f'%{q}%',))
    players = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"players": players}

@app.get("/players/{player_id}")
async def get_player_info(player_id: str):
    conn = get_db_connection()
    cur = conn.cursor()
    
    player = robust_player_lookup(cur, player_id)
    if not player:
        conn.close()
        raise HTTPException(status_code=404, detail="Player not found")
    
    db_pid = player['player_id']
    
    # Batter Seasons
    cur.execute("SELECT *, (single + double + triple + home_run) as hits, on_base_plus_slugging as ops FROM kbo_official_batter_stats WHERE player_id = ? ORDER BY season DESC", (db_pid,))
    player['batter_seasons'] = [dict(r) for r in cur.fetchall()]
    
    # Pitcher Seasons
    cur.execute("SELECT *, walks_plus_hits_per_inning_pitched as whip FROM kbo_official_pitcher_stats WHERE player_id = ? ORDER BY season DESC", (db_pid,))
    player['pitcher_seasons'] = [dict(r) for r in cur.fetchall()]
    
    conn.close()
    return player

@app.get("/players/{player_id}/news")
async def get_player_news(player_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT p.player_name, t.team_name 
            FROM players p 
            LEFT JOIN teams t ON p.team_id = t.team_id 
            WHERE p.player_id = ?
        """, (player_id,))
        player = cur.fetchone()
        if not player and str(player_id).isdigit():
            cur.execute("""
                SELECT p.player_name, t.team_name 
                FROM players p 
                LEFT JOIN teams t ON p.team_id = t.team_id 
                WHERE p.player_id = ?
            """, (int(player_id),))
            player = cur.fetchone()
             
        conn.close()
        
        if not player:
            return {"player_name": "Unknown", "news": [], "error": "Player lookup failed"}
            
        player_name = player['player_name']
        team_name = player['team_name'] or ""
        
        query = f"{team_name} {player_name} 야구"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
        
        response = requests.get(url, timeout=5)
        root = ET.fromstring(response.text)
        items = root.findall('.//item')
        
        news_items = []
        for item in items[:5]:
            title_node = item.find('title')
            title = title_node.text if title_node is not None else "No Title"
            link_node = item.find('link')
            link = link_node.text if link_node is not None else "#"
            source_node = item.find('source')
            press = source_node.text if source_node is not None else "Google News"
            
            if " - " in title:
                title = title.rsplit(" - ", 1)[0]
                
            news_items.append({
                "title": title,
                "link": link,
                "press": press,
                "desc": "",
                "thumb": None
            })
            
        return {"player_name": player_name, "news": news_items}
        
    except Exception as e:
        print(f"Google News fetch error for {player_id}: {str(e)}")
        return {"player_name": "Error", "news": [], "error": str(e)}

@app.get("/players/{player_id}/arsenal")
async def get_pitch_arsenal(player_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        player = robust_player_lookup(cur, player_id)
        if not player:
            conn.close()
            return {"error": "Player not found"}
        
        db_pid = player['player_id']

        sql = """
            SELECT pbp.pitch_type, pbp.px, pbp.pz, pbp.speed, pbp.pitch_result, pbp.pfx_x, pbp.pfx_z
            FROM play_by_play pbp
            JOIN games g ON pbp.gameID = g.game_id
            WHERE pbp.pitcher_ID = ? 
            AND g.season = 2025
            AND pbp.px IS NOT NULL 
            AND pbp.pz IS NOT NULL
            AND pbp.pitch_type IS NOT NULL
            AND pbp.pitch_type NOT IN ('', '-', 'null')
        """
        cur.execute(sql, (db_pid,))
        rows = cur.fetchall()
        
        arsenal = [dict(row) for row in rows]
        conn.close()
        
        return {"player_id": player_id, "arsenal": arsenal, "count": len(arsenal)}
        
    except Exception as e:
        print(f"Arsenal fetch error for {player_id}: {str(e)}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/players/{player_id}/usage")
async def get_pitch_usage(player_id: str):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        player = robust_player_lookup(cur, player_id)
        if not player:
            conn.close()
            return {"error": "Player not found"}
        
        db_pid = player['player_id']

        sql = """
            SELECT pbp.pitch_type, pbp.stands, pbp.throws
            FROM play_by_play pbp
            JOIN games g ON pbp.gameID = g.game_id
            WHERE pbp.pitcher_ID = ? 
            AND g.season = 2025
            AND pbp.pitch_type IS NOT NULL
            AND pbp.pitch_type NOT IN ('', '-', 'null')
        """
        cur.execute(sql, (db_pid,))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"player_id": player_id, "usage": []}

        # Abbreviation Map
        abb_map = {
            '너클볼': 'KN', '스위퍼': 'ST', '슬라이더': 'SL', '슬러브': 'SV',
            '싱커': 'SI', '직구': 'FF', '체인지업': 'CH', '커브': 'CU',
            '커터': 'FC', '투심': 'SI', '포크': 'FS'
        }

        pitch_counts = {} # {type: {L: 0, R: 0, Total: 0}}
        total_l = 0
        total_r = 0
        total_all = 0

        for row in rows:
            ptype = row['pitch_type']
            stands = row['stands'] or '우'
            throws = row['throws'] or '우'
            
            actual_stands = stands
            if stands == '양':
                if throws == '우': actual_stands = '좌'
                elif throws == '좌': actual_stands = '우'
            
            if ptype not in pitch_counts:
                pitch_counts[ptype] = {'L': 0, 'R': 0, 'Total': 0}
            
            pitch_counts[ptype]['Total'] += 1
            total_all += 1
            
            if actual_stands == '좌':
                pitch_counts[ptype]['L'] += 1
                total_l += 1
            else: # Defaults to R if not L
                pitch_counts[ptype]['R'] += 1
                total_r += 1

        result = []
        for ptype, counts in pitch_counts.items():
            result.append({
                "pitch_type": ptype,
                "abbreviation": abb_map.get(ptype, ptype[:2].upper()),
                "count": counts['Total'],
                "usage_all": round(counts['Total'] / total_all * 100, 1) if total_all > 0 else 0,
                "usage_l": round(counts['L'] / total_l * 100, 1) if total_l > 0 else 0,
                "usage_r": round(counts['R'] / total_r * 100, 1) if total_r > 0 else 0
            })
        
        result.sort(key=lambda x: x['usage_all'], reverse=True)

        return {
            "player_id": player_id,
            "total_pitches": total_all,
            "total_l": total_l,
            "total_r": total_r,
            "usage": result
        }
    except Exception as e:
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/stats/batters")
async def get_batter_stats(season: int = 2025, limit: int = 100, min_pa: int = 0, team_ids: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT b.*, p.player_name, p.team_id, p.position, b.on_base_plus_slugging as ops 
        FROM kbo_official_batter_stats b
        JOIN players p ON b.player_id = p.player_id
        WHERE b.season = ? AND b.plate_appearance >= ?
    """
    params = [season, min_pa]
    
    if team_ids:
        ids = [t.strip() for t in team_ids.split(',') if t.strip()]
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            query += f" AND p.team_id IN ({placeholders})"
            params.extend(ids)
        
    query += " ORDER BY b.batting_average DESC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, tuple(params))
    data = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"batters": data, "season": season, "min_pa": min_pa, "team_ids": team_ids}

@app.get("/stats/pitchers")
async def get_pitcher_stats(season: int = 2025, limit: int = 100, min_ip: int = 0, team_ids: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    query = """
        SELECT ps.*, p.player_name, p.team_id, ps.walks_plus_hits_per_inning_pitched as whip
        FROM kbo_official_pitcher_stats ps
        JOIN players p ON ps.player_id = p.player_id
        WHERE ps.season = ? AND CAST(ps.innings_pitched AS REAL) >= ?
    """
    params = [season, min_ip]
    
    if team_ids:
        ids = [t.strip() for t in team_ids.split(',') if t.strip()]
        if ids:
            placeholders = ','.join(['?'] * len(ids))
            query += f" AND p.team_id IN ({placeholders})"
            params.extend(ids)
        
    query += " ORDER BY ps.earned_run_average ASC LIMIT ?"
    params.append(limit)
    
    cur.execute(query, tuple(params))
    data = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"pitchers": data, "season": season, "min_ip": min_ip, "team_ids": team_ids}

@app.get("/games")
async def get_games(season: int = 2025, limit: int = 50):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT g.*, g.game_date as date, t1.team_name as home_team, t2.team_name as away_team
        FROM games g
        LEFT JOIN teams t1 ON g.home_team_id = t1.team_id
        LEFT JOIN teams t2 ON g.away_team_id = t2.team_id
        WHERE g.season = ?
        ORDER BY g.game_date DESC
        LIMIT ?
    """, (season, limit))
    data = [dict(row) for row in cur.fetchall()]
    conn.close()
    return {"games": data, "season": season}

# ===== KBO 경기 일정/결과 (Naver 스포츠 API 프록시) =====
import time as _time
import concurrent.futures as _futures

_SCHEDULE_CACHE = {}
_SCHEDULE_TTL = 30  # seconds


def _kbo_fetch_json(url, timeout=8):
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _kbo_game_meta(game_id):
    try:
        return _kbo_fetch_json("https://api-gw.sports.naver.com/schedule/games/" + game_id)
    except Exception:
        return None


def _kbo_normalize_game(meta):
    g = (meta or {}).get("result", {}).get("game", {})
    if not g:
        return None
    status = g.get("statusCode", "") or ""
    final = status in ("RESULT", "ENDED")
    live = status in ("LIVE", "PLAYING", "STARTED")
    show_score = final or live
    dt = g.get("gameDateTime", "") or ""
    time_str = dt[11:16] if len(dt) >= 16 else ""

    def _score(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None

    def _team(prefix):
        return {
            "name": g.get(prefix + "TeamName", "") or "",
            "code": g.get(prefix + "TeamCode", "") or "",
            "emblem": g.get(prefix + "TeamEmblemUrl", "") or "",
            "score": _score(g.get(prefix + "TeamScore")) if show_score else None,
            "starter": g.get(prefix + "StarterName", "") or "",
        }

    return {
        "gameId": g.get("gameId"),
        "datetime": dt,
        "time": time_str,
        "stadium": g.get("stadium", "") or "",
        "statusCode": status,
        "statusInfo": g.get("statusInfo", "") or "",
        "currentInning": g.get("currentInning", "") or "",
        "broadChannel": g.get("broadChannel", "") or "",
        "cancel": bool(g.get("cancel")),
        "final": final,
        "live": live,
        "showScore": show_score,
        "winner": g.get("winner", "") or "",
        "home": _team("home"),
        "away": _team("away"),
    }


@app.get("/schedule")
async def get_schedule(date: str = None):
    """KBO 경기 일정/결과 (Naver 스포츠 API 프록시). date=YYYY-MM-DD (미지정 시 KST 오늘)."""
    try:
        if not date:
            kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
            date = kst.strftime("%Y-%m-%d")
        target = date.replace("-", "")

        cached = _SCHEDULE_CACHE.get(date)
        if cached and (_time.time() - cached[0] < _SCHEDULE_TTL):
            return cached[1]

        cal = _kbo_fetch_json(
            "https://api-gw.sports.naver.com/schedule/calendar"
            "?upperCategoryId=kbaseball&categoryIds=kbo&date=" + date
        )
        gids = []
        for d in cal.get("result", {}).get("dates", []):
            dkey = str(d.get("ymd") or d.get("date") or "").replace("-", "")
            if dkey == target:
                for gi in (d.get("gameInfos") or []):
                    if gi.get("gameId"):
                        gids.append(gi.get("gameId"))
                break

        games = []
        if gids:
            with _futures.ThreadPoolExecutor(max_workers=8) as ex:
                metas = list(ex.map(_kbo_game_meta, gids))
            for m in metas:
                ng = _kbo_normalize_game(m)
                if ng:
                    games.append(ng)
            games.sort(key=lambda x: ((x.get("datetime") or ""), (x.get("gameId") or "")))

        result = {"date": date, "count": len(games), "games": games}
        _SCHEDULE_CACHE[date] = (_time.time(), result)
        return result
    except Exception as e:
        return {"date": date, "count": 0, "games": [], "error": str(e)}


# ===== KBO 팀 순위 (koreabaseball.com 공식 TeamRank.aspx 파싱) =====
import re as _re
import html as _html

_STANDINGS_CACHE = {}
_STANDINGS_TTL = 300  # seconds (순위는 자주 바뀌지 않음)

# KBO 표기명 -> dashboard 엠블럼 코드(assets/logos/{code}.png)
_KBO_TEAM_CODE = {
    "LG": "LG", "KT": "KT", "두산": "OB", "삼성": "SS", "KIA": "HT",
    "롯데": "LT", "SSG": "SK", "NC": "NC", "키움": "WO", "한화": "HH",
}


@app.get("/standings")
async def get_standings():
    """KBO 정규시즌 팀 순위 (koreabaseball.com 공식 TeamRank.aspx 스크래핑). 5분 캐시.
    컬럼: 순위, 팀명, 경기, 승, 패, 무, 승률, 게임차, 최근10경기, 연속, 홈, 방문.
    순위표만 파싱(summary="순위..."); 팀간승패표(summary="팀간승패표")는 제외."""
    try:
        cached = _STANDINGS_CACHE.get("rank")
        if cached and (_time.time() - cached[0] < _STANDINGS_TTL):
            return cached[1]

        r = requests.get(
            "https://www.koreabaseball.com/Record/TeamRank/TeamRank.aspx",
            headers={"User-Agent": "Mozilla/5.0"}, timeout=8,
        )
        r.raise_for_status()
        page = r.text

        m = _re.search(r'<table[^>]*summary="순위[^"]*"[^>]*>(.*?)</table>', page, _re.S)
        teams = []
        if m:
            tb = _re.search(r'<tbody>(.*?)</tbody>', m.group(1), _re.S)
            body = tb.group(1) if tb else m.group(1)
            for tr in _re.findall(r'<tr[^>]*>(.*?)</tr>', body, _re.S):
                cells = [_html.unescape(_re.sub(r'<[^>]+>', '', c)).strip()
                         for c in _re.findall(r'<td[^>]*>(.*?)</td>', tr, _re.S)]
                if len(cells) >= 8 and cells[0].isdigit():
                    name = cells[1]
                    teams.append({
                        "rank": int(cells[0]),
                        "team": name,
                        "code": _KBO_TEAM_CODE.get(name, ""),
                        "games": cells[2],
                        "wins": cells[3],
                        "losses": cells[4],
                        "draws": cells[5],
                        "pct": cells[6],
                        "gb": cells[7],
                        "last10": cells[8] if len(cells) > 8 else "",
                        "streak": cells[9] if len(cells) > 9 else "",
                    })

        result = {"count": len(teams), "teams": teams, "source": "koreabaseball.com"}
        if teams:
            _STANDINGS_CACHE["rank"] = (_time.time(), result)
        return result
    except Exception as e:
        return {"count": 0, "teams": [], "error": str(e)}


# ===== KBO 개인 순위 (타자/투수 Top5 — 대시보드 DB) =====
_LEADERS_CACHE = {}
_LEADERS_TTL = 600  # seconds

# 연도별 Statiz 상수: (woba_scale, ebb, single_w, double_w, triple_w, hr_w)
# 출처: research/data/statiz_yearly_constants.csv. wrc-comparison 페이지와 동일 산식.
_WOBA_CONST = {
    2011: (1.081, 0.407, 0.581, 0.972, 1.168, 1.364),
    2012: (1.134, 0.395, 0.565, 0.947, 1.162, 1.377),
    2013: (1.235, 0.314, 0.479, 0.821, 1.134, 1.442),
    2014: (1.094, 0.334, 0.513, 0.853, 1.169, 1.430),
    2015: (1.107, 0.375, 0.505, 0.808, 1.071, 1.419),
    2016: (1.095, 0.354, 0.502, 0.859, 1.258, 1.424),
    2017: (1.097, 0.353, 0.507, 0.869, 1.081, 1.398),
    2018: (1.074, 0.370, 0.509, 0.831, 1.167, 1.440),
    2019: (1.196, 0.357, 0.493, 0.802, 1.170, 1.433),
    2020: (1.109, 0.378, 0.516, 0.879, 1.081, 1.431),
    2021: (1.169, 0.362, 0.499, 0.867, 1.063, 1.460),
    2022: (1.211, 0.361, 0.484, 0.804, 1.210, 1.441),
    2023: (1.198, 0.355, 0.495, 0.865, 1.191, 1.408),
    2024: (1.093, 0.389, 0.519, 0.852, 1.046, 1.418),
    2025: (1.173, 0.371, 0.502, 0.801, 1.131, 1.406),
    2026: (1.191, 0.364, 0.493, 0.802, 1.175, 1.411),
}


def _ip_to_outs(s):
    """innings_pitched 문자열('68', '68 1/3', '1/3')을 아웃 수로 변환."""
    whole = 0
    frac = 0
    for part in str(s or "").split():
        if "/" in part:
            try:
                frac = int(part.split("/")[0])
            except ValueError:
                frac = 0
        else:
            try:
                whole = int(part)
            except ValueError:
                whole = 0
    return whole * 3 + frac


def _team_park_factors(cur, ref_season):
    """games 테이블에서 팀(홈구장) 파크팩터를 나무위키 기본공식으로 계산.
    PF = (홈경기 양팀합산득점/홈경기수) / (원정경기 양팀합산득점/원정경기수). 1.0=중립."""
    cur.execute(
        "SELECT home_team_id AS h, away_team_id AS a, home_score AS hs, away_score AS asc_ "
        "FROM games WHERE season=? AND home_score IS NOT NULL AND away_score IS NOT NULL",
        (ref_season,),
    )
    hr = {}
    hg = {}
    rr = {}
    rg = {}
    for row in cur.fetchall():
        d = dict(row)
        runs = (d["hs"] or 0) + (d["asc_"] or 0)
        h, a = d["h"], d["a"]
        hr[h] = hr.get(h, 0) + runs
        hg[h] = hg.get(h, 0) + 1
        rr[a] = rr.get(a, 0) + runs
        rg[a] = rg.get(a, 0) + 1
    pf = {}
    for t in hg:
        if hg[t] and rg.get(t) and rr.get(t):
            pf[t] = (hr[t] / hg[t]) / (rr[t] / rg[t])
    return pf


def _eff_min_pa(cur, season, requested):
    """진행중 시즌은 규정타석(3.1 × 팀 경기수)으로 임계값 자동 하향. 완료시즌은 요청값(기본 300) 유지."""
    try:
        g = cur.execute("SELECT COUNT(DISTINCT gameID) FROM play_by_play WHERE substr(gameID,1,4)=?",
                        (str(season),)).fetchone()[0] or 0
    except Exception:
        g = 0
    qual = int(round(3.1 * round(2.0 * g / 10.0)))   # 10 teams; team_games = 2*league_games/10
    return min(requested, qual) if qual > 0 else requested


@app.get("/wrc/seasons")
async def wrc_seasons(min_pa: int = 300):
    """시즌 목록 + summary. 진행중 시즌은 규정타석(3.1×팀경기)으로 min_pa 자동 하향(완료시즌 기본 300). 각 행에 적용 min_pa 포함."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        WITH gp AS (
            SELECT CAST(substr(gameID,1,4) AS INT) AS season, COUNT(DISTINCT gameID) AS g
            FROM play_by_play WHERE substr(gameID,1,4) BETWEEN '2015' AND '2026' GROUP BY 1
        ),
        thr AS (
            SELECT season, MIN(?, CAST(ROUND(3.1 * ROUND(2.0*g/10.0)) AS INT)) AS t FROM gp
        )
        SELECT w.season,
               (SELECT t FROM thr WHERE thr.season = w.season) AS min_pa,
               COUNT(*) AS n_batters,
               ROUND(AVG(w.wRC_home), 2) AS mean_wrc_home,
               ROUND(AVG(w.wRC_half), 2) AS mean_wrc_half,
               ROUND(AVG(w.wRC_weighted), 2) AS mean_wrc_weighted,
               ROUND(AVG(w.wRC_weighted - w.wRC_half), 2) AS mean_delta
        FROM wrc_plus_comparison w
        JOIN thr ON thr.season = w.season
        WHERE w.PA >= thr.t
        GROUP BY w.season
        ORDER BY w.season
    """, (min_pa,))
    rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        cur.execute("SELECT (wRC_weighted - wRC_half) FROM wrc_plus_comparison WHERE PA>=? AND season=?",
                    (r["min_pa"], r["season"]))
        deltas = [x[0] for x in cur.fetchall()]
        n = len(deltas)
        if n > 1:
            mean = sum(deltas) / n
            r["std_delta"] = round((sum((d - mean)**2 for d in deltas) / (n-1))**0.5, 2)
        else:
            r["std_delta"] = None
    conn.close()
    return rows


@app.get("/wrc/by-stadium")
async def wrc_by_stadium(season: int, min_pa: int = 300):
    conn = get_db_connection()
    cur = conn.cursor()
    min_pa = _eff_min_pa(cur, season, min_pa)
    cur.execute("""
        SELECT wpf.home_stadium AS home_stadium,
               sd.primary_team,
               COUNT(*) AS n,
               ROUND(AVG(wpf.home_run_pf), 1) AS home_pf,
               ROUND(AVG(wpf.wpf_run), 1) AS weighted_pf,
               ROUND(AVG(wrc.wRC_home), 2) AS mean_home,
               ROUND(AVG(wrc.wRC_half), 2) AS mean_half,
               ROUND(AVG(wrc.wRC_weighted), 2) AS mean_weighted,
               ROUND(AVG(wrc.wRC_weighted - wrc.wRC_half), 2) AS delta_mean
        FROM wrc_plus_comparison wrc
        JOIN weighted_pf_by_batter_season wpf
          ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
        LEFT JOIN stadium_dim sd ON sd.full_name = wpf.home_stadium
        WHERE wrc.PA >= ? AND wrc.season = ?
        GROUP BY wpf.home_stadium, sd.primary_team
        ORDER BY mean_half DESC
    """, (min_pa, season))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/wrc/leaderboard")
async def wrc_leaderboard(season: int, sort: str = "half", n: int = 50, min_pa: int = 300):
    sort_col = {"home": "wRC_home", "half": "wRC_half", "weighted": "wRC_weighted",
                "wOBA": "wOBA"}.get(sort, "wRC_half")
    conn = get_db_connection()
    cur = conn.cursor()
    min_pa = _eff_min_pa(cur, season, min_pa)
    cur.execute(f"""
        SELECT wrc.batter_ID,
               COALESCE(b.player_name, 'Unknown') AS player_name,
               b.player_team,
               wrc.season, wrc.PA,
               ROUND(wrc.wOBA, 4) AS wOBA,
               ROUND(wrc.wRAA_FG, 1) AS wRAA,
               wpf.home_stadium,
               ROUND(wpf.home_run_pf, 1) AS home_pf,
               ROUND(wpf.wpf_run, 1) AS weighted_pf,
               ROUND(wrc.wRC_home, 1) AS wRC_home,
               ROUND(wrc.wRC_half, 1) AS wRC_half,
               ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
               ROUND(wrc.wRC_weighted - wrc.wRC_half, 2) AS delta_methods
        FROM wrc_plus_comparison wrc
        JOIN weighted_pf_by_batter_season wpf
          ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
        LEFT JOIN kbo_official_batter_stats b
          ON b.player_id = CAST(wrc.batter_ID AS TEXT) AND b.season = wrc.season
        WHERE wrc.season = ? AND wrc.PA >= ?
        ORDER BY {sort_col} DESC
        LIMIT ?
    """, (season, min_pa, n))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/wrc/top-changes")
async def wrc_top_changes(season: int, direction: str = "up", n: int = 15, min_pa: int = 300):
    if direction not in ("up", "down"):
        raise HTTPException(status_code=400, detail="direction must be 'up' or 'down'")
    order = "DESC" if direction == "up" else "ASC"
    conn = get_db_connection()
    cur = conn.cursor()
    min_pa = _eff_min_pa(cur, season, min_pa)
    cur.execute(f"""
        SELECT wrc.batter_ID,
               COALESCE(b.player_name, 'Unknown') AS player_name,
               b.player_team,
               wrc.season, wrc.PA,
               wpf.home_stadium,
               ROUND(wpf.home_run_pf, 1) AS home_pf,
               ROUND(wpf.wpf_run, 1) AS weighted_pf,
               ROUND(wrc.wRC_half, 1) AS wRC_half,
               ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
               ROUND(wrc.wRC_weighted - wrc.wRC_half, 2) AS delta
        FROM wrc_plus_comparison wrc
        JOIN weighted_pf_by_batter_season wpf
          ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
        LEFT JOIN kbo_official_batter_stats b
          ON b.player_id = CAST(wrc.batter_ID AS TEXT) AND b.season = wrc.season
        WHERE wrc.season = ? AND wrc.PA >= ?
        ORDER BY (wrc.wRC_weighted - wrc.wRC_half) {order}
        LIMIT ?
    """, (season, min_pa, n))
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/wrc/batter/{batter_id}")
async def wrc_batter_history(batter_id: str):
    """특정 batter 시즌별 history + Stadium별 PA 분포"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT wrc.season, wrc.PA,
               wpf.home_stadium,
               ROUND(wrc.wOBA, 4) AS wOBA,
               ROUND(wrc.wRAA_FG, 1) AS wRAA,
               ROUND(wpf.home_run_pf, 1) AS home_pf,
               ROUND(wpf.wpf_run, 1) AS weighted_pf,
               ROUND(wrc.wRC_home, 1) AS wRC_home,
               ROUND(wrc.wRC_half, 1) AS wRC_half,
               ROUND(wrc.wRC_weighted, 1) AS wRC_weighted,
               COALESCE(b.player_name, 'Unknown') AS player_name,
               b.player_team,
               b.batting_average AS AVG, b.on_base_percentage AS OBP,
               b.slugging_percentage AS SLG, b.on_base_plus_slugging AS OPS
        FROM wrc_plus_comparison wrc
        JOIN weighted_pf_by_batter_season wpf
          ON wrc.batter_ID = wpf.batter_ID AND wrc.season = wpf.season
        LEFT JOIN kbo_official_batter_stats b
          ON b.player_id = CAST(wrc.batter_ID AS TEXT) AND b.season = wrc.season
        WHERE wrc.batter_ID = ?
        ORDER BY wrc.season
    """, (batter_id,))
    history = [dict(r) for r in cur.fetchall()]

    cur.execute("""
        SELECT substr(gameID,1,4) AS season, stadium, COUNT(*) AS pa
        FROM play_by_play
        WHERE batter_ID = ? AND substr(gameID,1,4) BETWEEN '2015' AND '2026'
        GROUP BY season, stadium
        ORDER BY season, pa DESC
    """, (batter_id,))
    stadium_dist = [dict(r) for r in cur.fetchall()]

    name = history[0]["player_name"] if history else None
    conn.close()
    return {"batter_id": batter_id, "player_name": name,
            "history": history, "stadium_distribution": stadium_dist}


@app.get("/wrc/batter-search")
async def wrc_batter_search(q: str = "", season: int = 0):
    """batter 이름·ID 검색 (부분 일치). season=0이면 모든 시즌."""
    conn = get_db_connection()
    cur = conn.cursor()
    where = "b.player_name LIKE ?"
    params = [f"%{q}%"]
    if season:
        where += " AND b.season = ?"
        params.append(season)
    cur.execute(f"""
        SELECT DISTINCT b.player_id, b.player_name, b.player_team, b.season
        FROM kbo_official_batter_stats b
        WHERE {where}
        ORDER BY b.season DESC, b.player_name
        LIMIT 50
    """, params)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    return rows


@app.get("/wrc/distribution")
async def wrc_distribution(season: int, min_pa: int = 100):
    """시즌 wRC+ 분포 (히스토그램, 5점 bin) + percentile"""
    conn = get_db_connection()
    cur = conn.cursor()
    min_pa = _eff_min_pa(cur, season, min_pa)
    cur.execute("""
        SELECT wRC_home, wRC_half, wRC_weighted
        FROM wrc_plus_comparison
        WHERE PA >= ? AND season = ?
    """, (min_pa, season))
    rows = cur.fetchall()
    conn.close()

    def stats(values):
        v = sorted(x for x in values if x is not None)
        n = len(v)
        if n == 0:
            return {"n": 0}
        return {
            "n": n,
            "mean": round(sum(v) / n, 2),
            "p10": round(v[int(n * 0.10)], 1),
            "median": round(v[n // 2], 1),
            "p90": round(v[int(n * 0.90)], 1),
        }

    def histogram(values, bin_size=5, min_v=40, max_v=200):
        bins = {}
        for v in values:
            if v is None:
                continue
            b = max(min_v, min(max_v, int(v // bin_size) * bin_size))
            bins[b] = bins.get(b, 0) + 1
        return [{"bin": k, "count": v} for k, v in sorted(bins.items())]

    home = [r[0] for r in rows]
    half = [r[1] for r in rows]
    weighted = [r[2] for r in rows]

    return {
        "season": season, "n": len(rows), "min_pa": min_pa,
        "stats": {"home": stats(home), "half": stats(half), "weighted": stats(weighted)},
        "histogram": {
            "home": histogram(home),
            "half": histogram(half),
            "weighted": histogram(weighted),
        },
    }


@app.get("/leaders")
async def get_leaders(season: int = None):
    """KBO 개인 순위 Top5. 타자: 타율/OPS/wRC+, 투수: ERA/이닝/탈삼진.
    타율·OPS·ERA·wRC+는 규정타석/규정이닝(팀 최다경기 기준) 충족자만; 이닝·탈삼진은 누적. 10분 캐시."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        if season is None:
            cur.execute("SELECT MAX(season) FROM kbo_official_batter_stats")
            row = cur.fetchone()
            season = row[0] if row and row[0] else 2026

        ckey = str(season)
        cached = _LEADERS_CACHE.get(ckey)
        if cached and (_time.time() - cached[0] < _LEADERS_TTL):
            conn.close()
            return cached[1]

        cur.execute("SELECT MAX(games) FROM kbo_official_batter_stats WHERE season=?", (season,))
        row = cur.fetchone()
        team_g = (row[0] if row and row[0] else 0)
        qual_pa = round(3.1 * team_g)
        qual_outs = team_g * 3  # 규정이닝 = 1.0 IP/경기

        def _code(team):
            return _KBO_TEAM_CODE.get(team or "", "")

        def _batter_top(order_col):
            cur.execute(
                "SELECT p.player_name AS name, p.team_id AS team, "
                "b.batting_average AS bavg, b.on_base_plus_slugging AS bops "
                "FROM kbo_official_batter_stats b JOIN players p ON b.player_id=p.player_id "
                "WHERE b.season=? AND b.plate_appearance >= ? "
                "ORDER BY b." + order_col + " DESC LIMIT 5",
                (season, qual_pa),
            )
            out = []
            for r in cur.fetchall():
                d = dict(r)
                val = d["bavg"] if order_col == "batting_average" else d["bops"]
                out.append({"name": d["name"], "team": d["team"], "code": _code(d["team"]),
                            "value": ("%.3f" % float(val)) if val is not None else "-"})
            return out

        avg_top = _batter_top("batting_average")
        ops_top = _batter_top("on_base_plus_slugging")

        # wRC+ : wrc_plus_comparison(자체 파크팩터 3년 산식, half-PF)에서 직접 Top5 — 'wRC+ 강건성' 페이지와 동일 출처
        cur.execute(
            "SELECT p.player_name AS name, p.team_id AS team, ROUND(w.wRC_half, 1) AS wrc "
            "FROM wrc_plus_comparison w JOIN players p ON p.player_id = CAST(w.batter_ID AS TEXT) "
            "WHERE w.season=? AND w.PA >= ? "
            "ORDER BY w.wRC_half DESC LIMIT 5",
            (season, qual_pa),
        )
        wrc_top = [{"name": d["name"], "team": d["team"], "code": _code(d["team"]),
                    "value": ("%.1f" % d["wrc"]) if d["wrc"] is not None else "-"}
                   for d in (dict(r) for r in cur.fetchall())]

        cur.execute(
            "SELECT p.player_name AS name, p.team_id AS team, ps.earned_run_average AS era, "
            "ps.innings_pitched AS ip, ps.strikeout AS k "
            "FROM kbo_official_pitcher_stats ps JOIN players p ON ps.player_id=p.player_id "
            "WHERE ps.season=?",
            (season,),
        )
        pit = []
        for r in cur.fetchall():
            d = dict(r)
            d["_outs"] = _ip_to_outs(d.get("ip"))
            try:
                d["_era"] = float(d["era"])
            except (TypeError, ValueError):
                d["_era"] = 999.0
            try:
                d["_k"] = int(d["k"])
            except (TypeError, ValueError):
                d["_k"] = 0
            pit.append(d)

        def _pit_entry(d, val):
            return {"name": d["name"], "team": d["team"], "code": _code(d["team"]), "value": val}

        era_top = [_pit_entry(d, "%.2f" % d["_era"])
                   for d in sorted([x for x in pit if x["_outs"] >= qual_outs], key=lambda x: x["_era"])[:5]]
        ip_top = [_pit_entry(d, str(d.get("ip") or "").strip())
                  for d in sorted(pit, key=lambda x: -x["_outs"])[:5]]
        k_top = [_pit_entry(d, str(d["_k"]))
                 for d in sorted(pit, key=lambda x: -x["_k"])[:5]]

        conn.close()
        result = {
            "season": season,
            "qual_pa": qual_pa,
            "qual_ip": team_g,
            "wrc_pf_season": season,
            "batter": {"avg": avg_top, "ops": ops_top, "wrc": wrc_top},
            "pitcher": {"era": era_top, "ip": ip_top, "k": k_top},
        }
        _LEADERS_CACHE[ckey] = (_time.time(), result)
        return result
    except Exception as e:
        return {"season": season, "batter": {"avg": [], "ops": [], "wrc": []},
                "pitcher": {"era": [], "ip": [], "k": []}, "error": str(e)}


# ==========================================================================
# DB Explorer - 범용 데이터 탐색 (SQLite를 직접 다루지 않고 웹에서 조회)
# 테이블/컬럼 이름은 항상 실제 sqlite_master 목록으로 검증하여 SQL 주입을 차단
# ==========================================================================

def list_table_names(cur):
    """실제 존재하는 테이블 이름 목록 (sqlite 내부 테이블 제외)"""
    rows = cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


@app.get("/db/tables")
async def db_tables():
    """모든 테이블 목록 + 행/컬럼 수"""
    conn = get_db_connection()
    cur = conn.cursor()
    result = []
    for name in list_table_names(cur):
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except Exception:
            n = None
        cols = cur.execute(f'PRAGMA table_info("{name}")').fetchall()
        result.append({"name": name, "rows": n, "columns": len(cols)})
    conn.close()
    return {"tables": result, "count": len(result)}


@app.get("/db/table/{table_name}")
async def db_table(table_name: str, limit: int = 50, offset: int = 0):
    """단일 테이블의 스키마 + 페이지네이션된 데이터"""
    conn = get_db_connection()
    cur = conn.cursor()
    if table_name not in list_table_names(cur):
        conn.close()
        raise HTTPException(status_code=404, detail="Table not found")

    limit = max(1, min(int(limit), 500))   # 한 번에 최대 500행
    offset = max(0, int(offset))

    cols_info = cur.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    schema = [{
        "name": c["name"],
        "type": c["type"] or "",
        "pk": bool(c["pk"]),
        "notnull": bool(c["notnull"]),
    } for c in cols_info]
    columns = [c["name"] for c in cols_info]

    total = cur.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
    rows = cur.execute(
        f'SELECT * FROM "{table_name}" LIMIT ? OFFSET ?', (limit, offset)
    ).fetchall()
    data = [dict(r) for r in rows]
    conn.close()

    return {
        "table": table_name,
        "schema": schema,
        "columns": columns,
        "rows": data,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@app.get("/db/table/{table_name}/csv")
async def db_table_csv(table_name: str, limit: int = 0):
    """테이블 전체(또는 limit행)를 CSV로 스트리밍 다운로드 (엑셀에서 열기 용)"""
    # 테이블 검증 + 컬럼 목록 확보 (요청 스레드에서 먼저 처리)
    conn = get_db_connection()
    cur = conn.cursor()
    valid = table_name in list_table_names(cur)
    cols_info = cur.execute(f'PRAGMA table_info("{table_name}")').fetchall() if valid else []
    conn.close()
    if not valid:
        raise HTTPException(status_code=404, detail="Table not found")

    columns = [c["name"] for c in cols_info]
    lim = int(limit)

    def generate():
        # 스트리밍 제너레이터는 스레드풀에서 순회되므로 전용 연결을 새로 연다.
        # check_same_thread=False: next() 호출이 직렬화되어 동시 접근은 없음.
        gen_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        gen_conn.row_factory = sqlite3.Row
        gcur = gen_conn.cursor()
        query = f'SELECT * FROM "{table_name}"'
        if lim > 0:
            query += f' LIMIT {lim}'
        gcur.execute(query)
        try:
            buf = io.StringIO()
            writer = csv.writer(buf)
            buf.write("﻿")  # UTF-8 BOM: 엑셀 한글 깨짐 방지
            writer.writerow(columns)
            yield buf.getvalue(); buf.seek(0); buf.truncate(0)
            for r in gcur:  # 커서를 점진적으로 순회 (대용량도 메모리 안전)
                writer.writerow([r[c] for c in columns])
                yield buf.getvalue(); buf.seek(0); buf.truncate(0)
        finally:
            gen_conn.close()

    return StreamingResponse(
        generate(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{table_name}.csv"'},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
