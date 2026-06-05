import sqlite3
try:
    conn = sqlite3.connect('/home/ubuntu/b_project/database/kbo_stats.db')
    cur = conn.cursor()
    cur.execute('SELECT COUNT(*) FROM teams')
    teams_count = cur.fetchone()[0]
    cur.execute('SELECT COUNT(*) FROM players')
    players_count = cur.fetchone()[0]
    print(f"Teams: {teams_count}")
    print(f"Players: {players_count}")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
