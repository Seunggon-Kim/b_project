import requests
pid = '65949'
url = f'http://localhost:8888/players/{pid}/arsenal'
r = requests.get(url).json()
a = r.get('arsenal', [])
if a:
    stands_values = [p.get('stands') for p in a]
    from collections import Counter
    print("API Stands distribution:", Counter(stands_values))
    print("First 3 stands values and their codes:")
    for v in stands_values[:10]:
        if v:
            print(f"Value: '{v}', Codes: {[ord(c) for c in v]}")
