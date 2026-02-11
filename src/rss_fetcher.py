import feedparser
from datetime import datetime
import time
from typing import List, Dict

def parse_date(entry):
    """Attempt to parse date from RSS entry"""
    if hasattr(entry, 'published_parsed'):
        return datetime.fromtimestamp(time.mktime(entry.published_parsed))
    if hasattr(entry, 'updated_parsed'):
        return datetime.fromtimestamp(time.mktime(entry.updated_parsed))
    return datetime.now()

import requests

def fetch_feed(url: str, platform_name: str) -> List[Dict]:
    """Fetch and parse a single RSS feed"""
    print(f"Fetching {url}...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        content = response.content
    except Exception as e:
        print(f"Failed to fetch URL {url}: {e}")
        return []

    feed = feedparser.parse(content)
    articles = []
    
    if not feed.entries:
        print(f"No entries found in {url}. Feed status: {getattr(feed, 'status', 'unknown')}")
    
    for entry in feed.entries[:5]: # Limit to 5 latest entries per feed for performance
        # Extract image if available
        image_url = None
        if 'media_content' in entry:
            image_url = entry.media_content[0]['url']
        elif 'media_thumbnail' in entry:
            image_url = entry.media_thumbnail[0]['url']
            
        # Parse content/summary
        summary = entry.get('summary', '') or entry.get('description', '')
        
        # Clean up summary (basic tag stripping could be added here if needed)
        
        article = {
            "id": entry.get('id', entry.get('link')),
            "title": entry.get('title', 'No Title'),
            "summary": summary[:300] + '...' if len(summary) > 300 else summary,
            "source_platform": platform_name,
            "source_url": entry.get('link'),
            "publish_date": parse_date(entry).strftime("%Y-%m-%d"),
            "keywords": [tag.term for tag in entry.get('tags', [])][:3], # Extract first 3 tags
            "status": "pending",
            "image_url": image_url
        }
        articles.append(article)
        
    return articles

def fetch_all_feeds(feed_list: List[Dict]) -> List[Dict]:
    """
    Fetch multiple feeds.
    feed_list should be a list of dicts: {'url': '...', 'name': '...'}
    """
    all_articles = []
    for feed in feed_list:
        try:
            feed_articles = fetch_feed(feed['url'], feed['name'])
            all_articles.extend(feed_articles)
        except Exception as e:
            print(f"Error fetching {feed['name']}: {e}")
            
    # Sort by date descending
    all_articles.sort(key=lambda x: x['publish_date'], reverse=True)
    return all_articles

if __name__ == "__main__":
    # Test
    test_feeds = [
        {'url': 'https://www.bnext.com.tw/rss', 'name': '數位時代'},
    ]
    results = fetch_all_feeds(test_feeds)
    print(f"Fetched {len(results)} articles")
    if results:
        print(results[0])
