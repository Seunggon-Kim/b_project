import sqlite3

db_path = "/home/ubuntu/b_project/database/kbo_stats.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

def dump_cols(table):
    print(f"--- {table} ---")
    cur.execute(f"SELECT * FROM {table} LIMIT 1")
    row = cur.fetchone()
    if row:
        for k in dict(row).keys():
            print(k)

dump_cols("kbo_official_batter_stats")
dump_cols("kbo_official_pitcher_stats")
conn.close()
