import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("PRAGMA table_info(players)")
print("Players Table Info:")
for row in cur.fetchall():
    print(row)

cur.execute("SELECT player_id, player_name FROM players WHERE player_name = '원태인'")
p = cur.fetchone()
print(f"Lookup 원태인: {p}")
if p:
    pid = p[0]
    print(f"Type of player_id: {type(pid)}")
    # Try query with string
    cur.execute("SELECT player_name FROM players WHERE player_id = ?", (str(pid),))
    print(f"Query with str({pid}): {cur.fetchone()}")
    # Try query with int
    try:
        cur.execute("SELECT player_name FROM players WHERE player_id = ?", (int(pid),))
        print(f"Query with int({pid}): {cur.fetchone()}")
    except:
        print("Query with int failed")

conn.close()
