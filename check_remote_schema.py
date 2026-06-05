import sqlite3
import os

db_path = "database/kbo_stats.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()

def check_table(table_name):
    print(f"\n--- {table_name} ---")
    cur.execute(f"PRAGMA table_info({table_name})")
    cols = [row[1] for row in cur.fetchall()]
    print(", ".join(cols))

check_table("players")
check_table("teams")
check_table("kbo_official_batter_stats")
check_table("kbo_official_pitcher_stats")

conn.close()
