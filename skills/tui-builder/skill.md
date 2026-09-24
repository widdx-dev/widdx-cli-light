---
name: tui-builder
description: Build professional Textual TUI interfaces for WIDDX — complete, fast, error-free
icon: 🖥️
---

# TUI Builder — Textual Framework Skill for WIDDX

## 🚨 Golden Rules (من Textual الرسمية)

### 1. `@work` — فقط على DOMNode (Screen/App/Widget)
```python
class MainScreen(Screen):
    # ✅ CORRECT — Screen هو DOMNode
    @work(exclusive=True, thread=True)
    def run_chat(self, text: str) -> None:
        worker = get_current_worker()
        result = self.backend.chat(text)
        if not worker.is_cancelled:
            self.call_from_thread(self._on_result, result)

# ❌ WRONG — ChatEngine مش DOMNode
class ChatEngine:
    @work(thread=True)  # assert isinstance(self, DOMNode) FAILS!
    def _run_chat(self):
        pass
```

### 2. worker — Async vs Thread
```python
# ✅ Async worker (يعمل على event loop — يقدر يحدث UI مباشرة)
@work(exclusive=True)
async def fetch_weather(self, city: str) -> None:
    weather = await self.api.get_weather(city)
    self.query_one("#weather").update(weather)  # ✅ مباشر

# ✅ Thread worker (يعمل في thread منفصل — ما يقدر يحدث UI)
@work(exclusive=True, thread=True)
def fetch_weather(self, city: str) -> None:
    weather = self.api.get_weather_sync(city)
    # ⚠️ لازم call_from_thread
    self.call_from_thread(self.query_one("#weather").update, weather)
    # ✅ post_message آمن من thread
    self.app.post_message(WeatherMsg(weather))
```

### 3. exclusive=True — يمنع race conditions
```python
# ✅ exclusive=True: لو المستخدم ضغط Enter مرتين سريعاً
#   أول worker يكمل، الثاني يُلغى
@work(exclusive=True, thread=True)
def run_chat(self, text: str) -> None:
    ...
```

### 4. Imports — مسار مطلق
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from core import tools
```

### 5. RichLog — الأداء
```python
# ✅ 500 سطر كافي
RichLog(max_lines=500, highlight=True, markup=True, wrap=True)
```

### 6. reactive — تحديث UI تلقائي
```python
from textual.reactive import reactive

class TimeDisplay(Digits):
    time = reactive(0.0)
    
    def watch_time(self, time: float) -> None:
        """يتصل تلقائياً عند تغيير self.time"""
        self.update(f"{time:.2f}")
```

### 7. set_interval — للمهام الدورية
```python
def on_mount(self) -> None:
    self.update_timer = self.set_interval(1/60, self._tick, pause=True)

def _tick(self) -> None:
    self.time = self.total + (monotonic() - self.start_time)
```

---

## Core Architecture

```
App (WIDDXTUI)
 └── MODES dict → Screen classes
       ├── "main" → MainScreen (chat + all views)
       │     ├── TUIState (state.py)        ← central state
       │     ├── ChatEngine (chat_engine.py) ← logic (NO @work)
       │     └── CommandHandler (commands.py) ← commands
       │
       └── ModalScreens (push_screen):
             ├── HelpScreen
             ├── SettingsScreen
             ├── SessionCRUDScreen
             └── UbuntuGrid
