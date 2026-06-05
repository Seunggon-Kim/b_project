import sqlite3
db_path = '/home/ubuntu/b_project/database/kbo_stats.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("SELECT * FROM players LIMIT 1")
desc = [d[0] for d in cur.description]
row = cur.fetchone()
print(dict(zip(desc, row)))
conn.close()
