import sqlite3
db_path = '/home/ubuntu/b_project/database/kbo_stats.db'
conn = sqlite3.connect(db_path)
cur = conn.cursor()
cur.execute("""
    SELECT pitcher_ID, count(*) 
    FROM play_by_play 
    WHERE pitch_type IS NOT NULL AND pitch_type != ''
    GROUP BY pitcher_ID 
    HAVING count(*) = 2493
""")
print("Pitcher with 2493 pitches:", cur.fetchall())

# If not 2493 exactly, maybe nearby
cur.execute("""
    SELECT p.player_name, p.player_id, count(*) 
    FROM play_by_play pbp
    JOIN players p ON pbp.pitcher_ID = p.player_id
    WHERE pbp.pitch_type IS NOT NULL AND pbp.pitch_type != ''
    GROUP BY pitcher_ID 
    ORDER BY abs(count(*) - 2493) ASC
    LIMIT 5
""")
print("\nTop 5 pitchers closest to 2493 pitches:")
print(cur.fetchall())
conn.close()
