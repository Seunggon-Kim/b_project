import sqlite3
import json

def get_schema():
    conn = sqlite3.connect("database/kbo_stats.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    schema = {}
    tables = ["games", "players", "teams", "kbo_official_batter_stats", "kbo_official_pitcher_stats"]
    
    for table in tables:
        try:
            cur.execute(f"SELECT * FROM {table} LIMIT 1")
            row = cur.fetchone()
            if row:
                schema[table] = list(row.keys())
            else:
                cur.execute(f"PRAGMA table_info({table})")
                schema[table] = [r[1] for r in cur.fetchall()]
        except Exception as e:
            schema[table] = f"Error: {str(e)}"
            
    conn.close()
    return schema

if __name__ == "__main__":
    print(json.dumps(get_schema(), indent=2))
