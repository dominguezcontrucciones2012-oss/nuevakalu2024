import requests
import time

URL_API = "https://routellm.abacus.ai/v1/chat/completions"
# Using the key from the ENV
ABACUS_API_KEY = "s2_6599ec2a5ba74be6a9230a1e2f5fccfb"

payload = {
    "model": "gpt-4o-mini",
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 1
}

headers = {
    "Authorization": f"Bearer {ABACUS_API_KEY}",
    "Content-Type": "application/json"
}

print("Testing credits with a 1-token request...")
start = time.time()
try:
    response = requests.post(URL_API, headers=headers, json=payload, timeout=20)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.text}")
    print(f"Time: {time.time() - start:.2f}s")
except Exception as e:
    print(f"Error: {e}")
    print(f"Time: {time.time() - start:.2f}s")
