"""Compatibility shim that forwards to app.core.storage."""

from app.core.storage import create_backup, load_vault, restore_from_backup, save_vault

__all__ = ["create_backup", "load_vault", "restore_from_backup", "save_vault"]
