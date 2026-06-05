import sqlite3
import json

db_path = "/home/ubuntu/b_project/database/kbo_stats.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def get_cols(table):
    cur.execute(f"PRAGMA table_info({table})")
    return [r['name'] for r in cur.fetchall() if r['name'] not in ['created_at', 'updated_at', 'player_id', 'season', 'player_name', 'team_id', 'player_team']]

batter_cols = get_cols('kbo_official_batter_stats')
pitcher_cols = get_cols('kbo_official_pitcher_stats')

print(json.dumps({'batter': batter_cols, 'pitcher': pitcher_cols}))
conn.close()
