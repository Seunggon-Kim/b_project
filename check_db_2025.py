import sqlite3

conn = sqlite3.connect('database/kbo_stats.db')
cur = conn.cursor()

cur.execute('SELECT COUNT(*) FROM games WHERE season = 2025')
games_count = cur.fetchone()[0]

cur.execute('SELECT COUNT(*) FROM play_by_play WHERE gameID LIKE "2025%"')
plays_count = cur.fetchone()[0]

conn.close()

print(f"✅ 2025 시즌 경기 수: {games_count}개")
print(f"✅ 2025 시즌 플레이 수: {plays_count:,}개")
