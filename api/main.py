"""
KBO Baseball Analytics API
FastAPI backend for JavaScript dashboard - v1.0.7
Fixed: API endpoint for Pitch Usage, encoding issues, and indentation
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, Response
import sqlite3
import json
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

def _has_table(cur, name):
    """sqlite_master에 해당 table/view가 있는지 확인(없는 DB에서도 안전하게 동작하도록 가드)."""
    try:
        return cur.execute(
            "SELECT 1 FROM sqlite_master WHERE type IN ('table','view') AND name=?",
            (name,)
        ).fetchone() is not None
    except Exception:
        return False

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
    cur.execute("SELECT *, single as hits, on_base_plus_slugging as ops FROM kbo_official_batter_stats WHERE player_id = ? ORDER BY season DESC", (db_pid,))
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
async def get_pitch_arsenal(player_id: str, season: int = 2026):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        player = robust_player_lookup(cur, player_id)
        if not player:
            conn.close()
            return {"error": "Player not found"}
        
        db_pid = player['player_id']

        sql = """
            SELECT pbp.pitch_type, pbp.px, pbp.pz, pbp.speed, pbp.pitch_result, pbp.pfx_x, pbp.pfx_z, pbp.game_date, pbp.x0, pbp.z0, pbp.sz_top, pbp.sz_bot
            FROM play_by_play pbp
            -- (removed games join)
            WHERE pbp.pitcher_ID = ? 
            AND substr(pbp.gameID,1,4) = CAST(? AS TEXT)
            AND pbp.px IS NOT NULL 
            AND pbp.pz IS NOT NULL
            AND pbp.pitch_type IS NOT NULL
            AND pbp.pitch_type NOT IN ('', '-', 'null')
        """
        cur.execute(sql, (db_pid, season))
        rows = cur.fetchall()
        
        arsenal = [dict(row) for row in rows]
        conn.close()
        
        return {"player_id": player_id, "arsenal": arsenal, "count": len(arsenal)}
        
    except Exception as e:
        print(f"Arsenal fetch error for {player_id}: {str(e)}")
        return {"error": str(e), "traceback": traceback.format_exc()}

@app.get("/players/{player_id}/usage")
async def get_pitch_usage(player_id: str, season: int = 2026):
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
            -- (removed games join)
            WHERE pbp.pitcher_ID = ? 
            AND substr(pbp.gameID,1,4) = CAST(? AS TEXT)
            AND pbp.pitch_type IS NOT NULL
            AND pbp.pitch_type NOT IN ('', '-', 'null')
        """
        cur.execute(sql, (db_pid, season))
        rows = cur.fetchall()
        conn.close()

        if not rows:
            return {"player_id": player_id, "usage": []}

        # Abbreviation Map
        abb_map = {
            '너클볼': 'KN', '스위퍼': 'ST', '슬라이더': 'SL', '슬러브': 'SV',
            '싱커': 'SI', '직구': 'FF', '체인지업': 'CH', '커브': 'CU',
            '커터': 'FC', '투심': 'SI', '스플리터': 'FS'
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

@app.get("/stats/seasons")
async def get_stats_seasons():
    """타자/투수 시즌 통계가 존재하는 시즌 목록을 내림차순으로 반환합니다."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT season FROM (
            SELECT season FROM kbo_official_batter_stats
            UNION
            SELECT season FROM kbo_official_pitcher_stats
        )
        WHERE season IS NOT NULL
        ORDER BY season DESC
    """)
    seasons = [row[0] for row in cur.fetchall()]
    conn.close()
    return {"seasons": seasons}

