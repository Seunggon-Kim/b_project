import sqlite3
import json

try:
    conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    cur.execute('SELECT team_id, team_name FROM teams')
    teams = [dict(row) for row in cur.fetchall()]
    print("Teams:", json.dumps(teams, ensure_ascii=False))
    
    cur.execute('SELECT DISTINCT team_id FROM players')
    player_teams = [row[0] for row in cur.fetchall()]
    print("Player Teams:", player_teams)
    
    conn.close()
except Exception as e:
    print(f"Error: {e}")
