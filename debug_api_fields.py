import requests
pid = '65949' # Placeholder, will try to get from current context if possible
url = f'http://localhost:8888/players/{pid}/arsenal'
r = requests.get(url).json()
if 'arsenal' in r and len(r['arsenal']) > 0:
    first_item = r['arsenal'][0]
    print(f"ARSENAL_KEYS: {list(first_item.keys())}")
    print(f"ARSENAL_SAMPLE: {first_item}")

url_p = f'http://localhost:8888/players/{pid}'
rp = requests.get(url_p).json()
print(f"PLAYER_KEYS: {list(rp.keys())}")
print(f"PLAYER_SAMPLE: {rp}")
