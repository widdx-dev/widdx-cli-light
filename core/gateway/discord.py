"""Discord adapter for WIDDX Gateway.

Connects to Discord via Bot Gateway.
Requires: discord.py, DISCORD_BOT_TOKEN env var.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import discord
from discord.ext import commands

from core.gateway import GatewayCore, Message, Platform, Reply

if TYPE_CHECKING:
    pass

logger = logging.getLogger("widdx.gateway.discord")


class DiscordAdapter:
    """Discord bot adapter using discord.py."""

    def __init__(self, token: str = "", gateway: GatewayCore | None = None):
        self._token = token or os.environ.get("DISCORD_BOT_TOKEN", "")
        self._gateway = gateway
        self._bot: commands.Bot | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def run(self):
        """Start the Discord bot (runs in background thread)."""
        if not self._token:
            logger.warning("DISCORD_BOT_TOKEN not set — Discord adapter disabled")
            return

        intents = discord.Intents.default()
        intents.message_content = True

        self._bot = commands.Bot(command_prefix="!", intents=intents)

        @self._bot.event
        async def on_ready():
            logger.info("Discord bot logged in as %s", self._bot.user)  # type: ignore[union-attr]

        @self._bot.event
        async def on_message(message):
            if message.author == self._bot.user:  # type: ignore[union-attr]
                return
            if message.content.startswith("!"):
                await self._bot.process_commands(message)  # type: ignore[union-attr]
                return

            msg = Message(
                text=message.content,
                platform=Platform.DISCORD,
                user_id=str(message.author.id),
                chat_id=str(message.channel.id),
                username=message.author.name,
                message_id=str(message.id),
            )

            if self._gateway:
                reply = self._gateway.process_message(msg)
                if reply:
                    await message.channel.send(reply.text[:2000])

        @self._bot.command(name="help")
        async def _help(ctx):
            await ctx.send(
                "🤖 WIDDX Nexus — Discord Bot\n\n"
                "Send any message and I'll help you.\n"
                "Commands:\n"
                "!help — Show this\n"
                "!status — System check"
            )

        @self._bot.command(name="status")
        async def _status(ctx):
            await ctx.send("✅ WIDDX Nexus is running!")

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._bot.start(self._token))
        except Exception as e:
            logger.error("Discord adapter error: %s", e)

    def send(self, reply: Reply):
        """Send a reply to a Discord channel."""
        if self._bot is None or self._loop is None:
            return
        async def _send():
            channel = self._bot.get_channel(int(reply.chat_id))  # type: ignore[union-attr]
            if channel:
                try:
                    await channel.send(reply.text[:2000])
                except Exception as e:
                    logger.error("Discord send error: %s", e)
        asyncio.run_coroutine_threadsafe(_send(), self._loop)

    @property
    def is_connected(self) -> bool:
        return self._bot is not None and self._bot.is_ready()
