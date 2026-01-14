import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(r'c:\Users\USERNAME\Desktop\b_project')
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / '2025'

def import_csv_lite_robust(csv_path, existing_game_ids):
    game_id_stem = Path(csv_path).stem
    if game_id_stem in existing_game_ids:
        return True, "skipped"

    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        
        rows = []
        # Try UTF-8 first, then others
        for encoding in ["utf-8", "utf-8-sig", "cp949"]:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    reader = csv.DictReader(f)
                    rows = list(reader)
                    if rows: # Successfully read something
                        break
            except Exception:
                continue
        else:
            return False, f"Failed to decode {csv_path}"

        if not rows:
            return False, "Empty file"

        last_row = None
        rows_added = 0
        game_id = None
        
        for row in rows:
            game_id = row.get("gameID")
            last_row = row
            
            # outs value clipping to satisfy DB constraint (0-2)
            try:
                outs = int(row.get("outs", 0)) if row.get("outs") else 0
                if outs > 2:
                    outs = 2
            except:
                outs = 0
                
            # inning_topbot mapping
            top_bottom = row.get("inning_topbot", "")
            if top_bottom in ["T", "top"]: top_bottom = "초"
            if top_bottom in ["B", "bottom"]: top_bottom = "말"
            if top_bottom not in ["초", "말"]:
                # If it's something else, we might need a default or skip
                # Let's try to infer from 'inning_topbot' if it's garbled but contains '초' or '말'
                if "초" in top_bottom: top_bottom = "초"
                elif "말" in top_bottom: top_bottom = "말"
                else: top_bottom = "초" # Default

            pbp_data = (
                row.get("gameID"),
                int(row.get("inning", 1)) if row.get("inning") else 1,
                top_bottom,
                outs,
                row.get("batter_ID"),
                row.get("pitcher_ID"),
                row.get("pa_result") if row.get("pa_result") else row.get("pitch_result"),
                row.get("description"),
                row.get("on_1b_id"),
                row.get("on_2b_id"),
                row.get("on_3b_id"),
                int(row.get("runs_scored", 0)) if row.get("runs_scored") else 0,
                int(row.get("score_home", 0)) if row.get("score_home") else 0,
                int(row.get("score_away", 0)) if row.get("score_away") else 0,
                None # timestamp
            )
            
            cur.execute("""
                INSERT INTO play_by_play (
                    game_id, inning, top_bottom, outs, batter_id, pitcher_id, 
                    play_result, play_description, base_1, base_2, base_3, 
                    runs_scored, home_score, away_score, timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        return True, f"Success ({rows_added} rows)"
    except Exception as e:
        if conn:
            conn.rollback()
        return False, str(e)
    finally:
        if conn:
            conn.close()

def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT game_id FROM games")
    existing_game_ids = set(row[0] for row in cur.fetchall())
    conn.close()
    
    csv_files = sorted(list(CSV_DIR.glob("*.csv")))
    
    success_count = 0
    skip_count = 0
    fail_count = 0
    
    for i, csv_file in enumerate(csv_files, 1):
        success, message = import_csv_lite_robust(str(csv_file), existing_game_ids)
        if success:
            if message == "skipped":
                skip_count += 1
            else:
                success_count += 1
        else:
            fail_count += 1
            print(f"FAILED: {csv_file.name} - {message}")
            
    print(f"\nFinal Results: {success_count} added, {skip_count} skipped, {fail_count} failed.")
    
    # Verify final count
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM games WHERE season = 2025")
    print(f"Total games in 2025 DB: {cur.fetchone()[0]}")
    conn.close()

if __name__ == "__main__":
    main()
