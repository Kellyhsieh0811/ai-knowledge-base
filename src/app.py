  import sys
import os
print(f"LOADING APP FROM: {__file__}")

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template, jsonify, request
import json
from datetime import datetime
from config import settings
from src.rss_fetcher import fetch_feedfrom src.notion_service import NotionService
from src.ai_service import AIService
import time
import feedparser
import re
from html import unescape
import traceback
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_talisman import Talisman
from flask_cors import CORS

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# 設定 Flask Secret Key (從環境變數讀取，若無則生成隨機值以維持基礎安全)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', os.urandom(24))

# 啟用 CORS (跨來源資源共享)
CORS(app)

# 啟用 Talisman (設定安全標頭，如 Content Security Policy)
# 由於是開發環境且目前多為內網存取，我們先不強制 HTTPS
talisman = Talisman(
    app,
