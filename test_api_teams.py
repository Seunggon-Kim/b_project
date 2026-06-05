import requests

def test_stats(team_ids):
    url = f"http://localhost:8000/stats/batters?season=2025&limit=10&min_pa=0"
    if team_ids:
        url += f"&team_ids={team_ids}"
    
    print(f"\nTesting URL: {url}")
    try:
        response = requests.get(url)
        data = response.json()
        print(f"DEBUG: Server returned team_ids: {data.get('team_ids')}")
        batters = data.get('batters', [])
        print(f"Found {len(batters)} batters")
        for b in batters[:5]:
            print(f" - {b['player_name']} ({b.get('team_id')})")
    except Exception as e:
        print(f"Error: {e}")

print("--- Test All ---")
test_stats(None)
print("\n--- Test KIA ---")
test_stats("KIA")
print("\n--- Test KIA,LG ---")
test_stats("KIA,LG")
