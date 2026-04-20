import re

with open('src/app.py', 'r') as f:
    app_py = f.read()

# 1. ADD IMPORTS
import_insert = """import jwt\nfrom datetime import datetime, timedelta\nfrom functools import wraps\nfrom flask_cors import CORS\n"""
app_py = import_insert + app_py

# Wait, CORS is already in app_py (we saw it around line 29)
# Let's clean up existing CORS(app) if we insert a new one, OR just insert before it.

cors_config = """
# ==================== 權限控管 ====================

@app.route('/api/auth/login', methods=['POST'])
def admin_login():
    try:
        from flask import request, jsonify
        data = request.json
        password = data.get('password', '')
        
        if password != ADMIN_PASSWORD:
            return jsonify({
                'success': False,
                'error': '密碼錯誤'
            }), 401
        
        # 生成 JWT token (8 小時有效)
        token = jwt.encode({
            'role': 'admin',
            'exp': datetime.utcnow() + timedelta(hours=8)
        }, SECRET_KEY, algorithm='HS256')
        
        return jsonify({
            'success': True,
            'token': token,
            'message': '登入成功'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

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
"""

# Find app = Flask(__name__...)
app_flask_match = re.search(r"app = Flask\([^)]+\)", app_py)
if app_flask_match:
    idx = app_flask_match.end()
    insert_str = "\n# 啟用 CORS\nCORS(app)\n\n# 權限設定\nADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'demo2026')\nSECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-change-in-production')\n"
    app_py = app_py[:idx] + insert_str + app_py[idx:]

# Remove duplicate CORS(app) that was already there
# Only replace the one below app.secret_key
app_py = re.sub(r'CORS\(app\)(?!\n\n# 權限設定)', '', app_py) # This might be risky, let's just do a simpler search & replace

# we'll insert cors_config before @app.route('/')
route_idx = app_py.find("@app.route('/')")
app_py = app_py[:route_idx] + cors_config + "\n" + app_py[route_idx:]

# Decorate specific routes:
# - POST /api/sources (新增來源) -> def add_source():
app_py = re.sub(r"(@app\.route\('/api/sources',\s*methods=\['POST'\]\)\n)(def add_source)", r"\1@require_admin\n\2", app_py)
# - DELETE /api/sources/<source_id> (刪除來源) -> def delete_source(source_id):
app_py = re.sub(r"(@app\.route\('/api/sources/<source_id>',\s*methods=\['DELETE'\]\)\n)(def delete_source)", r"\1@require_admin\n\2", app_py)
# - POST /api/articles/fetch (抓取文章) -> def fetch_articles():
# Note: we have @app.route('/api/rss/fetch', methods=['POST']) \n @app.route('/api/articles/fetch', methods=['POST'])
app_py = re.sub(r"(@app\.route\('/api/articles/fetch',\s*methods=\['POST'\]\).*\n@limiter[^\n]+\n)(def fetch_articles)", r"\1@require_admin\n\2", app_py)
# - POST /api/ai/rewrite (AI 重製) -> def ai_rewrite():
app_py = re.sub(r"(@app\.route\('/api/ai/rewrite',\s*methods=\['POST'\]\)\n)(def ai_rewrite)", r"\1@require_admin\n\2", app_py)


with open('src/app_patched.py', 'w') as f:
    f.write(app_py)
