import sqlite3
db_path = '/home/ubuntu/b_project/database/kbo_stats.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
    SELECT pitcher_ID, count(*) 
    FROM play_by_play 
    WHERE pitch_type IS NOT NULL AND pitch_type != ''
    GROUP BY pitcher_ID 
    HAVING count(*) = 1061
""")
res = cur.fetchall()
print("Pitchers with 1061 pitches:", res)
if res:
    pid = res[0][0]
    cur.execute("SELECT stands, count(*) FROM play_by_play WHERE pitcher_ID = ? GROUP BY stands", (pid,))
    print(f"Stands for {pid}:", cur.fetchall())
conn.close()
