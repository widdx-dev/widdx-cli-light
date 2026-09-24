import httpx
import json

# Try various OpenCode API endpoints
endpoints = [
    'https://opencode.ai/api/config',
    'https://opencode.ai/api/v1/config',
    'https://opencode.ai/api/providers',
    'https://opencode.ai/api/v1/providers',
    'https://opencode.ai/zen/v1/models',
    'https://opencode.ai/api/models',
]

headers = {
    'User-Agent': 'widdx-nexus/3.2.0 (Windows 11; x64)',
    'Accept': 'application/json',
}

for url in endpoints:
    try:
        resp = httpx.get(url, headers=headers, timeout=10)
        print(f'{resp.status_code} | {url}')
        if resp.status_code == 200:
            print(f'  Response: {resp.text[:200]}')
    except Exception as e:
        print(f'ERROR | {url} | {e}')
