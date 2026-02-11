import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, jsonify, request
import json
from datetime import datetime
from config import settings
from src.rss_fetcher import fetch_feed
from src.notion_service import NotionService
from src.ai_service import AIService
import time
import feedparser
import re
from html import unescape
import traceback

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Persistence for frontend display (cache)
DATA_FILE = 'articles_data.json'

def save_articles(articles):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)

def load_articles():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def clean_html_content(html_content):
    """清理 HTML，移除標籤和圖片"""
    
    if not html_content:
        return ""
    
    # 移除 HTML 標籤
    text = re.sub(r'<[^>]+>', '', html_content)
    
    # 移除多餘空白
    text = re.sub(r'\s+', ' ', text)
    
    # 解碼 HTML 實體
    text = unescape(text)
    
    # 移除圖片 URL 或路徑
    text = re.sub(r'https?://\S+\.(jpg|jpeg|png|gif|webp)', '', text)
    
    # 移除特殊字元 (保留中英文和標點)
    text = re.sub(r'[^\w\s\u4e00-\u9fa5.,!?;:，。！？；：-]', '', text)
    
    return text.strip()

def is_hr_article(title, summary):
    """嚴格檢查是否為 HR 文章"""
    
    # ✅ 必須包含的核心 HR 關鍵字（至少 2 個）
    hr_core_keywords = [
        # 組織/人才
        'employee', 'talent', 'workforce', 'hr', 'human resource',
        'recruitment', 'hiring', 'onboarding', 'retention',
        
        # 領導/文化
        'leadership', 'culture', 'engagement', 'wellbeing',
        'diversity', 'inclusion', 'dei',
        
        # 績效/發展
        'performance', 'training', 'development', 'learning',
        'career', 'promotion', 'succession',
        
        # 薪酬/福利
        'compensation', 'salary', 'benefits', 'reward',
        
        # 中文
        '員工', '人才', '人力資源', '招募', '留任',
        '領導力', '企業文化', '敬業度', '多元', '共融',
        '績效', '培訓', '發展', '薪酬', '福利', '職場'
    ]
    
    # ❌ 排除的非 HR 主題
    exclude_keywords = [
        # 金融/經濟
        'stock', 'market', 'investment', 'gold', 'currency',
        '股票', '市場', '投資', '黃金', '貨幣', '期貨',
        
        # 產業/科技（非 HR）
        'blockchain', 'crypto', 'bitcoin', 'semiconductor',
        '區塊鏈', '加密貨幣', '比特幣', '半導體',
        
        # 個人故事（非組織 HR）
        'obituary', 'biography', 'personal story',
        '訃聞', '傳記', '個人故事', '歲女', '歲男',
        
        # 商業（非 HR）
        'merger', 'acquisition', 'ipo', 'market share',
        '併購', '上市', '市佔率', '商業中心'
    ]
    
    content = (title + ' ' + summary).lower()
    
    # 1. 檢查是否包含排除關鍵字（有就直接排除）
    if any(keyword.lower() in content for keyword in exclude_keywords):
        return False
    
    # 2. 必須至少包含 2 個 HR 核心關鍵字
    hr_count = sum(1 for keyword in hr_core_keywords if keyword.lower() in content)
    
    return hr_count >= 2

from apscheduler.schedulers.background import BackgroundScheduler
import pytz

# ... existing imports ...

# Fetch Log
FETCH_LOG_FILE = 'fetch_log.json'

def save_fetch_time(fetch_type='manual'):
    """記錄抓取時間"""
    try:
        log = {}
        if os.path.exists(FETCH_LOG_FILE):
             with open(FETCH_LOG_FILE, 'r') as f:
                log = json.load(f)
        else:
             log = {'history': []}
    except:
        log = {'history': []}
    
    if 'history' not in log:
        log['history'] = []
        
    log['last_fetch'] = {
        'time': datetime.now().isoformat(),
        'type': fetch_type  # 'manual' or 'auto'
    }
    log['history'].append(log['last_fetch'])
    # Keep history manageable
    log['history'] = log['history'][-50:] 
    
    with open(FETCH_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)

