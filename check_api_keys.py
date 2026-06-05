import requests
pid = '69446'
url = f'http://localhost:8888/players/{pid}/arsenal'
r = requests.get(url).json()
a = r.get('arsenal', [])
if a:
    print("Keys in API response:", sorted(a[0].keys()))
