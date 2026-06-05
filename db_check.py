import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- Sample Batter Stats (2025) ---")
cur.execute("SELECT player_id, player_name, season FROM kbo_official_batter_stats WHERE season = 2025 LIMIT 5")
for row in cur.fetchall():
    print(dict(row))

print("\n--- Sample Players ---")
cur.execute("SELECT player_id, player_name, team_id FROM players LIMIT 5")
for row in cur.fetchall():
    print(dict(row))

print("\n--- Testing Join ---")
cur.execute("""
    SELECT b.player_name, p.team_id 
    FROM kbo_official_batter_stats b
    JOIN players p ON b.player_id = p.player_id
    WHERE b.season = 2025
    LIMIT 10
""")
for row in cur.fetchall():
    print(dict(row))

conn.close()
