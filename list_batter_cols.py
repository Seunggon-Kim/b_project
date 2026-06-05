import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(kbo_official_batter_stats)")
print("Columns in kbo_official_batter_stats:")
for row in cur.fetchall():
    print(row[1])
conn.close()
