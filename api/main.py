"""
KBO Baseball Analytics API
FastAPI backend for JavaScript dashboard - v1.0.7
Fixed: API endpoint for Pitch Usage, encoding issues, and indentation
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
from pathlib import Path
from typing import Optional, List
import datetime
import traceback
import sys
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
        cur.execute("SELECT COUNT(*) as count FROM games")
        games = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) as count FROM players")
        players = cur.fetchone()['count']
        cur.execute("SELECT COUNT(*) as count FROM teams")
        teams = cur.fetchone()['count']
        conn.close()
        return {"games": games, "players": players, "teams": teams, "status": "ok"}
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
