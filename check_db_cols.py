import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
c = conn.cursor()
c.execute("PRAGMA table_info(kbo_official_batter_stats)")
for r in c.fetchall():
    print(f"BAT_COL: {r[1]}")
c.execute("PRAGMA table_info(kbo_official_pitcher_stats)")
for r in c.fetchall():
    print(f"PIT_COL: {r[1]}")
conn.close()
