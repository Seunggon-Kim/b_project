import sqlite3
import os

db_path = "/home/ubuntu/b_project/database/kbo_stats.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

print("--- Batter Stats Schema ---")
cur.execute("PRAGMA table_info(kbo_official_batter_stats)")
cols = [r['name'] for r in cur.fetchall()]
print(cols)

print("\n--- Pitcher Stats Schema ---")
cur.execute("PRAGMA table_info(kbo_official_pitcher_stats)")
cols = [r['name'] for r in cur.fetchall()]
print(cols)

print("\n--- Sample Batter Data ---")
cur.execute("SELECT * FROM kbo_official_batter_stats LIMIT 5")
for row in cur.fetchall():
    print(dict(row))

conn.close()
