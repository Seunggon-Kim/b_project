import sqlite3
import json

def get_db_data():
    conn = sqlite3.connect("database/kbo_stats.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    data = {}
    tables = ["games", "players", "teams", "kbo_official_batter_stats", "kbo_official_pitcher_stats"]
    
    for table in tables:
        try:
            cur.execute(f"SELECT * FROM {table} LIMIT 1")
            row = cur.fetchone()
            if row:
                data[table] = dict(row)
            else:
                data[table] = "empty"
        except Exception as e:
            data[table] = f"Error: {str(e)}"
            
    conn.close()
    return data

if __name__ == "__main__":
    print(json.dumps(get_db_data(), indent=2, ensure_ascii=False))
