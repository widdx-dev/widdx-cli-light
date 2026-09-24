"""Detail screen modal — for viewing long text content (history messages, memories)."""

from textual.screen import ModalScreen
from textual.widgets import Static, Button, Markdown, Label
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding


class TextDetailScreen(ModalScreen):
    """General-purpose modal for viewing long text content with word-wrap."""

    BINDINGS = [
        Binding("escape", "dismiss", "Back"),
        Binding("q", "dismiss", "Dismiss"),
    ]

    def __init__(self, title: str, text: str):
        super().__init__()
        self.title_text = title
        self.body_text = text

    def compose(self):
        with Vertical(id="text-detail-dialog", classes="dialog-box"):
            yield Static(f"  📄  {self.title_text}", classes="dialog-title")
            yield Label(f"  {len(self.body_text)} chars", classes="dialog-subtitle")
            with ScrollableContainer(classes="dialog-body", id="text-detail-content"):
                yield Markdown(self.body_text)
            with Horizontal(classes="dialog-actions"):
                yield Button("  Close (Esc)  ", id="btn-close", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss()
