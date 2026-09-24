import httpx
import json

url = 'https://opencode.ai/zen/v1/chat/completions'
key = 'public'
headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {key}'}
body = {'model': 'deepseek-v4-flash-free', 'messages': [{'role': 'user', 'content': 'Say hello.'}], 'max_tokens': 50, 'stream': False}

try:
    resp = httpx.post(url, json=body, headers=headers, timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
