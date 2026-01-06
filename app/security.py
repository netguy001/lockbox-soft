"""Compatibility shim that forwards to app.core.security."""

from app.core.security import SecurityManager

__all__ = ["SecurityManager"]
