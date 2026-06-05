import sqlite3

db_path = r'c:\Users\김승곤\Desktop\b_project\database\kbo_stats.db'

def check_db_summary():
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("--- Database Summary ---")
        
        # 1. Season count
        cursor.execute("SELECT season, COUNT(*) FROM games GROUP BY season")
        seasons = cursor.fetchall()
        for s in seasons:
            print(f"Season {s[0]}: {s[1]} games")
            
        # 2. Total counts in other tables
        cursor.execute("SELECT COUNT(*) FROM players")
        print(f"Total players: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM play_by_play")
        print(f"Total play-by-play entries: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM game_team_stats")
        print(f"Total game_team_stats entries: {cursor.fetchone()[0]}")
        
        # 3. Check for specific date mentioned in history (2025-06-28)
        cursor.execute("SELECT game_id FROM games WHERE game_date = '2025-06-28'")
        games_0628 = cursor.fetchall()
        print(f"Games on 2025-06-28: {[g[0] for g in games_0628]}")

        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    check_db_summary()
