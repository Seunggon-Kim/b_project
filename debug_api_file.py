import requests
from collections import Counter

try:
    r = requests.get('http://localhost:8888/players/55912/arsenal').json()
    a = r.get('arsenal', [])
    c = Counter([p.get('stands') for p in a])
    with open('counts.txt', 'w', encoding='utf-8') as f:
        f.write(f"Total: {len(a)}\n")
        for k, v in c.items():
            f.write(f"{k}: {v}\n")
except Exception as e:
    with open('counts.txt', 'w') as f:
        f.write(str(e))
