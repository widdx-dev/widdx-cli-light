import httpx
import json

# Test Nous Research Inference API
base_url = 'https://inference-api.nousresearch.com/v1'

# 1. Get model catalog (public, no auth)
print('=' * 70)
print('1. Nous Research — Model Catalog (Public)')
print('=' * 70)

try:
    resp = httpx.get(f'{base_url}/models', timeout=15)
    print(f'Status: {resp.status_code}')
    
    if resp.status_code == 200:
        data = resp.json()
        models = data.get('data', [])
        print(f'Total models: {len(models)}')
        
        # Show first 10 models
        for m in models[:10]:
            mid = m.get('id', '')
            name = m.get('name', '')
            print(f'  - {mid} ({name})')
        
        # Look for free models
        free = [m for m in models if 'free' in m.get('id', '').lower() or 'free' in m.get('name', '').lower()]
        if free:
            print(f'\nFree models found: {len(free)}')
            for m in free[:5]:
                print(f'  - {m.get("id")}')
except Exception as e:
    print(f'Error: {e}')

# 2. Try chat completions without key
print()
print('=' * 70)
print('2. Nous Research — Chat without API key')
print('=' * 70)

try:
    resp = httpx.post(f'{base_url}/chat/completions', 
        json={'model': 'nousresearch/hermes-4-405b', 'messages': [{'role': 'user', 'content': 'Say hello.'}], 'max_tokens': 50},
        timeout=15)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')

# 3. Try with empty key
print()
print('=' * 70)
print('3. Nous Research — Chat with empty key')
print('=' * 70)

empty_key = ''
try:
    resp = httpx.post(f'{base_url}/chat/completions', 
        headers={'Authorization': f'Bearer {empty_key}'},
        json={'model': 'nousresearch/hermes-4-405b', 'messages': [{'role': 'user', 'content': 'Say hello.'}], 'max_tokens': 50},
        timeout=15)
    print(f'Status: {resp.status_code}')
    print(f'Response: {resp.text[:500]}')
except Exception as e:
    print(f'Error: {e}')
