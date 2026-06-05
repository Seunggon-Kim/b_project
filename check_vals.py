import sqlite3
c = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
c.row_factory = sqlite3.Row
cur = c.cursor()
cur.execute("""
    SELECT player_name, games_played, hits, rbi, stolen_base, caught_stealing, double_play, sacrifice_hit 
    FROM kbo_official_batter_stats 
    LIMIT 10
""")
for r in cur.fetchall():
    print(dict(r))
c.close()
