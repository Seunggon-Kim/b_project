import sqlite3
import csv
import os
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'

def import_csv_lite(csv_path):
    print(f"Importing {csv_path} to DB...")
    
    # Connect
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Try encodings
    rows = []
    for encoding in ["utf-8", "cp949"]:
        try:
            with open(csv_path, "r", encoding=encoding) as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                break
        except Exception:
            continue
    else:
        print(f"Failed to decode {csv_path}")
        return

    last_row = None
    rows_added = 0
    game_id = None
    
    target_columns = [
        'pitch_type', 'pitcher', 'batter', 'pitcher_ID', 'batter_ID', 'speed',
        'pitch_result', 'pa_result', 'pa_result_detail', 'description',
        'balls', 'strikes', 'outs', 'inning', 'inning_topbot', 'score_away',
        'score_home', 'outs_on_play', 'runs_scored', 'stands', 'throws',
        'on_1b', 'on_2b', 'on_3b', 'pos_1', 'pos_2', 'pos_3', 'pos_4', 'pos_5',
        'pos_6', 'pos_7', 'pos_8', 'pos_9', 'on_1b_id', 'on_2b_id', 'on_3b_id',
        'pos_1_id', 'pos_2_id', 'pos_3_id', 'pos_4_id', 'pos_5_id', 'pos_6_id',
        'pos_7_id', 'pos_8_id', 'pos_9_id', 'px', 'pz', 'pfx_x', 'pfx_z',
        'pfx_x_raw', 'pfx_z_raw', 'x0', 'z0', 'sz_top', 'sz_bot', 'y0',
        'vx0', 'vy0', 'vz0', 'ax', 'ay', 'az', 'game_date', 'home', 'away',
        'home_alias', 'away_alias', 'stadium', 'referee', 'pa_number',
        'pitch_number', 'pitchID', 'gameID'
    ]

    for row in rows:
        game_id = row.get("gameID")
        last_row = row
        
        placeholders = ", ".join(["?"] * len(target_columns))
        columns_str = ", ".join(target_columns)
        
        pbp_data = [row.get(col) for col in target_columns]
        
        cur.execute(f"""
            INSERT INTO play_by_play ({columns_str}) VALUES ({placeholders})
        """, pbp_data)
        rows_added += 1

    if last_row:
        game_date = last_row.get("game_date")
        season = game_date[:4] if game_date else "2025"
        home_id = last_row.get("home_alias")
        away_id = last_row.get("away_alias")
        h_score = int(last_row.get("score_home", 0)) if last_row.get("score_home") else 0
        a_score = int(last_row.get("score_away", 0)) if last_row.get("score_away") else 0
        stadium = last_row.get("stadium")
        
        cur.execute("""
            INSERT OR REPLACE INTO games (
                game_id, game_date, season, game_type, home_team_id, 
                away_team_id, home_score, away_score, stadium
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (game_id, game_date, season, "정규시즌", home_id, away_id, h_score, a_score, stadium))

    conn.commit()
    conn.close()
    print(f"Successfully added {rows_added} rows for game {game_id}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        import_csv_lite(sys.argv[1])
    else:
        csv_dir = PROJECT_ROOT / 'crawler' / 'save' / '2025'
        for csv_file in csv_dir.glob("*.csv"):
            import_csv_lite(str(csv_file))
