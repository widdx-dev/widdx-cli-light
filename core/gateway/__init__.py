"""WIDDX Gateway — connect to messaging platforms.

Architecture:
  GatewayCore
  ├── TelegramAdapter  ← python-telegram-bot
  ├── DiscordAdapter   ← discord.py
  └── TUI  (مدمج أصلاً)

التدفق:
  المستخدم يرسل رسالة على تيليجرام
  → TelegramAdapter.receive()
  → GatewayCore.process(text, platform="telegram", user_id=...)
  → WIDDX engine (chat + tools + agents)
  → GatewayCore.send(response, platform, user_id)
  → TelegramAdapter.send() → المستخدم يرى الرد
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Optional

logger = logging.getLogger("widdx.gateway")


class Platform(Enum):
    TELEGRAM = "telegram"
    DISCORD = "discord"
    TUI = "tui"
    CLI = "cli"
    API = "api"


@dataclass
class Message:
    """A message from any platform, normalized."""
    text: str
    platform: Platform
    user_id: str
    chat_id: str
    username: str = ""
    message_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_log(self) -> str:
        return f"[{self.platform.value}] {self.username}({self.user_id}): {self.text[:60]}"


@dataclass
class Reply:
    """A reply to send back to a platform."""
    text: str
    platform: Platform
    chat_id: str
    user_id: str
    parse_mode: str = "markdown"


class GatewayCore:
    """Central message router between platforms and the WIDDX engine.

    Usage:
        gateway = GatewayCore()

        # Register a message handler (WIDDX engine)
        def handle(msg: Message) -> str:
            return provider.chat(msg.text, ...)

        gateway.set_handler(handle)

        # Start platform adapters
        gateway.start_platform("telegram", token="...")
        gateway.start_platform("discord", token="...")
    """

    def __init__(self):
        self._handler: Optional[Callable[[Message], str]] = None
        self._adapters: dict[str, object] = {}
        self._history: list[Message] = []
        self._lock = threading.Lock()

    def set_handler(self, handler: Callable[[Message], str]):
        """Set the function that processes incoming messages.

        The handler receives a Message and returns a response string.
        """
        self._handler = handler

    def process_message(self, msg: Message) -> Optional[Reply]:
        """Process an incoming message through the handler."""
        if self._handler is None:
            logger.warning("No handler set for gateway")
            return None

        with self._lock:
            self._history.append(msg)

        logger.info("Gateway received: %s", msg.to_log())
        try:
            response = self._handler(msg)
            return Reply(
                text=response,
                platform=msg.platform,
                chat_id=msg.chat_id,
                user_id=msg.user_id,
            )
        except Exception as e:
            logger.error("Gateway handler error: %s", e, exc_info=True)
            return Reply(
                text=f"⚠️ Error: {e}",
                platform=msg.platform,
                chat_id=msg.chat_id,
                user_id=msg.user_id,
            )

    def send_reply(self, reply: Reply):
        """Send a reply through the appropriate platform adapter."""
        adapter = self._adapters.get(reply.platform.value)
        if adapter is None:
            logger.warning("No adapter for platform: %s", reply.platform.value)
            return
        try:
            adapter.send(reply)  # type: ignore[attr-defined]
        except Exception as e:
            logger.error("Gateway send error: %s", e)

    def register_adapter(self, platform: str, adapter: object):
        """Register a platform adapter."""
        self._adapters[platform] = adapter
        logger.info("Gateway adapter registered: %s", platform)

    def start_platform(self, platform: str, **kwargs):
        """Start a platform adapter by name with config.

        Supported: "telegram", "discord"
        """
        if platform == "telegram":
            self._start_telegram(**kwargs)
        elif platform == "discord":
            self._start_discord(**kwargs)
        else:
            logger.warning("Unknown platform: %s", platform)

    def stop_platform(self, platform: str):
        """Stop a running platform adapter."""
        self._adapters.pop(platform, None)
        logger.info("Platform %s stopped", platform)

    def _start_telegram(self, token: str = "", **kwargs):
        """Start Telegram adapter in a background thread."""
        from core.gateway.telegram import TelegramAdapter
        adapter = TelegramAdapter(token=token, gateway=self)
        thread = threading.Thread(target=adapter.run, daemon=True, name="gateway-telegram")
        thread.start()
        self.register_adapter("telegram", adapter)
        logger.info("Telegram adapter started")

    def _start_discord(self, token: str = "", **kwargs):
        """Start Discord adapter in a background thread."""
        from core.gateway.discord import DiscordAdapter
        adapter = DiscordAdapter(token=token, gateway=self)
        thread = threading.Thread(target=adapter.run, daemon=True, name="gateway-discord")
        thread.start()
        self.register_adapter("discord", adapter)
        logger.info("Discord adapter started")

    def get_history(self, limit: int = 20) -> list[Message]:
        """Return recent message history."""
        with self._lock:
            return self._history[-limit:]

    @property
    def active_platforms(self) -> list[str]:
        return list(self._adapters.keys())

    @property
    def is_running(self) -> bool:
        return len(self._adapters) > 0
