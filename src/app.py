import jwt
from datetime import datetime, timedelta
from functools import wraps
from flask_cors import CORS
import sys
import os
print(f"LOADING APP FROM: {__file__}")

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
import signal
import concurrent.futures
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS

_base = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
app = Flask(__name__, template_folder=os.path.join(_base, 'templates'), static_folder=os.path.join(_base, 'static'))
# 啟用 CORS
CORS(app)

# 權限設定
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')
ROLE_PASSWORDS = {
    'admin':    os.getenv('ADMIN_PASSWORD',    'admin2026'),
    'employee': os.getenv('EMPLOYEE_PASSWORD', 'employee2026'),
    'guest':    os.getenv('GUEST_PASSWORD',    'guest2026'),
}


app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))



talisman = Talisman(
    app,
    content_security_policy=None,
    force_https=False
)

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

app.config['JSON_AS_ASCII'] = False
app.json.ensure_ascii = False

@app.route('/favicon.ico')
def favicon():
    return '', 204

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
    if not html_content:
        return ""
    text = re.sub(r'<[^>]+>', '', html_content)
    text = re.sub(r'\s+', ' ', text)
    text = unescape(text)
    text = re.sub(r'https?://\S+\.(jpg|jpeg|png|gif|webp)', '', text)
    text = re.sub(r'[^\w\s\u4e00-\u9fa5.,!?;:，。！？；：-]', '', text)
    return text.strip()

def is_hr_or_ai_related(title, summary, filter_type='hr'):
    content = (title + ' ' + summary).lower()

    # ─── 第一關：硬排除（有這些就直接丟掉）───
    hard_exclude = [
        # 金融/投資
        'ipo', '上市', '融資', '估值', '股票', '期貨', '加密貨幣', '比特幣', '區塊鏈',
        'cryptocurrency', 'blockchain', 'bitcoin', 'stock market', 'fund raising',
        # 產品/硬體（非 HR）
        '床墊', '感測器', '半導體', '晶片', '電動車', '機器人硬體',
        'semiconductor', 'chip', 'electric vehicle',
        # 媒體/娛樂
        '電視網', '收視率', 'z世代觀眾', 'gen z viewer', 'fox news',
        # 個人傳記/故事
        '訃聞', '傳記', 'obituary',
        # 醫療美容
        '醫美', '整形',
    ]
    if any(kw in content for kw in hard_exclude):
        return False

    # ─── 第二關：HR 核心關鍵字（至少要有 1 個）───
    hr_core = [
        # 英文
        'employee', 'talent', 'workforce', 'hr ', 'human resource',
        'recruitment', 'hiring', 'onboarding', 'retention',
        'leadership', 'culture', 'engagement', 'wellbeing', 'well-being',
        'diversity', 'inclusion', 'dei',
        'performance', 'training', 'learning', 'development', 'coaching',
        'compensation', 'salary', 'benefits',
        'future of work', 'workplace', 'remote work', 'hybrid work',
        'organization', 'team', 'manager', 'executive',
        # 中文
        '員工', '人才', '人力資源', '人資', '招募', '留任',
        '領導力', '企業文化', '敬業度', '多元共融',
        '績效', '培訓', '學習發展', '薪酬', '福利',
        '職場', '遠距工作', '混合辦公', '未來工作',
        '組織', '管理者', '主管', '團隊建立',
        # 日文 HR 常見詞
        '人材', '採用', 'リーダーシップ', '組織文化', '従業員',
    ]

    # ─── AI + 工作相關（ai_hr 來源專用）───
    ai_work_keywords = [
        'ai in workplace', 'ai productivity', 'ai automation',
        'future of work', 'digital transformation',
        'generative ai', 'llm', 'large language model',
        'ai colleague', 'ai assistant', 'ai coworker',
        '人工智慧.*職場', '職場.*人工智慧',
        'ai 生產力', 'ai 工作', '生成式 ai',
    ]

    if filter_type == 'hr':
        return any(kw in content for kw in hr_core)

    elif filter_type == 'ai_hr':
        has_hr = any(kw in content for kw in hr_core)
        has_ai_work = False
        import re
        for kw in ai_work_keywords:
            if '.*' in kw:
                if re.search(kw, content):
                    has_ai_work = True
                    break
            else:
                if kw in content:
                    has_ai_work = True
                    break
        # AI 來源：必須同時有 AI 工作關鍵字 + HR 核心關鍵字
        # 或者直接有 HR 核心關鍵字也可以
        return has_hr or (has_ai_work and ('work' in content or '工作' in content or '員工' in content))

    return False

