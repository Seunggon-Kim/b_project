
import sqlite3
import json

def check_player(player_id):
    conn = sqlite3.connect('database/kbo_stats.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Player info
    cur.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
    row = cur.fetchone()
    if not row:
        print(f"Player {player_id} not found in players table")
        return
    
    player = dict(row)
    print("--- Player Table Data ---")
    for k, v in player.items():
        print(f"{k}: {v} ({type(v)})")
        
    # Check stats
    cur.execute("SELECT * FROM kbo_official_pitcher_stats WHERE player_id = ? AND season = 2025", (player_id,))
    p_stats = cur.fetchone()
    print(f"\nPitcher Stats 2025: {'Found' if p_stats else 'Not Found'}")
    
    conn.close()

if __name__ == "__main__":
    check_player('69446') # 원태인
