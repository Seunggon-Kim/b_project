import sqlite3
import json

def get_all_teams():
    conn = sqlite3.connect("database/kbo_stats.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams")
    teams = [dict(row) for row in cur.fetchall()]
    conn.close()
    return teams

if __name__ == "__main__":
    print(json.dumps(get_all_teams(), indent=2, ensure_ascii=False))
