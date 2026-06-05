import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
print("Teams table:")
cur.execute("SELECT team_id, team_name FROM teams")
for row in cur.fetchall():
    print(row)

print("\nPlayers table unique team_ids (first 10):")
cur.execute("SELECT DISTINCT team_id FROM players LIMIT 10")
for row in cur.fetchall():
    print(row)
conn.close()
