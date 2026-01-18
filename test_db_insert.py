import sqlite3
import csv
from pathlib import Path

PROJECT_ROOT = Path(r'c:\Users\USERNAME\Desktop\b_project')
DB_PATH = PROJECT_ROOT / 'database' / 'kbo_stats.db'
CSV_DIR = PROJECT_ROOT / 'crawler' / 'save' / '2025'

# Get first CSV file
csv_files = sorted(list(CSV_DIR.glob("*.csv")))
csv_path = csv_files[0]

print(f"Testing file: {csv_path.name}")

# Try to read the file
rows = []
for encoding in ["utf-8", "utf-8-sig", "cp949"]:
    try:
        with open(csv_path, "r", encoding=encoding) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                print(f"✅ Successfully read with {encoding}: {len(rows)} rows")
                break
    except Exception as e:
        print(f"❌ Failed with {encoding}: {str(e)[:100]}")

if not rows:
    print("❌ Could not read file with any encoding")
    exit(1)

# Check the columns
print(f"\nColumns in CSV: {list(rows[0].keys())[:15]}")
print(f"\nFirst row sample:")
for key in list(rows[0].keys())[:10]:
    print(f"  {key}: {rows[0].get(key)}")

# Try to insert into DB
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

try:
    # Get the last row for game info
    last_row = rows[-1]
    
    # Check required fields
    print(f"\nChecking required fields:")
    print(f"  gameID: {last_row.get('gameID')}")
    print(f"  game_date: {last_row.get('game_date')}")
    print(f"  home_alias: {last_row.get('home_alias')}")
    print(f"  away_alias: {last_row.get('away_alias')}")
    print(f"  score_home: {last_row.get('score_home')}")
    print(f"  score_away: {last_row.get('score_away')}")
    print(f"  stadium: {last_row.get('stadium')}")
    
    # Try to insert first row
    row = rows[0]
    
    # outs value clipping
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
        if "초" in top_bottom: top_bottom = "초"
        elif "말" in top_bottom: top_bottom = "말"
        else: top_bottom = "초"
    
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
        None  # timestamp
    )
    
    print(f"\nTrying to insert play-by-play data:")
    print(f"  Data: {pbp_data[:7]}...")
    
    cur.execute("""
        INSERT INTO play_by_play (
            game_id, inning, top_bottom, outs, batter_id, pitcher_id, 
            play_result, play_description, base_1, base_2, base_3, 
            runs_scored, home_score, away_score, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, pbp_data)
    
    print("✅ Successfully inserted play-by-play row")
    
    # Insert game info
    game_date = last_row.get("game_date")
    season = game_date[:4] if game_date else "2025"
    game_id = last_row.get("gameID")
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
    
    print("✅ Successfully inserted game info")
    
    conn.commit()
    print("\n✅ All operations successful!")
    
except Exception as e:
    print(f"\n❌ Error during database operations: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    conn.close()
