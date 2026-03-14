# 專案技術棧與 Ubuntu 佈署指南

## 1. 網站使用的技術與框架

### 後端 (Backend)
- **程式語言**: Python 3
- **Web 框架**: Flask (輕量級 Web 應用框架)
- **排程管理**: APScheduler (用於背景定時抓取 RSS)
- **資料解析**: feedparser (解析 RSS Feed)
- **API 整合**: 
  - `openai` (負責翻譯、摘要、提取標籤與改寫)
  - `notion-client` (與 Notion 資料庫同步資料)
- **資訊安全**: 
  - `Flask-Limiter` (API 頻率限制，防止暴力破解)
  - `Flask-Talisman` (設定安全 HTTP 標頭)
  - `Flask-CORS` (跨來源請求保護)

### 前端 (Frontend)
- **基礎技術**: HTML, CSS, 原生 JavaScript (Vanilla JS)
- **模板引擎**: Jinja2 (Flask 內建，用於動態渲染 `templates/` 目錄下的 HTML)
- **設計風格**: 客製化 CSS，支援回應式排版 (RWD) 與動態互動。

### 生產環境部署架構推薦
- **Web 伺服器 / 反向代理**: Nginx
- **WSGI 應用伺服器**: Gunicorn
- **進程管理守護程式**: Systemd

---

## 2. Ubuntu 伺服器佈署操作指令規劃 

以下指令以乾淨的 **Ubuntu 22.04 LTS** 為例進行規劃。

### 步驟 1：更新系統與安裝基礎套件
首先登入您的 Ubuntu 伺服器，更新系統列表並安裝 Python 環境、Nginx 與 Git。
```bash
sudo apt update
sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx git -y
```

### 步驟 2：下載專案原始碼
進入您規劃放置網站檔案的目錄，這裡以 `/var/www` 為例。
```bash
cd /var/www

# 請將這裡的網址替換為您的 repository 網址
sudo git clone https://github.com/Kellyhsieh0811/ai-knowledge-base.git

# 進入專案目錄
cd ai-knowledge-base
```

### 步驟 3：設定 Python 虛擬環境與安裝依賴
為了不污染系統 Python 環境，建議建立獨立的虛擬環境。
```bash
# 建立名為 venv 的虛擬環境
sudo python3 -m venv venv

# 更改目前資料夾擁有者，方便後續操作 (假設您的 ubuntu 登入帳號為 ubuntu)
sudo chown -R $USER:$GROUPS /var/www/ai-knowledge-base

# 啟動虛擬環境
source venv/bin/activate

# 安裝 requirements.txt 所需套件
pip install -r requirements.txt

# 安裝生產環境運行 Flask 所需的 Gunicorn
pip install gunicorn
```

### 步驟 4：設定環境變數
```bash
# 複製範本檔
cp .env.example .env

# 使用 nano 編輯器開啟 .env，填入您真實的 API Keys 等敏感資料
nano .env
# (填寫完畢後，按 Ctrl+O 存檔，Enter 確認，再按 Ctrl+X 離開)
```

### 步驟 5：建立 Systemd 服務 (使用 Gunicorn)
為了讓網站即使伺服器重新開機也能自動啟動，並在背景穩定運行，我們需要設定 systemd。

```bash
sudo nano /etc/systemd/system/rss-kb.service
```

在編輯器中貼上以下設定內容（請根據您實際的 Ubuntu 登入使用者調整 `User`）：
```ini
[Unit]
Description=Gunicorn daemon for RSS AI Knowledge Base
After=network.target

[Service]
# 請換成您伺服器使用的日常帳號名稱，例如 ubuntu 或 root
User=ubuntu
Group=www-data
WorkingDirectory=/var/www/ai-knowledge-base
Environment="PATH=/var/www/ai-knowledge-base/venv/bin"
# 啟動 Gunicorn，綁定 unix socket 檔案，設定 3 個 worker 處理並行請求，逾時設為 120 秒
ExecStart=/var/www/ai-knowledge-base/venv/bin/gunicorn --workers 3 --bind unix:rss-kb.sock -m 007 --timeout 120 'src.app:app'

[Install]
WantedBy=multi-user.target
```

啟動並啟用該背景服務：
```bash
sudo systemctl start rss-kb
sudo systemctl enable rss-kb

# 檢查一下狀態是否顯示為 active (running)
sudo systemctl status rss-kb
```

### 步驟 6：設定 Nginx 反向代理
設定 Nginx 做為對外伺服器，並將請求轉發給我們建立的 Gunicorn 應用程式。

```bash
sudo nano /etc/nginx/sites-available/rss-kb
```

貼上以下配置內容：
```nginx
server {
    listen 80;
    # 這裡請替換為您綁定的網域名稱 (domain name) 或您的伺服器公網 IP
    server_name your_domain_or_ip; 

    location / {
        include proxy_params;
        proxy_pass http://unix:/var/www/ai-knowledge-base/rss-kb.sock;
    }
}
```

啟用該網站設定檔，並重新啟動 Nginx：
```bash
# 建立快捷方式啟用配置
sudo ln -s /etc/nginx/sites-available/rss-kb /etc/nginx/sites-enabled

# 測試 nginx 設定語法是否正確
sudo nginx -t

# 若顯示 syntax is ok，則重啟 Nginx 讓設定生效
sudo systemctl restart nginx
```

### 步驟 7：開放防火牆
如果您的伺服器有開啟 ufw 防火牆，請開放 Nginx 通訊埠口：
```bash
sudo ufw allow 'Nginx Full'
# 如果防火牆還沒啟用，可以執行: sudo ufw enable
```

### 完成！
設定至此，您的網站應該已經可以在網際網路上透過您的伺服器 IP 或網域名稱訪問了。
