"""
Session Manager for LockBox
Handles auto-lock, idle detection, and session security
"""

import time
from datetime import datetime, timedelta
from typing import Optional, Callable


class SessionManager:
    """Manages vault session lifecycle and security"""

    def __init__(self, auto_lock_minutes: int = 5):
        self.auto_lock_minutes = auto_lock_minutes
        self.last_activity = None
        self.session_start = None
        self.is_active = False
        self.lock_callback: Optional[Callable] = None
        self.failed_unlock_attempts = 0
        self.max_failed_attempts = 3

    def start_session(self):
        """Start a new session"""
        self.session_start = datetime.now()
        self.last_activity = datetime.now()
        self.is_active = True
        self.failed_unlock_attempts = 0

    def end_session(self):
        """End current session"""
        self.is_active = False
        self.session_start = None
        self.last_activity = None

    def update_activity(self):
        """Update last activity timestamp"""
        if self.is_active:
            self.last_activity = datetime.now()

    def should_auto_lock(self) -> bool:
        """Check if vault should auto-lock due to inactivity"""
        if not self.is_active or not self.last_activity:
            return False

        idle_time = datetime.now() - self.last_activity
        return idle_time.total_seconds() > (self.auto_lock_minutes * 60)

    def get_idle_time(self) -> int:
        """Get idle time in seconds"""
        if not self.last_activity:
            return 0
        return int((datetime.now() - self.last_activity).total_seconds())

    def get_session_duration(self) -> int:
        """Get total session duration in seconds"""
        if not self.session_start:
            return 0
        return int((datetime.now() - self.session_start).total_seconds())

    def set_lock_callback(self, callback: Callable):
        """Set callback function to call when auto-lock triggers"""
        self.lock_callback = callback

    def check_and_lock(self) -> bool:
        """Check if should lock and execute lock callback"""
        if self.should_auto_lock():
            if self.lock_callback:
                self.lock_callback()
            self.end_session()
            return True
        return False

    def set_auto_lock_time(self, minutes: int):
        """Update auto-lock timeout"""
        if minutes < 1:
            minutes = 1
        if minutes > 120:
            minutes = 120
        self.auto_lock_minutes = minutes

    def get_time_until_lock(self) -> int:
        """Get seconds remaining until auto-lock"""
        if not self.is_active or not self.last_activity:
            return 0

        elapsed = (datetime.now() - self.last_activity).total_seconds()
        timeout = self.auto_lock_minutes * 60
        remaining = timeout - elapsed

        return max(0, int(remaining))

    def record_failed_unlock(self) -> bool:
        """Record failed unlock attempt, returns True if should lock"""
        self.failed_unlock_attempts += 1
        return self.failed_unlock_attempts >= self.max_failed_attempts

    def reset_failed_attempts(self):
        """Reset failed unlock counter"""
        self.failed_unlock_attempts = 0

    def get_session_info(self) -> dict:
        """Get current session information"""
        return {
            "is_active": self.is_active,
            "session_duration": self.get_session_duration(),
            "idle_time": self.get_idle_time(),
            "time_until_lock": self.get_time_until_lock(),
            "auto_lock_enabled": self.auto_lock_minutes > 0,
            "auto_lock_minutes": self.auto_lock_minutes,
        }

    def extend_session(self):
        """Manually extend session (reset idle timer)"""
        self.update_activity()

    def force_lock(self):
        """Force immediate lock"""
        if self.lock_callback:
            self.lock_callback()
        self.end_session()
