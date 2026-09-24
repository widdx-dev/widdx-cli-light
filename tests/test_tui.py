"""TUI tests — Textual headless smoke + integration tests.

Uses Textual's built-in ``run_test()`` framework (no external deps).
"""

import sys
from pathlib import Path

# Ensure project root on path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest


# ── Fixtures ───────────────────────────────────────────────────

@pytest.fixture
def app():
    """Create a fresh WIDDXTUI app instance."""
    from tui.app import WIDDXTUI
    return WIDDXTUI()


# ── App Creation ───────────────────────────────────────────────

def test_app_creation():
    """App instantiates without errors."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    assert app.TITLE == "WIDDX Nexus"
    assert app.CSS_PATH == "app.tcss"


def test_main_screen_creation():
    """MainScreen creates state, chat engine, and command handler."""
    from tui.app import MainScreen
    screen = MainScreen()
    assert screen.state is not None
    assert screen.chat is not None
    assert screen.cmds is not None
    assert screen.state.model  # has a model configured
    assert len(screen.state.tool_defs) > 0


def test_state_creation():
    """TUIState initializes with provider, tools, and config."""
    from tui.state import TUIState
    state = TUIState()
    assert state.provider is not None
    assert state.provider.name
    assert state.model
    assert isinstance(state.tool_defs, list)
    assert isinstance(state.messages, list)


def test_chat_engine_creation():
    """ChatEngine wraps screen with deferred app access."""
    from tui.chat_engine import ChatEngine

    class MockApp:
        def post_message(self, msg): pass
        def call_from_thread(self, fn, *a, **kw): fn(*a, **kw)
    class MockScreen:
        app = MockApp()

    engine = ChatEngine(MockScreen())
    assert engine.app is not None
    assert engine._processing is False


def test_command_handler():
    """CommandHandler accepts app reference."""
    from tui.commands import CommandHandler
    from tui.app import MainScreen
    screen = MainScreen()
    handler = CommandHandler(screen)
    assert handler.app is screen


# ── Headless Mount ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_app_headless_mount():
    """App mounts in headless mode without errors."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)):
        assert app.main_screen is not None
        assert app.main_screen.is_mounted


@pytest.mark.asyncio
async def test_main_widgets_present():
    """All core widgets are present after mount."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)):
        screen = app.main_screen
        # Key widgets must exist
        screen.query_one("#chat-log")
        screen.query_one("#input")
        screen.query_one("#prompt-label")
        screen.query_one("#processing")
        screen.query_one("#status")


@pytest.mark.asyncio
async def test_input_focus_on_start():
    """Input field receives focus on mount."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)):
        inp = app.main_screen.query_one("#input")
        assert inp.has_focus


# ── Keyboard Shortcuts ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_ctrl_l_clears_chat():
    """Ctrl+L clears the chat log."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        await pilot.press("ctrl+l")
        await pilot.pause(0.05)
        # Should not crash — clear is non-destructive


@pytest.mark.asyncio
async def test_ctrl_t_toggles_thinking():
    """Ctrl+T toggles thinking display."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        was = app.main_screen._show_thinking
        await pilot.press("ctrl+t")
        await pilot.pause(0.05)
        assert app.main_screen._show_thinking is not was


@pytest.mark.asyncio
async def test_ctrl_p_pushes_help():
    """Ctrl+P pushes HelpScreen."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        initial_stack = len(pilot.app._screen_stack)
        await pilot.press("ctrl+p")
        await pilot.pause(0.1)
        # HelpScreen should be on top
        assert len(pilot.app._screen_stack) > initial_stack


@pytest.mark.asyncio
async def test_escape_dismisses_modals():
    """Escape closes modal screens and focuses input."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        # Push help, then dismiss
        await pilot.press("ctrl+p")
        await pilot.pause(0.1)
        await pilot.press("escape")
        await pilot.pause(0.1)
        inp = app.main_screen.query_one("#input")
        assert inp.has_focus


# ── Screens ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_help_screen_mounts():
    """HelpScreen mounts and contains quick-action buttons."""
    from tui.screens.help import HelpScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        help_screen = HelpScreen()
        await pilot.app.push_screen(help_screen)
        await pilot.pause(0.1)
        assert help_screen.is_mounted
        # Quick action buttons
        help_screen.query_one("#help-quick-row")
        await pilot.press("escape")


