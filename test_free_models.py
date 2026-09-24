import httpx
import json

free_models = [
    'deepseek-v4-flash-free',
    'ling-3.0-flash-fin-free',
    'mimo-v2.5-free',
    'muse-spark-1.2-contributor-free',
    'muse-spark-1.3-contributor-free',
    'nemotron-3-ultra-free',
    'nemotron-3.5-lightning-free',
]

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

print('=' * 70)
print('Testing Free Models via Direct API')
print('=' * 70)

for model in free_models:
    body = {
        'model': model,
        'messages': [{'role': 'user', 'content': 'Say hello in 3 words.'}],
        'max_tokens': 50,
        'stream': False,
    }
    
    try:
        resp = httpx.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            print(f'OK {model}: {content[:50]}')
        else:
            error = resp.text[:100]
            print(f'FAIL {model}: {resp.status_code} - {error}')
    except Exception as e:
        print(f'FAIL {model}: Error - {e}')

print()
print('=' * 70)