@app.get("/stats/regulation")
async def get_regulation():
    """시즌별 규정타석/규정이닝을 반환합니다.
    규정타석 = 3.1 × 팀경기수, 규정이닝 = 1.0 × 팀경기수.
    팀경기수 = 시즌 내 타자 MAX(games) (진행 중 시즌은 진행 경기수가 반영되어 임계값이 함께 상승).
    /leaders 의 규정타석 산식과 동일하므로 페이지 간 기준이 일치합니다."""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT season, MAX(games) AS team_games
        FROM kbo_official_batter_stats
        WHERE season IS NOT NULL AND games IS NOT NULL
        GROUP BY season
    """)
    out = {}
    for r in cur.fetchall():
        g = r["team_games"] or 0
        out[str(r["season"])] = {
            "team_games": g,
            "qual_pa": int(round(3.1 * g)),
            "qual_ip": g,
        }
    conn.close()
    return {"regulation": out}

@app.get("/stats/batters")
async def get_batter_stats(season: int = 2025, limit: int = 100, min_pa: int = 0, team_ids: str = None):
    conn = get_db_connection()
    cur = conn.cursor()
    # wOBA/wRAA/wRC+ 는 wrc_plus_comparison(자체 파크팩터 산식, half-PF=wRC_half)에서 가져온다.
    # 해당 테이블이 없는 DB(구버전·로컬 스냅샷)에서는 NULL 폴백으로 안전하게 동작한다.
    # PA<50 등 산출 대상이 아닌 타자는 LEFT JOIN 으로 비게 되어 프런트에서 '-'로 표기된다.
    has_wrc = _has_table(cur, "wrc_plus_comparison")
    if has_wrc:
        wrc_select = (", ROUND(w.wOBA, 3) AS woba, ROUND(w.wRAA_FG, 1) AS wraa, "
                      "ROUND(w.wRC_half, 1) AS wrc_plus")
        wrc_join = (" LEFT JOIN wrc_plus_comparison w "
                    "ON CAST(w.batter_ID AS TEXT) = b.player_id AND w.season = b.season")
    else:
        wrc_select = ", NULL AS woba, NULL AS wraa, NULL AS wrc_plus"
        wrc_join = ""
    query = f"""
        SELECT b.*, p.player_name, p.team_id, p.position, b.on_base_plus_slugging as ops{wrc_select}
        FROM kbo_official_batter_stats b
        JOIN players p ON b.player_id = p.player_id{wrc_join}
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

# --- 기간별(PBP) 팀 성적 (date-range team stats from play-by-play) ---
# pa_result 분류는 build_re24_run_values.py의 검증된 MAP을 기준으로 함.
_TR_H1 = {'안타', '내야안타', '번트 안타'}
_TR_D2 = {'2루타'}
_TR_D3 = {'3루타'}
_TR_HR = {'홈런'}
_TR_HIT = _TR_H1 | _TR_D2 | _TR_D3 | _TR_HR
_TR_WALK = {'볼넷', '자동 고의4구', '고의4구', '고의 4구', '자동 고의 4구'}
_TR_HBP = {'몸에 맞는 볼', '몸에 맞는 공'}
_TR_SOK = {'삼진', '낫아웃 출루'}            # 투수 탈삼진 크레딧 (낫아웃 출루는 out 아님)
_TR_OUTP = {'필드 아웃', '포스 아웃', '병살타', '삼중살', '타구맞음 아웃'}
_TR_ROE = {'실책'}
_TR_FC = {'야수 선택'}
_TR_SACB = {'희생번트', '희생번트 야수선택'}
_TR_SACF = {'희생플라이'}
_TR_AB = _TR_HIT | {'삼진', '낫아웃 출루'} | _TR_OUTP | _TR_ROE | _TR_FC


def _tr_norm_date(s):
    s = str(s).strip().replace('-', '').replace('/', '')
    return int(s) if s.isdigit() and len(s) == 8 else None


