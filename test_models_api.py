import httpx
import json

# Get full models list from OpenCode Zen
url = 'https://opencode.ai/zen/v1/models'
headers = {
    'User-Agent': 'widdx-nexus/3.2.0 (Windows 11; x64)',
    'Accept': 'application/json',
}

try:
    resp = httpx.get(url, headers=headers, timeout=30)
    print(f'Status: {resp.status_code}')
    
    if resp.status_code == 200:
        data = resp.json()
        models = data.get('data', [])
        print(f'Total models: {len(models)}')
        print()
        
        # Group by provider
        providers = {}
        for m in models:
            provider = m.get('owned_by', 'unknown')
            if provider not in providers:
                providers[provider] = []
            providers[provider].append(m['id'])
        
        for provider, model_ids in sorted(providers.items()):
            print(f'{provider}:')
            for mid in sorted(model_ids):
                print(f'  - {mid}')
            print()
except Exception as e:
    print(f'Error: {e}')
