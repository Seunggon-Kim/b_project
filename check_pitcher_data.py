import sqlite3
import json

conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
cur = conn.cursor()

# Get a pitcher with many records
cur.execute('SELECT pitcher_ID, COUNT(*) as cnt FROM play_by_play GROUP BY pitcher_ID ORDER BY cnt DESC LIMIT 1')
pid = cur.fetchone()[0]

cur.execute('SELECT DISTINCT throws FROM play_by_play WHERE pitcher_ID = ?', (pid,))
throws = cur.fetchall()
print(f"Pitcher {pid} throws: {throws}")

cur.execute('SELECT DISTINCT stands FROM play_by_play WHERE pitcher_ID = ?', (pid,))
stands = cur.fetchall()
print(f"Pitcher {pid} faces stands: {stands}")

conn.close()
