import requests
from bs4 import BeautifulSoup
import urllib.parse

def test_news():
    query = "김현수 LG 야구"
    encoded_query = urllib.parse.quote(query)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}&sm=tab_pge&sort=0"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
    }
    
    print(f"Fetching: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        items = soup.select(".news_ritem, .news_area")
        print(f"Found {len(items)} news items")
        
        for item in items[:2]:
            title_node = item.select_one(".news_tit")
            if title_node:
                print(f"Title: {title_node.get_text()}")
                print(f"Link: {title_node['href']}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_news()