def is_hr_or_ai_related(title, summary, filter_type='hr'):
    """檢查文章是否相關 (HR 或 AI+HR)"""
    
    content = (title + ' ' + summary).lower()
    
    # HR 核心關鍵字
    hr_keywords = [
        'employee', 'talent', 'workforce', 'hr', 'human resource',
        'recruitment', 'hiring', 'leadership', 'culture', 'learning',
        '員工', '人才', '人力資源', '招募', '領導', '文化', '培訓'
    ]
    
    # AI + 工作相關關鍵字
    ai_work_keywords = [
        'ai colleague', 'ai coworker', 'ai assistant',
        'frontier model', 'llm', 'large language model',
        'generative ai', 'chatgpt', 'claude', 'gemini',
        'ai in workplace', 'ai productivity', 'ai automation',
        'future of work', 'digital transformation',
        'ai 同事', 'ai 助手', '生成式 ai', '大型語言模型',
        '前沿模型', '工作場所 ai', 'ai 生產力', '人工智慧'
    ]
    
    # 排除的關鍵字（即使是 AI 文章）
    exclude_keywords = [
        'cryptocurrency', 'blockchain', 'bitcoin', 'stock market',
        '加密貨幣', '區塊鏈', '比特幣', '股市', '醫美'
    ]
    
    # 檢查排除關鍵字
    if any(keyword in content for keyword in exclude_keywords):
        return False
    
    if filter_type == 'hr':
        # HR 來源：必須包含 HR 關鍵字
        return any(keyword in content for keyword in hr_keywords)
    
    elif filter_type == 'ai_hr':
        # AI 來源：必須包含 (AI 關鍵字 + 工作相關) 或 (AI + HR 關鍵字)
        has_ai = any(keyword in content for keyword in ai_work_keywords)
        has_hr = any(keyword in content for keyword in hr_keywords)
        
        # AI 文章必須與工作/HR 相關
        if has_ai:
             # 如果有 AI 關鍵字，必須同時有 HR 關鍵字 OR 提到 'work'/'employee'
             return has_hr or 'work' in content or 'employee' in content or '工作' in content
        return False
    
    return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/feeds', methods=['GET'])
def get_feeds():
    """Get active feeds from Notion + Static Config"""
    service = NotionService()
    
    # 1. Notion Sources
    notion_feeds = service.get_active_feeds()
    
    # 2. Static AI Configs (as suggestions if not in Notion)
    existing_urls = {f.get('url2', f.get('url', '')).rstrip('/') for f in notion_feeds}
    
    static_feeds = []
    for url, config in settings.AI_FEED_CONFIGS.items():
        if url.rstrip('/') not in existing_urls:
            static_feeds.append({
                'id': f'static-{hash(url)}',
                'name': config.get('name'),
                'url': url,
                'platform': config.get('name'),
                'status': 'Suggested',
                'type': config.get('filter', 'hr')
            })
            
    return jsonify(notion_feeds + static_feeds)

@app.route('/api/articles')
def get_articles():
    """從 Notion 獲取文章列表 (Direct Fetch)"""
    try:
        service = NotionService()
        articles = service.get_articles()
        print(f"✅ 成功讀取 {len(articles)} 篇文章")
        return jsonify(articles)
    except Exception as e:
        print(f"❌ 讀取文章失敗: {e}")
        import traceback
        traceback.print_exc()
        return jsonify([]), 500

# ... existing routes ...

