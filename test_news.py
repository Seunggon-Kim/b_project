import requests
from bs4 import BeautifulSoup
import urllib.parse

query = "삼성 원태인"
encoded_query = urllib.parse.quote(query)
url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&sort=0"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

print(f"Searching for: {query}")
print(f"URL: {url}")

try:
    response = requests.get(url, headers=headers, timeout=5)
    print(f"Status: {response.status_code}")
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Check for results
    total_news = soup.select(".news_area, .news_rita, .news_ritem, .bx")
    print(f"Found selectors: {len(total_news)}")
    
    for i, item in enumerate(total_news[:5]):
        title_node = item.select_one(".news_tit, .news_tit_link, a[title]")
        if title_node:
            print(f"[{i}] {title_node.get_text().strip()}")
        else:
            print(f"[{i}] No title node found")

except Exception as e:
    print(f"Error: {e}")
