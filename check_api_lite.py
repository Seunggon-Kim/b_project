import requests
from collections import Counter
r = requests.get('http://localhost:8888/players/55912/arsenal').json()
a = r.get('arsenal', [])
c = Counter([p.get('stands') for p in a])
print(dict(c))
