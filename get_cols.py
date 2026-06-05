import sqlite3
conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()
cur.execute('PRAGMA table_info(play_by_play)')
for c in cur.fetchall():
    print(c[1])
conn.close()
