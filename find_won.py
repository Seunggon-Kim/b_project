import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("SELECT player_id, player_name, team_id FROM players WHERE player_name LIKE '%원태인%'")
print("All Won Tae-in players:")
for row in cur.fetchall():
    print(row)
conn.close()