@app.get("/stats/team_range")
async def team_range(start: str, end: str):
    """날짜 범위(YYYY-MM-DD 또는 YYYYMMDD)의 팀 타격/투구를 PBP에서 집계.
    투구는 자책 구분이 어려워 ERA 대신 RA/9(실점 기준)를 제공. '가용 PBP 기준' 캐비엇."""
    s = _tr_norm_date(start)
    e = _tr_norm_date(end)
    if not s or not e:
        raise HTTPException(status_code=400, detail="start/end must be YYYY-MM-DD or YYYYMMDD")
    if s > e:
        s, e = e, s
    conn = get_db_connection()
    cur = conn.cursor()

    def blank():
        return {"team": None, "G": 0, "PA": 0, "AB": 0, "H": 0, "2B": 0, "3B": 0, "HR": 0,
                "BB": 0, "HBP": 0, "SF": 0, "SH": 0, "SO": 0, "R": 0,
                "outs": 0, "Hd": 0, "BBd": 0, "SOd": 0, "HRd": 0, "ABf": 0, "Rd": 0}
    T = {}

    def g(t):
        if t not in T:
            d = blank()
            d["team"] = t
            T[t] = d
        return T[t]

    # 경기 수(팀별 G) + 날짜 경계
    cur.execute("SELECT game_id, home_team_id, away_team_id, game_date FROM games "
                "WHERE game_date>=? AND game_date<=? AND game_type='정규시즌'", (s, e))
    games = cur.fetchall()
    dmin = dmax = None
    for row in games:
        home, away, gd = row[1], row[2], row[3]
        g(home)["G"] += 1
        g(away)["G"] += 1
        dmin = gd if dmin is None or gd < dmin else dmin
        dmax = gd if dmax is None or gd > dmax else dmax

    # PA 행: 카운팅 스탯
    cur.execute("SELECT p.inning_topbot, p.pa_result, gm.home_team_id, gm.away_team_id "
                "FROM play_by_play p JOIN games gm ON gm.game_id = p.gameID "
                "WHERE gm.game_date>=? AND gm.game_date<=? AND gm.game_type='정규시즌' "
                "AND p.pa_result IS NOT NULL AND p.pa_result<>''", (s, e))
    for row in cur.fetchall():
        tb, res, home, away = row[0], row[1], row[2], row[3]
        bat = away if tb == '초' else home
        pit = home if tb == '초' else away
        b = g(bat)
        pp = g(pit)
        b["PA"] += 1
        if res in _TR_AB:
            b["AB"] += 1
            pp["ABf"] += 1
        if res in _TR_HIT:
            b["H"] += 1
            pp["Hd"] += 1
            if res in _TR_D2:
                b["2B"] += 1
            elif res in _TR_D3:
                b["3B"] += 1
            elif res in _TR_HR:
                b["HR"] += 1
                pp["HRd"] += 1
        if res in _TR_WALK:
            b["BB"] += 1
            pp["BBd"] += 1
        if res in _TR_HBP:
            b["HBP"] += 1
        if res in _TR_SACF:
            b["SF"] += 1
        if res in _TR_SACB:
            b["SH"] += 1
        if res in _TR_SOK:
            b["SO"] += 1
            pp["SOd"] += 1

    # 전체 행: outs_on_play + runs_scored + 삼진 out (삼진 out은 outs_on_play에 없음)
    cur.execute("SELECT p.inning_topbot, gm.home_team_id, gm.away_team_id, "
                "SUM(p.outs_on_play), SUM(p.runs_scored), "
                "SUM(CASE WHEN p.pa_result='삼진' THEN 1 ELSE 0 END) "
                "FROM play_by_play p JOIN games gm ON gm.game_id = p.gameID "
                "WHERE gm.game_date>=? AND gm.game_date<=? AND gm.game_type='정규시즌' "
                "GROUP BY p.inning_topbot, gm.home_team_id, gm.away_team_id", (s, e))
    for row in cur.fetchall():
        tb, home, away, oop, runs, ko = row[0], row[1], row[2], row[3], row[4], row[5]
        bat = away if tb == '초' else home
        pit = home if tb == '초' else away
        g(bat)["R"] += (runs or 0)
        pp = g(pit)
        pp["outs"] += (oop or 0) + (ko or 0)
        pp["Rd"] += (runs or 0)
    conn.close()

    def rnd(x, n):
        return round(x, n) if x is not None else None

    batting = []
    pitching = []
    for t, d in T.items():
        AB = d["AB"]
        H = d["H"]
        TB = H + d["2B"] + 2 * d["3B"] + 3 * d["HR"]
        obpden = AB + d["BB"] + d["HBP"] + d["SF"]
        avg = H / AB if AB else 0
        obp = (H + d["BB"] + d["HBP"]) / obpden if obpden else 0
        slg = TB / AB if AB else 0
        batting.append({"team": t, "G": d["G"], "PA": d["PA"], "AB": AB, "R": d["R"], "H": H,
                        "2B": d["2B"], "3B": d["3B"], "HR": d["HR"], "BB": d["BB"], "HBP": d["HBP"],
                        "SO": d["SO"], "SH": d["SH"], "SF": d["SF"], "TB": TB,
                        "AVG": rnd(avg, 3), "OBP": rnd(obp, 3), "SLG": rnd(slg, 3), "OPS": rnd(obp + slg, 3)})
        outs = d["outs"]
        ip = outs / 3
        whip = (d["Hd"] + d["BBd"]) * 3 / outs if outs else 0
        ra9 = d["Rd"] * 27 / outs if outs else 0
        k9 = d["SOd"] * 27 / outs if outs else 0
        bb9 = d["BBd"] * 27 / outs if outs else 0
        avga = d["Hd"] / d["ABf"] if d["ABf"] else 0
        ip_text = ("%d %d/3" % (outs // 3, outs % 3)) if outs % 3 else ("%d" % (outs // 3))
        pitching.append({"team": t, "G": d["G"], "IP_outs": outs, "IP": rnd(ip, 1), "IP_text": ip_text,
                         "H": d["Hd"], "R": d["Rd"], "BB": d["BBd"], "SO": d["SOd"], "HR": d["HRd"],
                         "AB_against": d["ABf"], "WHIP": rnd(whip, 3), "RA9": rnd(ra9, 2),
                         "K9": rnd(k9, 2), "BB9": rnd(bb9, 2), "AVG_against": rnd(avga, 3)})
    batting.sort(key=lambda x: (x["OPS"] is None, -(x["OPS"] or 0)))
    pitching.sort(key=lambda x: (x["IP_outs"] == 0, x["RA9"] if x["RA9"] is not None else 9e9))
    return {"start": start, "end": end, "date_min": dmin, "date_max": dmax, "games": len(games),
            "batting": batting, "pitching": pitching,
            "note": "가용 PBP 이벤트 기준 집계입니다. KBO 공식 누적과 정의 차이로 미세한 차이가 있을 수 있습니다. "
                    "투구는 자책점 구분이 어려워 ERA 대신 RA/9(실점 기준)를 제공합니다."}


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


_COL_DICT = None

def load_col_dict():
    """데이터 사전(테이블/컬럼 설명·카테고리·업데이트 주기) 로드 (1회 캐시)"""
    global _COL_DICT
    if _COL_DICT is None:
        try:
            p = Path(__file__).parent.parent / 'database' / 'column_descriptions.json'
            with open(p, encoding='utf-8') as f:
                _COL_DICT = json.load(f)
        except Exception:
            _COL_DICT = {"categories": [], "tables": {}}
    return _COL_DICT


@app.get("/db/tables")
async def db_tables():
    """모든 테이블 목록 + 행/컬럼 수 + 분류/설명/업데이트 주기"""
    conn = get_db_connection()
    cur = conn.cursor()
    meta = load_col_dict()
    tmeta = meta.get("tables", {})
    result = []
    for name in list_table_names(cur):
        try:
            n = cur.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        except Exception:
            n = None
        cols = cur.execute(f'PRAGMA table_info("{name}")').fetchall()
        m = tmeta.get(name, {})
        result.append({
            "name": name,
            "rows": n,
            "columns": len(cols),
            "category": m.get("category", ""),
            "table_desc": m.get("table_desc", ""),
            "update_freq": m.get("update_freq", ""),
        })
    conn.close()
    return {"tables": result, "count": len(result), "categories": meta.get("categories", [])}


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

    tmeta = load_col_dict().get("tables", {}).get(table_name, {})
    cdesc = tmeta.get("columns", {})

    cols_info = cur.execute(f'PRAGMA table_info("{table_name}")').fetchall()
    schema = [{
        "name": c["name"],
        "type": c["type"] or "",
        "pk": bool(c["pk"]),
        "notnull": bool(c["notnull"]),
        "desc": cdesc.get(c["name"], ""),
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
        "table_desc": tmeta.get("table_desc", ""),
        "update_freq": tmeta.get("update_freq", ""),
        "category": tmeta.get("category", ""),
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


# ── AI Proxy ──────────────────────────────────────────────────────────────────
import os
from fastapi import Request

def _get_api_keys():
    """환경변수에서 모든 API 키를 수집 (ANTHROPIC_API_KEY, _2, _3, ...)"""
    keys = []
    primary = os.environ.get("ANTHROPIC_API_KEY", "")
    if primary:
        keys.append(primary)
    for i in range(2, 10):
        k = os.environ.get(f"ANTHROPIC_API_KEY_{i}", "")
        if k:
            keys.append(k)
    return keys


def _call_anthropic_with_failover(body, timeout=60):
    """API 키 failover: 크레딧 소진 시 자동으로 다음 키로 전환"""
    keys = _get_api_keys()
    if not keys:
        raise HTTPException(status_code=500, detail="No API keys configured")

    last_error = None
    for i, api_key in enumerate(keys):
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=body,
            timeout=timeout,
        )
        result = response.json()

        # 크레딧 부족 또는 인증 에러면 다음 키로
        if response.status_code in (400, 401, 403):
            err_msg = str(result.get("error", {}).get("message", ""))
            if "credit" in err_msg.lower() or "api key" in err_msg.lower() or "auth" in err_msg.lower():
                print(f"API key #{i+1} failed ({err_msg[:60]}), trying next...")
                last_error = result
                continue

        return response, result

    # 모든 키 실패
    return None, last_error


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
            # 진행 중인 경기에서 현재 마운드에 등판 중인 투수 (예정·종료 시엔 빈 문자열)
            "currentPitcher": (g.get(prefix + "CurrentPitcherName", "") or "") if live else "",
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
        # 종료 경기의 승/패/세이브 투수 (get_schedule에서 record 엔드포인트로 채움)
        "decisions": {"win": "", "lose": "", "save": ""},
    }


def _kbo_game_decisions(game_id):
    """종료 경기의 승리/패전/세이브 투수.
    record 엔드포인트 pitchingResult[].wls (W=승, L=패, S=세이브, H=홀드)에서 추출.
    세이브 투수는 정의상 승리팀 소속이므로 별도 팀 판별 불필요."""
    out = {"win": "", "lose": "", "save": ""}
    try:
        data = _kbo_fetch_json(
            "https://api-gw.sports.naver.com/schedule/games/" + game_id + "/record"
        )
        pr = ((data or {}).get("result", {}).get("recordData", {}) or {}).get("pitchingResult", []) or []
        for p in pr:
            wls = (p.get("wls") or "").upper()
            name = p.get("name") or ""
            if wls == "W" and not out["win"]:
                out["win"] = name
            elif wls == "L" and not out["lose"]:
                out["lose"] = name
            elif wls == "S" and not out["save"]:
                out["save"] = name
    except Exception:
        pass
    return out


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

            # 종료 경기는 승/패/세이브 투수를 record 엔드포인트에서 병렬로 보강
            finals = [ng for ng in games if ng.get("final") and ng.get("gameId")]
            if finals:
                with _futures.ThreadPoolExecutor(max_workers=8) as ex:
                    decs = list(ex.map(lambda ng: _kbo_game_decisions(ng["gameId"]), finals))
                for ng, d in zip(finals, decs):
                    ng["decisions"] = d

            games.sort(key=lambda x: ((x.get("datetime") or ""), (x.get("gameId") or "")))

        _attach_pitcher_ids(games)  # 투수 이름 -> player_id 부착(캐시 저장 전)
        result = {"date": date, "count": len(games), "games": games}
        _SCHEDULE_CACHE[date] = (_time.time(), result)
        return result
    except Exception as e:
        return {"date": date, "count": 0, "games": [], "error": str(e)}


# ===== KBO 퓨처스리그 일정/결과 (실시간 스코어보드 프록시) =====
# Schedule.asmx(스케줄 리스트)는 진행 중 경기를 0:0으로만 표시(라이브 스코어 없음)하므로,
# 1군(Naver)처럼 실시간 스코어보드 GetKboGameList(leId=2)를 프록시한다.
# 라이브 스코어·현재 이닝·등판 투수·승/패/세이브까지 제공하며 과거 날짜·교류전도 동일 처리.
# (data_collection/futures_schedule.py + futures_games 테이블은 분석용 웨어하우스로 별도 유지)
_FUTURES_SCHED_CACHE = {}
_FUTURES_SCHED_TTL = 30  # seconds (라이브 갱신)
_FUTURES_STATE = {"1": "scheduled", "2": "live", "3": "final"}
_FUTURES_SRID = "0,9,10"  # 0=정규, 10=교류전 (모두 포함)
_FUTURES_SB_URL = "https://www.koreabaseball.com/ws/Main.asmx/GetKboGameList"


def _futures_teams_map():
    """code -> {display_name, division} (futures_teams 마스터)."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT code, display_name, division FROM futures_teams"
    ).fetchall()
    conn.close()
    return {r["code"]: dict(r) for r in rows}


def _futures_scoreboard(ymd):
    """GetKboGameList(leId=2, date=YYYYMMDD) -> game 리스트 (BOM 처리)."""
    r = requests.post(
        _FUTURES_SB_URL,
        data={"leId": "2", "srId": _FUTURES_SRID, "date": ymd},
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://www.koreabaseball.com/Schedule/GameCenter/Main.aspx",
            "X-Requested-With": "XMLHttpRequest",
        },
        timeout=8,
    )
    r.raise_for_status()
    data = json.loads(r.content.decode("utf-8-sig", "replace"))
    return data.get("game") or []


def _futures_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@app.get("/schedule/futures")
async def get_futures_schedule(date: str = None):
    """KBO 퓨처스리그 일정/결과 (실시간 스코어보드 프록시). date=YYYY-MM-DD. 30초 캐시."""
    try:
        if not date:
            kst = datetime.datetime.utcnow() + datetime.timedelta(hours=9)
            date = kst.strftime("%Y-%m-%d")

        cached = _FUTURES_SCHED_CACHE.get(date)
        if cached and (_time.time() - cached[0] < _FUTURES_SCHED_TTL):
            return cached[1]

        raw_games = _futures_scoreboard(date.replace("-", ""))
        teams = _futures_teams_map()

        games = []
        for g in raw_games:
            state = str(g.get("GAME_STATE_SC") or "")
            cancel = str(g.get("CANCEL_SC_ID") or "0") not in ("0", "")
            status = "canceled" if cancel else _FUTURES_STATE.get(state, "scheduled")
            final = status == "final"
            live = status == "live"
            show = final or live

            ac = g.get("AWAY_ID") or ""
            hc = g.get("HOME_ID") or ""
            at = teams.get(ac, {})
            ht = teams.get(hc, {})
            a_sc = _futures_int(g.get("T_SCORE_CN")) if show else None
            h_sc = _futures_int(g.get("B_SCORE_CN")) if show else None

            winner = ""
            if final and a_sc is not None and h_sc is not None:
                winner = "AWAY" if a_sc > h_sc else "HOME" if h_sc > a_sc else ""

            inning = ""
            if live and g.get("GAME_INN_NO"):
                inning = "%s회%s" % (g.get("GAME_INN_NO"), g.get("GAME_TB_SC_NM") or "")

            sr = _futures_int(g.get("SR_ID"))
            status_info = ("취소" if cancel else inning if live
                           else "종료" if final else "경기예정")

            # 라이브 현재 타석. KBO 스코어보드의 T_P/B_P는 '투수/타자' 고정이 아니라
            # 공격측 기준 선수(원정=T_P, 홈=B_P)이고, 이닝 초/말(GAME_TB_SC)에 따라
            # 타자·투수가 뒤바뀐다(초=원정 공격, 말=홈 공격).
            #   초(T): 타자=T_P(원정), 투수=B_P(홈 수비)
            #   말(B): 타자=B_P(홈),   투수=T_P(원정 수비)
            tb = str(g.get("GAME_TB_SC") or "")
            t_p = (g.get("T_P_NM") or "").strip()
            b_p = (g.get("B_P_NM") or "").strip()
            cur_batter = (t_p if tb == "T" else b_p) if live else ""
            cur_pitcher = (b_p if tb == "T" else t_p) if live else ""

            games.append({
                "gameId": g.get("G_ID"),
                "time": g.get("G_TM") or "",
                "stadium": g.get("S_NM") or "",
                "seriesId": sr if sr is not None else 0,
                "series": "교류전" if sr == 10 else "퓨처스리그",
                "status": status,
                "final": final,
                "live": live,
                "cancel": cancel,
                "showScore": show,
                "winner": winner,
                "currentInning": inning,
                "statusInfo": status_info,
                "currentPitcher": cur_pitcher,
                "currentBatter": cur_batter,
                "away": {
                    "code": ac,
                    "name": at.get("display_name") or g.get("AWAY_NM") or ac,
                    "division": at.get("division") or "",
                    "score": a_sc,
                },
                "home": {
                    "code": hc,
                    "name": ht.get("display_name") or g.get("HOME_NM") or hc,
                    "division": ht.get("division") or "",
                    "score": h_sc,
                },
                "decisions": {
                    "win": (g.get("W_PIT_P_NM") or "") if final else "",
                    "lose": (g.get("L_PIT_P_NM") or "") if final else "",
                    "save": (g.get("SV_PIT_P_NM") or "") if final else "",
                },
            })

        games.sort(key=lambda x: ((x.get("time") or ""), (x.get("gameId") or "")))
        result = {"date": date, "count": len(games), "games": games,
                  "source": "koreabaseball.com"}
        _FUTURES_SCHED_CACHE[date] = (_time.time(), result)
        return result
    except Exception as e:
        return {"date": date, "count": 0, "games": [], "error": str(e)}


@app.get("/logo/{code}")
async def get_logo(code: str):
    """팀 로고 서빙 (team_logos BLOB). code=HH/WO/SM/UL/SO 등. png/svg 모두 지원."""
    conn = get_db_connection()
    row = conn.execute(
        "SELECT mime, image FROM team_logos WHERE code = ?", (code.upper(),)
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="logo not found")
    return Response(
        content=bytes(row["image"]),
        media_type=row["mime"],
        headers={"Cache-Control": "public, max-age=86400"},
    )


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

# 엠블럼 코드 -> KBO 표기명(players.team_id) 역매핑.
# schedule 투수 이름(네이버 표기)을 players.player_id로 매칭할 때 팀을 좁히는 데 사용.
_KBO_CODE_TO_TEAM = {v: k for k, v in _KBO_TEAM_CODE.items()}


_players_cols_cache = None


def _players_has_col(cur, col):
    """players 테이블에 컬럼이 있는지(스키마 캐시). is_active 등 신규 컬럼이 없는
    구버전 DB 스냅샷에서도 안전하게 동작하기 위함."""
    global _players_cols_cache
    if _players_cols_cache is None:
        _players_cols_cache = {r[1] for r in cur.execute("PRAGMA table_info(players)")}
    return col in _players_cols_cache


def _resolve_pitcher_id(cur, name, code):
    """경기 카드 투수 이름 + 팀 엠블럼 코드 -> players.player_id.
    is_active 컬럼이 있으면 현역만 후보로 둠(은퇴/동명 중복 선수로의 오링크 방지).
    단일 매칭이면 그 id, 동명이인이면 투수(position='투수')로 1명만 좁혀질 때만 반환.
    미매칭·모호 시 None(프론트는 일반 텍스트, 딥링크 없음)."""
    if not name or not code:
        return None
    team_id = _KBO_CODE_TO_TEAM.get(code)
    if not team_id:
        return None
    has_active = _players_has_col(cur, "is_active")
    sel = ("SELECT player_id, position, is_active FROM players "
           if has_active else "SELECT player_id, position FROM players ")
    cur.execute(sel + "WHERE player_name=? AND team_id=?", (name, team_id))
    rows = cur.fetchall()
    if has_active:
        rows = [r for r in rows if r["is_active"] == 1]  # 현역만 링크
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]["player_id"]
    pitchers = [r for r in rows if (r["position"] or "") == "투수"]
    return pitchers[0]["player_id"] if len(pitchers) == 1 else None


def _attach_pitcher_ids(games):
    """schedule 응답의 각 경기 투수 이름에 player_id를 부착(매칭된 것만, 캐시 저장 전에 호출).
    팀 판별: 선발/현재투수=원정·홈 각 팀, 승=승리팀·패=패전팀·세=승리팀."""
    if not games:
        return
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        for g in games:
            home = g.get("home") or {}
            away = g.get("away") or {}
            hcode, acode = home.get("code"), away.get("code")
            away["starterId"] = _resolve_pitcher_id(cur, away.get("starter"), acode)
            home["starterId"] = _resolve_pitcher_id(cur, home.get("starter"), hcode)
            away["currentPitcherId"] = _resolve_pitcher_id(cur, away.get("currentPitcher"), acode)
            home["currentPitcherId"] = _resolve_pitcher_id(cur, home.get("currentPitcher"), hcode)
            winner = (g.get("winner") or "").upper()
            win_code = hcode if winner == "HOME" else (acode if winner == "AWAY" else None)
            lose_code = acode if winner == "HOME" else (hcode if winner == "AWAY" else None)
            d = g.get("decisions") or {}
            d["winId"] = _resolve_pitcher_id(cur, d.get("win"), win_code)
            d["loseId"] = _resolve_pitcher_id(cur, d.get("lose"), lose_code)
            d["saveId"] = _resolve_pitcher_id(cur, d.get("save"), win_code)
            g["decisions"] = d
    finally:
        conn.close()


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


@app.get("/leaders")
async def get_leaders(season: int = None):
    """KBO 개인 순위 Top5. 타자: 타율/출루율/장타율/OPS/wOBA/wRC+, 투수: 이닝/탈삼진/ERA/K%/BB%/K-BB%.
    타율·출루율·장타율·OPS·wOBA·wRC+·ERA·K%·BB%·K-BB%는 규정타석/규정이닝(팀 최다경기 기준) 충족자만;
    이닝·탈삼진은 누적. 10분 캐시.
    wRC+는 wrc-comparison 페이지와 동일 산식(wOBA->wRAA->wRC+)을 현재 데이터로 실시간 계산.
    파크팩터는 games 테이블에서 자체 계산(나무위키 기본공식); 해당 시즌 경기 미적재 시 직전 보유 시즌 사용."""
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

        # 타율/출루율/장타율/OPS — 규정타석 충족자, 해당 컬럼 내림차순 Top5
        # (order_col은 아래 호출부의 내부 화이트리스트 컬럼만 사용)
        def _batter_top(order_col):
            cur.execute(
                "SELECT p.player_id AS player_id, p.player_name AS name, p.team_id AS team, b." + order_col + " AS val "
                "FROM kbo_official_batter_stats b JOIN players p ON b.player_id=p.player_id "
                "WHERE b.season=? AND b.plate_appearance >= ? "
                "ORDER BY b." + order_col + " DESC LIMIT 5",
                (season, qual_pa),
            )
            out = []
            for r in cur.fetchall():
                d = dict(r)
                val = d["val"]
                out.append({"player_id": d.get("player_id"), "name": d["name"], "team": d["team"], "code": _code(d["team"]),
                            "value": ("%.3f" % float(val)) if val is not None else "-"})
            return out

        avg_top = _batter_top("batting_average")
        obp_top = _batter_top("on_base_percentage")
        slg_top = _batter_top("slugging_percentage")
        ops_top = _batter_top("on_base_plus_slugging")

        # wRC+ : wrc_plus_comparison(자체 파크팩터 3년 산식, half-PF)에서 직접 Top5 — 'wRC+ 강건성' 페이지와 동일 출처
        cur.execute(
            "SELECT p.player_id AS player_id, p.player_name AS name, p.team_id AS team, ROUND(w.wRC_half, 1) AS wrc "
            "FROM wrc_plus_comparison w JOIN players p ON p.player_id = CAST(w.batter_ID AS TEXT) "
            "WHERE w.season=? AND w.PA >= ? "
            "ORDER BY w.wRC_half DESC LIMIT 5",
            (season, qual_pa),
        )
        wrc_top = [{"player_id": d.get("player_id"), "name": d["name"], "team": d["team"], "code": _code(d["team"]),
                    "value": ("%.1f" % d["wrc"]) if d["wrc"] is not None else "-"}
                   for d in (dict(r) for r in cur.fetchall())]

        # wOBA : 동일 wrc_plus_comparison 출처, 규정타석 충족자 Top5
        cur.execute(
            "SELECT p.player_id AS player_id, p.player_name AS name, p.team_id AS team, ROUND(w.wOBA, 3) AS woba "
            "FROM wrc_plus_comparison w JOIN players p ON p.player_id = CAST(w.batter_ID AS TEXT) "
            "WHERE w.season=? AND w.PA >= ? "
            "ORDER BY w.wOBA DESC LIMIT 5",
            (season, qual_pa),
        )
        woba_top = [{"player_id": d.get("player_id"), "name": d["name"], "team": d["team"], "code": _code(d["team"]),
                     "value": ("%.3f" % d["woba"]) if d["woba"] is not None else "-"}
                    for d in (dict(r) for r in cur.fetchall())]

        # 투수 (정렬 기준이 달라 파이썬에서 산정)
        cur.execute(
            "SELECT p.player_id AS player_id, p.player_name AS name, p.team_id AS team, ps.earned_run_average AS era, "
            "ps.innings_pitched AS ip, ps.strikeout AS k, "
            "ps.strikeout_per_pa AS kpct, ps.base_on_balls_per_pa AS bbpct "
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
            try:
                d["_kpct"] = float(d["kpct"])
            except (TypeError, ValueError):
                d["_kpct"] = None
            try:
                d["_bbpct"] = float(d["bbpct"])
            except (TypeError, ValueError):
                d["_bbpct"] = None
            pit.append(d)

        def _pit_entry(d, val):
            return {"player_id": d.get("player_id"), "name": d["name"], "team": d["team"], "code": _code(d["team"]), "value": val}

        # 이닝/탈삼진: 누적(규정 미적용). ERA/K%/BB%/K-BB%: 규정이닝 충족자.
        qual_pit = [x for x in pit if x["_outs"] >= qual_outs]
        ip_top = [_pit_entry(d, str(d.get("ip") or "").strip())
                  for d in sorted(pit, key=lambda x: -x["_outs"])[:5]]
        k_top = [_pit_entry(d, str(d["_k"]))
                 for d in sorted(pit, key=lambda x: -x["_k"])[:5]]
        era_top = [_pit_entry(d, "%.2f" % d["_era"])
                   for d in sorted(qual_pit, key=lambda x: x["_era"])[:5]]
        # K%는 높을수록, BB%는 낮을수록 상위
        kpct_top = [_pit_entry(d, "%.1f%%" % d["_kpct"])
                    for d in sorted([x for x in qual_pit if x["_kpct"] is not None], key=lambda x: -x["_kpct"])[:5]]
        bbpct_top = [_pit_entry(d, "%.1f%%" % d["_bbpct"])
                     for d in sorted([x for x in qual_pit if x["_bbpct"] is not None], key=lambda x: x["_bbpct"])[:5]]
        # K-BB% = K% - BB% (높을수록 상위), 규정이닝 충족자
        def _kbb(x):
            return None if (x["_kpct"] is None or x["_bbpct"] is None) else (x["_kpct"] - x["_bbpct"])
        kbb_top = [_pit_entry(d, "%.1f%%" % _kbb(d))
                   for d in sorted([x for x in qual_pit if _kbb(x) is not None], key=lambda x: -_kbb(x))[:5]]

        conn.close()
        result = {
            "season": season,
            "qual_pa": qual_pa,
            "qual_ip": team_g,
            "wrc_pf_season": season,
            "batter": {"avg": avg_top, "obp": obp_top, "slg": slg_top,
                       "ops": ops_top, "woba": woba_top, "wrc": wrc_top},
            "pitcher": {"ip": ip_top, "k": k_top, "era": era_top,
                        "kpct": kpct_top, "bbpct": bbpct_top, "kbb": kbb_top},
        }
        _LEADERS_CACHE[ckey] = (_time.time(), result)
        return result
    except Exception as e:
        return {"season": season,
                "batter": {"avg": [], "obp": [], "slg": [], "ops": [], "woba": [], "wrc": []},
                "pitcher": {"ip": [], "k": [], "era": [], "kpct": [], "bbpct": [], "kbb": []},
                "error": str(e)}

