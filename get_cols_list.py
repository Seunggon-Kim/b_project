import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("SELECT * FROM kbo_official_batter_stats LIMIT 1")
for d in cur.description:
    print(d[0])
conn.close()
