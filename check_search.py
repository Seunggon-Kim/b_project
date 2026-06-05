import requests
r = requests.get("http://localhost:8000/players/search?q=원태인")
print("Search Results for 원태인:")
print(r.json())
