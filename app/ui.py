"""Compatibility wrapper for LockBox UI.

This module preserves legacy imports while delegating to the new
structured UI entrypoint under app.ui.app_window.
"""

from app.ui.app_window import AppWindow, start_app


def start():
    """Legacy entrypoint; forwards to start_app."""
    start_app()


__all__ = ["AppWindow", "start_app", "start"]