from apscheduler.schedulers.background import BackgroundScheduler
import pytz

FETCH_LOG_FILE = 'fetch_log.json'

def save_fetch_time(fetch_type='manual'):
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
        'type': fetch_type
    }
    log['history'].append(log['last_fetch'])
    log['history'] = log['history'][-50:]

    with open(FETCH_LOG_FILE, 'w') as f:
        json.dump(log, f, indent=2)

class DummyEntry:
    def __init__(self, title, link, summary=""):
        self.title = title
        self.link = link
        self.summary = summary
        self.description = summary
        self.published_parsed = datetime.now().timetuple()

def scrape_bnext():
    import requests
    from bs4 import BeautifulSoup
    url = "https://www.bnext.com.tw/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    entries = []
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for a_tag in soup.find_all('a', href=True):
                href = a_tag['href']
                if '/article/' in href:
                    title = a_tag.get('title', '').strip() or a_tag.get_text(strip=True)
                    if title and len(title) > 5 and title != "前往內容授權":
                        full_url = href if href.startswith('http') else f"https://www.bnext.com.tw{href}"
                        if not any(e.link == full_url for e in entries):
                            entries.append(DummyEntry(title=title, link=full_url))
        return entries
    except Exception as e:
        print(f"Scrape Bnext error: {e}")
        return []

# ─────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────


# ==================== 權限控管 ====================

