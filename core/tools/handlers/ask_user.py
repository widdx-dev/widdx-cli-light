"""Ask User tool — allows the AI to ask clarifying questions to the user."""

import logging
import os

logger = logging.getLogger("widdx.tools.ask_user")

_ASK_USER_ENABLED = True
_pending_question: str | None = None
_pending_answer: str | None = None
_answer_callback = None
_question_consumed: bool = False  # tracks if current question has been sent to client


def set_answer_callback(cb):
    """Set a callback for TUI/Web modes to provide answers."""
    global _answer_callback
    _answer_callback = cb


def provide_answer(answer: str):
    """Provide an answer to a pending question (used by TUI/Web)."""
    global _pending_answer
    _pending_answer = answer


def get_pending_question() -> str | None:
    """Get the current pending question (used by TUI/Web)."""
    return _pending_question


def clear_pending():
    """Clear any pending question."""
    global _pending_question, _pending_answer, _question_consumed
    _pending_question = None
    _pending_answer = None
    _question_consumed = False


def mark_question_consumed():
    """Mark that the current question has been sent to the client (Web/TUI)."""
    global _question_consumed
    _question_consumed = True


def is_question_consumed() -> bool:
    """Check if the current question has already been consumed."""
    return _question_consumed


def _ask_user(question: str) -> str:
    """Ask the user a question and return their answer."""
    global _pending_question, _pending_answer, _question_consumed

    if not _ASK_USER_ENABLED:
        return "Interactive questions are disabled."

    _pending_question = question
    _question_consumed = False

    # Detect if we're in TUI mode (Textual)
    in_tui = os.environ.get("WIDDX_TUI", "") == "1"

    # Detect if we're in Web mode
    in_web = os.environ.get("WIDDX_WEB", "") == "1"

    if in_web or in_tui:
        if _answer_callback:
            _answer_callback(question)
        _pending_answer = None
        import time
        timeout = 300
        interval = 0.1
        waited = 0.0
        while _pending_answer is None and waited < timeout:
            time.sleep(interval)
            waited += interval
        if _pending_answer is not None:
            answer = _pending_answer
            clear_pending()
            return answer
        clear_pending()
        if in_web or in_tui:
            return "[No answer provided — timed out]"
        return "[Interactive questions not available in this mode. The AI should make reasonable assumptions and proceed.]"

    from rich.console import Console
    from rich.prompt import Prompt
    from rich.text import Text

    console = Console(highlight=False)
    console.print()
    console.print(Text(f"\n❓ {question}", style="bold #00c896"))
    console.print(Text("  (type your answer, or 'skip' to skip)", style="dim"))

    try:
        answer = Prompt.ask("", default="skip")
    except (EOFError, KeyboardInterrupt):
        answer = "skip"

    clear_pending()
    if answer.lower() == "skip":
        return "[User skipped the question]"
    return answer
