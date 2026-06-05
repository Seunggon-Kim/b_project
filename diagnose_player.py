import sqlite3
import json

def diagnose_player(player_id):
    conn = sqlite3.connect("database/kbo_stats.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    print(f"Testing Player ID: {player_id}")
    steps = [
        ("Base Info", "SELECT * FROM players WHERE player_id = ?", (player_id,)),
        ("Batter 2025", "SELECT * FROM kbo_official_batter_stats WHERE player_id = ? AND season = 2025", (player_id,)),
        ("Batter Seasons", "SELECT * FROM kbo_official_batter_stats WHERE player_id = ? ORDER BY season DESC", (player_id,)),
        ("Pitcher 2025", "SELECT * FROM kbo_official_pitcher_stats WHERE player_id = ? AND season = 2025", (player_id,)),
        ("Pitcher Seasons", "SELECT * FROM kbo_official_pitcher_stats WHERE player_id = ? ORDER BY season DESC", (player_id,))
    ]
    
    for name, sql, params in steps:
        try:
            print(f"  {name}...", end="")
            cur.execute(sql, params)
            rows = cur.fetchall()
            print(f" OK ({len(rows)} rows)")
        except Exception as e:
            print(f" FAIL: {e}")
            
    conn.close()

if __name__ == "__main__":
    conn = sqlite3.connect("database/kbo_stats.db")
    cur = conn.cursor()
    cur.execute("SELECT player_id, player_name FROM players WHERE player_name = '김현수'")
    players = cur.fetchall()
    conn.close()
    
    for pid, name in players:
        diagnose_player(pid)
