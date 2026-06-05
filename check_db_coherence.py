import sqlite3
import os

db_path = r'c:\Users\김승곤\Desktop\b_project\database\kbo_stats.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("--- Sample from play_by_play ---")
cur.execute("SELECT pitcher_ID, pitcher, pitch_type FROM play_by_play WHERE pitch_type IS NOT NULL LIMIT 5")
rows = cur.fetchall()
for r in rows:
    print(r)

print("\n--- Sample from kbo_official_pitcher_stats ---")
cur.execute("SELECT player_id, player_name FROM kbo_official_pitcher_stats LIMIT 5")
rows = cur.fetchall()
for r in rows:
    print(r)

conn.close()
