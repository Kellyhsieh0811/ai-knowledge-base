import os
import sys
import json
from datetime import datetime

# Add project root and src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '..')
src_dir = os.path.join(project_root, 'src')

sys.path.append(project_root)
sys.path.append(src_dir)

from src.notion_service import NotionService
from config import settings

def cleanup_notion_database():
    print("🚀 開始清理 Notion 資料庫...")
    
    service = NotionService()
    
    # ✅ 允許的標籤清單 (Whitelist)
    allowed_tags = {
        '人力資源科技', '人才管理', '員工體驗', '領導力發展',
        '多元共融', '職場文化', '薪酬福利', '績效管理',
        '學習發展', '人力規劃', '員工敬業度', '變革管理',
        '人工智慧', '數位轉型'
    }
    
    # ❌ 禁止的關鍵字 (Blacklist)
    blocked_keywords = [
        '102歲', '醫美', '黃金', '去美元化', '待處理',
        '市場拓展', '品牌管理', '供應鏈', '股票', '期貨', '投資'
    ]
    
    try:
        # 1. 獲取所有文章
        print("📥 正在讀取所有文章...")
        # Override default sort to get everything if possible, or just default behavior
        articles = service.get_articles()
        print(f"📦 共找到 {len(articles)} 篇文章")
        
        deleted_count = 0
        kept_count = 0
        
        for article in articles:
            page_id = article['id']
            title = article['title']
            topics = article.get('topics', [])
            status = article.get('status', '')
            
            should_delete = False
            delete_reason = ""
            
            # 檢查 1: 是否包含禁止關鍵字
            for keyword in blocked_keywords:
                if keyword in title or keyword in status:
                    should_delete = True
                    delete_reason = f"包含禁止關鍵字: {keyword}"
                    break
            
            # 檢查 2: 是否有允許的標籤 (如果沒有被關鍵字刪除)
            if not should_delete:
                if not topics:
                    should_delete = True
                    delete_reason = "沒有任何標籤"
                else:
                    # 檢查是否至少有一個允許的標籤
                    has_valid_tag = any(tag in allowed_tags for tag in topics)
                    if not has_valid_tag:
                        should_delete = True
                        delete_reason = f"無有效標籤 (現有: {topics})"
            
            # 執行刪除或保留
            if should_delete:
                print(f"🗑️ 刪除: {title} | 原因: {delete_reason}")
                # Notion API Delete (Archive)
                service._request("PATCH", f"pages/{page_id}", {"archived": True})
                deleted_count += 1
            else:
                print(f"✅ 保留: {title} | 標籤: {topics}")
                kept_count += 1
                
        print("\n" + "="*30)
        print(f"🎉 清理完成！")
        print(f"✅ 保留: {kept_count} 篇")
        print(f"🗑️ 刪除: {deleted_count} 篇")
        print("="*30)
        
    except Exception as e:
        print(f"❌ 清理失敗: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    cleanup_notion_database()