@app.route('/api/auth/login', methods=['POST'])
def admin_login():
    try:
        data = request.json
        role = data.get('role', 'admin')
        password = data.get('password', '')

        if role not in ROLE_PASSWORDS:
            return jsonify({'success': False, 'error': '無效的身份'}), 400

        if password != ROLE_PASSWORDS[role]:
            return jsonify({'success': False, 'error': '密碼錯誤'}), 401

        token = jwt.encode({
            'role': role,
            'exp': datetime.utcnow() + timedelta(hours=8)
        }, SECRET_KEY, algorithm='HS256')

        return jsonify({'success': True, 'token': token, 'role': role})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def require_login(f):
    """Allow any authenticated role (admin / employee / guest)."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': '請先登入'}), 401
        token = auth_header[7:]
        try:
            jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token 已過期，請重新登入'}), 401
        except Exception:
            return jsonify({'success': False, 'error': 'Token 無效'}), 401
        return f(*args, **kwargs)
    return decorated


def require_employee(f):
    """Allow admin or employee roles; return 403 for guest or unauthenticated."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': '請先登入'}), 401
        token = auth_header[7:]
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            if payload.get('role') not in ('admin', 'employee'):
                return jsonify({'success': False, 'error': '權限不足，需要員工或管理員身份'}), 403
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Token 已過期，請重新登入'}), 401
        except Exception:
            return jsonify({'success': False, 'error': 'Token 無效'}), 401
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        from flask import request, jsonify
        auth_header = request.headers.get('Authorization', '')
        
        if not auth_header.startswith('Bearer '):
            return jsonify({
                'success': False,
                'error': '需要管理員權限'
            }), 403
        
        token = auth_header[7:]
        
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
            if payload.get('role') != 'admin':
                return jsonify({
                    'success': False,
                    'error': '權限不足'
                }), 403
        except jwt.ExpiredSignatureError:
            return jsonify({
                'success': False,
                'error': 'Token 已過期，請重新登入'
            }), 401
        except:
            return jsonify({
                'success': False,
                'error': 'Token 無效'
            }), 401
        
        return f(*args, **kwargs)
    
    return decorated

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/feeds', methods=['GET'])
def get_feeds():
    try:
        suggested_sources = [
            {'id': 'hr-tech', 'name': 'HR Technologist', 'url': 'https://www.hrtechnologist.com/feed/', 'is_active': False},
            {'id': 'shrm', 'name': 'SHRM', 'url': 'https://www.shrm.org/resourcesandtools/hr-topics/pages/rss.aspx', 'is_active': False},
            {'id': 'workday', 'name': 'Workday Blog', 'url': 'https://blog.workday.com/en-us/feed', 'is_active': False}
        ]

        added_sources = [
            {'id': 'cw1', 'name': '天下雜誌 管理頻道', 'url': 'https://www.cw.com.tw/RSS/cw_content.xml', 'is_active': True},
            {'id': 'cw2', 'name': '天下雜誌 職場頻道', 'url': 'https://www.cw.com.tw/RSS/cw_content.xml', 'is_active': True},
            {'id': 'bnext1', 'name': '數位時代 所有最新文章', 'url': 'https://www.bnext.com.tw/rss/articles', 'is_active': True},
            {'id': 'bnext2', 'name': '數位時代 未來商務', 'url': 'https://fc.bnext.com.tw/rss', 'is_active': True},
            {'id': 'hbr1', 'name': 'HBR (US) Human Resource Management', 'url': 'https://hbr.org/topic/human-resource-management/rss', 'is_active': True},
            {'id': 'hbr2', 'name': 'HBR (US) Strategy', 'url': 'https://hbr.org/topic/strategy/rss', 'is_active': True},
            {'id': 'hbr3', 'name': 'HBR (US) Leadership', 'url': 'https://hbr.org/topic/leadership/rss', 'is_active': True},
            {'id': 'josh', 'name': 'Josh Bersin Latest Insights (HR Tech)', 'url': 'https://joshbersin.com/feed/', 'is_active': True},
            {'id': 'oxford', 'name': 'Oxford Review Podcast', 'url': 'https://feed.podbean.com/oxford-review/feed.xml', 'is_active': True},
            {'id': 'economist', 'name': 'The Economist', 'url': 'https://www.economist.com/business/rss.xml', 'is_active': True},
            {'id': '36kr', 'name': '36氪 (Lattice)', 'url': 'https://36kr.com/feed', 'is_active': True},
            {'id': 'president', 'name': 'PRESIDENT Online', 'url': 'https://president.jp/list/rss', 'is_active': True},
            {'id': 'itmedia', 'name': 'ITmedia Business', 'url': 'https://rss.itmedia.co.jp/rss/2.0/business.xml', 'is_active': True},
            {'id': 'nikkei', 'name': '日経中文網', 'url': 'https://zh.cn.nikkei.com/rss.xml', 'is_active': True},
            {'id': 'handelsblatt', 'name': 'Handelsblatt', 'url': 'https://www.handelsblatt.com/contentexport/feed/top-themen', 'is_active': True},
            {'id': 'ainews', 'name': 'AI News', 'url': 'https://www.artificialintelligence-news.com/feed/', 'is_active': True}
        ]

        return jsonify({
            'success': True,
            'suggested_sources': suggested_sources,
            'rss_sources': added_sources
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/fetch-status')
def fetch_status():
    try:
        if os.path.exists(FETCH_LOG_FILE):
            with open(FETCH_LOG_FILE, 'r') as f:
                log = json.load(f)
            return jsonify(log.get('last_fetch', {}))
        return jsonify({})
    except:
        return jsonify({})

# ─────────────────────────────────────────────
# 核心抓取邏輯（供路由和排程共用）
# ─────────────────────────────────────────────

def perform_fetch_process():
    """背景可重用的抓取流程"""
    notion_manager = NotionService()
    ai_service = AIService()

    print("\n" + "=" * 50)
    print(f"開始抓取 RSS 文章 (Time: {datetime.now()})")
    print("=" * 50)

    sources = notion_manager.get_active_feeds()

    if not sources:
        print("⚠️ Notion RSS DB 無法存取，改用備援來源清單")
        sources = [
            {'id': 'josh', 'name': 'Josh Bersin (HR Tech)', 'url': 'https://joshbersin.com/feed/', 'platform': 'HR媒體'},
            {'id': 'cw', 'name': '天下雜誌', 'url': 'https://www.cw.com.tw/RSS/cw_content.xml', 'platform': '天下雜誌'},
        ]

    all_articles = []
    errors = []
    all_articles_for_display = load_articles()
    existing_urls = {a.get('source_url') for a in all_articles_for_display}

    for i, source in enumerate(sources, 1):
        try:
            url = source.get('url')
            name = source.get('name', 'Unknown')
            source_start_time = time.time()

            print(f"\n[{i}/{len(sources)}] 處理來源: {name}")
            print(f"    URL: {url}")

            if 'bnext.com.tw' in url:
                print(f"  > 使用 BeautifulSoup 抓取 Bnext")
                entries = scrape_bnext()
                if not entries:
                    continue
                class DummyFeed:
                    pass
                feed = DummyFeed()
                feed.entries = entries
            else:
                feed = feedparser.parse(url)

            if getattr(feed, 'entries', None) is None or not feed.entries:
                print(f"  ⚠ 沒有找到文章")
                continue

            print(f"  ✓ 找到 {len(feed.entries)} 篇文章")

            filter_type = 'ai_hr' if ('bnext.com.tw' in url or 'oxford-review' in url) else 'hr'

            max_entries = 3 if ('josh' in url.lower() or 'joshbersin' in url.lower()) else 10
            for j, entry in enumerate(feed.entries[:max_entries], 1):
                if time.time() - source_start_time > 30:
                    print(f"    ⚠️ 來源 {name} 超過 30 秒，強制跳出")
                    break

                try:
                    art_url = entry.link
                    try:
                        existing_id = notion_manager.check_article_exists(art_url)
                        if existing_id:
                            print(f"    [{j}] 文章已存在，更新抓取日期")
                            notion_manager.update_article_fetched_date(existing_id)
                            existing_urls.add(art_url)
                            continue
                    except Exception:
                        pass

                    if art_url in existing_urls:
                        print(f"    [{j}] 跳過（本地已存在）")
                        continue

                    en_title = entry.title
                    raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    en_summary = clean_html_content(raw_summary)[:800]

                    if not is_hr_or_ai_related(en_title, en_summary, filter_type):
                        print(f"    [Skip] 不符合主題: {en_title[:40]}")
                        continue

                    print(f"    [{j}] ✅ 發現: {en_title[:40]}...")

                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        dt_parsed = datetime(*entry.published_parsed[:6])
                        dt_utc = dt_parsed.replace(tzinfo=pytz.UTC)
                        pub_date = dt_utc.astimezone(pytz.timezone('Asia/Taipei')).isoformat()

                        # ✅ 超過 30 天的文章直接跳過，不寫入
                        age_days = (datetime.now(pytz.UTC) - dt_utc).days
                        if age_days > 30:
                            print(f"    [Skip] 文章超過 30 天（{age_days} 天前）: {en_title[:40]}")
                            continue
                    else:
                        pub_date = datetime.now(pytz.timezone('Asia/Taipei')).isoformat()

                    print(f"        翻譯中...")
                    zh_title = ai_service.translate_to_chinese(en_title, "標題")
                    zh_summary = ai_service.translate_to_chinese(en_summary, "摘要")
                    print(f"        中文標題: {zh_title[:30]}...")

                    print(f"        提取標籤...")
                    topics = ai_service.extract_topics(en_title, en_summary)
                    print(f"        標籤: {topics}")

                    article_data = {
                        'id': f"local_{int(time.time()*1000)}",
                        'title': zh_title,
                        'summary': zh_summary,
                        'topics': topics,
                        'url': art_url,
                        'published_date': pub_date,
                        'source': name,
                        'status': '待處理',
                        'source_platform': source.get('platform', '新聞媒體'),
                        'source_url': art_url,
                        'ai_content': ''
                    }

                    try:
                        resp = notion_manager.create_article(article_data, source.get('id'))
                        if resp:
                            article_data['id'] = resp['id']
                            print(f"        ✅ 已寫入 Notion")
                        else:
                            print(f"        ⚠️ Notion 寫入失敗，存本地快取")
                    except Exception as e:
                        print(f"        ⚠️ Notion 不可用: {e}，存本地快取")

                    all_articles.append(article_data)
                    if art_url not in existing_urls:
                        all_articles_for_display.insert(0, article_data)
                        existing_urls.add(art_url)

                    time.sleep(0.5)

                except Exception as e:
                    print(f"    ❌ 處理文章失敗: {e}")
                    errors.append(str(e))
                    continue

            # ✅ 修正：更新 RSS 來源的最後抓取時間，失敗時印出原因
            try:
                notion_manager.update_feed_timestamp(source['id'])
            except Exception as e:
                print(f"  ⚠️ 更新最後抓取時間失敗 ({name}): {e}")

        except Exception as e:
            print(f"  ❌ 來源錯誤 ({source.get('name', '?')}): {e}")
            errors.append(str(e))
            continue

    save_articles(all_articles_for_display)
    print(f"\n✅ 抓取完成，共新增 {len(all_articles)} 篇")
    return {'processed': len(all_articles), 'errors': errors}

def scheduled_fetch():
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

# ─────────────────────────────────────────────
# RSS Fetch Route（前端按鈕觸發）
# ─────────────────────────────────────────────



@app.route('/api/fetch', methods=['POST'])
def manual_fetch():
    try:
        result = perform_fetch_process()
        save_fetch_time('manual')
        return jsonify({'success': True, 'time': datetime.now().isoformat(), 'details': result})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ─────────────────────────────────────────────
# AI Routes
# ─────────────────────────────────────────────

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
@require_employee
def ai_rewrite():
    data = request.json
    article_id = data.get('article_id')
    platform = data.get('platform')
    style = data.get('style')

    service = NotionService()
    ai_service = AIService()
    article_data = {}

    if article_id:
        page = service.get_article(article_id)
        if page and 'properties' in page:
            props = page['properties']
            title_list = props.get('Title', {}).get('title', [])
            article_data['title'] = title_list[0]['text']['content'] if title_list else ""
            summary_list = props.get('Summary', {}).get('rich_text', [])
            article_data['summary'] = "".join([t['text']['content'] for t in summary_list]) if summary_list else ""
            article_data['url'] = props.get('URL', {}).get('url')
            tags = props.get('Topic', {}).get('multi_select', [])
            article_data['topics'] = [t['name'] for t in tags]
    else:
        article_data = data.get('article', {})
# Updated Fetch Logic (Issue 1 Fix)
def timeout_handler(signum, frame):
    raise TimeoutError("Fetch operation timed out after 25 seconds")

@app.route('/api/rss/fetch', methods=['POST'])
@app.route('/api/articles/fetch', methods=['POST']) # Alias for user's request
@limiter.limit("10 per hour") # 對抓取 API 設定較嚴格的速率限制，防止資源濫用
@require_login
def fetch_articles():
    """Wrapper to enforce 25-second timeout on user requested fetch logic"""
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(_fetch_articles_internal)
        try:
            result = future.result(timeout=120)
            if isinstance(result, tuple):
                return jsonify(result[0]), result[1]
            return jsonify(result)
        except concurrent.futures.TimeoutError:
            print("❌ 手動抓取超時 (25秒)")
            return jsonify({'success': False, 'message': 'Fetch operation timed out after 25 seconds'}), 504
        except Exception as e:
            print(f"❌ 手動抓取失敗: {str(e)}")
            return jsonify({'success': False, 'message': str(e)}), 500

def _fetch_articles_internal():
    """抓取 RSS 並處理 (User Requested Logic)"""
    notion_manager = NotionService() # Alias for user's naming
    ai_service = AIService()
    
    try:
        print("\n" + "=" * 50)
        print("開始抓取 RSS 文章")
        print("=" * 50)
        
        # 備援來源清單（Notion 無法連線時使用）
        FALLBACK_SOURCES = [
            {'id': 'josh', 'name': 'Josh Bersin (HR Tech)', 'url': 'https://joshbersin.com/feed/', 'platform': 'HR媒體'},
            {'id': 'hbr_hr', 'name': 'HBR Human Resource Management', 'url': 'http://feeds.feedburner.com/harvardbusiness', 'platform': 'HBR'},
            {'id': 'mit', 'name': 'MIT Sloan Management Review', 'url': 'https://sloanreview.mit.edu/feed/', 'platform': 'MIT Sloan'},
            {'id': 'cw', 'name': '天下雜誌', 'url': 'https://www.cw.com.tw/RSS/cw_content.xml', 'platform': '天下雜誌'},
            {'id': 'bnext', 'name': '數位時代', 'url': 'https://www.bnext.com.tw/', 'platform': '數位時代'},
        ]

        # 1. 嘗試從 Notion DB1 讀取 RSS 來源，失敗時用備援清單
        sources = notion_manager.get_active_feeds()

        if not sources:
            print("⚠️  Notion RSS DB 無法存取，改用備援來源清單")
            sources = FALLBACK_SOURCES

        print(f"找到 {len(sources)} 個啟用的來源")
        
        all_articles = []
        errors = []
        
        # for frontend cache
        all_articles_for_display = load_articles()
        existing_urls = {a.get('source_url') for a in all_articles_for_display}
        
        # 2. 逐一處理每個來源
        for i, source in enumerate(sources, 1):
            try:
                source_start_time = time.time()
                print(f"\n[{i}/{len(sources)}] 處理來源: {source.get('name', 'Unknown')}")
                print(f"    URL: {source.get('url')}")
                
                # 抓取 RSS
                url = source['url']
                if 'bnext.com.tw' in url:
                    print(f"  > 使用 BeautifulSoup 抓取 Bnext 來源: {url}")
                    entries = scrape_bnext()
                    if not entries:
                        continue
                    class DummyFeed:
                        pass
                    feed = DummyFeed()
                    feed.entries = entries
                else:
                    feed = feedparser.parse(url)
                
                if getattr(feed, 'entries', None) is None or not feed.entries:
                    print(f"  ⚠ 沒有找到文章")
                    continue
                
                print(f"  ✓ 找到 {len(feed.entries)} 篇文章")
                
                max_entries = 3 if ('josh' in url.lower() or 'joshbersin' in url.lower()) else 10
                for j, entry in enumerate(feed.entries[:max_entries], 1):
                    if time.time() - source_start_time > 30:
                        print(f"    ⚠️ 處理來源 {source.get('name', 'Unknown')} 超過 30 秒，強制跳出保護 worker")
                        break

                    try:
                        # 先查是否在 Notion 中
                        art_url = entry.link
                        try:
                            existing_id = notion_manager.check_article_exists(art_url)
                            if existing_id:
                                print(f"    [{j}] 文章已存在 Notion，更新抓取日期")
                                notion_manager.update_article_fetched_date(existing_id)
                                existing_urls.add(art_url)
                                continue
                        except Exception:
                            pass

                        if art_url in existing_urls:
                            print(f"    [{j}] 跳過（本地已存在）")
                            continue

                        print(f"    [{j}] 處理文章...")
                        en_title = entry.title
                        raw_summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                        en_summary = clean_html_content(raw_summary)[:800]

                        current_filter_type = 'ai_hr' if ('bnext.com.tw' in url or 'oxford-review' in url) else 'hr'
                        if not is_hr_or_ai_related(en_title, en_summary, filter_type=current_filter_type):
                            print(f"    [Skip] 不符合主題: {en_title}")
                            continue

                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            dt_parsed = datetime(*entry.published_parsed[:6])
                            dt_utc = dt_parsed.replace(tzinfo=pytz.UTC)
                            pub_date = dt_utc.astimezone(pytz.timezone('Asia/Taipei')).isoformat()
                        else:
                            pub_date = datetime.now(pytz.timezone('Asia/Taipei')).isoformat()

                        print(f"        翻譯中...")
                        zh_title = ai_service.translate_to_chinese(en_title, "標題")
                        zh_summary = ai_service.translate_to_chinese(en_summary, "摘要")
                        print(f"        中文標題: {zh_title[:30]}...")

                        print(f"        提取標籤...")
                        topics = ai_service.extract_topics(en_title, en_summary)
                        print(f"        標籤: {', '.join(topics)}")

                        article_data = {
                            'id': f"local_{int(time.time()*1000)}",
                            'title': zh_title,
                            'summary': zh_summary,
                            'topics': topics,
                            'url': art_url,
                            'published_date': pub_date,
                            'source': source.get('name', ''),
                            'status': '待處理',
                            'source_platform': source.get('platform', '新聞媒體'),
                            'source_url': art_url,
                            'ai_content': ''
                        }

                        # 嘗試寫入 Notion，失敗時沿用本地 ID
                        try:
                            resp = notion_manager.create_article(article_data, source.get('id'))
                            if resp:
                                article_data['id'] = resp['id']
                                print(f"        ✅ 已寫入 Notion")
                            else:
                                print(f"        ⚠️  Notion 寫入失敗，存本地快取")
                        except Exception:
                            print(f"        ⚠️  Notion 不可用，存本地快取")

                        all_articles.append(article_data)
                        if art_url not in existing_urls:
                            all_articles_for_display.insert(0, article_data)
                            existing_urls.add(art_url)

                        time.sleep(0.5)

                    except Exception as e:
                        error_msg = f"處理文章失敗: {str(e)}"
                        print(f"      ❌ {error_msg}")
                        errors.append(error_msg)
                        continue

                # 嘗試更新 Notion 時間戳（失敗時略過）
                try:
                    notion_manager.update_feed_timestamp(source['id'])
                except Exception:
                    pass
                
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
        
        return {
            'success': True,
            'status': 'success',
            'articles_processed': len(all_articles),
            'message': f'成功處理 {len(all_articles)} 篇新文章',
            'errors': errors if errors else None,
            'articles': all_articles_for_display
        }
        
    except Exception as e:
        print(f"\n❌ 抓取流程錯誤: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            'success': False,
            'status': 'error',
            'error': str(e),
            'message': str(e)
        }, 500

@app.route('/api/articles', methods=['GET'])
def list_articles():
    """獲取文章列表，只返回有效的 HR 文章 (Synced with Notion)"""
    try:
        service = NotionService()
        
        # ✅ 允許的標籤清單 (Whitelist) — 含 Notion 中帶括號的變體
        allowed_tags = {
            # 標準標籤
            '人力資源科技', '人才管理', '員工體驗', '領導力發展',
            '多元共融', '職場文化', '薪酬福利', '績效管理',
            '學習發展', '人力規劃', '員工敬業度', '變革管理',
            '人工智慧', '數位轉型', '未來工作', '遠距工作', '員工福祉',
            # Notion 中的帶括號變體
            '人工智慧 (AI)', '多元共融 (DEI)', '人力資源科技 (HR Tech)',
            '未來工作 (Future of Work)'
        }
        
        # 從 Notion 獲取所有文章
        print("🔄 API Request: Fetching articles from Notion...")
        all_articles = service.get_articles()
        print(f"✅ Notion 回傳: {len(all_articles)} 篇")
        
        # 過濾文章
        valid_articles = []
        for article in all_articles:
            # 檢查標籤
            topics = article.get('topics', [])
            # 無標籤文章：直接放行（不嚴格過濾）
            if not topics:
                valid_articles.append(article)
                continue
                
            # 必須有至少一個允許的標籤
            has_valid_tag = any(tag in allowed_tags for tag in topics)
            
            # 再次檢查標題關鍵字 (Double Insurance)
            blocked_keywords = ['102歲', '醫美', '黃金', '去美元化', '市場拓展']
            has_blocked = any(k in article.get('title', '') for k in blocked_keywords)
            
            if has_valid_tag and not has_blocked:
                # 確保格式與前端一致
                if 'id' not in article:
                    article['id'] = str(int(time.time()))
                valid_articles.append(article)
        
        print(f"✅ 過濾後: {len(valid_articles)} 篇")
        
        # 1. 依照 Fetched Date 降序排列 (防呆機制：若無 fetched_date 則退回 published_date 處理)
        valid_articles.sort(key=lambda x: x.get('fetched_date') or x.get('published_date', ''), reverse=True)
        
        # 2. 只取前 100 筆
        valid_articles = valid_articles[:100]
        
        # ⚠️ 只有在有結果時才更新快取，避免空資料蓋掉本地快取
        if valid_articles:
            save_articles(valid_articles)
        else:
            print("⚠️ 過濾結果為空，保留本地快取不覆蓋")
            return jsonify(load_articles())
        
        return jsonify(valid_articles)
        
    except Exception as e:
        print(f"❌ Error fetching articles: {e}")
        # Fallback to cache if Notion fails
        return jsonify(load_articles())

@app.route('/api/generate-content', methods=['POST'])
@require_employee
def generate_content():
    try:
        data = request.json
        article_id = data.get('article_id')
        platform = data.get('platform', 'Instagram')
        style = data.get('style', '輕鬆親切')

        notion_service = NotionService()
        all_articles = notion_service.get_articles()
        article = next((a for a in all_articles if str(a.get('id')) == str(article_id)), None)

        if not article:
            return jsonify({'success': False, 'error': '找不到文章'}), 404

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
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )

        content = response.choices[0].message.content
        return jsonify({'success': True, 'content': content})

    except Exception as e:
        print(f"錯誤: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ─────────────────────────────────────────────
# Notion Save / Sources / RSS Validate
# ─────────────────────────────────────────────

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
    return jsonify({'success': False, 'error': 'Notion update failed'}), 500

@app.route('/api/save-to-notion', methods=['POST'])
def save_to_notion():
    try:
        data = request.json
        article_id = data.get('article_id')
        content = data.get('content')
        platform = data.get('platform', 'Social Media')

        if not article_id:
            return jsonify({'success': False, 'error': '缺少 Article ID'}), 400

        notion_service = NotionService()
        page_response = notion_service._request("GET", f"pages/{article_id}")

        if not page_response:
            return jsonify({'success': False, 'error': '找不到原文章'}), 404

        existing_content = ""
        props = page_response.get('properties', {})
        ai_content_prop = props.get('AI Content') or props.get('AI重製')
        if ai_content_prop and ai_content_prop.get('rich_text'):
            existing_content = ''.join([t.get('plain_text', '') for t in ai_content_prop['rich_text']])

        platform_emoji = {'Instagram': '📷', 'LinkedIn': '💼', 'Facebook': '📘', 'Twitter': '🐦'}.get(platform, '📱')
        separator = "\n\n" + "-"*30 + "\n\n"

        if existing_content:
            new_full_content = f"{platform_emoji} [{platform}]\n\n{content}{separator}{existing_content}"
        else:
            new_full_content = f"{platform_emoji} [{platform}]\n\n{content}"

        if len(new_full_content) > 2000:
            new_full_content = new_full_content[:1950] + "\n\n...(內容過長已截斷)"

        payload = {
            "properties": {
                "AI Content": {
                    "rich_text": [{"text": {"content": new_full_content}}]
                }
            }
        }

        update_response = notion_service._request("PATCH", f"pages/{article_id}", payload)

        if update_response and 'id' in update_response:
            return jsonify({'success': True, 'notion_page_id': article_id, 'message': f'已新增 {platform} 內容到原文章'})
        return jsonify({'success': False, 'error': 'Notion API 更新失敗'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sources', methods=['GET'])
def get_sources():
    try:
        service = NotionService()
        sources = service.get_all_sources()
        return jsonify({'success': True, 'sources': sources})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sources', methods=['POST'])
@require_admin
def add_source():
    try:
        data = request.json
        service = NotionService()
        source_id = service.create_source(
            name=data['name'],
            url=data['url'],
            platform=data.get('platform', '新聞媒體'),
            is_active=data.get('is_active', True)
        )
        if source_id:
            return jsonify({'success': True, 'source_id': source_id})
        return jsonify({'success': False, 'error': 'Notion creation returned None'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sources/<source_id>', methods=['PATCH'])
def update_source(source_id):
    try:
        data = request.json
        service = NotionService()
        service.update_source(source_id, data)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/sources/<source_id>', methods=['DELETE'])
@require_admin
def delete_source(source_id):
    try:
        service = NotionService()
        service.delete_source(source_id)
        return jsonify({'success': True})
    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rss/validate', methods=['POST'])
def validate_rss():
    try:
        data = request.json
        url = data.get('url')

        if not url:
            return jsonify({'success': False, 'error': 'URL 不能為空'}), 400

        import requests as req_lib

        try:
            response = req_lib.get(url, timeout=10, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if response.status_code != 200:
                return jsonify({'success': False, 'valid': False, 'message': f'HTTP {response.status_code}'})
        except req_lib.exceptions.Timeout:
            return jsonify({'success': False, 'valid': False, 'message': '連線逾時'})
        except req_lib.exceptions.RequestException as e:
            return jsonify({'success': False, 'valid': False, 'message': str(e)[:100]})

        feed = feedparser.parse(response.content)
        if not feed.entries:
            return jsonify({'success': False, 'valid': False, 'message': 'RSS 可訪問但沒有文章'})

        return jsonify({
            'success': True,
            'valid': True,
            'article_count': len(feed.entries),
            'feed_title': feed.feed.get('title', 'Unknown'),
            'message': f'✅ RSS 有效！找到 {len(feed.entries)} 篇文章'
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({'success': False, 'valid': False, 'message': str(e)[:100]}), 500

@app.route('/api/rss/update-status', methods=['POST'])
def update_rss_status():
    try:
        data = request.json
        feed_id = data.get('feed_id')
        is_active = data.get('is_active')
        url = data.get('url')

        from notion_client import Client
        client = Client(auth=os.getenv('NOTION_TOKEN'))

        if is_active:
            import requests as req_lib
            try:
                response = req_lib.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
                if response.status_code != 200:
                    return jsonify({'success': False, 'message': f'RSS URL 無效（HTTP {response.status_code}）'}), 400
                feed = feedparser.parse(response.content)
                if not feed.entries:
                    return jsonify({'success': False, 'message': 'RSS 沒有文章內容'}), 400
            except Exception as e:
                return jsonify({'success': False, 'message': f'驗證失敗: {str(e)[:100]}'}), 400

        client.pages.update(
            page_id=feed_id,
            properties={"Is Active": {"checkbox": is_active}}
        )

        return jsonify({'success': True, 'message': f'已{"啟用" if is_active else "停用"} RSS 來源'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ─────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────

if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        save_articles([])

    port = int(os.environ.get('PORT', 5005))
    print(f"Starting server on port {port}...")

    if not scheduler.running:
        scheduler.start()

    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=port)
