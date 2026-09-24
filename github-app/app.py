"""
WIDDX Nexus — GitHub App
==========================
Automated PR review, issue triage, and repository management.

Deploy as a webhook handler (Flask/FastAPI) or GitHub Action.
Uses the WIDDX Core engine for AI-powered analysis.

Endpoints:
  POST /webhook  — Receive GitHub webhook events
  GET  /health   — Health check

Environment:
  GITHUB_TOKEN         — GitHub PAT for API access
  GITHUB_APP_ID        — GitHub App ID
  GITHUB_APP_PRIVATE_KEY — GitHub App private key (path or PEM)
  WIDDX_API_URL        — WIDDX API server URL (default: http://localhost:8000)
"""

import os
import sys
import json
import hashlib
import hmac
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

import httpx

try:
    from core._path import ensure_project_root
except ImportError:
    _root = str(Path(__file__).resolve().parent.parent)
    if _root not in sys.path:
        sys.path.insert(0, _root)
    from core._path import ensure_project_root

# ── Config ────────────────────────────────────────────────────
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
WIDDX_API_URL = os.environ.get("WIDDX_API_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.environ.get("GITHUB_WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError(
        "GITHUB_WEBHOOK_SECRET environment variable is required.\n"
        "Set it to your GitHub webhook secret token. Generate one at:\n"
        "  GitHub → Settings → Webhooks → Add webhook → Secret"
    )
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [widdx-github] %(levelname)s %(message)s"
)
logger = logging.getLogger("widdx.github")

# ── GitHub API Client ─────────────────────────────────────────

class GitHubClient:
    """Minimal GitHub REST API client."""

    def __init__(self, token: str = ""):
        self.token = token or GITHUB_TOKEN
        self.base = "https://api.github.com"
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _request(self, method: str, path: str, **kwargs) -> dict:
        async with httpx.AsyncClient(timeout=30) as client:
            res = await client.request(
                method, f"{self.base}{path}",
                headers=self.headers, **kwargs
            )
            res.raise_for_status()
            return res.json()

    async def get_pr(self, owner: str, repo: str, pr_number: int) -> dict:
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}")

    async def get_pr_files(self, owner: str, repo: str, pr_number: int) -> list[dict]:
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{pr_number}/files")

    async def create_pr_review(
        self, owner: str, repo: str, pr_number: int,
        body: str, event: str = "COMMENT"
    ) -> dict:
        return await self._request(
            "POST", f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            json={"body": body, "event": event}
        )

    async def create_issue_comment(
        self, owner: str, repo: str, issue_number: int, body: str
    ) -> dict:
        return await self._request(
            "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/comments",
            json={"body": body}
        )

    async def add_labels(
        self, owner: str, repo: str, issue_number: int, labels: list[str]
    ) -> dict:
        return await self._request(
            "POST", f"/repos/{owner}/{repo}/issues/{issue_number}/labels",
            json={"labels": labels}
        )


# ── AI Analysis ───────────────────────────────────────────────

class WiddxAnalyzer:
    """Call the WIDDX Nexus API for code analysis."""

    def __init__(self, api_url: str = ""):
        self.api_url = (api_url or WIDDX_API_URL).rstrip("/")

    async def analyze_pr(self, title: str, body: str, diffs: list[dict]) -> str:
        """Review a pull request — returns markdown review."""
        diff_summary = "\n".join(
            f"- `{f['filename']}` (+{f.get('additions', 0)} -{f.get('deletions', 0)})"
            for f in diffs[:20]
        )
        if len(diffs) > 20:
            diff_summary += f"\n- ... and {len(diffs) - 20} more files"

        diffs_text = "\n\n".join(
            f"### {f['filename']}\n```diff\n{f.get('patch', '')[:2000]}\n```"
            for f in diffs[:5]
        )

        prompt = f"""Review this Pull Request:

**Title:** {title}
**Description:** {body[:500] or 'No description'}
**Files changed ({len(diffs)}):**
{diff_summary}

**Key diffs:**
{diffs_text}

Provide a concise code review in this format:
1. **Summary** — one-sentence overview
2. **Issues Found** — list bugs, security concerns, or logic errors
3. **Suggestions** — improvements for readability, performance, or patterns
4. **Verdict** — ✅ Approve / ⚠️ Changes Requested / 💬 Comment

Keep it professional and constructive. Focus on real issues, not style nitpicks."""

        async with httpx.AsyncClient(timeout=120) as client:
            try:
                res = await client.post(
                    f"{self.api_url}/api/chat",
                    json={"message": prompt}
                )
                res.raise_for_status()
                data = res.json()
                return data.get("response", "Analysis unavailable.")
            except Exception as e:
                logger.error(f"WIDDX API error: {e}")
                return f"⚠️ Automated review unavailable: {e}"

    async def triage_issue(self, title: str, body: str) -> dict:
        """Analyze an issue for auto-labeling and severity."""
        prompt = f"""Triage this GitHub issue:

**Title:** {title}
**Description:** {body[:1000] or 'No description'}

Return JSON only:
{{
    "labels": ["bug", "enhancement", ...],
    "severity": "low|medium|high|critical",
    "assignee_suggestion": "team or skill area",
    "summary": "one-line summary in English"
}}"""

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                res = await client.post(
                    f"{self.api_url}/api/chat",
                    json={"message": prompt}
                )
                res.raise_for_status()
                data = res.json()
                # Try to parse JSON from response
                text = data.get("response", "{}")
                # Extract JSON block if wrapped in markdown
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0]
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0]
                return json.loads(text.strip())
            except Exception as e:
                logger.error(f"Triage error: {e}")
                return {"labels": [], "severity": "medium", "summary": str(e)}


