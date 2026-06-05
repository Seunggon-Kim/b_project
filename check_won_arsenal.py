import sqlite3
conn = sqlite3.connect("/home/ubuntu/b_project/database/kbo_stats.db")
cur = conn.cursor()
cur.execute("""
    SELECT pitch_type, COUNT(*) 
    FROM play_by_play 
    WHERE pitcher_ID = '69446' 
    GROUP BY pitch_type
""")
print("Won Tae-in Pitch Types:")
for row in cur.fetchall():
    print(f"'{row[0]}': {row[1]}")
conn.close()
