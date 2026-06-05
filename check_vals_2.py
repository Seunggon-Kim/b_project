import sqlite3
c = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("SELECT games, hits FROM kbo_official_batter_stats LIMIT 5")
for r in cur.fetchall():
    print(dict(r))
c.close()
