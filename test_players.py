import sqlite3
import json

def test_player_info(player_id):
    conn = sqlite3.connect("database/kbo_stats.db")
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    try:
        # 1. Player Info
        cur.execute("SELECT * FROM players WHERE player_id = ?", (player_id,))
        player = cur.fetchone()
        if not player:
            return {"error": "Player not found"}
        
        result = {"player": dict(player)}
        
        # 2. Batter Stats 2025
        try:
            cur.execute("SELECT * FROM kbo_official_batter_stats WHERE player_id = ? AND season = 2025", (player_id,))
            batter = cur.fetchone()
            result["batter_stats"] = dict(batter) if batter else None
        except Exception as e:
            result["batter_stats_error"] = str(e)

        # 3. Pitcher Stats 2025
        try:
            cur.execute("SELECT * FROM kbo_official_pitcher_stats WHERE player_id = ? AND season = 2025", (player_id,))
            pitcher = cur.fetchone()
            result["pitcher_stats"] = dict(pitcher) if pitcher else None
        except Exception as e:
            result["pitcher_stats_error"] = str(e)
            
        return result
    except Exception as e:
        return {"error": str(e)}
    finally:
        conn.close()

if __name__ == "__main__":
    # Test with some Kim Hyun-soo IDs if possible, or just the first player
    conn = sqlite3.connect("database/kbo_stats.db")
    cur = conn.cursor()
    cur.execute("SELECT player_id, player_name FROM players WHERE player_name LIKE '%김현수%'")
    players = cur.fetchall()
    conn.close()
    
    results = []
    for pid, name in players:
        results.append({"name": name, "id": pid, "data": test_player_info(pid)})
    
    print(json.dumps(results, indent=2, ensure_ascii=False))
