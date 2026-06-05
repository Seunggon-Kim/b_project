import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = [t[0] for t in cur.fetchall()]
print(json.dumps(tables))
conn.close()
