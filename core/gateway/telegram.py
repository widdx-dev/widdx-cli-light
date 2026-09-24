"""Telegram adapter for WIDDX Gateway.

Connects to Telegram via Bot API (polling).
Requires: python-telegram-bot, TELEGRAM_BOT_TOKEN env var.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from core.gateway import GatewayCore, Message, Platform, Reply

if TYPE_CHECKING:
    pass

logger = logging.getLogger("widdx.gateway.telegram")


class TelegramAdapter:
    """Telegram bot adapter using python-telegram-bot."""

    def __init__(self, token: str = "", gateway: GatewayCore | None = None):
        self._token = token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self._gateway = gateway
        self._app: Application | None = None

    def run(self):
        """Start polling (runs in background thread)."""
        if not self._token:
            logger.warning("TELEGRAM_BOT_TOKEN not set — Telegram adapter disabled")
            return

        async def _start():
            self._app = Application.builder().token(self._token).build()
            self._app.add_handler(CommandHandler("start", self._cmd_start))
            self._app.add_handler(CommandHandler("help", self._cmd_help))
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
            logger.info("Telegram bot started")
            await self._app.run_polling(allowed_updates=Update.ALL_TYPES)

        # python-telegram-bot needs an async event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(_start())
        except Exception as e:
            logger.error("Telegram adapter error: %s", e)

    def send(self, reply: Reply):
        """Send a reply to a Telegram chat."""
        if self._app is None:
            return
        async def _send():
            try:
                if self._app is None:
                    return
                bot = self._app.bot
                if bot is None:
                    return
                await bot.send_message(
                    chat_id=reply.chat_id,
                    text=reply.text[:4000],
                    parse_mode="Markdown" if reply.parse_mode == "markdown" else None,
                )
            except Exception as e:
                logger.error("Telegram send error: %s", e)
        asyncio.run_coroutine_threadsafe(_send(), self._app.loop if hasattr(self._app, 'loop') else asyncio.get_event_loop())

    async def _cmd_start(self, update: Update, context):
        """Handle /start command."""
        user = update.effective_user
        await update.message.reply_text(
            f"👋 Welcome, {user.first_name}!\n\n"
            "I am WIDDX Nexus — your AI assistant.\n"
            "Send me any message and I'll help you.\n\n"
            "Commands:\n"
            "/help — Show this help\n"
            "/status — System status"
        )

    async def _cmd_help(self, update: Update, context):
        """Handle /help command."""
        await update.message.reply_text(
            "🤖 WIDDX Nexus — Telegram Bot\n\n"
            "Simply send a message and I'll process it.\n"
            "Available tools:\n"
            "• Browse websites\n"
            "• Run commands (sandboxed)\n"
            "• Search files\n"
            "• And more...\n\n"
            "Commands:\n"
            "/status — System health check"
        )

    async def _handle_message(self, update: Update, context):
        """Handle incoming text messages."""
        if not update.message or not update.message.text:
            return

        user = update.effective_user
        msg = Message(
            text=update.message.text,
            platform=Platform.TELEGRAM,
            user_id=str(user.id),
            chat_id=str(update.effective_chat.id),
            username=user.username or user.first_name or "unknown",
            message_id=str(update.message.message_id),
        )

        if self._gateway:
            reply = self._gateway.process_message(msg)
            if reply:
                self.send(reply)

    @property
    def is_connected(self) -> bool:
        return self._app is not None
