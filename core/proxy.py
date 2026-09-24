"""Proxy Manager — fetches free proxies, tests them, and rotates automatically.

Handles proxy rotation for the OpenCode Zen provider to avoid rate limits.
Manages a pool of working proxies, tests them periodically, and cycles
through them when requests fail with 429 or connection errors.
"""

import time
import threading
import logging
import httpx
from typing import Optional

logger = logging.getLogger("widdx.proxy")

# ---------------------------------------------------------------------------
# Proxy Manager -- fetches free proxies, tests them, and rotates automatically
# ---------------------------------------------------------------------------

PROXY_SOURCES = [
    "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&country=all&ssl=all&anonymity=all&simplified=true",
    "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
    "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
]

ZEN_BASE = "https://opencode.ai/zen/v1"

def _get_probe_model() -> str:
    """Get the probe model from config, with dynamic fallback."""
    try:
        import json
        from pathlib import Path
        cfg_path = Path(__file__).parent.parent / "config.json"
        if cfg_path.exists():
            cfg = json.loads(cfg_path.read_text())
            return cfg.get("provider", {}).get("model", "deepseek-v4-flash-free")
    except Exception:
        logger.debug("Exception suppressed (line 37)")
    return "deepseek-v4-flash-free"


_PROBE_BODY = {
    "model": None,  # filled at first use
    "messages": [{"role": "user", "content": "hi"}],
    "max_tokens": 5,
}
_PROBE_HEADERS = {
    "Authorization": "Bearer public",
    "Content-Type": "application/json",
}


def _build_probe_body() -> dict:
    """Build the probe body with the current config model."""
    body: dict[str, object] = dict(_PROBE_BODY)
    body["model"] = _get_probe_model()
    return body

class ProxyManager:
    """
    Manages a list of free HTTP proxies:
    - Fetches from multiple sources
    - Tests each proxy against opencode.ai directly
    - Maintains a sorted list of working proxies
    - Rotates automatically on 429 or failure
    - Refreshes the cache every hour in the background
    """

    CACHE_TTL = 3600          # seconds -- cache TTL
    PROBE_TIMEOUT = 8         # seconds -- proxy test timeout
    MAX_WORKING = 10          # max working proxies to keep
    MAX_TEST = 60             # max proxies to test per cycle

    def __init__(self):
        self._lock = threading.Lock()
        self._working: list[str] = []   # ["ip:port", ...]
        self._index: int = 0            # current rotation index
        self._last_refresh: float = 0
        self._refreshing: bool = False
        self._no_proxy_mode: bool = True   # default: direct connection (more reliable)

    # ------------------------------------------------------------------ #
    # Public Interface
    # ------------------------------------------------------------------ #

    def get_transport(self) -> Optional[httpx.HTTPTransport]:
        """
        Returns an HTTPTransport with the current proxy, or None if no proxy is available.
        Triggers automatic refresh if cache has expired.
        """
        self._maybe_refresh()
        with self._lock:
            if self._no_proxy_mode or not self._working:
                return None
            proxy = self._working[self._index % len(self._working)]
        return httpx.HTTPTransport(proxy=f"http://{proxy}")

    def rotate(self):
        """Rotate to the next proxy -- called on 429 or failure."""
        with self._lock:
            if not self._working:
                return
            self._index = (self._index + 1) % len(self._working)
            # Completed a full cycle -> request immediate refresh
            if self._index == 0:
                self._last_refresh = 0

    def current_proxy(self) -> Optional[str]:
        with self._lock:
            if self._no_proxy_mode or not self._working:
                return None
            return self._working[self._index % len(self._working)]

    def status(self) -> str:
        with self._lock:
            if self._no_proxy_mode:
                return "No proxy (direct connection)"
            if not self._working:
                return "Searching for proxy..."
            proxy = self._working[self._index % len(self._working)]
            return f"proxy: {proxy} ({len(self._working)} available)"

    # ------------------------------------------------------------------ #
    # Internal Logic
    # ------------------------------------------------------------------ #

    def _maybe_refresh(self):
        now = time.time()
        with self._lock:
            needs = (now - self._last_refresh) > self.CACHE_TTL
            already = self._refreshing
        if needs and not already:
            t = threading.Thread(target=self._refresh, daemon=True)
            t.start()

    def _refresh(self):
        with self._lock:
            self._refreshing = True
        try:
            raw_list = self._fetch_proxy_list()
            working = self._test_proxies(raw_list)
            with self._lock:
                if working:
                    self._working = working
                    self._index = 0
                    self._no_proxy_mode = False
                else:
                    # Found nothing -- work without proxy
                    self._working = []
                    self._no_proxy_mode = True
                self._last_refresh = time.time()
        finally:
            with self._lock:
                self._refreshing = False

    def _fetch_proxy_list(self) -> list[str]:
        """Fetches raw proxies from multiple sources."""
        proxies = set()
        for url in PROXY_SOURCES:
            try:
                r = httpx.get(url, timeout=10)
                if r.status_code == 200:
                    for line in r.text.strip().splitlines():
                        line = line.strip()
                        if line and ":" in line:
                            proxies.add(line)
            except Exception as e:
                logger.debug("proxy fetch failed for %s: %s", url, e)
                pass
        return list(proxies)

    def _test_proxies(self, proxy_list: list[str]) -> list[str]:
        """Tests proxies against opencode.ai and returns only working ones."""
        working: list[str] = []
        tested = 0
        for proxy_addr in proxy_list:
            if tested >= self.MAX_TEST:
                break
            if len(working) >= self.MAX_WORKING:
                break
            tested += 1
            proxy_url = f"http://{proxy_addr}"
            try:
                transport = httpx.HTTPTransport(proxy=proxy_url)
                with httpx.Client(transport=transport, timeout=self.PROBE_TIMEOUT) as client:
                    r = client.post(
                        f"{ZEN_BASE}/chat/completions",
                        headers=_PROBE_HEADERS,
                        json=_build_probe_body(),
                    )
                if r.status_code == 200:
                    working.append(proxy_addr)
                elif r.status_code == 429:
                    # Proxy works but this IP is also blocked -- skip
                    pass
            except Exception as e:
                logger.debug("proxy test failed for %s: %s", proxy_addr, e)
        return working

    def force_refresh(self):
        """Force refresh -- called from /proxy in the UI."""
        with self._lock:
            self._last_refresh = 0
        self._maybe_refresh()


# Singleton -- single instance for the entire app
proxy_manager = ProxyManager()
