import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path('database/kbo_stats.db')
conn = sqlite3.connect(DB_PATH)

print("--- 타자 통계 샘플 (K%, BB% 확인) ---")
df_b = pd.read_sql("SELECT player_name, season, plate_appearance, strikeout, base_on_balls, strikeout_per_pa, base_on_balls_per_pa FROM kbo_official_batter_stats LIMIT 5", conn)
print(df_b)

print("\n--- 투수 통계 샘플 (K%, BB% 확인) ---")
df_p = pd.read_sql("SELECT player_name, season, total_batters_faced, strikeout, base_on_balls, strikeout_per_pa, base_on_balls_per_pa FROM kbo_official_pitcher_stats LIMIT 5", conn)
print(df_p)

conn.close()
