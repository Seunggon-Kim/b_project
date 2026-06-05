import requests
import json
from collections import Counter

player_id = '55912'
url = f'http://localhost:8888/players/{player_id}/arsenal'

try:
    response = requests.get(url)
    data = response.json()
    arsenal = data.get('arsenal', [])
    
    print(f"Total pitches for {player_id}: {len(arsenal)}")
    
    stands_counter = Counter([p.get('stands') for p in arsenal])
    print("\nStands distribution in API response:")
    for s, count in stands_counter.items():
        # Print with repr to see exact characters
        print(f"{repr(s)}: {count}")
        
    if arsenal:
        print("\nFirst pitch sample:")
        print(json.dumps(arsenal[0], indent=2, ensure_ascii=False))

except Exception as e:
    print(f"Error: {e}")
