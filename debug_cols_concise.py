import sqlite3
c = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = c.cursor()
cur.execute("PRAGMA table_info(kbo_official_batter_stats)")
print(",".join([r[1] for r in cur.fetchall()]))
c.close()
