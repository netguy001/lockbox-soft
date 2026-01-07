"""
LockBox Core Module
Exports all core functionality
"""

from app.core.vault import Vault
from app.core.crypto import derive_key, encrypt, decrypt, check_password_strength
from app.core.recovery import RecoverySystem
from app.core.security import SecurityManager
from app.core.storage import save_vault, load_vault, create_backup, restore_from_backup
from app.core.file_protection import FileProtection
from app.core.process_security import ProcessSecurity
from app.core.session_manager import SessionManager
from app.core.security_manager import SecurityOrchestrator, get_security

__all__ = [
    "Vault",
    "derive_key",
    "encrypt",
    "decrypt",
    "check_password_strength",
    "RecoverySystem",
    "SecurityManager",
    "save_vault",
    "load_vault",
    "create_backup",
    "restore_from_backup",
    "FileProtection",
    "ProcessSecurity",
    "SessionManager",
    "SecurityOrchestrator",
    "get_security",
]
