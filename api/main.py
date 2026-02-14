"""
KBO Baseball Analytics API
FastAPI backend for JavaScript dashboard
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import sqlite3
from pathlib import Path
from typing import Optional, List
import datetime

app = FastAPI(title="KBO Analytics API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DB 경로
DB_PATH = Path(__file__).parent.parent / 'database' / 'kbo_stats.db'


def get_db_connection():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/")
async def root():
    """API 루트"""
    return {
        "message": "KBO Baseball Analytics API",
        "version": "1.0.0",
        "endpoints": [
            "/dashboard/stats",
            "/teams",
            "/players/search",
            "/players/{player_id}",
            "/stats/batters",
            "/stats/pitchers",
            "/games"
        ]
    }


@app.get("/dashboard/stats")
async def get_dashboard_stats():
    """대시보드 메인 통계"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 2025 시즌 데이터
        cur.execute("SELECT COUNT(*) as count FROM games WHERE season = 2025")
        games_2025 = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM play_by_play WHERE gameID LIKE '2025%'")
        plays_2025 = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM kbo_official_batter_stats WHERE season = 2025")
        batters_2025 = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM kbo_official_pitcher_stats WHERE season = 2025")
        pitchers_2025 = cur.fetchone()['count']
        
        cur.execute("SELECT COUNT(*) as count FROM teams")
        teams_count = cur.fetchone()['count']
        
        conn.close()
        
        return {
            "season": 2025,
            "games": games_2025,
            "plays": plays_2025,
            "batters": batters_2025,
            "pitchers": pitchers_2025,
            "teams": teams_count,
            "completion_rate": round((games_2025 / 720 * 100), 1) if games_2025 > 0 else 0,
            "last_update": datetime.date.today().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/teams")
async def get_teams():
    """팀 목록"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT team_id, team_name, stadium, founded_year
            FROM teams
            ORDER BY team_name
        """)
        
        teams = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {"teams": teams}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/players/search")
async def search_players(q: str):
    """선수 검색"""
    if not q or len(q) < 1:
        return {"players": []}
    
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                player_id,
                player_name,
                team_id,
                back_number,
                position
            FROM players
            WHERE player_name LIKE ?
            ORDER BY player_name
            LIMIT 50
        """, (f'%{q}%',))
        
        players = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {"players": players}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/players/{player_id}")
async def get_player_info(player_id: str):
    """선수 상세 정보"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 기본 정보
        cur.execute("""
            SELECT 
                player_id,
                player_name,
                team_id,
                back_number,
                position,
                throw,
                bat,
                birthday,
                height,
                weight,
                career,
                draft_year,
                draft_order,
                signing_bonus,
                salary,
                image_url
            FROM players
            WHERE player_id = ?
        """, (player_id,))
        
        player = cur.fetchone()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        
        player_dict = dict(player)
        
        # 타자 성적 (2025)
        cur.execute("""
            SELECT 
                plate_appearance,
                at_bat,
                run,
                single,
                double,
                triple,
                home_run,
                batting_average,
                on_base_percentage,
                slugging_percentage,
                on_base_plus_slugging as ops
            FROM kbo_official_batter_stats
            WHERE player_id = ? AND season = 2025
        """, (player_id,))
        
        batter_stats = cur.fetchone()
        player_dict['batter_stats'] = dict(batter_stats) if batter_stats else None
        
        # 타자 성적 (전체 시즌)
        cur.execute("""
            SELECT 
                season,
                plate_appearance,
                at_bat,
                run,
                single + double + triple + home_run as hits,
                home_run,
                batting_average,
                on_base_percentage,
                slugging_percentage,
                on_base_plus_slugging as ops
            FROM kbo_official_batter_stats
            WHERE player_id = ?
            ORDER BY season DESC
        """, (player_id,))
        
        batter_seasons = [dict(row) for row in cur.fetchall()]
        player_dict['batter_seasons'] = batter_seasons
        
        # 투수 성적 (2025)
        cur.execute("""
            SELECT 
                wins,
                losses,
                earned_run_average,
                games,
                games_started,
                save,
                innings_pitched,
                strikeout,
                walks_plus_hits_per_inning_pitched as whip
            FROM kbo_official_pitcher_stats
            WHERE player_id = ? AND season = 2025
        """, (player_id,))
        
        pitcher_stats = cur.fetchone()
        player_dict['pitcher_stats'] = dict(pitcher_stats) if pitcher_stats else None
        
        # 투수 성적 (전체 시즌)
        cur.execute("""
            SELECT 
                season,
                wins,
                losses,
                earned_run_average,
                games,
                games_started,
                save,
                innings_pitched,
                strikeout,
                walks_plus_hits_per_inning_pitched as whip
            FROM kbo_official_pitcher_stats
            WHERE player_id = ?
            ORDER BY season DESC
        """, (player_id,))
        
        pitcher_seasons = [dict(row) for row in cur.fetchall()]
        player_dict['pitcher_seasons'] = pitcher_seasons
        
        conn.close()
        
        return player_dict
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/batters")
async def get_batter_stats(season: int = 2025, limit: int = 100):
    """타자 통계"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                b.player_id,
                p.player_name,
                p.team_id,
                p.position,
                b.plate_appearance,
                b.at_bat,
                b.run,
                b.single + b.double + b.triple + b.home_run as hits,
                b.home_run,
                b.batting_average,
                b.on_base_percentage,
                b.slugging_percentage,
                b.on_base_plus_slugging as ops
            FROM kbo_official_batter_stats b
            JOIN players p ON b.player_id = p.player_id
            WHERE b.season = ?
            ORDER BY b.batting_average DESC
            LIMIT ?
        """, (season, limit))
        
        batters = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {"batters": batters, "season": season}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stats/pitchers")
async def get_pitcher_stats(season: int = 2025, limit: int = 100):
    """투수 통계"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                ps.player_id,
                p.player_name,
                p.team_id,
                ps.wins,
                ps.losses,
                ps.earned_run_average,
                ps.games,
                ps.games_started,
                ps.save,
                ps.innings_pitched,
                ps.strikeout,
                ps.walks_plus_hits_per_inning_pitched as whip
            FROM kbo_official_pitcher_stats ps
            JOIN players p ON ps.player_id = p.player_id
            WHERE ps.season = ?
            ORDER BY ps.earned_run_average ASC
            LIMIT ?
        """, (season, limit))
        
        pitchers = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {"pitchers": pitchers, "season": season}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/games")
async def get_games(season: int = 2025, limit: int = 50):
    """경기 목록"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT 
                gameID,
                date,
                home_team,
                away_team,
                home_score,
                away_score,
                stadium
            FROM games
            WHERE season = ?
            ORDER BY date DESC
            LIMIT ?
        """, (season, limit))
        
        games = [dict(row) for row in cur.fetchall()]
        conn.close()
        
        return {"games": games, "season": season}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
