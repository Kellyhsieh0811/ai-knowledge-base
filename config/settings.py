import os
from dotenv import load_dotenv

load_dotenv()

# RSS Lists (Synced with Notion, but these are defaults/backups)
RSS_FEEDS = [
    # Business
    "http://www.cw.com.tw/RSS/cw_content.xml", # 天下雜誌
]

# AI Feed Configs (For mapping logic if not in Notion yet)
AI_FEED_CONFIGS = {
    'https://joshbersin.com/feed/': {'name': 'Josh Bersin', 'filter': 'hr'},
    'https://www.hrtechnologist.com/feed/': {'name': 'HR Technologist', 'filter': 'hr'},
    'https://www.shrm.org/resourcesandtools/rss/pages/default.aspx': {'name': 'SHRM', 'filter': 'hr'},
    'https://blog.workday.com/en-us/feed': {'name': 'Workday Blog', 'filter': 'hr'},
    'https://sloanreview.mit.edu/topic/artificial-intelligence/feed/': {'name': 'MIT Sloan AI', 'filter': 'ai_hr'},
    'https://hbr.org/topic/artificial-intelligence/feed': {'name': 'HBR AI', 'filter': 'ai_hr'},
    'https://www.artificialintelligence-news.com/feed/': {'name': 'AI News', 'filter': 'ai_hr'},
    'https://venturebeat.com/category/ai/feed/': {'name': 'VentureBeat AI', 'filter': 'ai_hr'}
}

# Notion Config
# Notion Config
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_RSS_DB_ID = os.getenv("NOTION_RSS_DB_ID")
NOTION_CONTENT_DB_ID = os.getenv("NOTION_CONTENT_DB_ID")

# AI Config
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
