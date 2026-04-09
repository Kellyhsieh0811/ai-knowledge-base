import os
import json
import time
from openai import OpenAI
from config.settings import OPENAI_API_KEY

class AIService:
    def __init__(self, api_key=None):
        self.client = OpenAI(api_key=api_key or OPENAI_API_KEY)
        self.model = "gpt-4o"

    def _call_openai_with_retry(self, messages, max_tokens=1000, temperature=0.3, retries=3):
        for attempt in range(retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=20
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                print(f"OpenAI API Error (Attempt {attempt+1}/{retries}): {e}")
                if attempt == retries - 1:
                    raise e
                time.sleep(2)
        return None

    def extract_topics(self, title, summary, source_name=""):
        """提取主題標籤 - 廣義 HR/管理/職場判斷"""

        tag_mapping = {
            "HR Technology": "人力資源科技",
            "Talent Management": "人才管理",
            "Employee Experience": "員工體驗",
            "Leadership Development": "領導力發展",
            "Diversity & Inclusion": "多元共融",
            "Workplace Culture": "職場文化",
            "Compensation & Benefits": "薪酬福利",
            "Performance Management": "績效管理",
            "Learning & Development": "學習發展",
            "Workforce Planning": "人力規劃",
            "Employee Engagement": "員工敬業度",
            "Change Management": "變革管理",
            "AI in HR": "人工智慧",
            "Digital HR": "數位轉型",
            "Wellbeing": "員工福祉",
            "DEI": "多元共融",
            "Remote Work": "遠距工作",
            "Future of Work": "未來工作"
        }

        prompt = f"""你是 HR 與職場內容的分類專家。請為這篇文章選擇最相關的標籤。

文章標題：{title}
文章摘要：{summary[:400]}

【判斷原則】
- 凡涉及「組織管理、職場、人才、科技趨勢、商業策略、未來工作」的文章都算相關
- 只有完全無關的內容（如：純金融炒作、娛樂八卦、體育賽事）才回傳空陣列
- 如果不確定，優先給標籤而不是回傳空陣列

從以下標籤中選 1-3 個最相關的：
{', '.join(tag_mapping.keys())}

只回傳 JSON 格式，例如：{{"topics": ["Future of Work", "AI in HR"]}}
如果真的完全無關：{{"topics": []}}
"""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你是內容分類專家。只回傳 JSON 格式，不要解釋。"},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=100
            )

            content = response.choices[0].message.content.strip()
            content = content.replace('```json', '').replace('```', '').strip()

            result = json.loads(content)
            english_topics = result.get('topics', [])

            # 轉換成中文
            chinese_topics = [tag_mapping[t] for t in english_topics if t in tag_mapping]

            # 如果 AI 回傳空陣列，給預設標籤（避免文章被前端過濾掉）
            if not chinese_topics:
                print(f"⚠️ AI 判定非 HR 文章，給預設標籤")
                chinese_topics = ["未來工作", "數位轉型"]

            # 補足到至少 2 個標籤
            defaults = ["人才管理", "職場文化", "未來工作"]
            for tag in defaults:
                if tag not in chinese_topics and len(chinese_topics) < 2:
                    chinese_topics.append(tag)

            print(f"✓ AI 標籤: {', '.join(chinese_topics)}")
            return chinese_topics[:5]

        except Exception as e:
            print(f"❌ 提取標籤失敗: {e}")
            return ["人才管理", "職場文化"]

    def translate_to_chinese(self, text, text_type="title"):
        """翻譯成繁體中文"""
        prompt = f"""請將以下內容（可能是簡體中文、英文、日文或其他語言）翻譯成繁體中文（台灣用語）。
保持 HR 專業術語的準確性。

{text}

只回傳翻譯結果，不要任何說明或前言。"""

        try:
            return self._call_openai_with_retry([
                {"role": "system", "content": "你是專業的翻譯員，精通 HR 領域術語。你的任務是將任何輸入語言（包含簡體中文）翻譯成流暢的繁體中文（台灣用語）。"},
                {"role": "user", "content": prompt}
            ], max_tokens=1000)

        except Exception as e:
            print(f"翻譯錯誤: {e}")
            return text

    def rewrite_for_social(self, article, platform, style):
        """改寫成社群媒體內容"""

        platform_guides = {
            "LinkedIn": "專業、深度、數據導向，1500-2000字，適合 HR 專業人士。使用專業語氣，包含洞察和趨勢分析。",
            "Facebook": "親和、實用、案例分享，800-1200字，適合一般職場人士。語氣友善，強調實用性。",
            "Instagram": "簡潔、視覺化、重點條列，300-500字，搭配 5-10 個 hashtags。使用 emoji，易於快速閱讀。"
        }

        style_tones = {
            "專業洞察": "以專業 HR 角度提供深度見解，引用數據和研究",
            "輕鬆分享": "用輕鬆對話的方式分享實用知識，親和力強",
            "激勵觀點": "激勵讀者思考與行動，充滿正能量",
            "深度分析": "深入分析趨勢與影響，提供策略建議"
        }

        platform_normalized = platform.capitalize()
        if platform_normalized not in platform_guides:
            platform_guides[platform] = f"適合 {platform} 的專業內容"

        system_prompt = """你是一位資深的 HR 內容策展專家，擅長將專業文章改寫成適合不同社群媒體平台的內容。
你的改寫內容既保持專業性，又具有吸引力和互動性。
你精通繁體中文（台灣用語），熟悉台灣職場文化。"""

        topics_str = ', '.join(article.get('topics', [])) if isinstance(article.get('topics'), list) else str(article.get('topics', ''))

        user_prompt = f"""請將以下 HR 文章改寫成適合 {platform} 的貼文：

原文標題：{article.get('title', '')}
原文摘要：{article.get('summary', '')}
主題標籤：{topics_str}

改寫要求：
- 平台：{platform}
- 平台特性：{platform_guides.get(platform, platform_guides.get(platform_normalized, ''))}
- 風格：{style}
- 風格說明：{style_tones.get(style, style)}
- 語言：繁體中文（台灣用語）
- 保持專業性，但要有吸引力
- 包含行動呼籲（CTA），鼓勵互動
- 適當使用 emoji（但不要過度）
- 結構清晰，易於閱讀
- 在文末加入「📖 延伸閱讀：[原文連結]」

請直接輸出改寫後的貼文內容，不要任何前言、說明或後記。"""

        try:
            content = self._call_openai_with_retry([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ], max_tokens=2500, temperature=0.7)

            if 'url' in article and article['url']:
                content += f"\n\n📖 延伸閱讀：{article['url']}"

            return content

        except Exception as e:
            print(f"重製內容錯誤: {e}")
            return f"生成內容時發生錯誤：{str(e)}"

    def batch_translate_and_tag(self, articles):
        """批次處理：翻譯和提取標籤"""
        results = []

        for article in articles:
            try:
                print(f"Processing: {article.get('title')[:30]}...")
                chinese_title = self.translate_to_chinese(article['title'], text_type="標題")
                chinese_summary = self.translate_to_chinese(article['summary'], text_type="摘要")
                topics = self.extract_topics(article['title'], article['summary'])

                results.append({
                    'original_title': article['title'],
                    'title': chinese_title,
                    'original_summary': article['summary'],
                    'summary': chinese_summary,
                    'topics': topics,
                    'url': article.get('url', article.get('source_url', '')),
                    'published_date': article.get('published_date', article.get('publish_date')),
                    'source_platform': article.get('source_platform'),
                    'id': article.get('id')
                })

                print(f"✓ AI 處理完成：{chinese_title[:20]}...")

            except Exception as e:
                print(f"✗ 處理失敗 (跳過): {article.get('title', '')} - {e}")
                results.append(article)

        return results
