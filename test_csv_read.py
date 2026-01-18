import csv
from pathlib import Path

csv_path = Path('crawler/save/2025/20250322HHKT02025.csv')

# Try different encodings
for encoding in ['utf-8', 'utf-8-sig', 'cp949']:
    try:
        with open(csv_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            if rows:
                print(f"✅ Success with {encoding}")
                print(f"Total rows: {len(rows)}")
                print(f"Columns: {list(rows[0].keys())[:10]}")
                print(f"gameID: {rows[0].get('gameID')}")
                print(f"First row sample: {dict(list(rows[0].items())[:5])}")
                break
    except Exception as e:
        print(f"❌ Failed with {encoding}: {str(e)[:100]}")
