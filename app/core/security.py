"""Simple Security Module for LockBox

This module writes the small `security.json` file using an atomic
replace pattern. If the primary file is not writable (PermissionError)
we fall back to a per-user file name such as `security.<username>.json`
to avoid permanently locking the user out.
"""

import json
import os
import tempfile
import getpass
from pathlib import Path
from datetime import datetime, timedelta


class SecurityManager:
    """Prevents brute-force attacks on your vault"""

    def __init__(self, security_file_path):
        self._original_path = Path(security_file_path)
        self.security_file = Path(security_file_path)
        self.security_file.parent.mkdir(parents=True, exist_ok=True)
        self._used_fallback = False
        self.data = self._load()

    def _load(self):
        """Load security data, trying primary then fallback."""
        try_paths = [self.security_file]
        # include a per-user fallback if present
        username = getpass.getuser()
        fallback = self.security_file.with_name(f"security.{username}.json")
        if fallback != self.security_file:
            try_paths.append(fallback)

        for p in try_paths:
            try:
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    # if we loaded from fallback, mark it so future saves go there
                    if p != self._original_path:
                        self.security_file = p
                        self._used_fallback = True
                    return data
            except Exception:
                # ignore and try next path
                continue

        return {"failed_attempts": 0, "lockout_until": None}

    def _atomic_write(self, target_path: Path, data: dict) -> bool:
        """Write `data` to `target_path` atomically. Returns True on success."""
        try:
            dirpath = target_path.parent
            # create a temp file in the same directory to ensure os.replace is atomic
            fd, tmp_path = tempfile.mkstemp(dir=dirpath)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tf:
                    json.dump(data, tf)
                    tf.flush()
                    os.fsync(tf.fileno())
                # atomic replace
                os.replace(tmp_path, target_path)
                return True
            finally:
                # if something went wrong and tmp_path still exists, remove it
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
        except PermissionError:
            return False
        except Exception:
            return False

    def _save(self):
        """Save security data with atomic replace and per-user fallback.

        If both primary and fallback writes fail, we log and continue without
        raising to avoid permanently locking the user out.
        """
        # attempt primary path first
        primary = self._original_path
        if self._atomic_write(primary, self.data):
            # if we previously used a fallback, switch back
            if self._used_fallback and self.security_file != primary:
                self.security_file = primary
                self._used_fallback = False
            return

        # primary failed; attempt per-user fallback
        username = getpass.getuser()
        fallback = primary.with_name(f"security.{username}.json")
        if self._atomic_write(fallback, self.data):
            self.security_file = fallback
            self._used_fallback = True
            print(
                f"[LockBox] Primary security file unwritable; using fallback {fallback}"
            )
            return

        # both writes failed — log and continue to avoid self-lockout
        print(
            f"[LockBox] WARNING: Unable to persist security settings to {primary} or {fallback}."
        )

    def is_locked_out(self):
        """Check if locked out due to too many failed attempts"""
        if self.data.get("lockout_until"):
            try:
                lockout_time = datetime.fromisoformat(self.data["lockout_until"])
            except Exception:
                self.data["lockout_until"] = None
                self.data["failed_attempts"] = 0
                self._save()
                return False, 0

            if datetime.now() < lockout_time:
                minutes_left = int((lockout_time - datetime.now()).seconds / 60)
                return True, minutes_left
            self.data["lockout_until"] = None
            self.data["failed_attempts"] = 0
            self._save()

        return False, 0

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.data["failed_attempts"] = int(self.data.get("failed_attempts", 0)) + 1

        if self.data["failed_attempts"] >= 5:
            lockout_until = datetime.now() + timedelta(minutes=30)
            self.data["lockout_until"] = lockout_until.isoformat()

        self._save()

        return max(0, 5 - self.data["failed_attempts"])

    def record_successful_login(self):
        """Record successful login - reset failed attempts"""
        self.data["failed_attempts"] = 0
        self.data["lockout_until"] = None
        self._save()
