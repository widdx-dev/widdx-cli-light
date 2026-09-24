import httpx
import json

url = 'https://opencode.ai/zen/v1/chat/completions'
key = 'public'
referer = 'https://opencode.ai/'
title = 'opencode'
source = 'opencode'
ua = 'widdx-nexus/3.2.0 opencode-ai-sdk (Windows 11; x64)'

headers = {
    'Content-Type': 'application/json',
    'Authorization': f'Bearer {key}',
    'HTTP-Referer': referer,
    'X-Title': title,
    'X-Source': source,
    'User-Agent': ua,
}
body = {
    'model': 'deepseek-v4-flash-free',
    'messages': [{'role': 'user', 'content': 'Say hello.'}],
    'max_tokens': 50,
    'stream': False,
}

try:
    resp = httpx.post(url, json=body, headers=headers, timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
