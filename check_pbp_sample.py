import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT pitcher, pitcher_ID, batter, batter_ID, stands, throws FROM play_by_play LIMIT 5')
rows = [dict(r) for r in cur.fetchall()]
print(json.dumps(rows, indent=2, ensure_ascii=False))
conn.close()
