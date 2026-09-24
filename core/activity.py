"""ActivityStore — central event bus for all WIDDX subsystems.

Every component (chat, background, delegation, cron, gateway, settings)
writes events here. The Web UI subscribes via callback for real-time push.

Architecture:
  Component calls:  ActivityStore.add(type="tool_call", ...)
  ──────────────────► ActivityStore (thread-safe, JSON file + memory)
                      ├── get_recent(limit=50)  ← REST API
                      └── subscribers           ← WebSocket push
"""

from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("widdx.activity")

_EVENT_TYPES = {
    "tool_call",      # Agent called a tool (Bash, Read, Edit, …)
    "agent_spawn",    # A sub-agent was created
    "agent_complete", # A sub-agent finished
    "message",        # User or assistant message
    "error",          # Error / exception
    "cron_trigger",   # Cron job fired
    "cron_create",    # New cron job created
    "settings_change",# Settings updated
    "bg_start",       # Background task started
    "bg_complete",    # Background task completed
    "gateway_msg",    # Message via Telegram/Discord/SMS
    "gateway_status", # Gateway channel status change
    "file_change",    # File created/modified/deleted
    "system",         # System event (startup, shutdown, …)
}


class ActivityEvent:
    """A single activity event with all metadata."""

    def __init__(self, event_type: str, detail: str, icon: str = "fa-circle",
                 agent: str = "system", status: str = "done", **kwargs):
        assert event_type in _EVENT_TYPES, f"Unknown event type: {event_type}"
        self.id = f"evt_{uuid.uuid4().hex[:12]}"
        self.type = event_type
        self.icon = icon
        self.agent = agent
        self.detail = detail
        self.status = status
        self.timestamp = time.time()
        self.metadata = kwargs

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "icon": self.icon,
            "agent": self.agent,
            "detail": self.detail,
            "status": self.status,
            "timestamp": self.timestamp,
            "elapsed": "—",
            **self.metadata,
        }


# ── Icon map — event type → Font Awesome icon ────────────────

_TYPE_ICON = {
    "tool_call": "fa-wrench",
    "agent_spawn": "fa-robot",
    "agent_complete": "fa-check-circle",
    "message": "fa-comment",
    "error": "fa-triangle-exclamation",
    "cron_trigger": "fa-clock",
    "cron_create": "fa-calendar-plus",
    "settings_change": "fa-sliders",
    "bg_start": "fa-play",
    "bg_complete": "fa-check",
    "gateway_msg": "fa-tower-broadcast",
    "gateway_status": "fa-plug",
    "file_change": "fa-file-pen",
    "system": "fa-star",
}


# ═══════════════════════════════════════════════════════════════
# ActivityStore
# ═══════════════════════════════════════════════════════════════

class ActivityStore:
    """Thread-safe central event store with subscriber callbacks.

    Usage:
        store = ActivityStore()
        store.add("tool_call", detail="Bash: git status", agent="main")
        recent = store.get_recent(limit=10)
    """

    def __init__(self, max_events: int = 500, persist_path: Optional[Path] = None):
        self._max = max_events
        self._events: list[ActivityEvent] = []
        self._lock = threading.Lock()
        self._subscribers: list[Callable[[dict], None]] = []
        self._path = persist_path or Path.cwd() / ".widdx" / "activity.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    # ── Subscribe / unsubscribe ─────────────────────────────

    def subscribe(self, callback: Callable[[dict], None]) -> Callable:
        """Register a callback that receives every new event as dict.

        Returns an unsubscribe function.
        """
        self._subscribers.append(callback)
        logger.debug("Activity subscriber added (total %d)", len(self._subscribers))

        def unsubscribe():
            if callback in self._subscribers:
                self._subscribers.remove(callback)

        return unsubscribe

    # ── Add event ───────────────────────────────────────────

    def add(self, event_type: str, detail: str, *, icon: Optional[str] = None,
            agent: str = "system", status: str = "done", **kwargs) -> ActivityEvent:
        """Create an event, store it, push to subscribers, persist.

        Returns the created ActivityEvent.
        """
        icon = icon or _TYPE_ICON.get(event_type, "fa-circle")
        event = ActivityEvent(event_type, detail, icon=icon, agent=agent,
                               status=status, **kwargs)
        with self._lock:
            self._events.append(event)
            if len(self._events) > self._max:
                self._events = self._events[-self._max:]
            snapshot = event.to_dict()
            subscribers = list(self._subscribers)

        # Persist asynchronously
        self._persist(event)

        # Push to all subscribers
        for cb in subscribers:
            try:
                cb(snapshot)
            except Exception as e:
                logger.warning("Activity subscriber error: %s", e)

        logger.debug("Activity: [%s] %s — %s", event_type, agent, detail[:60])
        return event

    # ── Bulk add (for loading historical data) ──────────────

    def add_batch(self, events: list[ActivityEvent]):
        """Add multiple events at once (used when loading history)."""
        with self._lock:
            self._events.extend(events)
            if len(self._events) > self._max:
                self._events = self._events[-self._max:]

    # ── Query ──────────────────────────────────────────────

    def get_recent(self, limit: int = 50, event_type: Optional[str] = None) -> list[dict]:
        """Return recent events, optionally filtered by type."""
        with self._lock:
            events = list(self._events)
        events.reverse()
        if event_type:
            events = [e for e in events if e.type == event_type]
        return [e.to_dict() for e in events[:limit]]

    def get_by_type(self, event_type: str, limit: int = 20) -> list[dict]:
        """Return recent events of a specific type."""
        return self.get_recent(limit=limit, event_type=event_type)

    def count(self) -> int:
        """Total events in memory."""
        with self._lock:
            return len(self._events)

    # ── Subscriber helpers ─────────────────────────────────

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    # ── Persistence ────────────────────────────────────────

    def _persist(self, event: ActivityEvent):
        """Append event to JSON file (thread-safe write)."""
        try:
            data = event.to_dict()
            # Read existing, append, write back (simple but safe)
            existing = []
            if self._path.exists():
                try:
                    existing = json.loads(self._path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    existing = []
            existing.append(data)
            # Keep only the most recent max_events*2 in file
            if len(existing) > self._max * 2:
                existing = existing[-self._max:]
            self._path.write_text(
                json.dumps(existing, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning("Activity persist error: %s", e)

    def _load(self):
        """Load historical events from JSON file."""
        try:
            if self._path.exists():
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                for item in raw[-self._max:]:
                    evt = ActivityEvent(
                        event_type=item.get("type", "system"),
                        detail=item.get("detail", ""),
                        icon=item.get("icon", "fa-circle"),
                        agent=item.get("agent", "system"),
                        status=item.get("status", "done"),
                    )
                    evt.id = item.get("id", evt.id)
                    evt.timestamp = item.get("timestamp", evt.timestamp)
                    self._events.append(evt)
                logger.info("Activity: loaded %d historical events", len(self._events))
        except Exception as e:
            logger.debug("Activity load error (first run?): %s", e)


# ── Global singleton ──────────────────────────────────────────

_activity_store: Optional[ActivityStore] = None
_lock = threading.Lock()


def get_store() -> ActivityStore:
    """Return the global ActivityStore singleton."""
    global _activity_store
    if _activity_store is None:
        with _lock:
            if _activity_store is None:
                _activity_store = ActivityStore()
    return _activity_store


def add(event_type: str, detail: str, **kwargs) -> ActivityEvent:
    """Shortcut: add an event to the global store.

    Usage:
        from core.activity import add
        add("tool_call", detail="Bash: npm install", agent="main")
    """
    return get_store().add(event_type, detail, **kwargs)
