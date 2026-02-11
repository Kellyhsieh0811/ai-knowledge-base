import sys
import os

# Ensure we can import from src and config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import settings
from src.rss_fetcher import fetch_feed

def test_rss_fetch():
    print("Testing RSS Fetch...")
    
    # 1. Get a feed from settings or hardcoded (if settings is empty)
    # 1. Get a feed from settings
    feed_url = "http://www.cw.com.tw/RSS/cw_content.xml"
    if hasattr(settings, 'RSS_FEEDS') and settings.RSS_FEEDS:
        feed_url = settings.RSS_FEEDS[0]
        
    print(f"Target Feed: {feed_url}")
    
    # 2. Fetch
    try:
        articles = fetch_feed(feed_url, "Test Platform")
        
        # 3. Print Results
        print(f"\nSuccessfully fetched {len(articles)} articles:")
        print("-" * 50)
        for i, article in enumerate(articles[:5], 1):
            print(f"{i}. [{article['publish_date']}] {article['title']}")
            print(f"   URL: {article['source_url']}")
        print("-" * 50)
            
    except Exception as e:
        print(f"Error fetching RSS: {e}")

if __name__ == "__main__":
    test_rss_fetch()
