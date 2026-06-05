import pandas as pd
df = pd.read_csv("/home/ubuntu/b_project/crawler/save/official_stats/batter_stats_2025.csv")
for col in df.columns:
    print(f"COL: {col}")
