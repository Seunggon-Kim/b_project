import sqlite3
from pathlib import Path

PROJECT_ROOT = Path(r'c:\Users\USERNAME\Desktop\b_project')
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def show_sample_data():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    print("=" * 100)
    print("1. [games] 테이블 샘플 (최근 5경기)")
    print("-" * 100)
    cur.execute("SELECT game_id, game_date, home_team_id, away_team_id, home_score, away_score, stadium FROM games ORDER BY game_date DESC LIMIT 5")
    columns = [desc[0] for desc in cur.description]
    print(f"{' | '.join(columns)}")
    for row in cur.fetchall():
        print(f"{' | '.join(map(str, row))}")
        
    print("\n" + "=" * 100)
    print("2. [play_by_play] 테이블 샘플 (최근 1경기 상세)")
    print("-" * 100)
    # Get the latest game_id
    cur.execute("SELECT game_id FROM games ORDER BY game_date DESC LIMIT 1")
    latest_game_id = cur.fetchone()[0]
    print(f"경기 ID: {latest_game_id}")
    
    cur.execute("""
        SELECT inning, top_bottom, outs, batter_id, pitcher_id, play_result, play_description 
        FROM play_by_play 
        WHERE game_id = ? 
        LIMIT 10
    """, (latest_game_id,))
    columns = [desc[0] for desc in cur.description]
    print(f"{' | '.join(columns)}")
    for row in cur.fetchall():
        print(f"{' | '.join(map(str, row))}")

    print("\n" + "=" * 100)
    print("3. [teams] 테이블 정보")
    print("-" * 100)
    cur.execute("SELECT team_id, team_name, city, stadium FROM teams")
    columns = [desc[0] for desc in cur.description]
    print(f"{' | '.join(columns)}")
    for row in cur.fetchall():
        print(f"{' | '.join(map(str, row))}")

    conn.close()

if __name__ == "__main__":
    show_sample_data()
