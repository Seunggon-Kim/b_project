import requests
from bs4 import BeautifulSoup
import urllib.parse

def debug_naver_news():
    query = "김현수 LG 야구"
    encoded_query = urllib.parse.quote(query)
    url = f"https://search.naver.com/search.naver?where=news&query={encoded_query}"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }
    
    print(f"URL: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try different selectors
        selectors = [
            "li.bx",             # Desktop news item
            ".news_area",        # Another common desktop selector
            ".news_item",        # Old selector
            ".list_news > li",   # Container based selector
            "article"            # Generic fall back
        ]
        
        for selector in selectors:
            items = soup.select(selector)
            print(f"Selector '{selector}': found {len(items)} items")
            
        if len(soup.select("li.bx")) == 0:
            print("--- HTML SNIPPET (First 500 chars) ---")
            print(response.text[:500])
            
            # Check for block/captcha
            if "captcha" in response.text.lower() or "forbidden" in response.text.lower():
                print("BLOCK DETECTED: Naver is blocking the request or asking for captcha.")

    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    debug_naver_news()
