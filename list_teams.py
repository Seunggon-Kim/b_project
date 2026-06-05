
import sqlite3

def list_teams():
    conn = sqlite3.connect('database/kbo_stats.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM teams")
    rows = cur.fetchall()
    print("Teams Table:")
    for row in rows:
        print(row)
    conn.close()

if __name__ == "__main__":
    list_teams()
