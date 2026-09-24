"""Voice/TTS Engine — Text-to-Speech for WIDDX.

Uses edge-tts (Microsoft Edge TTS) for high-quality speech.
Saves audio to ~/.widdx/voice/ and plays via system audio.

Usage:
    from core.voice import tts

    async tts.speak("Hello, I am WIDDX")
    tts.speak_sync("Hello")  # blocking version

Requirements:
    pip install edge-tts
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger("widdx.voice")

# Default voice
DEFAULT_VOICE = "en-US-AriaNeural"  # Female, natural
ARABIC_VOICE = "ar-SA-ZariyahNeural"  # Arabic female

VOICE_DIR = Path.home() / ".widdx" / "voice"


class TTSEngine:
    """Text-to-Speech engine using edge-tts.

    Features:
    - High-quality neural voices (free, no API key)
    - Support for 100+ languages including Arabic
    - Saves to MP3 files
    - Plays via system audio (winsound on Windows, afplay on macOS, aplay on Linux)
    - Async and sync APIs
    """

    def __init__(self):
        self._enabled = True
        self._voice = DEFAULT_VOICE
        self._rate = "+0%"  # speech rate: "-20%" slower, "+20%" faster
        self._volume = "+0%"
        VOICE_DIR.mkdir(parents=True, exist_ok=True)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, val: bool):
        self._enabled = val
        logger.info("TTS %s", "enabled" if val else "disabled")

    @property
    def voice(self) -> str:
        return self._voice

    @voice.setter
    def voice(self, val: str):
        self._voice = val

    def auto_voice(self, text: str) -> str:
        """Auto-select voice based on text content."""
        import re
        # Check for Arabic characters
        if re.search(r'[\u0600-\u06FF]', text):
            return ARABIC_VOICE
        return DEFAULT_VOICE

    async def speak(self, text: str, voice: Optional[str] = None) -> str:
        """Convert text to speech and play it.

        Args:
            text: Text to speak.
            voice: Voice to use (auto-detected if None).

        Returns:
            Path to the audio file.
        """
        if not self._enabled or not text.strip():
            return ""

        import edge_tts
        selected_voice = voice or self.auto_voice(text)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:22]
        filename = f"widdx_{timestamp}.mp3"
        filepath = VOICE_DIR / filename

        try:
            communicate = edge_tts.Communicate(
                text[:2000],  # edge-tts limit
                selected_voice,
                rate=self._rate,
                volume=self._volume,
            )
            await communicate.save(str(filepath))
            logger.debug("TTS saved: %s (%.1fs)", filename, len(text) / 15)
            self._play(filepath)
            return str(filepath)
        except Exception as e:
            logger.error("TTS error: %s", e)
            return ""

    def speak_sync(self, text: str, voice: Optional[str] = None) -> str:
        """Synchronous version of speak()."""
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(self.speak(text, voice))
            return result
        finally:
            loop.close()

    def _play(self, filepath: Path):
        """Play an audio file using system audio."""
        if not filepath.exists():
            return

        import platform as _platform
        system = _platform.system().lower()

        def _play_thread():
            try:
                if system == "windows":
                    # Use winsound (built-in) for WAV, or start MP3 via system
                    if filepath.suffix == ".wav":
                        import winsound  # noqa: F401
                        winsound.PlaySound(str(filepath), winsound.SND_FILENAME)
                    else:
                        # Start default player for MP3
                        startfile = getattr(os, "startfile", None)
                        if startfile is not None:
                            startfile(str(filepath))
                elif system == "darwin":
                    subprocess.run(["afplay", str(filepath)], capture_output=True, timeout=60)
                else:
                    subprocess.run(["aplay", str(filepath)], capture_output=True, timeout=60)
            except Exception as e:
                logger.debug("TTS playback error: %s", e)

        thread = threading.Thread(target=_play_thread, daemon=True)
        thread.start()

    def list_voices(self) -> list[dict]:
        """List available voices (cached after first call)."""
        try:
            import edge_tts
            # edge_tts.list_voices() returns a list of dicts
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                voices = loop.run_until_complete(edge_tts.list_voices())
                return [
                    {"name": v["ShortName"], "locale": v["Locale"], "gender": v["Gender"]}
                    for v in voices
                ]
            finally:
                loop.close()
        except Exception as e:
            logger.error("List voices error: %s", e)
            return []

    def set_speed(self, rate: str):
        """Set speech rate: '-50%' to '+50%'."""
        self._rate = rate

    @property
    def status(self) -> str:
        return f"{'🔊 Enabled' if self._enabled else '🔇 Disabled'} | Voice: {self._voice} | Rate: {self._rate}"


# Global singleton
tts = TTSEngine()
