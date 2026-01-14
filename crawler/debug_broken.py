import datetime
import os
from pathlib import Path
from download import get_game_ids, get_game_data_renewed
from game_parse import game_status
import pandas as pd

def debug():
    start_date = datetime.date(2025, 6, 28)
    end_date = datetime.date(2025, 6, 28)
    
    print("Fetching game IDs for 2025-06-28...")
    game_ids = get_game_ids(start_date, end_date)
    print(f"Found IDs: {game_ids}")
    
    save_dir = Path("save/2025")
    
    for gid in game_ids:
        gid_year = int(gid[:4])
        if gid_year > 3000: gid_year = int(gid[-4:])
        gid_for_save = f"{gid_year}{gid[4:]}"
        
        file_path = save_dir / f"{gid_for_save}.csv"
        
        if file_path.exists():
            print(f"Game {gid} already exists at {file_path}")
            continue
            
        print(f"\n--- Debugging Game: {gid} ---")
        try:
            print("fetching data via get_game_data_renewed...")
            data = get_game_data_renewed(gid)
            
            if data[0] is None:
                print(f"Error from get_game_data_renewed: {data[-1]}")
                continue
            
            print("parsing game data...")
            gs = game_status()
            # gs.load(gid, pitching_df, batting_df, relay_df)
            gs.load(gid, data[0], data[1], data[2])
            
            parse_result = gs.parse_game(debug_mode=True)
            print(f"Parse result: {parse_result}")
            
            if not parse_result:
                print("Game status might have more info in its internal state.")
                
        except Exception as e:
            print(f"Exception during debugging: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    debug()