# ── Webhook Handler ───────────────────────────────────────────

def verify_webhook(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature using HMAC-SHA256."""
    if not WEBHOOK_SECRET:
        logger.error("No webhook secret configured — rejecting request")
        return False
    expected = "sha256=" + hmac.new(
        WEBHOOK_SECRET.encode(), payload, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


async def handle_pull_request(event: str, payload: dict):
    """Handle pull_request webhook events."""
    action = payload.get("action", "")
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})

    owner = repo.get("owner", {}).get("login", "")
    repo_name = repo.get("name", "")
    pr_number = pr.get("number", 0)
    title = pr.get("title", "")
    body = pr.get("body", "") or ""

    if action not in ("opened", "reopened", "synchronize"):
        logger.info(f"Skipping PR action: {action}")
        return

    logger.info(f"Reviewing PR #{pr_number} ({title}) in {owner}/{repo_name}")

    gh = GitHubClient()
    analyzer = WiddxAnalyzer()

    try:
        diffs = await gh.get_pr_files(owner, repo_name, pr_number)
        review = await analyzer.analyze_pr(title, body, diffs)

        # Post as PR review
        verdict_emoji = "✅" if "✅ Approve" in review else "💬"
        full_review = (
            f"## 🤖 WIDDX Nexus — Automated Code Review\n\n"
            f"{review}\n\n"
            f"---\n*🤖 Generated by [WIDDX Nexus](https://github.com/widdx1990/widdx-cli-light) "
            f"on {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}*"
        )

        event_type = "COMMENT"
        if "✅ Approve" in review:
            event_type = "APPROVE"
        elif "⚠️ Changes Requested" in review:
            event_type = "REQUEST_CHANGES"

        await gh.create_pr_review(owner, repo_name, pr_number, full_review, event_type)
        logger.info(f"Review posted on PR #{pr_number} — verdict: {event_type}")

    except Exception as e:
        logger.error(f"Failed to review PR #{pr_number}: {e}")


async def handle_issues(event: str, payload: dict):
    """Handle issues webhook events."""
    action = payload.get("action", "")
    issue = payload.get("issue", {})
    repo = payload.get("repository", {})

    if action != "opened":
        return

    owner = repo.get("owner", {}).get("login", "")
    repo_name = repo.get("name", "")
    issue_number = issue.get("number", 0)
    title = issue.get("title", "")
    body = issue.get("body", "") or ""

    logger.info(f"Triaging issue #{issue_number} in {owner}/{repo_name}")

    gh = GitHubClient()
    analyzer = WiddxAnalyzer()

    try:
        result = await analyzer.triage_issue(title, body)

        # Add labels
        labels = result.get("labels", [])
        if labels:
            await gh.add_labels(owner, repo_name, issue_number, labels)
            logger.info(f"Labels added: {labels}")

        # Post triage comment
        comment = (
            f"## 🤖 Automated Triage\n\n"
            f"**Severity:** {result.get('severity', 'N/A')}\n"
            f"**Summary:** {result.get('summary', 'N/A')}\n"
            f"**Suggested labels:** {', '.join(labels) if labels else 'none'}\n\n"
            f"---\n*🤖 Generated by WIDDX Nexus*"
        )
        await gh.create_issue_comment(owner, repo_name, issue_number, comment)

    except Exception as e:
        logger.error(f"Failed to triage issue #{issue_number}: {e}")


# ── FastAPI App ───────────────────────────────────────────────

def create_app():
    """Create the FastAPI application."""
    try:
        from fastapi import FastAPI, Request, Response
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError:
        logger.error("FastAPI required: pip install fastapi uvicorn")
        sys.exit(1)

    app = FastAPI(
        title="WIDDX Nexus — GitHub App",
        description="Automated PR review and issue triage powered by WIDDX AI",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "widdx-github-app", "version": "1.0.0"}

    @app.post("/webhook")
    async def webhook(request: Request):
        payload = await request.body()
        signature = request.headers.get("X-Hub-Signature-256", "")

        if not verify_webhook(payload, signature):
            return Response(status_code=401, content="Invalid signature")

        event_type = request.headers.get("X-GitHub-Event", "")
        data = json.loads(payload)

        if event_type == "pull_request":
            await handle_pull_request(event_type, data)
        elif event_type == "issues":
            await handle_issues(event_type, data)
        else:
            logger.debug(f"Ignored event: {event_type}")

        return {"status": "processed", "event": event_type}

    return app


# ── CLI Entry ─────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    app = create_app()
    port = int(os.environ.get("PORT", "8001"))
    logger.info(f"Starting WIDDX GitHub App on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)
