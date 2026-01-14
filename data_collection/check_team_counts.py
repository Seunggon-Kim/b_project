import os
import pandas as pd
from collections import Counter

csv_dir = r"C:\Users\USERNAME\Desktop\b_project\crawler\save\2025"
files = [f for f in os.listdir(csv_dir) if f.endswith(".csv")]

team_games = Counter()

for f in files:
    # Pattern: YYYYMMDDHHAW0YYYY.csv
    # Teams are at indices 8:10 and 10:12 usually, but let's be smarter.
    # The filename format is 20250322HHKT02025.csv
    # Date: 20250322 (8 chars)
    # Away: HH (2 chars)
    # Home: KT (2 chars)
    # Number: 0 (1 char)
    # Year: 2025 (4 chars)
    
    away = f[8:10]
    home = f[10:12]
    
    # Some team codes might be 3 chars? No, Korean team codes are usually 2 letters (OB, LG, SS, HT, LT, SK, HH, KT, NC, WO)
    # Wait, SK is SSG now (SK is the old code used in this crawler).
    # OB is Doosan.
    # HT is KIA.
    # WO is Kiwoom.
    
    team_games[away] += 1
    team_games[home] += 1

print("Team Game Counts (Expected 144):")
for team, count in sorted(team_games.items()):
    print(f"{team}: {count}")

print(f"\nTotal Files: {len(files)}")
print(f"Total Unique Combinations (should be 720): {len(files)}")
