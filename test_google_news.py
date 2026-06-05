import requests
import xml.etree.ElementTree as ET
import urllib.parse

def test_google_news():
    query = "김현수 LG 야구"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"
    
    print(f"Fetching Google News RSS: {url}")
    try:
        response = requests.get(url, timeout=10)
        print(f"Status: {response.status_code}")
        
        root = ET.fromstring(response.text)
        items = root.findall('.//item')
        print(f"Found {len(items)} items")
        
        for item in items[:5]:
            title = item.find('title').text
            link = item.find('link').text
            pub_date = item.find('pubDate').text
            source = item.find('source').text
            print(f"- {title} ({source})")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_google_news()
