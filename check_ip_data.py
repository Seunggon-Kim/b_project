import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("""
    SELECT p.player_name, ps.innings_pitched 
    FROM kbo_official_pitcher_stats ps
    JOIN players p ON ps.player_id = p.player_id 
    LIMIT 20
""")
for r in cur.fetchall():
    print(f"{r[0]}: {r[1]} (Type: {type(r[1])})")
conn.close()
