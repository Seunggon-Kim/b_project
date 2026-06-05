import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
def pr(t):
    print(f"@@@ {t} @@@")
    c = conn.cursor()
    c.execute(f"PRAGMA table_info({t})")
    for r in c.fetchall():
        print(f"{r[1]} ({r[2]})")

pr("kbo_official_batter_stats")
pr("kbo_official_pitcher_stats")
conn.close()
