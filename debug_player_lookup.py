
import sqlite3

def debug_search():
    conn = sqlite3.connect('database/kbo_stats.db')
    cur = conn.cursor()
    
    q = '원태인'
    print(f"Searching for '{q}' in players table...")
    cur.execute("SELECT player_id, player_name FROM players WHERE player_name LIKE ?", (f'%{q}%',))
    results = cur.fetchall()
    print(f"Search results: {results}")
    
    conn.close()

if __name__ == "__main__":
    debug_search()
