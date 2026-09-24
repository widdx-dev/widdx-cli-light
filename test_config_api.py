import httpx
import json

# Try to access OpenCode config API
url = 'https://opencode.ai/api/config'
headers = {
    'User-Agent': 'widdx-nexus/3.2.0 (Windows 11; x64)',
    'Accept': 'application/json',
}

try:
    resp = httpx.get(url, headers=headers, timeout=30)
    print(f'Status: {resp.status_code}')
    print(f'Headers: {dict(resp.headers)}')
    print(f'Response: {resp.text[:1000]}')
except Exception as e:
    print(f'Error: {e}')
