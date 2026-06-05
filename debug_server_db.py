import sqlite3
import os

db_path = "/home/ubuntu/b_project/database/kbo_stats.db"
if not os.path.exists(db_path):
    print(f"Error: DB not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("--- Testing Player Query ---")
cur.execute("SELECT player_id, player_name, team_id FROM players WHERE player_name LIKE '%원태인%'")
rows = cur.fetchall()
for row in rows:
    print(f"ID: {row[0]}, Name: {row[1]}, Team: {row[2]}")

if rows:
    pid = rows[0][0]
    print(f"\n--- Testing Stats for {rows[0][1]} ({pid}) ---")
    cur.execute("SELECT season, wins, earned_run_average FROM kbo_official_pitcher_stats WHERE player_id = ? ORDER BY season DESC", (pid,))
    stats = cur.fetchall()
    print(f"Stats found: {len(stats)}")
    for s in stats:
        print(f"Season: {s[0]}, Wins: {s[1]}, ERA: {s[2]}")

conn.close()
