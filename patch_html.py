import re

with open('templates/index.html', 'r') as f:
    html = f.read()

# 1. Insert CSS before </style>
css_snippet = """
        /* 展示模式橫幅 */
        .demo-banner {
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 0.75rem 1rem;
            z-index: 9999;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
            animation: slideDown 0.3s ease;
        }

        @keyframes slideDown {
            from { transform: translateY(-100%); }
            to { transform: translateY(0); }
        }

        .demo-banner-content {
            max-width: 1280px;
            margin: 0 auto;
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.875rem;
            font-weight: 500;
        }

        .demo-login-btn {
            background: white;
            color: #667eea;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.875rem;
            transition: all 0.2s;
        }

        .demo-login-btn:hover {
            background: #f0f0f0;
            transform: translateY(-1px);
        }

        body:has(.demo-banner) .container {
            margin-top: 3rem;
        }
"""
html = html.replace("</style>", css_snippet + "\n    </style>")


# 2. Insert JS at beginning of <script>
js_snippet = """
        // ==================== 展示模式 ====================

        let demoMode = true;
        let adminToken = null;

        function loadInitialData() {
            adminToken = sessionStorage.getItem('admin_token');
            
            if (adminToken) {
                demoMode = false;
                removeDemoBanner();
            } else {
                demoMode = true;
                showDemoBanner();
            }
            
            updateUIPermissions();
            loadSources();
            loadArticles();
        }

        function showDemoBanner() {
            if (document.querySelector('.demo-banner')) return;
            
            const banner = document.createElement('div');
            banner.className = 'demo-banner';
            banner.innerHTML = `
                <div class="demo-banner-content">
                    <span>👁️ 展示模式 - 唯讀瀏覽</span>
                    <button onclick="promptAdminLogin()" class="demo-login-btn">
                        🔓 員工登入
                    </button>
                </div>
            `;
            document.body.prepend(banner);
        }

        function removeDemoBanner() {
            const banner = document.querySelector('.demo-banner');
            if (banner) banner.remove();
        }

        async function promptAdminLogin() {
            const password = prompt('請輸入管理員密碼：');
            if (!password) return;
            
            try {
                const response = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({password})
                });
                
                const data = await response.json();
                
                if (data.success) {
                    adminToken = data.token;
                    sessionStorage.setItem('admin_token', data.token);
                    demoMode = false;
                    
                    removeDemoBanner();
                    updateUIPermissions();
                    showNotification('✅ 登入成功', 'success');
                } else {
                    showNotification('❌ ' + (data.error || '密碼錯誤'), 'error');
                }
            } catch (error) {
                showNotification('❌ 登入失敗', 'error');
            }
        }

        function updateUIPermissions() {
            // 隱藏/顯示刪除按鈕
            document.querySelectorAll('.delete-source-btn').forEach(btn => {
                btn.style.display = demoMode ? 'none' : 'inline-block';
            });
            
            // 隱藏/顯示新增來源按鈕
            const addBtn = document.getElementById('add-source-btn');
            if (addBtn) addBtn.style.display = demoMode ? 'none' : 'inline-block';
            
            // 隱藏/顯示抓取文章按鈕
            const fetchBtn = document.getElementById('fetch-articles-btn');
            if (fetchBtn) fetchBtn.style.display = demoMode ? 'none' : 'inline-block';
        }

        // 帶 token 的 API 請求
        async function fetchWithAuth(url, options = {}) {
            if (adminToken) {
                options.headers = {
                    ...options.headers,
                    'Authorization': `Bearer ${adminToken}`
                };
            }
            
            const response = await fetch(url, options);
            
            if (response.status === 401) {
                sessionStorage.removeItem('admin_token');
                adminToken = null;
                demoMode = true;
                showDemoBanner();
                updateUIPermissions();
                throw new Error('登入已過期，請重新登入');
            }
            
            return response;
        }
"""
html = html.replace("<script>", "<script>\n" + js_snippet)

# 3. Change DOMContentLoaded content
old_dom_loaded = """        document.addEventListener('DOMContentLoaded', () => {
            loadSources();
            loadArticles();
        });"""
new_dom_loaded = """        document.addEventListener('DOMContentLoaded', () => {
            loadInitialData();  // 改用新的初始化函數
        });"""
html = html.replace(old_dom_loaded, new_dom_loaded)

# 4. Replace fetch with fetchWithAuth for restricted endpoints
# Restricted ones based on the user's instructions:
# - POST /api/sources
# - DELETE /api/sources/<source_id>
# - POST /api/articles/fetch
# - POST /api/ai/rewrite
# Looking at the code, we should replace fetch('/api/sources') for POST, and fetch(`/api/sources/${sourceId}` for DELETE.
# Also fetch('/api/rss/fetch') and fetch('/api/ai/rewrite')

html = html.replace("await fetch('/api/rss/fetch'", "await fetchWithAuth('/api/rss/fetch'")
html = html.replace("await fetch('/api/sources'", "await fetchWithAuth('/api/sources'")
html = html.replace("await fetch(`/api/sources/${sourceId}`", "await fetchWithAuth(`/api/sources/${sourceId}`")
html = html.replace("await fetch('/api/ai/rewrite'", "await fetchWithAuth('/api/ai/rewrite'")
# Any others? user didn't mention /api/generate-content or others, but specifically: /api/sources (POST), DELETE /api/sources/<source_id>, /api/articles/fetch (which is /api/rss/fetch in UI), /api/ai/rewrite

# For GET /api/sources, we can also use fetchWithAuth since it doesn't hurt, but GET doesn't have @require_admin.
# The user's example snippet just showed fetch('/api/sources') -> fetchWithAuth.

with open('templates/index.html', 'w') as f:
    f.write(html)
