import sqlite3
c = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("PRAGMA table_info(kbo_official_batter_stats)")
cols = [r['name'] for r in cur.fetchall()]
print("DB_BATTER_COLS:" + "|".join(cols))
c.close()
