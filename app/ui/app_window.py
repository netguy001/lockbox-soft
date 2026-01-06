"""Application window entrypoint for LockBox UI."""

from app.ui.vault_view import LockBoxUI


class AppWindow(LockBoxUI):
    """Main application window.
    Inherits existing LockBoxUI behavior without modifying UI or logic.
    """


def start_app():
    """Create and run the application."""
    app = AppWindow()
    app.run()
