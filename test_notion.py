import sys
import os

# Ensure we can import from src and config
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.notion_service import NotionService

def test_notion():
    print("Testing Notion Integration...")
    
    # Initialize Service
    try:
        service = NotionService()
        print(f"Token loaded: {'Yes' if service.token else 'No'}")
        print(f"RSS DB ID: {service.rss_db_id}")
        print(f"Content DB ID: {service.content_db_id}")
        
        if not service.token:
            print("Error: No Token found!")
            return

        if not service.rss_db_id:
            print("RSS Database ID missing")
            return

        # 1. Test RSS Feeds DB (DB1) - via get_active_feeds
        print("\n1. Testing RSS Feeds Database (DB1)...")
        try:
            feeds = service.get_active_feeds()
            print(f"   Success! Found {len(feeds)} active feeds.")
            for feed in feeds:
                print(f"   - [{feed['platform']}] {feed['name']} ({feed['url']})")
        except Exception as e:
            print(f"   Failed to query DB1: {e}")

        # 2. Test Content DB (DB2) - via retrieve
        print("\n2. Testing Content Database (DB2)...")
        if not service.content_db_id:
            print("   Error: Content DB ID missing.")
        else:
            try:
                # Test checking for a non-existent article to verify query rights
                exists = service.check_article_exists("http://test-non-existent-url.com")
                print(f"   Success! Connected to Content DB (Check result: {exists})")
            except Exception as e:
                print(f"   Failed to access DB2: {e}")
                
    except Exception as e:
        print(f"Initialization Error: {e}")

if __name__ == "__main__":
    test_notion()
