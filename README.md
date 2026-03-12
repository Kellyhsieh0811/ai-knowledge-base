# RSS AI Knowledge Base (Notion)

一個基於 Python 和 Notion 的 RSS 抓取與 AI 知識管理系統。自動從多個 RSS 來源抓取文章，利用 AI 進行翻譯、摘要與標籤提取，並同步至 Notion 資料庫進行結構化管理。

## 主要功能
- **RSS 自動抓取**：對接多個 RSS feed，自動過濾與 HR / AI 相關的高品質內容。
- **AI 智能處理**：自動翻譯標題與摘要（英翻中），並提取關鍵標籤。
- **Notion 同步**：與 Notion 資料庫深度整合，實現結構化知識存儲。
- **社群媒體改寫**：支援將文章改寫為適合社群媒體發布的格式。

## 系統要求
- Python 3.8+
- Notion API Token 與資料庫 ID
- OpenAI API Key

## 安裝與設定

### 1. 複製專案
```bash
git clone <your-repo-url>
cd rss-knowledge-base
```

### 2. 安裝依賴環境
建議使用虛擬環境 (venv)：
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 .\venv\Scripts\activate # Windows

pip install -r requirements.txt
```

### 3. 環境變數設定
將目錄下的 `.env.example` 複製一份並命名為 `.env`，接著填入您的真實密鑰：
```bash
cp .env.example .env
```
編輯 `.env`：
- `NOTION_TOKEN`: 您的 Notion 整合 Token。
- `NOTION_RSS_DB_ID`: 存放 RSS 來源清單的資料庫 ID。
- `NOTION_CONTENT_DB_ID`: 存放文章內容的資料庫 ID。
- `OPENAI_API_KEY`: 您的 OpenAI API 密鑰。

## 啟動服務
執行以下指令啟動 Flask 伺服器：
```bash
python3 src/app.py
```
啟動後可存取 `http://127.0.0.1:5005` 開啟管理介面。

## 專案結構
- `src/app.py`: Flask 主程式與路由。
- `src/notion_service.py`: Notion API 互動邏輯。
- `src/ai_service.py`: AI 處理邏輯（翻譯、提取、改寫）。
- `src/rss_fetcher.py`: RSS 抓取基礎功能。
- `templates/`: 前端網頁範本。

## 授權
MIT License
