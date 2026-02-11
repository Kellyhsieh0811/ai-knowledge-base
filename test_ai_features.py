import os
import sys
import json
from dotenv import load_dotenv

# Load env before importing settings
load_dotenv()

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__))))

from src.ai_service import AIService

def test_ai():
    print("Initializing AI Service...")
    try:
        service = AIService()
        print(f"Model: {service.model}")
    except Exception as e:
        print(f"Error initializing service: {e}")
        return

    # Mock Article
    title = "The Future of Remote Work in 2024"
    summary = "Remote work is here to stay, but hybrid models are becoming the norm. Companies need to focus on culture and digital tools to maintain engagement and productivity in distributed teams."
    article = {
        'title': title,
        'summary': summary,
        'url': 'https://example.com/remote-work',
        'topics': []
    }

    print("\n--- 1. Testing Translation ---")
    try:
        zh_title = service.translate_to_chinese(title, 'title')
        print(f"Original Title: {title}")
        print(f"Translated Title: {zh_title}")
        
        zh_summary = service.translate_to_chinese(summary, 'summary')
        print(f"Translated Summary: {zh_summary[:50]}...")
    except Exception as e:
        print(f"Translation failed: {e}")

    print("\n--- 2. Testing Auto-tagging ---")
    try:
        topics = service.extract_topics(title, summary)
        print(f"Topics: {topics}")
        article['topics'] = topics
    except Exception as e:
        print(f"Tagging failed: {e}")

    print("\n--- 3. Testing Content Repurposing (LinkedIn) ---")
    try:
        content = service.rewrite_for_social(article, 'LinkedIn', '專業洞察')
        print(f"Generated Content Length: {len(content)}")
        print(f"Preview: {content[:100]}...")
    except Exception as e:
        print(f"Repurposing failed: {e}")

if __name__ == "__main__":
    if not os.getenv("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not found in environment.")
    else:
        test_ai()
