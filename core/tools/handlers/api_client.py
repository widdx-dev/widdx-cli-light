"""API/HTTP client — make HTTP requests to test APIs."""

import json
import logging
from typing import Any

logger = logging.getLogger("widdx.tools.api_client")


def _api_request(method: str = "GET", url: str = "",
                  headers: dict[str, str] | None = None,
                  body: str | None = None,
                  params: dict[str, str] | None = None,
                  timeout: int = 30,
                  follow_redirects: bool = True) -> str:
    """Make an HTTP request and return the response."""
    if not url:
        return "url is required"

    try:
        import httpx
    except ImportError:
        return "httpx not available"

    try:
        client_kwargs: dict[str, Any] = {
            "timeout": timeout,
            "follow_redirects": follow_redirects,
        }
        if headers:
            client_kwargs["headers"] = headers

        with httpx.Client(**client_kwargs) as client:
            request_kwargs: dict[str, Any] = {}
            if params:
                request_kwargs["params"] = params
            if body and method in ("POST", "PUT", "PATCH"):
                request_kwargs["content"] = body

            response = client.request(method, url, **request_kwargs)

    except httpx.TimeoutException:
        return f"⏱  Request timed out after {timeout}s"
    except httpx.ConnectError as e:
        return f"🔌 Connection error: {e}"
    except httpx.HTTPStatusError as e:
        response = e.response
    except Exception as e:
        return f"❌ Error: {e}"

    status = response.status_code
    reason = httpx.codes.get_reason_phrase(status) or "Unknown"
    headers_out = dict(response.headers)
    try:
        body_out = response.json()
        body_str = json.dumps(body_out, indent=2, ensure_ascii=False)
    except Exception:
        body_str = response.text

    total_size = len(response.content)
    truncated = ""
    if len(body_str) > 5000:
        body_str = body_str[:5000]
        truncated = "\n... (truncated, full response is {} bytes)".format(total_size)

    elapsed = response.elapsed.total_seconds()

    buf = [
        f"🌐 {method} {url}",
        f"📡 Status: {status} {reason}",
        f"⏱  Time: {elapsed:.2f}s",
        f"📦 Size: {total_size} bytes",
        "",
        "📋 Headers:",
    ]
    for k, v in list(headers_out.items())[:20]:
        buf.append(f"  {k}: {v}")
    if len(headers_out) > 20:
        buf.append(f"  ... and {len(headers_out) - 20} more")

    buf.extend(["", "📄 Body:"])
    if body_str:
        buf.append(body_str[:3000])
        if len(body_str) > 3000:
            buf.append("... (body truncated)")
    else:
        buf.append("  (empty body)")
    if truncated:
        buf.append(truncated)

    return "\n".join(buf)
