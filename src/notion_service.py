import requests
import json
from datetime import datetime
import pytz
from config import settings


class NotionService:
    def __init__(self, token=None, rss_db_id=None, content_db_id=None):
        self.token = token or settings.NOTION_TOKEN
        self.rss_db_id = rss_db_id or settings.NOTION_RSS_DB_ID
        self.content_db_id = content_db_id or settings.NOTION_CONTENT_DB_ID

        if not self.token:
            print("Warning: Notion Token not provided")

        self.base_url = "https://api.notion.com/v1"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json"
        }

    def _format_uuid(self, uuid_str):
        if uuid_str and len(uuid_str) == 32:
            return f"{uuid_str[:8]}-{uuid_str[8:12]}-{uuid_str[12:16]}-{uuid_str[16:20]}-{uuid_str[20:]}"
        return uuid_str or ""

    def _request(self, method, endpoint, payload=None):
        url = f"{self.base_url}/{endpoint}"
        try:
            response = requests.request(
                method, url, headers=self.headers, json=payload, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Notion API Request Error ({method} {endpoint}): {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"Response: {e.response.text}")
            return None

    def get_active_feeds(self):
        """Fetch active RSS feeds from Database 1 (RSS Feeds)"""
        if not self.rss_db_id:
            print("RSS Database ID missing")
            return []

        db_id = self._format_uuid(self.rss_db_id)
        endpoint = f"databases/{db_id}/query"

        payload = {
            "filter": {
                "property": "Is Active",
                "checkbox": {"equals": True}
            }
        }

        results = []
        has_more = True
        next_cursor = None

        while has_more:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            data = self._request("POST", endpoint, payload)
            if not data:
                break
            results.extend(data.get('results', []))
            has_more = data.get('has_more', False)
            next_cursor = data.get('next_cursor')

        print(f"[DEBUG] get_active_feeds: 撈出 {len(results)} 筆 Is Active=True 的來源")

        feeds = []
        for page in results:
            props = page['properties']
            url_obj = props.get('URL', {})
            url = url_obj.get('url') if url_obj else None
            title_list = props.get('名稱', {}).get('title', [])
            name = title_list[0]['text']['content'] if title_list else "Unknown Source"
            select_prop = props.get('平台', {}).get('select')
            platform = select_prop['name'] if select_prop else "Other"

            if url:
                feeds.append({
                    "id": page['id'],
                    "url": url,
                    "name": name,
                    "platform": platform
                })
            else:
                print(f"[DEBUG] 略過無 URL 來源: {name}")

        print(f"[DEBUG] get_active_feeds: 有效來源 {len(feeds)} 筆")
        return feeds

    def check_article_exists(self, url):
        """Check if article URL exists in Database 2"""
        if not self.content_db_id:
            return False

        db_id = self._format_uuid(self.content_db_id)
        endpoint = f"databases/{db_id}/query"

        payload = {
            "filter": {
                "property": "URL",
                "url": {"equals": url}
            },
            "page_size": 1
        }

        data = self._request("POST", endpoint, payload)
        if data and data.get('results'):
            return data['results'][0]['id']
        return None

    def create_article(self, article_data, source_id=None):
        """Create a new article in Database 2 (Content Radar)"""
        if not self.content_db_id:
            return None

        title = article_data.get('title', 'No Title')
        summary = article_data.get('summary', '')
        url = article_data.get('url', '')
        pub_date = article_data.get('published_date')
        if not pub_date:
            pub_date = datetime.now(pytz.timezone('Asia/Taipei')).isoformat()

        platform = article_data.get('source_platform', 'Other')
        now_taipei = datetime.now(pytz.timezone('Asia/Taipei')).isoformat()

        properties = {
            "名稱": {
                "title": [{"text": {"content": title}}]
            },
            "URL": {"url": url},
            "Published Date": {
                "rich_text": [{"text": {"content": pub_date}}]
            },
            "Fetched Date": {
                "rich_text": [{"text": {"content": now_taipei}}]
            },
            "Platform": {
                "select": {"name": platform}
            },
            "Summary": {
                "rich_text": [{"text": {"content": summary[:2000]}}]
            },
            "Topic": {
                "rich_text": [{"text": {"content": ", ".join(article_data.get('topics', []))}}]
            },
            "Source": {
                "select": {"name": article_data.get('source', 'Unknown')}
            },
            "AI Content": {
                "rich_text": [{"text": {"content": article_data.get('ai_content', '')[:2000]}}]
            },
            # ✅ Bug 2 fix: 欄位名稱已改為小寫 status（與 Notion 一致）
            "status": {
                "select": {"name": "待處理"}
            }
        }

        children = [
            {
                "object": "block",
                "type": "heading_2",
                "heading_2": {"rich_text": [{"text": {"content": "摘要"}}]}
            },
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": summary[:2000]}}]}
            }
        ]

        payload = {
            "parent": {"database_id": self._format_uuid(self.content_db_id)},
            "properties": properties,
            "children": children
        }

        return self._request("POST", "pages", payload)

    def update_article_fetched_date(self, page_id):
        """Update Fetched Date to current Asia/Taipei time"""
        taipei_tz = pytz.timezone('Asia/Taipei')
        now_str = datetime.now(taipei_tz).isoformat()
        payload = {
            "properties": {
                "Fetched Date": {
                    "rich_text": [{"text": {"content": now_str}}]
                }
            }
        }
        return self._request("PATCH", f"pages/{page_id}", payload)

    def update_feed_timestamp(self, page_id):
        """
        Update '最後抓取時間' in Database 1 (RSS Feeds)
        欄位型別是 rich_text
        """
        taipei_tz = pytz.timezone('Asia/Taipei')
        now_str = datetime.now(taipei_tz).strftime("%Y-%m-%d %H:%M:%S")
        endpoint = f"pages/{page_id}"
        payload = {
            "properties": {
                "最後抓取時間": {
                    "rich_text": [
                        {
                            "text": {
                                "content": now_str
                            }
                        }
                    ]
                }
            }
        }
        result = self._request("PATCH", endpoint, payload)
        if result:
            print(f"  ✅ 更新最後抓取時間成功: {now_str}")
        else:
            print(f"  ⚠️ 更新最後抓取時間失敗 (page_id: {page_id})")
        return result

    def get_article(self, page_id):
        """Retrieve a page (article) by ID"""
        return self._request("GET", f"pages/{page_id}")

    def update_article_ai_content(self, page_id, ai_content, platform):
        """Update AI Content and status fields"""
        payload = {
            "properties": {
                "AI Content": {
                    "rich_text": [{"text": {"content": ai_content[:2000]}}]
                },
                "Platform": {
                    "select": {"name": platform}
                },
                # ✅ 小寫 status 與 Notion 一致
                "status": {
                    "select": {"name": "已分析"}
                }
            }
        }
        return self._request("PATCH", f"pages/{page_id}", payload)

    def get_all_sources(self):
        """Fetch all active sources from DB1"""
        if not self.rss_db_id:
            return []

        db_id = self._format_uuid(self.rss_db_id)
        endpoint = f"databases/{db_id}/query"

        payload = {
            "filter": {
                "property": "Is Active",
                "checkbox": {"equals": True}
            },
            "sorts": [
                {
                    "timestamp": "created_time",
                    "direction": "descending"
                }
            ]
        }

        results = []
        has_more = True
        next_cursor = None

        while has_more:
            if next_cursor:
                payload["start_cursor"] = next_cursor
            data = self._request("POST", endpoint, payload)
            if not data:
                break
            results.extend(data.get('results', []))
            has_more = data.get('has_more', False)
            next_cursor = data.get('next_cursor')

        feeds = []
        for page in results:
            props = page['properties']
            url_obj = props.get('URL', {})
            url = url_obj.get('url') if url_obj else None
            title_list = props.get('名稱', {}).get('title', [])
            name = title_list[0]['text']['content'] if title_list else "Unknown"
            is_active = props.get('Is Active', {}).get('checkbox', False)
            platform = props.get('平台', {}).get('select', {}).get('name', 'Other') \
                if props.get('平台', {}).get('select') else 'Other'

            if url:
                feeds.append({
                    "id": page['id'],
                    "name": name,
                    "url": url,
                    "is_active": is_active,
                    "platform": platform
                })

        print(f"[DEBUG] get_all_sources: {len(feeds)} 筆")
        return feeds

    def create_source(self, name, url, platform="自訂", is_active=True):
        """Create a new RSS source in DB1"""
        if not self.rss_db_id:
            return None

        properties = {
            "名稱": {
                "title": [{"text": {"content": name}}]
            },
            "URL": {"url": url},
            "平台": {
                "select": {"name": platform}
            },
            "Is Active": {
                "checkbox": is_active
            }
            # ✅ 不帶 最後抓取時間，讓 Notion 保持空值即可，避免 type 不符報錯
        }

        payload = {
            "parent": {"database_id": self._format_uuid(self.rss_db_id)},
            "properties": properties
        }

        return self._request("POST", "pages", payload)

    def update_source(self, page_id, data):
        """Update source properties"""
        properties = {}
        if 'is_active' in data:
            properties["Is Active"] = {"checkbox": data['is_active']}

        return self._request("PATCH", f"pages/{page_id}", {"properties": properties})

    def delete_source(self, page_id):
        """Archive source (soft delete)"""
        return self._request("PATCH", f"pages/{page_id}", {"archived": True})

    def get_articles(self, filters=None):
        """從 Notion Database 2 讀取文章"""
        try:
            # 不在 Notion 端排序（因為 Published Date / Fetched Date 是 rich_text，Notion 無法正確排序）
            # 改由 Python 端排序
            payload = {}

            articles = []
            has_more = True
            next_cursor = None

            while has_more:
                if next_cursor:
                    payload["start_cursor"] = next_cursor
                response = self._request(
                    "POST",
                    f"databases/{self._format_uuid(self.content_db_id)}/query",
                    payload
                )
                if not response:
                    break
                has_more = response.get('has_more', False)
                next_cursor = response.get('next_cursor')

                for page in response.get('results', []):
                    try:
                        props = page.get('properties', {})

                        # 讀取來源
                        source_name = 'Unknown'
                        source_prop = props.get('Source', {})
                        if source_prop:
                            try:
                                if source_prop.get('type') == 'select' and source_prop.get('select'):
                                    source_name = source_prop['select']['name']
                                elif source_prop.get('type') == 'rich_text' and source_prop.get('rich_text'):
                                    source_name = source_prop['rich_text'][0]['text']['content']
                                if source_name and ' (http' in source_name:
                                    source_name = source_name.split(' (http')[0]
                            except Exception as e:
                                print(f"解析來源名稱失敗: {e}")

                        # 讀取標題
                        title = ''
                        for title_key in ['名稱', 'Name', 'Title']:
                            title_prop = props.get(title_key, {})
                            if title_prop.get('title') and len(title_prop['title']) > 0:
                                title = title_prop['title'][0]['text']['content']
                                break

                        # 讀取摘要
                        summary = ''
                        summary_prop = props.get('Summary', {})
                        if summary_prop.get('rich_text') and len(summary_prop['rich_text']) > 0:
                            summary = summary_prop['rich_text'][0]['text']['content']

                        # 讀取標籤（相容 multi_select 和 rich_text）
                        topics = []
                        topic_prop = props.get('Topic', {})
                        if topic_prop.get('type') == 'multi_select':
                            topics = [tag.get('name', '') for tag in topic_prop.get('multi_select', [])]
                        elif topic_prop.get('type') == 'rich_text' and topic_prop.get('rich_text'):
                            topics_str = topic_prop['rich_text'][0]['text']['content']
                            topics = [t.strip() for t in topics_str.split(',') if t.strip()]

                        # 讀取 URL
                        url_obj = props.get('URL', {})
                        url = url_obj.get('url') if url_obj else ''

                        # 讀取發布日期
                        published_date = ''
                        pub_date_prop = props.get('Published Date', {})
                        if pub_date_prop.get('type') == 'date' and pub_date_prop.get('date'):
                            published_date = pub_date_prop['date'].get('start', '')
                        elif pub_date_prop.get('type') == 'rich_text' and pub_date_prop.get('rich_text'):
                            published_date = pub_date_prop['rich_text'][0]['text']['content']

                        # 讀取抓取日期
                        fetched_date = ''
                        fetch_date_prop = props.get('Fetched Date', {})
                        if fetch_date_prop.get('type') == 'date' and fetch_date_prop.get('date'):
                            fetched_date = fetch_date_prop['date'].get('start', '')
                        elif fetch_date_prop.get('type') == 'rich_text' and fetch_date_prop.get('rich_text'):
                            fetched_date = fetch_date_prop['rich_text'][0]['text']['content']

                        # 讀取狀態（相容大小寫）
                        status = '待處理'
                        for status_key in ['status', 'Status']:
                            status_prop = props.get(status_key, {})
                            if status_prop.get('type') == 'select' and status_prop.get('select'):
                                status = status_prop['select'].get('name', '待處理')
                                break
                            elif status_prop.get('type') == 'status' and status_prop.get('status'):
                                status = status_prop['status'].get('name', '待處理')
                                break

                        articles.append({
                            'id': page.get('id', ''),
                            'title': title,
                            'summary': summary,
                            'topics': topics,
                            'url': url,
                            'published_date': published_date,
                            'fetched_date': fetched_date,
                            'source': source_name,
                            'status': status
                        })

                    except Exception as e:
                        print(f"處理單一文章失敗: {e}")
                        import traceback
                        traceback.print_exc()
                        continue

            return articles

        except Exception as e:
            print(f"讀取文章失敗: {e}")
            import traceback
            traceback.print_exc()
            return []
