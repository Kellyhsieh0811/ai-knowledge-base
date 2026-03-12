
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.notion_service import NotionService

def update_sources():
    service = NotionService()
    print("Fetching current sources from Notion...")
    sources = service.get_all_sources()
    
    print(f"Found {len(sources)} sources.")
    
    # 1. Update Map (Name/Partial Name -> New URL)
    updates = {
        '天下雜誌': 'https://www.cw.com.tw/RSS/cw_content.xml',
        'Oxford Review': 'https://feed.podbean.com/oxfordreview/feed.xml',
        '日経中文網': 'https://asia.nikkei.com/rss/feed/nar',
    }
    
    # 2. Rename Map (Name/Partial Name -> New Name)
    renames = {
        'Oxford Review': 'Oxford Review Podcast',
        '日経中文網': 'Nikkei Asia',
    }
    
    # 3. Disable List (Name/Partial Name)
    disables = [
        '數位時代',
        'SHRM',
        'HBR', # Covers all HBR
        'Deloitte',
        'PwC',
    ]

    for source in sources:
        name = source['name']
        page_id = source['id']
        current_active = source['is_active']
        
        # Check Disables
        should_disable = False
        for disable_key in disables:
            if disable_key in name:
                should_disable = True
                break
        
        if should_disable:
            if current_active:
                print(f"❌ Disabling: {name}")
                service.update_source(page_id, {'is_active': False})
            else:
                print(f"⏭️  Already disabled: {name}")
            continue

        # Check Updates
        new_url = None
        for update_key, url in updates.items():
            if update_key in name:
                new_url = url
                break
        
        # Check Renames
        new_name = None
        for rename_key, r_name in renames.items():
            if rename_key in name:
                new_name = r_name
                break
                
        # Perform Update
        props_to_update = {}
        if new_url and new_url != source['url']:
            props_to_update['URL'] = {'url': new_url}
            print(f"🔄 Updating URL for {name}: {new_url}")

        if new_name and new_name != name:
            props_to_update['名稱'] = {'title': [{'text': {'content': new_name}}]}
            print(f"🏷️  Renaming {name} to {new_name}")

        if props_to_update:
            payload = {'properties': props_to_update}
            service._request("PATCH", f"pages/{page_id}", payload)
            print("   ✅ Updated")
        else:
            print(f"✅ OK: {name}")

if __name__ == "__main__":
    update_sources()
