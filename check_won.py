import sqlite3
db_path = '/home/ubuntu/b_project/database/kbo_stats.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
pid = '69446'
cur.execute("""
    SELECT stands, count(*) 
    FROM play_by_play 
    WHERE pitcher_ID = ? AND pitch_type IS NOT NULL AND pitch_type != ''
    GROUP BY stands
""", (pid,))
print(f"Stands for {pid}:")
print(cur.fetchall())
conn.close()
