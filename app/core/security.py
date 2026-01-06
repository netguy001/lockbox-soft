"""
Simple Security Module for LockBox
"""

import json
from pathlib import Path
from datetime import datetime, timedelta


class SecurityManager:
    """Prevents brute-force attacks on your vault"""

    def __init__(self, security_file_path):
        self.security_file = Path(security_file_path)
        self.security_file.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        """Load security data"""
        if self.security_file.exists():
            with open(self.security_file, "r") as f:
                return json.load(f)
        return {"failed_attempts": 0, "lockout_until": None}

    def _save(self):
        """Save security data"""
        with open(self.security_file, "w") as f:
            json.dump(self.data, f)

    def is_locked_out(self):
        """Check if locked out due to too many failed attempts"""
        if self.data["lockout_until"]:
            lockout_time = datetime.fromisoformat(self.data["lockout_until"])
            if datetime.now() < lockout_time:
                minutes_left = int((lockout_time - datetime.now()).seconds / 60)
                return True, minutes_left
            self.data["lockout_until"] = None
            self.data["failed_attempts"] = 0
            self._save()

        return False, 0

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.data["failed_attempts"] += 1

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
