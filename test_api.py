import os
from dotenv import load_dotenv
from openai import OpenAI

# Load .env
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    print("❌ Không tìm thấy OPENAI_API_KEY")
    exit()

print(f"🔑 API Key: {api_key}...")

try:
    client = OpenAI(api_key=api_key)

    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # model nhẹ, rẻ
        messages=[
            {"role": "user", "content": "Say hello in one short sentence."}
        ],
        max_tokens=20
    )

    answer = response.choices[0].message.content
    print("✅ API KEY HOẠT ĐỘNG")
    print("Response:", answer)

except Exception as e:
    print("❌ API KEY KHÔNG DÙNG ĐƯỢC")
    print("Chi tiết lỗi:", str(e))