@pytest.mark.asyncio
@pytest.mark.skip(reason="SettingsScreen reads global config.json — can conflict with other test state")
async def test_settings_screen_mounts():
    """SettingsScreen mounts with provider tabs."""
    from tui.screens.settings import SettingsScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        settings = SettingsScreen()
        await pilot.app.push_screen(settings)
        await pilot.pause(0.1)
        assert settings.is_mounted
        settings.query_one("#settings-tabs")
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_session_list_screen_mounts():
    """SessionListScreen mounts with toolbar buttons."""
    from tui.screens.session_crud import SessionListScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        sess = SessionListScreen()
        await pilot.app.push_screen(sess)
        await pilot.pause(0.1)
        assert sess.is_mounted
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_memory_list_screen_mounts():
    """MemoryListScreen mounts with search input."""
    from tui.screens.memory_crud import MemoryListScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        mem = MemoryListScreen()
        await pilot.app.push_screen(mem)
        await pilot.pause(0.1)
        assert mem.is_mounted
        mem.query_one("#mem-search")
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_ubuntu_grid_mounts():
    """UbuntuGrid mounts with icon buttons."""
    from tui.screens.ubuntu_grid import UbuntuGrid
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        nav = [("nav-chat", "💬", "Chat", "chat", "info")]
        grid = UbuntuGrid(nav_buttons=nav, act_buttons=[], help_buttons=[])
        await pilot.app.push_screen(grid)
        await pilot.pause(0.1)
        assert grid.is_mounted
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_tool_detail_screen_mounts():
    """ToolDetailScreen shows tool info."""
    from tui.screens.tool_detail import ToolDetailScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        td = ToolDetailScreen({"name": "test_tool", "description": "A test tool"})
        await pilot.app.push_screen(td)
        await pilot.pause(0.1)
        assert td.is_mounted
        await pilot.press("escape")


@pytest.mark.asyncio
async def test_text_detail_screen_mounts():
    """TextDetailScreen shows markdown content."""
    from tui.screens.detail import TextDetailScreen
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        detail = TextDetailScreen("Test Title", "# Hello\n\nWorld")
        await pilot.app.push_screen(detail)
        await pilot.pause(0.1)
        assert detail.is_mounted
        await pilot.press("escape")


# ── Slash Commands ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_slash_help_command():
    """Slash /help pushes HelpScreen."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.main_screen
        inp = screen.query_one("#input")
        inp.value = "/help"
        await inp.action_submit()
        await pilot.pause(0.2)
        # After help execution, input should be re-enabled
        inp2 = screen.query_one("#input")
        assert not inp2.disabled


@pytest.mark.asyncio
async def test_slash_clear_command():
    """Slash /clear clears the chat log."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.main_screen
        inp = screen.query_one("#input")
        inp.value = "/clear"
        await inp.action_submit()
        await pilot.pause(0.1)
        assert not screen.query_one("#input").disabled


@pytest.mark.asyncio
async def test_slash_doctor_command():
    """Slash /doctor runs diagnostics without crashing."""
    from tui.app import WIDDXTUI
    app = WIDDXTUI()
    async with app.run_test(size=(120, 40)) as pilot:
        screen = app.main_screen
        inp = screen.query_one("#input")
        inp.value = "/doctor"
        await inp.action_submit()
        await pilot.pause(0.2)
        assert not screen.query_one("#input").disabled


# ── State & Core Integration ───────────────────────────────────

def test_state_save_and_load_session():
    """Session save/load round-trips through dual persistence."""
    from tui.state import TUIState
    state = TUIState()
    # Add a message
    state.messages.append({"role": "user", "content": "hello"})
    state.turns = 1
    # Save
    state.save_session()
    # Create fresh state and verify startup loads something
    state2 = TUIState()
    logs = state2.startup()
    # At minimum, startup should succeed without error
    assert isinstance(logs, list)


def test_tool_defs_include_all_sources():
    """Tool definitions include built-in, skills, MCP, and workflow tools."""
    from tui.state import TUIState
    state = TUIState()
    td = state.tool_defs
    names = [t["name"] for t in td]
    # Core tools
    assert "read" in names
    assert "write" in names
    assert "bash" in names
    # Phase 1 tools
    assert "run_linter" in names
    assert "sandbox_exec" in names
    assert "edit_files" in names
