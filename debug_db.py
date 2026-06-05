import sqlite3
import json

try:
    conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM teams')
    teams = [dict(row) for row in cur.fetchall()]
    
    cur.execute('SELECT COUNT(*) FROM kbo_official_batter_stats WHERE season = 2025')
    batter_count = cur.fetchone()[0]
    
    cur.execute('SELECT DISTINCT player_team FROM kbo_official_batter_stats WHERE season = 2025')
    batter_teams = [row[0] for row in cur.fetchall()]
    
    print(json.dumps({
        "teams_in_metadata": teams,
        "batter_record_count_2025": batter_count,
        "teams_with_records_2025": batter_teams
    }, indent=2, ensure_ascii=False))
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
