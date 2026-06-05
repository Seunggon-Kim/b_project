import requests
from collections import Counter
import json

pid = '69446'
url = f'http://localhost:8888/players/{pid}/arsenal'
r = requests.get(url).json()
a = r.get('arsenal', [])
c = Counter([p.get('stands') for p in a])
print(f"API result for {pid}:")
print(dict(c))
if a:
    print("\nSample stands value:", repr(a[0].get('stands')))
    print("Char codes:", [ord(c) for c in a[0].get('stands')] if a[0].get('stands') else "None")
