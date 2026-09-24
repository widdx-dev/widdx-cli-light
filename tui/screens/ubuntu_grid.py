"""Ubuntu-style Application Grid Launcher — شبكة أيقونات على غرار GNOME."""

import logging
logger = logging.getLogger("widdx.tui")

from textual.app import ComposeResult  # noqa: E402
from textual.binding import Binding  # noqa: E402
from textual.screen import Screen  # noqa: E402
from textual.widgets import Button, Select, Static  # noqa: E402
from textual.containers import Horizontal  # noqa: E402


class UbuntuGrid(Screen):
    """شبكة أيقونات على غرار Ubuntu/GNOME — تفتح عند النقر على زر الشبكة."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("ctrl+q", "app.quit", "Quit", show=False),
    ]

    def __init__(
        self,
        nav_buttons: list | None = None,
        act_buttons: list | None = None,
        help_buttons: list | None = None,
    ):
        logger.info("[UbuntuGrid] Initializing...")
        super().__init__()
        self._grid_ready = False
        self._nav_buttons = nav_buttons or []
        self._act_buttons = act_buttons or []
        self._help_buttons = help_buttons or []

    def compose(self) -> ComposeResult:
        logger.info("[UbuntuGrid] Compose called...")
        try:
            yield Static("[bold #6366f1]◈  W I D D X  C O R T E X  ◈[/]", id="grid-title")
            yield Static("[dim]Select an app to switch to[/dim]", id="grid-search-hint")

            # ── All buttons in a single grid ──
            with Horizontal(id="grid-all", classes="grid-row"):
                for _, icon, label, action, _ in self._nav_buttons:
                    yield Button(
                        f"{icon}\n\n{label}",
                        id=f"g{action}",
                        classes="grid-icon-btn",
                    )
                for _, icon, label, action, _ in self._act_buttons:
                    yield Button(
                        f"{icon}\n\n{label}",
                        id=f"g{action}",
                        classes="grid-icon-btn",
                    )
                for _, icon, label, action, _ in self._help_buttons:
                    yield Button(
                        f"{icon}\n\n{label}",
                        id=f"g{action}",
                        classes="grid-icon-btn",
                    )

            # ── Footer ──
            yield Static("[dim]Esc to close[/dim]", id="grid-footer")
            logger.info("[UbuntuGrid] Compose finished successfully")
        except Exception as e:
            logger.exception(f"[UbuntuGrid] Error in compose: {e}")

    def on_mount(self) -> None:
        """Initialize the grid."""
        logger.info("[UbuntuGrid] on_mount called...")
        try:
            self._grid_ready = True
            logger.info("[UbuntuGrid] on_mount finished successfully")
        except Exception as e:
            logger.exception(f"[UbuntuGrid] Error in on_mount: {e}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        logger.info(f"[UbuntuGrid] on_button_pressed, button id: {event.button.id}")
        try:
            bid = event.button.id or ""
            event.stop()
            if bid.startswith("g"):
                action = bid[1:]
                logger.info(f"[UbuntuGrid] Dismissing with action: {action.lower()}")
                self.dismiss(action.lower())
        except Exception as e:
            logger.exception(f"[UbuntuGrid] Error in on_button_pressed: {e}")

    def on_select_changed(self, event: Select.Changed) -> None:
        """Not used anymore since provider/branch are in MainScreen header."""
        event.stop()
