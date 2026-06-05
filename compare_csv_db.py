import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(r'c:\Users\김승곤\Desktop\b_project')
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / '2025'

def verify_merge():
    # 1. Get game IDs from CSV files
    csv_files = list(CSV_DIR.glob("*.csv"))
    csv_game_ids = set(f.stem for f in csv_files)
    print(f"Games in CSV folder: {len(csv_game_ids)}")

    # 2. Get game IDs from DB
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM games WHERE season = 2025")
    db_game_ids = set(row[0] for row in cur.fetchall())
    conn.close()
    print(f"Games in Database: {len(db_game_ids)}")

    # 3. Find missing games
    missing_in_db = csv_game_ids - db_game_ids
    print(f"Missing in DB: {len(missing_in_db)}")

    if missing_in_db:
        print("\nSample missing games (up to 10):")
        for gid in list(missing_in_db)[:10]:
            print(f"  {gid}")

    # 4. Check for games on 2025-06-28 (the problematic date)
    games_0628 = [gid for gid in csv_game_ids if gid.startswith('20250628')]
    print(f"\nGames found in CSV for 20250628: {games_0628}")
    
    db_games_0628 = [gid for gid in db_game_ids if gid.startswith('20250628')]
    print(f"Games found in DB for 20250628: {db_games_0628}")

if __name__ == "__main__":
    verify_merge()
