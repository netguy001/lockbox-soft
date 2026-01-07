"""
Security Manager - Central security orchestrator for LockBox
Integrates file protection, process security, and session management
"""

import os
import threading
from pathlib import Path
from typing import Optional, Callable, Dict, List
from datetime import datetime

from app.core.file_protection import FileProtection
from app.core.process_security import ProcessSecurity
from app.core.session_manager import SessionManager
from app.core.security import SecurityManager as LoginSecurityManager
from app.constants import (
    DATA_DIR,
    VAULT_FILE,
    BACKUP_DIR,
    ENABLE_FILE_PROTECTION,
    ENABLE_FILE_HIDING,
    ENABLE_INTEGRITY_CHECKS,
    ENABLE_ANTI_DEBUG,
    ENABLE_PROCESS_MONITORING,
    ENABLE_MEMORY_PROTECTION,
    ENABLE_AUTO_LOCK,
    AUTO_LOCK_MINUTES,
    WARN_SCREEN_CAPTURE,
    ENABLE_CLIPBOARD_CLEAR,
    ENABLE_MEMORY_CLEANUP,
    CLIPBOARD_CLEAR_SECONDS,
)


class SecurityOrchestrator:
    """Central security manager that coordinates all security modules"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        """Singleton pattern to ensure only one security manager exists"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.data_dir = DATA_DIR
        self.vault_file = VAULT_FILE

        # Initialize security modules
        self.file_protection = FileProtection(DATA_DIR)
        self.process_security = ProcessSecurity()
        self.session_manager = SessionManager(AUTO_LOCK_MINUTES)
        self.login_security = LoginSecurityManager(DATA_DIR / "security.json")

        # Runtime metadata-enabled flags (can be disabled if writes fail)
        self.integrity_enabled = ENABLE_INTEGRITY_CHECKS
        self.recovery_enabled = True
        self.security_metadata_enabled = True
        # File lock handles
        self.vault_lock_handle = None
        self.security_warnings: List[str] = []

        # Auto-lock timer
        self.auto_lock_job = None
        self.lock_callback: Optional[Callable] = None

        # Activity tracking
        self.last_activity = None

        self._initialized = True

    # ─────────────────────────────────────────────────────────────────────
    # STARTUP SECURITY
    # ─────────────────────────────────────────────────────────────────────

    def initialize_security(self) -> Dict:
        """Initialize all security measures on app startup"""
        results = {
            "file_protection": False,
            "file_hiding": False,
            "memory_protection": False,
            "warnings": [],
        }

        # Ensure data directory exists
        self.data_dir.mkdir(parents=True, exist_ok=True)
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)

        # Apply NTFS permissions (restrict to current user + admin)
        if ENABLE_FILE_PROTECTION:
            results["file_protection"] = self.file_protection.protect_directory()
            if results["file_protection"]:
                # Also protect backups directory
                backup_protection = FileProtection(BACKUP_DIR)
                backup_protection.protect_directory()

        # Hide sensitive files
        if ENABLE_FILE_HIDING:
            self.file_protection.hide_sensitive_files()
            results["file_hiding"] = True

        # Enable memory protection
        if ENABLE_MEMORY_PROTECTION:
            results["memory_protection"] = (
                self.process_security.enable_memory_protection()
            )

        # Check for security threats
        threats = self.check_security_threats()
        results["warnings"] = threats
        # Include any metadata manager warnings and update runtime flags
        try:
            from app.core.metadata import get_metadata_manager

            md = get_metadata_manager()
            for w in md.get_warnings():
                if w not in results["warnings"]:
                    results["warnings"].append(w)

            # Reflect disabled features
            if not md.is_enabled("integrity"):
                self.integrity_enabled = False
            if not md.is_enabled("recovery"):
                self.recovery_enabled = False
            if not md.is_enabled("security"):
                self.security_metadata_enabled = False
        except Exception:
            pass
        return results

    def check_security_threats(self) -> List[str]:
        """Check for active security threats"""
        warnings = []

        # Anti-debug check
        if ENABLE_ANTI_DEBUG and self.process_security.is_debugger_attached():
            warnings.append("⚠️ Debugger detected - security risk")

        # Check for suspicious processes
        if ENABLE_PROCESS_MONITORING:
            suspicious = self.process_security.detect_suspicious_processes()
            if suspicious:
                names = [p["name"] for p in suspicious[:3]]
                warnings.append(f"⚠️ Suspicious processes: {', '.join(names)}")

        # Check for screen capture
        if WARN_SCREEN_CAPTURE and self.process_security.check_screen_capture():
            warnings.append("⚠️ Screen recording software detected")

        self.security_warnings = warnings
        return warnings

    # ─────────────────────────────────────────────────────────────────────
    # FILE INTEGRITY
    # ─────────────────────────────────────────────────────────────────────

    def check_file_integrity(self) -> Dict:
        """Check if vault files have been tampered with"""
        if not self.integrity_enabled:
            return {"tampered": False, "message": "Integrity checks disabled"}

        return self.file_protection.check_integrity(self.vault_file)

    def update_integrity_hashes(self):
        """Update integrity hashes after vault save"""
        if self.integrity_enabled:
            self.file_protection.save_integrity_data(self.vault_file)

    # ─────────────────────────────────────────────────────────────────────
    # SESSION MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────

    def start_session(self, lock_callback: Optional[Callable] = None):
        """Start a new authenticated session"""
        self.lock_callback = lock_callback
        self.session_manager.start_session()
        self.session_manager.set_lock_callback(lock_callback)
        self.last_activity = datetime.now()

        # Lock the vault file to prevent external modification
        if ENABLE_FILE_PROTECTION and self.vault_file.exists():
            self.vault_lock_handle = self.file_protection.lock_file_while_open(
                self.vault_file
            )

    def end_session(self):
        """End current session securely"""
        self.session_manager.end_session()

        # Unlock vault file
        if self.vault_lock_handle:
            self.file_protection.unlock_file(self.vault_lock_handle)
            self.vault_lock_handle = None

        # Clear sensitive data from memory
        if ENABLE_MEMORY_CLEANUP:
            self.process_security.secure_memory_cleanup()

        # Clear clipboard
        if ENABLE_CLIPBOARD_CLEAR:
            self.process_security.clear_clipboard()

    def update_activity(self):
        """Update activity timestamp to prevent auto-lock"""
        self.session_manager.update_activity()
        self.last_activity = datetime.now()

    def should_auto_lock(self) -> bool:
        """Check if vault should auto-lock"""
        if not ENABLE_AUTO_LOCK:
            return False
        return self.session_manager.should_auto_lock()

    def get_session_info(self) -> Dict:
        """Get current session information"""
        return self.session_manager.get_session_info()

    # ─────────────────────────────────────────────────────────────────────
    # CLIPBOARD SECURITY
    # ─────────────────────────────────────────────────────────────────────

    def schedule_clipboard_clear(self, app, delay_seconds: int = None):
        """Schedule clipboard to be cleared after delay"""
        if not ENABLE_CLIPBOARD_CLEAR:
            return None

        if delay_seconds is None:
            delay_seconds = CLIPBOARD_CLEAR_SECONDS

        def clear():
            self.process_security.clear_clipboard()

        return app.after(delay_seconds * 1000, clear)

    def clear_clipboard_now(self):
        """Clear clipboard immediately"""
        self.process_security.clear_clipboard()

    # ─────────────────────────────────────────────────────────────────────
    # VAULT SAVE HOOK
    # ─────────────────────────────────────────────────────────────────────

    def on_vault_saved(self):
        """Called after vault is saved - update integrity hashes"""
        self.update_integrity_hashes()

        # Re-hide files if needed
        if ENABLE_FILE_HIDING:
            self.file_protection.hide_sensitive_files()

    # ─────────────────────────────────────────────────────────────────────
    # SECURITY REPORTS
    # ─────────────────────────────────────────────────────────────────────

    def get_comprehensive_report(self) -> Dict:
        """Get comprehensive security status report"""
        process_report = self.process_security.get_security_report()
        integrity = self.check_file_integrity()
        session = self.get_session_info()

        return {
            "timestamp": datetime.now().isoformat(),
            "environment": {
                "debugger": process_report.get("debugger_detected", False),
                "suspicious_processes": process_report.get("suspicious_processes", []),
                "screen_capture": process_report.get("screen_capture_active", False),
                "vm_detected": process_report.get("vm_environment", False),
            },
            "file_integrity": integrity,
            "session": session,
            "protection_status": {
                "file_protection": ENABLE_FILE_PROTECTION,
                "file_hiding": ENABLE_FILE_HIDING,
                "integrity_checks": ENABLE_INTEGRITY_CHECKS,
                "anti_debug": ENABLE_ANTI_DEBUG,
                "process_monitoring": ENABLE_PROCESS_MONITORING,
                "memory_protection": ENABLE_MEMORY_PROTECTION,
                "auto_lock": ENABLE_AUTO_LOCK,
            },
            "warnings": self.security_warnings,
        }

    def is_safe_environment(self) -> tuple:
        """Check if environment is safe for sensitive operations"""
        return self.process_security.is_safe_to_proceed()

    # ─────────────────────────────────────────────────────────────────────
    # SECURE DELETE
    # ─────────────────────────────────────────────────────────────────────

    def secure_delete_file(self, file_path: Path):
        """Securely delete a file"""
        self.file_protection.secure_delete(file_path)


# Convenience function to get singleton instance
def get_security() -> SecurityOrchestrator:
    """Get the singleton security orchestrator instance"""
    return SecurityOrchestrator()
