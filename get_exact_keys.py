import requests
pid = '65949'
url = f'http://localhost:8888/players/{pid}/arsenal'
try:
    r = requests.get(url).json()
    items = r.get('arsenal', [])
    if items:
        first = items[0]
        print(f"KEYS: {list(first.keys())}")
        print(f"SAMPLE: {first}")
    else:
        print("No arsenal items found.")
except Exception as e:
    print(f"Error: {e}")
