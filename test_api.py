import os

api_key = os.getenv("OPENAI_API_KEY")

if api_key:
    print("OPENAI_API_KEY =", api_key)
else:
    print("❌ Không tìm thấy OPENAI_API_KEY")
