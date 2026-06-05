import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()
name = '장규현'
cur.execute("SELECT p.player_id, p.player_name, p.team_id FROM players p WHERE p.player_name = ?", (name,))
for row in cur.fetchall():
    print(dict(row))
conn.close()
