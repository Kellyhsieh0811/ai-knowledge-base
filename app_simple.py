from flask import Flask, jsonify, render_template
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 測試用的假資料
SAMPLE_ARTICLES = [
    {
        'id': 1,
        'title': '測試文章 1：知識管理中的人工智慧',
        'source': 'Josh Bersin',
        'topics': ['人工智慧', '人才管理', '學習發展'],
        'summary': '這是一篇測試文章，用來驗證系統是否正常運作。',
        'url': 'http://example.com/1',
        'published_date': '2025-01-01',
        'ai_content': 'AI 分析內容'
    },
    {
        'id': 2,
        'title': '測試文章 2：員工敬業度與領導力',
        'source': 'Oxford Review',
        'topics': ['員工敬業度', '領導力發展', '職場文化'],
        'summary': '另一篇測試文章，確認文章顯示功能。',
        'url': 'http://example.com/2',
        'published_date': '2025-01-02',
        'ai_content': 'AI 分析內容'
    }
]

SAMPLE_FEEDS = [
    {'name': 'Josh Bersin', 'url': 'https://joshbersin.com/feed/', 'category': 'HR', 'status': 'Suggested', 'platform': 'HR Tech'},
    {'name': 'Oxford Review', 'url': 'https://oxford-review.com/feed/', 'category': 'HR', 'status': 'Suggested', 'platform': 'Research'}
]

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/articles')
def get_articles():
    """返回文章列表（測試用假資料）"""
    print(f"📊 API 被調用：/api/articles")
    # Note: Flattening response to match current Frontend expectation of direct list
    return jsonify(SAMPLE_ARTICLES)

@app.route('/api/feeds')
def get_feeds():
    """返回 RSS 來源列表"""
    print(f"📡 API 被調用：/api/feeds")
    # Note: Flattening response to match current Frontend expectation of direct list
    return jsonify(SAMPLE_FEEDS)

if __name__ == '__main__':
    print("🚀 啟動測試伺服器...")
    print("📍 URL: http://127.0.0.1:5005")
    print("📊 測試文章數量:", len(SAMPLE_ARTICLES))
    print("📡 測試 RSS 來源:", len(SAMPLE_FEEDS))
    app.run(host='0.0.0.0', port=5005, debug=True)
