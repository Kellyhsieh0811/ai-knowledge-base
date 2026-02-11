from src.notion_service import NotionService
import os
from dotenv import load_dotenv

# Load env vars
load_dotenv()

token = os.getenv('NOTION_TOKEN')
content_db = os.getenv('NOTION_CONTENT_DB_ID')

print(f"DEBUG: Token starts with {token[:5] if token else 'None'}")
print(f"DEBUG: Content DB ID: {content_db}")

notion = NotionService(
    token=token,
    content_db_id=content_db
)

try:
    print("Testing notion.get_articles()...")
    articles = notion.get_articles()
    print(f"✅ 成功讀取 {len(articles)} 篇文章")
    if len(articles) > 0:
        print(f"第一篇: {articles[0].get('title', 'No title')}")
    else:
        print("⚠️ Notion 返回 0 篇文章")
except Exception as e:
    import traceback
    traceback.print_exc()
    print(f"❌ 錯誤: {e}")
