"""Web fetch tool with SSRF protection."""

import re as _re
import html as html_mod
from urllib.parse import urlparse

import httpx


def _web_fetch(url: str, output_format: str = "markdown") -> str:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return f"❌ Blocked: URL scheme '{parsed.scheme}' not allowed (SSRF protection)"
    if parsed.hostname in ("localhost", "127.0.0.1", "::1", "0.0.0.0",
                           "169.254.169.254", "metadata.google.internal",
                           "100.100.100.200", "192.168.0.0/16"):
        return f"❌ Blocked: {parsed.hostname} is a private/internal address (SSRF protection)"
    try:
        resp = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
        resp.raise_for_status()
        html = resp.text
        clean = _re.sub(r'<(script|style|noscript|svg)[^>]*>.*?</\1>', '',
                        html, flags=_re.IGNORECASE | _re.DOTALL)
        text = _re.sub(r"<[^>]+>", " ", clean)
        text = html_mod.unescape(text)
        text = _re.sub(r"[\t\n\r]+", " ", text)
        text = _re.sub(r"\s{2,}", " ", text).strip()
        if output_format == "text":
            return text[:5000]
        return f"Content from {url}:\n\n{text[:5000]}"
    except Exception as e:
        return f"Web fetch error: {e}"
