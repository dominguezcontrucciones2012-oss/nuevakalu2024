import requests
import json

URL_API = "https://routellm.abacus.ai/v1/chat/completions"
# Using the key from the .env
ABACUS_API_KEY = "s2_6599ec2a5ba74be6a9230a1e2f5fccfb"

payload = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "Hola"}],
    "temperature": 0.7
}

headers = {
    "Authorization": f"Bearer {ABACUS_API_KEY}",
    "Content-Type": "application/json"
}

try:
    response = requests.post(URL_API, headers=headers, json=payload, timeout=20)
    print("STATUS:", response.status_code)
    print("JSON:", response.json())
except Exception as e:
    print("ERROR:", e)
