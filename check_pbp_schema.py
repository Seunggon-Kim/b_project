import sqlite3

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()

relevant_tables = ['pbp', 'pitches', 'relay_pbp', 'kbo_pbp'] # Guessing
cur.execute("SELECT name FROM sqlite_master WHERE type='table';")
all_tables = [t[0] for t in cur.fetchall()]

for table_name in all_tables:
    if 'stats' not in table_name and 'teams' not in table_name and 'players' not in table_name:
        print(f"\n--- {table_name} ---")
        cur.execute(f"PRAGMA table_info({table_name});")
        for col in cur.fetchall():
            print(col[1], col[2])

conn.close()
