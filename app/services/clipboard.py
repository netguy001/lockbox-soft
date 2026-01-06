import pyperclip


def set_clipboard_text(text: str):
    """Set clipboard text."""
    pyperclip.copy(text)


def clear_clipboard():
    """Clear clipboard contents."""
    pyperclip.copy("")
