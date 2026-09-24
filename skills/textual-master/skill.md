---
name: textual-master
description: Official Textual framework rules for building WIDDX TUI — error-free, performant, maintainable
icon: 📐
---

# Textual Master — Official Rules for WIDDX TUI

You are an expert Textual framework engineer. Follow these rules EXACTLY when building, fixing, or reviewing TUI code. These rules come from the official Textual documentation at https://textual.textualize.io/ and from lessons learned building WIDDX.

---

## RULE 1: `@work` Decorator — ONLY on DOM Nodes

The `@work` decorator can ONLY be used on methods of **DOM nodes**: `App`, `Screen`, or `Widget` subclasses.

```python
# ✅ CORRECT
class MainScreen(Screen):
    @work(exclusive=True, thread=True)
    def run_chat(self, text: str) -> None:
        ...

# ❌ WRONG — will raise AssertionError
class ChatEngine:
    @work(thread=True)
    def run(self):
        ...
```

**Why:** worker are tied to the DOM node where they are created. When the screen is popped, its worker are automatically cleaned up.

---

## RULE 2: Thread worker vs Async worker

### Async worker (`@work` without `thread=True`)
Run on the asyncio event loop. Can update UI directly:

```python
@work(exclusive=True)
async def fetch_data(self, url: str) -> None:
    data = await httpx.AsyncClient().get(url)
    self.query_one("#result").update(data.json())  # ✅ safe
```

### Thread worker (`@work(thread=True)`)
Run in a separate thread. MUST NOT touch UI directly:

```python
@work(exclusive=True, thread=True)
def fetch_data(self, url: str) -> None:
    data = httpx.get(url).json()
    # ❌ Direct UI update will crash
    # self.query_one("#result").update(data)
    
    # ✅ Use call_from_thread
    self.call_from_thread(self.query_one("#result").update, str(data))
    
    # ✅ post_message is thread-safe
    self.app.post_message(DataReady(data))
```

### `exclusive=True` — always use for chat/API calls
Prevents race conditions. If the user triggers the action twice, the first worker is cancelled and the second runs.

---

## RULE 3: Thread-Safe UI Updates

From thread worker, ONLY these operations are safe:

| Safe | Not Safe |
|---|---|
| `self.app.post_message(msg)` | `self.query_one(...)` |
| `self.call_from_thread(fn, *args)` | Direct widget manipulation |
| | Reading widget state |

### Pattern for stream responses:

```python
class MainScreen(Screen):
    @work(exclusive=True, thread=True)
    def run_chat(self, text: str) -> None:
        worker = get_current_worker()
        try:
            # Thread-safe: post custom messages
            for chunk in self._stream_chunks(text):
                if worker.is_cancelled:
                    return
                self.app.post_message(ChunkMsg(chunk))
            
            if not worker.is_cancelled:
                self.call_from_thread(self._on_chat_done)
        except Exception as e:
            if not worker.is_cancelled:
                self.call_from_thread(self._log_error, str(e))

    def _log_error(self, msg: str) -> None:
        """Runs on main thread — safe to update UI."""
        self.query_one("#chat-log").write(f"[red]Error: {msg}[/]")
```

---

## RULE 4: `compose()` Pattern

```python
def compose(self) -> ComposeResult:
    """Yield widgets. Use containers for layout."""
    yield Header(show_clock=True)
    yield RichLog(id="chat-log", max_lines=500, highlight=True, markup=True, wrap=True)
    with Horizontal():
        yield Input(placeholder="Type...", id="input")
        yield Button("Send", id="send-btn")
    yield Footer()
```

**Container types from official docs:**
- `Horizontal` / `HorizontalGroup` — row layout
- `Vertical` / `VerticalScroll` — column layout with scrolling
- `Grid` — grid layout (use with `grid-size` CSS)
- Use `with Container():` as context manager for nesting

---

## RULE 5: RichLog Performance

```python
# ✅ CORRECT — fast, memory-efficient
RichLog(max_lines=500, highlight=True, markup=True, wrap=True, auto_scroll=True)

# ❌ WRONG — will cause UI lag
RichLog(max_lines=5000)
```

Keep `max_lines` at 500 or less. The WIDDX chat log ONLY needs to show recent messages.

---

## RULE 6: Event Handlers — naming convention

Textual event handlers follow `on_<widget>_<event_name>`:

```python
def on_input_submitted(self, event: Input.Submitted) -> None: ...
def on_button_pressed(self, event: Button.Pressed) -> None: ...
def on_mount(self) -> None: ...
def on_worker_state_changed(self, event: Worker.StateChanged) -> None: ...
```

Actions binding follow `action_<name>`:

```python
BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]
def action_toggle_dark(self) -> None:
    self.dark = not self.dark
```

---

## RULE 7: CSS Styling

```css
/* Widget class names target widgets by type */
MainScreen { background: $surface; }

/* #id targets specific widgets */
#chat-log { border: solid $primary; height: 1fr; }
#input { dock: bottom; height: 3; }

/* .class targets CSS classes */
.started { background: $success-muted; }
```

Use Textual's built-in color variables ($surface, $primary, $text, $boost, $success-muted, $warning, $error).

---

## RULE 8: Reactive Attributes

```python
from textual.reactive import reactive

class StatusIndicator(Static):
    status = reactive("idle")
    
    def watch_status(self, status: str) -> None:
        """Auto-called when self.status changes."""
        self.update(f"Status: {status}")
        self.set_class(status == "processing", "active")

# Usage: self.status = "done" → auto-updates UI
```

---

## RULE 9: App Structure for WIDDX

```
tui/
├── app.py           ← App + Screen (compose, bindings, worker)
├── state.py         ← TUIState (plain class, NO Textual deps)
├── chat_engine.py   ← ChatEngine (plain class, NO @work)
├── commands.py      ← CommandHandler (plain class)
├── screens/         ← PushScreen modals
├── widgets/         ← Custom widgets
└── app.tcss         ← Stylesheet
```

**Key rule:** Only `app.py` imports from `textual`. `state.py`, `chat_engine.py`, and `commands.py` are plain Python classes that receive an `app` reference for `post_message()`.

---

## RULE 10: Error Handling in worker

```python
@work(exclusive=True, thread=True)
def run_chat(self, text: str) -> None:
    worker = get_current_worker()
    try:
        self.engine.start(text, self.state)
    except Exception as e:
        if not worker.is_cancelled:
            self.call_from_thread(self._show_error, str(e))

def _show_error(self, msg: str) -> None:
    """Safe: runs on main thread."""
    self.query_one("#chat-log").write(f"\\n[red]Error: {msg}[/]")
```

**Always check `worker.is_cancelled`** before any UI update in a worker. Always wrap worker bodies in try/except.

---

## RULE 11: WIDDX-Specific — Import Safety

WIDDX must work when run from ANY directory. Always use:

```python
import sys
from pathlib import Path
ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
```

This must be at the TOP of `app.py`, before any WIDDX imports.

---

## RULE 12: NEVER Use These Patterns

| Don't | Instead |
|---|---|
| `@work(thread=True)` on non-DOMNode | Move method to Screen/App |
| `time.sleep()` in TUI code | `set_interval()` or worker |
| Direct UI update from thread worker | `call_from_thread()` or `post_message()` |
| `RichLog(max_lines=5000)` | `max_lines=500` |
| Obsolete `@work(exclusive=True)` without thread | Already correct in latest Textual |
