from pathlib import Path

# Application info
APP_NAME = "LockBox"
APP_VERSION = "2.1.0"

# Directory paths
DATA_DIR = Path(__file__).parent.parent / "data"
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
}

# Security settings
AUTO_LOCK_MINUTES = 15
CLIPBOARD_CLEAR_SECONDS = 30
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_HISTORY = 10
PASSWORD_STRENGTH_THRESHOLD = 60

# UI Colors (modern dark theme)
COLORS = {
    "bg_primary": "#1a1a1a",
    "bg_secondary": "#2d2d2d",
    "bg_card": "#242424",
    "accent": "#0d7377",
    "accent_hover": "#14a085",
    "text_primary": "#ffffff",
    "text_secondary": "#a0a0a0",
    "success": "#2ecc71",
    "danger": "#e74c3c",
    "warning": "#f39c12",
}

# Password generator defaults
PASSWORD_DEFAULTS = {
    "length": 16,
    "use_uppercase": True,
    "use_lowercase": True,
    "use_digits": True,
    "use_symbols": True,
}
