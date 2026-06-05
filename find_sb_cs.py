import pandas as pd
df = pd.read_csv("/home/ubuntu/b_project/crawler/save/official_stats/batter_stats_2025.csv")
print("All columns:", df.columns.tolist())
potential = [c for c in df.columns if any(x in c.lower() for x in ['steal', 'sb', 'cs', 'stolen', 'caught', '도루', '도실'])]
print("Potential columns for SB/CS:", potential)
