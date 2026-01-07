import os
from pathlib import Path

APP_NAME = "LockBox"

DATA_DIR = Path(os.getenv("APPDATA")) / APP_NAME
VAULT_FILE = DATA_DIR / "lockbox.vault"
CONFIG_FILE = DATA_DIR / "config.json"
BACKUP_DIR = DATA_DIR / "backups"
SECURITY_FILE = DATA_DIR / "security.json"
RECOVERY_FILE = DATA_DIR / ".recovery_hash"
INTEGRITY_FILE = DATA_DIR / ".integrity"


# Vault structure
EMPTY_VAULT = {
    "passwords": [],
    "api_keys": [],
    "notes": [],
    "ssh_keys": [],
    "files": [],
    "encrypted_folders": [],
    "password_history": [],
    "totp_codes": [],
}

# Security settings
AUTO_LOCK_MINUTES = 10
CLIPBOARD_CLEAR_SECONDS = 15
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_HISTORY = 10
PASSWORD_STRENGTH_THRESHOLD = 60

# NEW SECURITY SETTINGS
MAX_LOGIN_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 30
SESSION_TIMEOUT_MINUTES = 30
MAX_FAILED_SESSION_UNLOCKS = 3

# File protection settings
ENABLE_FILE_PROTECTION = False  # Disabled - causes permission issues on some systems
ENABLE_FILE_HIDING = True
ENABLE_INTEGRITY_CHECKS = True
SECURE_DELETE_PASSES = 3

# Process security settings
ENABLE_ANTI_DEBUG = True
ENABLE_PROCESS_MONITORING = True
ENABLE_MEMORY_PROTECTION = True
WARN_SCREEN_CAPTURE = True

# Session security
ENABLE_AUTO_LOCK = True
ENABLE_CLIPBOARD_CLEAR = True
ENABLE_MEMORY_CLEANUP = True

# Window security settings (NEW)
ENABLE_BLUR_ON_FOCUS_LOSS = True
ENABLE_BLUR_ON_MINIMIZE = True
BLUR_TO_LOCK_SECONDS = None  # None = never, or 15, 30, 60
ENABLE_SCREENSHOT_PROTECTION = True
CLEAR_CLIPBOARD_ON_BLUR = True

# Auto-lock timeout options (in seconds)
AUTO_LOCK_OPTIONS = [
    (0, "Off"),
    (30, "30 seconds"),
    (60, "1 minute"),
    (300, "5 minutes"),
    (600, "10 minutes"),
    (1800, "30 minutes"),
]

# Blur to lock timeout options (in seconds)
BLUR_TO_LOCK_OPTIONS = [
    (None, "Never"),
    (15, "15 seconds"),
    (30, "30 seconds"),
    (60, "1 minute"),
]

# Theme definitions
DARK_THEME = {
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

LIGHT_THEME = {
    "bg_primary": "#f8f9fa",
    "bg_secondary": "#ffffff",
    "bg_card": "#ffffff",
    "bg_hover": "#e9ecef",
    "border": "#dee2e6",
    "accent": "#3b82f6",
    "accent_hover": "#2563eb",
    "accent_soft": "#dbeafe",
    "text_primary": "#212529",
    "text_secondary": "#6c757d",
    "text_muted": "#adb5bd",
    "success": "#22c55e",
    "danger": "#ef4444",
    "warning": "#f59e0b",
}

# UI Colors (default to dark theme)
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
