import sqlite3
import pandas as pd

def check_db():
    conn = sqlite3.connect('database/kbo_stats.db')
    cursor = conn.cursor()
    
    # Check tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    print("Tables:", [t[0] for t in tables])
    
    # Check if temp tables exist and have data
    for table in ['batter_stats_temp', 'pitcher_stats_temp', 'team_rankings_temp']:
        if table in [t[0] for t in tables]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"Table '{table}' has {count} rows.")
            
            if count > 0:
                df = pd.read_sql_query(f"SELECT * FROM {table} LIMIT 5", conn)
                print(f"\nSample data from {table}:")
                print(df)
        else:
            print(f"Table '{table}' does not exist.")
    
    conn.close()

if __name__ == "__main__":
    check_db()
