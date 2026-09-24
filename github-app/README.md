# WIDDX Cortex — GitHub App

🤖 Automated PR review and issue triage powered by WIDDX AI.

## Features

- **PR Review** — Automatic code review on PR open/update
- **Issue Triage** — Auto-label and severity assessment for new issues
- **Verdict** — Approve, Request Changes, or Comment

## Setup

### Option A: Deploy as Web Service

```bash
pip install fastapi uvicorn httpx
export GITHUB_TOKEN="ghp_..."
export WIDDX_API_URL="http://localhost:8000"
export GITHUB_WEBHOOK_SECRET="your-secret"

python github-app/app.py
# → http://localhost:8001
```

### Option B: GitHub Action

```yaml
name: WIDDX Code Review
on:
  pull_request:
    types: [opened, synchronize, reopened]
  issues:
    types: [opened]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: widdx1990/widdx-cortex-review@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

## Webhook Configuration

In your GitHub App settings, configure:
- **Webhook URL:** `https://your-server.com/webhook`
- **Events:** Pull requests, Issues
- **Secret:** Same as `GITHUB_WEBHOOK_SECRET`

## Architecture

```
GitHub Webhook → FastAPI Server → WIDDX Cortex API → GitHub API
                                              ↓
                                     AI Analysis (PR/Issue)
```

🤖 Made in Palestine 🇵🇸
