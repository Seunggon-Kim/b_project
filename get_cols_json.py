import sqlite3
import json
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("SELECT * FROM kbo_official_batter_stats LIMIT 1")
desc = [d[0] for d in cur.description]
print(json.dumps(desc))
conn.close()
