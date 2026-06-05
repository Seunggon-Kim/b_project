import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(play_by_play);")
cols = cur.fetchall()
print(json.dumps(cols, indent=2))
conn.close()
