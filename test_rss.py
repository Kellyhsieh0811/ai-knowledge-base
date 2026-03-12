
import feedparser
import requests

# 從 rss_fetcher.py 讀取所有 RSS 來源
rss_sources = {
    # 中文來源
    '天下雜誌': 'https://www.cw.com.tw/rss/section.action?id=13',  # 管理
    '數位時代': 'https://www.bnext.com.tw/rss/articles',
    
    # 英文來源
    'The Economist': 'https://www.economist.com/business/rss.xml',
    'Josh Bersin Latest Insights (HR Tech)': 'https://joshbersin.com/feed/',
    'Oxford Review': 'https://oxford-review.com/feed/',
    'SHRM': 'https://www.shrm.org/ResourcesAndTools/hr-topics/Pages/RSS.aspx',
    'HBR (US) Human Resource Management': 'https://hbr.org/topic/human-resource-management/rss',
    'HBR (US) Strategy': 'https://hbr.org/topic/strategy/rss',
    'HBR (US) Leadership': 'https://hbr.org/topic/leadership/rss',
    'Deloitte Human Capital Trends': 'https://www2.deloitte.com/us/en/pages/about-deloitte/articles/rss-feeds.html',
    'PwC Strategy& (Thought Leadership)': 'https://www.strategyand.pwc.com/gx/en/insights.rss.xml',
    '36氪 (Lattice)': 'https://36kr.com/feed',
    'PRESIDENT Online': 'https://president.jp/list/rss',
    'ITmedia Business': 'https://rss.itmedia.co.jp/rss/2.0/business.xml',
    '日経中文網': 'https://zh.cn.nikkei.com/rss.xml',
    'Handelsblatt': 'https://www.handelsblatt.com/contentexport/feed/top-themen',
}

print("=== 測試 RSS 來源 ===\n")

valid_sources = []
invalid_sources = []

for name, url in rss_sources.items():
    print(f"測試: {name}")
    print(f"URL: {url}")
    
    try:
        # 測試 HTTP 狀態
        response = requests.get(url, timeout=10, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'
        })
        
        if response.status_code == 200:
            # 測試 RSS 解析
            feed = feedparser.parse(url)
            
            if feed.entries and len(feed.entries) > 0:
                print(f"✅ 有效 - 找到 {len(feed.entries)} 篇文章")
                valid_sources.append((name, url))
            else:
                print(f"⚠️  可訪問但無內容")
                invalid_sources.append((name, url, "無內容"))
        else:
            print(f"❌ HTTP {response.status_code}")
            invalid_sources.append((name, url, f"HTTP {response.status_code}"))
    
    except Exception as e:
        print(f"❌ 錯誤: {str(e)[:50]}")
        invalid_sources.append((name, url, str(e)[:50]))
    
    print()

print("\n=== 測試結果 ===")
print(f"✅ 有效來源: {len(valid_sources)} 個")
print(f"❌ 失效來源: {len(invalid_sources)} 個\n")

if invalid_sources:
    print("失效的來源：")
    for name, url, reason in invalid_sources:
        print(f"  - {name}: {reason}")
