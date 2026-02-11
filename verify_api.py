import os
from dotenv import load_dotenv
from openai import OpenAI

# Explicitly load .env
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
print(f"Loaded API Key: {api_key[:10]}...{api_key[-5:] if api_key else 'None'}")

if not api_key:
    print("Error: OPENAI_API_KEY not found in environment.")
    exit(1)

try:
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": "Hello"}],
        max_tokens=5
    )
    print("API Connection Successful!")
    print("Response:", response.choices[0].message.content)
except Exception as e:
    print(f"API Connection Failed: {e}")