@app.route('/api/fetch', methods=['POST'])
def manual_fetch():
    """手動抓取 API"""
    try:
        # Call the actual fetch function (we need to refactor fetch_articles to be callable properly not just as route)
        # However, fetch_articles returns Response object.
        # Let's extract the logic to a standalone function or calling it via test_client is hacky.
        # Best way: Refactor logic to `process_all_feeds()` and have `fetch_articles` call it.
        # For now, let's call the route handler logic? No, let's refactor.
        result = perform_fetch_process() # We will define this
        save_fetch_time('manual')
        return jsonify({'success': True, 'time': datetime.now().isoformat(), 'details': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fetch-status')
def fetch_status():
    """獲取上次抓取時間"""
    try:
        if os.path.exists(FETCH_LOG_FILE):
            with open(FETCH_LOG_FILE, 'r') as f:
                log = json.load(f)
            return jsonify(log.get('last_fetch', {}))
        return jsonify({})
    except:
        return jsonify({})

def perform_fetch_process():
    """Core logic to fetch and process articles"""
    notion_manager = NotionService()
    ai_service = AIService()
    
    print("\n" + "=" * 50)
    print(f"開始抓取 RSS 文章 (Time: {datetime.now()})")
    print("=" * 50)

    # 1. 獲取來源 - Mix of Notion and Settings (for AI)
    # Strategy: using Notion as primary. 
    # But user wants AI feeds added. 
    # If they are not in Notion, we temporarily iterate `settings.AI_FEED_CONFIGS`?
    # Better: Users should add them to Notion. 
    # But for "Filter Type" logic, we need mapping.
    
    sources = notion_manager.get_active_feeds()
    
    # If sources is empty and we have AI feeds in settings, maybe we should auto-add them?
    # For now, let's rely on Notion sources.
    
    all_articles = []
    errors = []
    all_articles_for_display = load_articles()
    existing_urls = {a.get('source_url') for a in all_articles_for_display}
    
    for i, source in enumerate(sources, 1):
        try:
            url = source.get('url')
            name = source.get('name', 'Unknown')
            
            # Determine Filter Type
            # Default to 'hr'
            filter_type = 'hr'
            
            # Check if this URL is in our AI Config
            # Normalize URL for check (strip slash maybe?)
            for ai_url, config in settings.AI_FEED_CONFIGS.items():
                if ai_url.rstrip('/') == url.rstrip('/'):
                    filter_type = config.get('filter', 'hr')
                    break
            
            print(f"\n[{i}/{len(sources)}] 處理來源: {name} (Filter: {filter_type})")
            
            feed = feedparser.parse(url)
            if not feed.entries:
                continue

            for j, entry in enumerate(feed.entries[:20], 1):
                try:
                    if notion_manager.check_article_exists(entry.link):
                        continue
                    
                    en_title = entry.title
                    raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    en_summary = clean_html_content(raw_summary)[:800]
                    
                    # ✅ Replace old is_hr_article with new is_hr_or_ai_related
                    if not is_hr_or_ai_related(en_title, en_summary, filter_type):
                         # print(f"    [Skip] 不符合 {filter_type} 主題: {en_title[:30]}...")
                         continue
                         
                    print(f"    [{j}] ✅ 發現文章: {en_title[:40]}...")
                    
                    # ... Process (Translate, AI Tag, Write to Notion) ...
                    # (Simplified for brevity, copying core logic)
                    
                    # 日期處理
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                         pub_date = datetime(*entry.published_parsed[:6]).isoformat()
                    else:
                         pub_date = datetime.now().isoformat()

                    zh_title = ai_service.translate_to_chinese(en_title, "標題")
                    zh_summary = ai_service.translate_to_chinese(en_summary, "摘要")
                    topics = ai_service.extract_topics(en_title, en_summary)
                    
                    article_data = {
                        'title': zh_title,
                        'summary': zh_summary,
                        'topics': topics,
                        'url': entry.link,
                        'published_date': pub_date,
                         # Use source name from Notion or Feed
                        'source': name,
                        'status': '待處理',
                        'source_platform': source.get('platform', '新聞媒體'), 
                        'source_url': entry.link,
                        'ai_content': ''
                    }
                    
                    resp = notion_manager.create_article(article_data, source.get('id'))
                    if resp:
                        article_data['id'] = resp['id']
                        all_articles.append(article_data)
                        if article_data['source_url'] not in existing_urls:
                            all_articles_for_display.insert(0, article_data)
                            existing_urls.add(article_data['source_url'])
                    
                    time.sleep(1) # Rate limit

                except Exception as e:
                    print(f"    ❌ Error: {e}")
                    continue
            
            notion_manager.update_feed_timestamp(source['id'])
            
        except Exception as e:
            print(f"  ❌ Source Error: {e}")
            continue

    save_articles(all_articles_for_display)
    return {'processed': len(all_articles)}

# API Wrapper for fetch
# Duplicate fetch_articles removed to fix startup error
# @app.route('/api/rss/fetch', methods=['POST'])
# @app.route('/api/articles/fetch', methods=['POST']) 
# def fetch_articles():
#     try:
#         result = perform_fetch_process()
#         save_fetch_time('manual')
#         return jsonify({
#             'success': True,
#             'status': 'success',
#             'articles_processed': result['processed'],
#             'message': f"成功處理 {result['processed']} 篇新文章"
#         })
#     except Exception as e:
#         return jsonify({'success': False, 'error': str(e)}), 500


def scheduled_fetch():
    """定時抓取任務"""
    print(f"🤖 自動抓取開始: {datetime.now()}")
    try:
        perform_fetch_process()
        save_fetch_time('auto')
        print("✅ 自動抓取完成")
    except Exception as e:
        print(f"❌ 自動抓取失敗: {e}")

# Scheduler Setup
scheduler = BackgroundScheduler()
taipei_tz = pytz.timezone('Asia/Taipei')
scheduler.add_job(
    func=scheduled_fetch,
    trigger='cron',
    hour=9,
    minute=0,
    timezone=taipei_tz,
    id='daily_fetch'
)
if not scheduler.running:
    scheduler.start()

# --- AI Endpoints ---

@app.route('/api/ai/translate', methods=['POST'])
def ai_translate():
    data = request.json
    ai_service = AIService()
    result = {
        'title': ai_service.translate_to_chinese(data.get('title'), 'title'),
        'summary': ai_service.translate_to_chinese(data.get('summary'), 'summary')
    }
    return jsonify(result)

@app.route('/api/ai/extract-topics', methods=['POST'])
def ai_extract_topics():
    data = request.json
    ai_service = AIService()
    topics = ai_service.extract_topics(data.get('title'), data.get('summary'))
    return jsonify({'topics': topics})

@app.route('/api/ai/rewrite', methods=['POST'])
def ai_rewrite():
    data = request.json
    
    # Needs article_id to fetch from Notion, OR raw content
    article_id = data.get('article_id')
    platform = data.get('platform')
    style = data.get('style')
    
    service = NotionService()
    ai_service = AIService()
    
    article_data = {}
    
    if article_id:
        # Fetch from Notion
        page = service.get_article(article_id)
        if page and 'properties' in page:
             props = page['properties']
             # Extract title
             title_list = props.get('Title', {}).get('title', [])
             article_data['title'] = title_list[0]['text']['content'] if title_list else ""
             
             # Extract summary
             summary_list = props.get('Summary', {}).get('rich_text', [])
             article_data['summary'] = "".join([t['text']['content'] for t in summary_list]) if summary_list else ""
             
             # Extract url
             article_data['url'] = props.get('URL', {}).get('url')
             
             # Extract topics
             tags = props.get('Topic', {}).get('multi_select', [])
             article_data['topics'] = [t['name'] for t in tags]
    else:
        # Fallback if passed directly (from frontend cache)
        article_data = data.get('article', {})

    content = ai_service.rewrite_for_social(article_data, platform, style)
    return jsonify({'content': content})

@app.route('/api/notion/update-ai-content', methods=['POST'])
def update_ai_content():
    data = request.json
    service = NotionService()
    
    resp = service.update_article_ai_content(
        data.get('article_id'),
        data.get('ai_content'),
        data.get('platform')
    )
    
    if resp:
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Notion update failed'}), 500

@app.route('/api/sources', methods=['GET'])
def get_sources():
    """讀取所有 RSS 來源"""
    try:
        service = NotionService()
        sources = service.get_all_sources()  # Includes active and inactive
        return jsonify({
            'success': True,
            'sources': sources
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sources', methods=['POST'])
def add_source():
    """新增 RSS 來源到 Notion DB1"""
    try:
        data = request.json
        service = NotionService()
        
        # Determine platform and active status
        platform = data.get('platform', '新聞媒體')
        is_active = data.get('is_active', True)
        
        # Call create_source with unpacked arguments
        source_id = service.create_source(
            name=data['name'],
            url=data['url'],
            platform=platform,
            is_active=is_active
        )
        
        if source_id:
            return jsonify({
                'success': True,
                'source_id': source_id
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Notion creation returned None'
            }), 500
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sources/<source_id>', methods=['PATCH'])
def update_source(source_id):
    """更新來源（例如啟用/停用）"""
    try:
        data = request.json
        service = NotionService()
        service.update_source(source_id, data)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/sources/<source_id>', methods=['DELETE'])
def delete_source(source_id):
    """刪除來源"""
    try:
        service = NotionService()
        print(f"嘗試刪除來源 ID: {source_id}")
        service.delete_source(source_id)
        return jsonify({'success': True})
    except Exception as e:
        print(f"刪除來源失敗: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Updated Fetch Logic (Issue 1 Fix)
@app.route('/api/rss/fetch', methods=['POST'])
@app.route('/api/articles/fetch', methods=['POST']) # Alias for user's request
def fetch_articles():
    """抓取 RSS 並處理 (User Requested Logic)"""
    notion_manager = NotionService() # Alias for user's naming
    ai_service = AIService()
    
    try:
        print("\n" + "=" * 50)
        print("開始抓取 RSS 文章")
        print("=" * 50)
        
        # 1. 從 Notion DB1 讀取 RSS 來源
        sources = notion_manager.get_active_feeds()
        
        if not sources:
            return jsonify({
                'success': False,
                'status': 'error', # Maintain compatibility with frontend
                'message': '沒有找到啟用的 RSS 來源'
            }), 404
        
        print(f"找到 {len(sources)} 個啟用的來源")
        
        all_articles = []
        errors = []
        
        # for frontend cache
        all_articles_for_display = load_articles()
        existing_urls = {a.get('source_url') for a in all_articles_for_display}
        
        # 2. 逐一處理每個來源
        for i, source in enumerate(sources, 1):
            try:
                print(f"\n[{i}/{len(sources)}] 處理來源: {source.get('name', 'Unknown')}")
                print(f"    URL: {source.get('url')}")
                
                # 抓取 RSS
                feed = feedparser.parse(source['url'])
                
                if not feed.entries:
                    print(f"  ⚠ 沒有找到文章")
                    continue
                
                print(f"  ✓ 找到 {len(feed.entries)} 篇文章")
                
                # 處理前 20 篇 (User requested limit increase)
                for j, entry in enumerate(feed.entries[:20], 1):
                    try:
                        # 檢查是否已存在
                        if notion_manager.check_article_exists(entry.link):
                            print(f"    [{j}] 跳過（已存在）")
                            continue
                        
                        print(f"    [{j}] 處理文章...")
                        
                        # 原文
                        en_title = entry.title
                        
                        # ✅ 清理摘要，移除 HTML 和圖片
                        raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                        en_summary = clean_html_content(raw_summary)
                        en_summary = en_summary[:800] # Limit summary length
                        
                        # ✅ 過濾不相關的文章 (Strict Logic)
                        if not is_hr_article(en_title, en_summary):
                            print(f"    [Skip] 非 HR 主題: {en_title}")
                            continue
                        
                        # 日期處理 (ISO 8601)
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                             pub_date = datetime(*entry.published_parsed[:6]).isoformat()
                        else:
                             pub_date = datetime.now().isoformat()

                        
                        # AI 翻譯 (Mandatory)
                        print(f"        翻譯中...")
                        zh_title = ai_service.translate_to_chinese(en_title, "標題")
                        zh_summary = ai_service.translate_to_chinese(en_summary, "摘要")
                        
                        print(f"        中文標題: {zh_title[:30]}...")
                        
                        # AI 提取標籤（中文）
                        print(f"        提取標籤...")
                        topics = ai_service.extract_topics(en_title, en_summary)
                        print(f"        標籤: {', '.join(topics)}")
                        
                        # 準備資料
                        article_data = {
                            'title': zh_title,
                            'summary': zh_summary,
                            'topics': topics,
                            'url': entry.link,
                            'published_date': pub_date,
                            'source': source.get('name', ''),
                            'status': '待處理',
                            'source_platform': source.get('platform', '新聞媒體'), # Keep platform info
                            'source_url': entry.link,
                            'ai_content': ''
                        }
                        
                        # 寫入 Notion
                        print(f"        寫入 Notion...")
                        resp = notion_manager.create_article(article_data, source.get('id'))
                        
                        if resp:
                            # Add Notion ID for frontend
                            article_data['id'] = resp['id']
                            
                            all_articles.append(article_data)
                            
                            # Cache update
                            if article_data['source_url'] not in existing_urls:
                                all_articles_for_display.insert(0, article_data)
                                existing_urls.add(article_data['source_url'])
                                
                            print(f"        ✅ 完成")
                        
                        # 避免 API 限制
                        time.sleep(1)
                        
                    except Exception as e:
                        error_msg = f"處理文章失敗: {str(e)}"
                        print(f"      ❌ {error_msg}")
                        errors.append(error_msg)
                        continue
                        
                # Update Timestamp
                notion_manager.update_feed_timestamp(source['id'])
                
            except Exception as e:
                error_msg = f"處理來源 {source.get('name')} 失敗: {str(e)}"
                print(f"  ❌ {error_msg}")
                errors.append(error_msg)
                continue
        
        print("\n" + "=" * 50)
        print(f"抓取完成！成功: {len(all_articles)} 篇")
        if errors:
            print(f"錯誤: {len(errors)} 個")
        print("=" * 50)
        
        # Save cache
        save_articles(all_articles_for_display)
        
        return jsonify({
            'success': True,
            'status': 'success',
            'articles_processed': len(all_articles),
            'message': f'成功處理 {len(all_articles)} 篇新文章',
            'errors': errors if errors else None,
            'articles': all_articles_for_display
        })
        
    except Exception as e:
        print(f"\n❌ 抓取流程錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'status': 'error',
            'error': str(e),
            'message': str(e)
        }), 500

@app.route('/api/articles', methods=['GET'])
def list_articles():
    """獲取文章列表，只返回有效的 HR 文章 (Synced with Notion)"""
    try:
        service = NotionService()
        
        # ✅ 允許的標籤清單 (Whitelist)
        allowed_tags = {
            '人力資源科技', '人才管理', '員工體驗', '領導力發展',
            '多元共融', '職場文化', '薪酬福利', '績效管理',
            '學習發展', '人力規劃', '員工敬業度', '變革管理',
            '人工智慧', '數位轉型', '未來工作', '遠距工作', '員工福祉'
        }
        
        # 從 Notion 獲取所有文章
        print("🔄 API Request: Fetching articles from Notion...")
        all_articles = service.get_articles()
        
        # 過濾文章
        valid_articles = []
        for article in all_articles:
            # 檢查標籤
            topics = article.get('topics', [])
            if not topics:
                continue
                
            # 必須有至少一個允許的標籤
            has_valid_tag = any(tag in allowed_tags for tag in topics)
            
            # 再次檢查標題關鍵字 (Double Insurance)
            blocked_keywords = ['102歲', '醫美', '黃金', '去美元化', '待處理', '市場拓展']
            has_blocked = any(k in article['title'] for k in blocked_keywords)
            
            if has_valid_tag and not has_blocked:
                # 確保格式與前端一致
                if 'id' not in article:
                    article['id'] = article.get('id', str(int(time.time())))
                    
                valid_articles.append(article)
        
        # Update Cache
        save_articles(valid_articles)
        
        return jsonify(valid_articles)
        
    except Exception as e:
        print(f"❌ Error fetching articles: {e}")
        # Fallback to cache if Notion fails
        return jsonify(load_articles())

@app.route('/api/generate-content', methods=['POST'])
def generate_content():
    """AI 重製內容"""
    try:
        data = request.json
        article_id = data.get('article_id')
        platform = data.get('platform', 'Instagram')
        style = data.get('style', '輕鬆親切')
        
        # 獲取文章
        notion_service = NotionService()
        all_articles = notion_service.get_articles()
        article = None
        for a in all_articles:
            if str(a.get('id')) == str(article_id):
                article = a
                break
        
        if not article:
            return jsonify({'success': False, 'error': '找不到文章'}), 404
        
        # AI 生成內容
        prompt = f'''將以下文章改寫為 {platform} 的社群貼文，風格：{style}

標題：{article.get('title')}
摘要：{article.get('summary')}

要求：
- 150-200 字
- 加入 emoji
- 3 個 hashtag
'''
        
        ai_service = AIService()
        response = ai_service.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        
        content = response.choices[0].message.content
        
        return jsonify({
            'success': True,
            'content': content
        })
        
    except Exception as e:
        print(f"錯誤: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/save-to-notion', methods=['POST'])
def save_to_notion():
    """儲存 AI 生成的內容到原文章的 AI Content 欄位 (追加模式)"""
    try:
        data = request.json
        
        article_id = data.get('article_id')
        content = data.get('content')
        platform = data.get('platform', 'Social Media')
        style = data.get('style', 'AI重製')
        
        notion_service = NotionService()

        # 1. 獲取原文章的完整資訊 (為了拿到 Notion Page ID)
        # 注意：這裡的 article_id 是我們系統內部的 ID (其實也是 Notion Page ID)
        # 但為了保險起見，我們還是用 notion_service.get_articles() 確認一下
        # 或者直接假設 article_id 就是 page_id (在我們的系統設計中確實如此)
        
        original_page_id = article_id
        
        # 簡單驗證 ID 格式 (這一步可選，但為了安全起見)
        if not original_page_id:
             return jsonify({'success': False, 'error': '缺少 Article ID'}), 400

        # 2. 獲取該頁面當前的 AI Content
        # 使用 NotionService._request 呼叫 API
        page_response = notion_service._request("GET", f"pages/{original_page_id}")
        
        if not page_response:
            return jsonify({'success': False, 'error': '找不到原文章'}), 404
            
        # 3. 讀取現有的 AI Content
        existing_content = ""
        props = page_response.get('properties', {})
        
        # 嘗試讀取 AI Content (或其他可能的欄位名)
        ai_content_prop = props.get('AI Content') or props.get('AI重製')
        
        if ai_content_prop and ai_content_prop.get('rich_text'):
            existing_texts = ai_content_prop['rich_text']
            existing_content = ''.join([text.get('plain_text', '') for text in existing_texts])
            
        # 4. 準備新內容（加在最上方）
        platform_emoji = {
            'Instagram': '📷',
            'LinkedIn': '💼',
            'Facebook': '📘',
            'Twitter': '🐦'
        }.get(platform, '📱')
        
        # 分隔線
        separator = "\n\n" + "-"*30 + "\n\n"
        
        if existing_content:
            new_full_content = f"{platform_emoji} [{platform}]\n\n{content}{separator}{existing_content}"
        else:
            new_full_content = f"{platform_emoji} [{platform}]\n\n{content}"
        
        # 限制長度（Notion rich_text 限制 2000 字）
        if len(new_full_content) > 2000:
            new_full_content = new_full_content[:1950] + "\n\n...(內容過長已截斷)"

        # 5. 更新頁面
        payload = {
            "properties": {
                "AI Content": {
                    "rich_text": [
                        {
                            "text": {
                                "content": new_full_content
                            }
                        }
                    ]
                }
            }
        }
        
        update_response = notion_service._request("PATCH", f"pages/{original_page_id}", payload)
        
        if update_response and 'id' in update_response:
             return jsonify({
                'success': True,
                'notion_page_id': original_page_id,
                'message': f'已新增 {platform} 內容到原文章'
            })
        else:
             return jsonify({'success': False, 'error': 'Notion API 更新失敗'}), 500
        
    except Exception as e:
        print(f"儲存失敗: {e}")
        import traceback
        traceback.print_exc()
        
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print(f"📅 排程器已啟動 - 每天 09:00 (Taipei)")
    app.run(debug=True, port=5005, use_reloader=False)