```

### File structure

```
tui/
├── app.py           ← App + MainScreen (integration only)
├── state.py         ← TUIState (state, startup, save)
├── chat_engine.py   ← ChatEngine (streaming, tools, agents)
├── commands.py      ← CommandHandler (/, ! commands)
├── screens/         ← push_screen modals
├── widgets/         ← custom widgets
└── app.tcss         ← stylesheet
```

---

## MainScreen Pattern — الصحيح (من Textual Docs)

```python
class MainScreen(Screen):
    """شاشة المحادثة الرئيسية — تطابق نمط Textual الرسمي."""
    
    BINDINGS = [
        Binding("ctrl+q", "app.quit", "Quit", show=False, priority=True),
        Binding("escape", "cancel_or_focus", "Cancel/Focus", show=False),
        Binding("ctrl+l", "clear_chat", "Clear", show=False),
        Binding("ctrl+p", "show_help", "Help", show=False),
    ]

    def __init__(self):
        super().__init__()
        self.state = TUIState()
        self.chat = ChatEngine(self)
        self.cmds = CommandHandler(self)

    def compose(self) -> ComposeResult:
        """أنشئ واجهة المستخدم — yield widgets."""
        yield Header(show_clock=True)
        yield RichLog(id="chat-log", max_lines=500, highlight=True, markup=True, wrap=True)
        yield Input(placeholder="Type a message...", id="input")
        yield Footer()

    def on_mount(self) -> None:
        """نُداء عند بدء التطبيق."""
        for log in self.state.startup():
            self._log_message("system", log)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """معالجة الإدخال — event handler نمط Textual."""
        text = event.value.strip()
        if not text:
            return
        event.input.value = ""
        self._log_message("user", text)
        self.run_chat(text)

    @work(exclusive=True, thread=True)
    def run_chat(self, text: str) -> None:
        """Worker: تنفيذ المحادثة في thread منفصل.
        @work(thread=True) يحافظ على استجابة الواجهة."""
        worker = get_current_worker()
        try:
            self.chat.start(text, self.state)
            if not worker.is_cancelled:
                self.call_from_thread(self._on_chat_done)
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(self._log_message, "system", f"❌ {e}")

    def _on_chat_done(self) -> None:
        """يُستدعى من call_from_thread بعد انتهاء worker."""
        self.query_one("#input", Input).focus()
```

---

## State Management (بدون self._state dict)

```python
class TUIState:
    """Central state — replaces inline dicts."""
    def __init__(self):
        self.cfg = load_config()
        self.provider = create_provider(self.cfg)
        self.mcp_mgr = get_mcp_manager()
        self.mcp_mgr.load_from_config(self.cfg)
        self.messages: list[dict] = []
        self.tool_defs: list[dict] = []

    def startup(self) -> list[str]:
        """Run on app start. Returns log messages."""
        logs = []
        # Session recovery, project scanner, memory, auto-setup etc.
        return logs

    def save_session(self):
        project_state.save_session(self.messages, {"model": self.model, ...})

    def clear_session(self):
        self.messages.clear()
```

---

## ChatEngine (بدون @work)

```python
class ChatEngine:
    """Pure logic — called from MainScreen's @work thread."""

    def __init__(self, app_ref: MainScreen):
        self.app = app_ref  # for post_message

    def start(self, text: str, state: TUIState):
        """Run UIL pipeline + execution."""
        # 1. Build message list with context
        msgs = list(state.messages)
        # 2. UIL routing
        # 3. Run executor (stream / agent / expert)
        # 4. Post ResultMsg or StreamEndMsg
```

---

## Commands

```python
class CommandHandler:
    """Handles /commands and !skills."""

    def __init__(self, app_ref: MainScreen):
        self.app = app_ref

    async def handle(self, text: str, state: TUIState) -> bool:
        """Returns True if it was a command."""
        if text.startswith("/"):
            await self._cmd(text, state)
            return True
        elif text.startswith("!"):
            self._skill(text[1:], state)
            return True
        return False
```

---

## Performance Checklist

| المشكلة | الحل |
|---|---|
| UI يتجمد عند الإرسال | `@work(thread=True)` على MainScreen |
| RichLog بطيء | `max_lines=500` (ليس 5000) |
| كل stream chunk يسبب lag | StreamChunkMsg يكتب سطراً واحداً |
| import يتحطم من مجلد آخر | `sys.path.insert(0, ...)` + مسار مطلق |
| `assert isinstance(self, DOMNode)` | `@work` فقط على Screen/App |
| `time.sleep` يوقف كل شيء | `set_interval()` أو Worker |

---

## Testing

```python
# Test that all screens compose without errors
def test_screens():
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        assert app.is_running

# Test chat engine imports
def test_chat_engine():
    from tui.chat_engine import ChatEngine
    from tui.state import TUIState
    # Just verify they import without error
    assert True
```
