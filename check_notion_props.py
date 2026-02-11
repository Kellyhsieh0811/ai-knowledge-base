
import sys
import os
sys.path.append(os.getcwd())
from src.notion_service import NotionService
import json

def check_properties():
    service = NotionService()
    if not service.content_db_id:
        print("Content DB ID not found")
        return

    # Notion API to retrieve database
    # https://developers.notion.com/reference/retrieve-a-database
    response = service._request("GET", f"databases/{service.content_db_id}")
    
    if response and 'properties' in response:
        print("=== Notion Database Properties ===")
        for name, prop in response['properties'].items():
            print(f"{name}: {prop['type']}")
    else:
        print("Failed to retrieve database info")
        print(response)

if __name__ == "__main__":
    check_properties()
