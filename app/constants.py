import os
from pathlib import Path

APP_NAME = "LockBox"

DATA_DIR = Path(os.getenv("APPDATA")) / APP_NAME
VAULT_FILE = DATA_DIR / "lockbox.vault"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"


# Vault structure
EMPTY_VAULT = {
    "passwords": [],
    "api_keys": [],
    "notes": [],
    "ssh_keys": [],
    "files": [],
    "encrypted_folders": [],
    "password_history": [],
    "totp_codes": [],  # ADD THIS LINE
}

# Security settings
AUTO_LOCK_MINUTES = 10
CLIPBOARD_CLEAR_SECONDS = 15
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_HISTORY = 10
PASSWORD_STRENGTH_THRESHOLD = 60

# UI Colors (professional dark theme)
COLORS = {
    "bg_primary": "#0f0f0f",
    "bg_secondary": "#1a1a1a",
    "bg_card": "#1f1f1f",
    "bg_hover": "#2a2a2a",
    "border": "#333333",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_soft": "#1e3a5f",
    "text_primary": "#f5f5f5",
    "text_secondary": "#888888",
    "text_muted": "#555555",
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
}

# Password generator defaults
PASSWORD_DEFAULTS = {
    "length": 16,
    "use_uppercase": True,
    "use_lowercase": True,
    "use_digits": True,
    "use_symbols": True,
}
