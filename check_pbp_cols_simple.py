import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()
cur.execute("PRAGMA table_info(play_by_play);")
cols = cur.fetchall()
# Print just (index, name) for brevity
for col in cols:
    print(f"{col[0]}: {col[1]} ({col[2]})")
conn.close()
