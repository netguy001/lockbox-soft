"""
Window Security Module for LockBox
Handles blur on focus loss, screenshot protection, and visual security
"""

import os
import ctypes
from typing import Optional, Callable, List
from datetime import datetime, timedelta


class WindowSecurity:
    """Manages window-level security features"""

    def __init__(self):
        self.is_windows = os.name == "nt"
        self.is_blurred = False
        self.blur_start_time: Optional[datetime] = None
        self.blur_callback: Optional[Callable] = None
        self.unblur_callback: Optional[Callable] = None
        self.lock_callback: Optional[Callable] = None
        self.blur_to_lock_timer = None

        # Settings (can be overridden)
        self.blur_on_focus_loss = True
        self.blur_on_minimize = True
        self.blur_to_lock_seconds: Optional[int] = None  # None = never

        # Screen capture processes to watch for
        self.capture_processes = [
            "obs",
            "obs64",
            "streamlabs",
            "xsplit",
            "bandicam",
            "fraps",
            "camtasia",
            "snagit",
            "sharex",
            "screenclip",
            "snippingtool",
            "screenpresso",
            "loom",
            "screencast",
            "recordit",
            "nvidia share",
            "geforce experience",
        ]

    def set_callbacks(
        self,
        blur_callback: Callable,
        unblur_callback: Callable,
        lock_callback: Callable,
    ):
        """Set callback functions for blur/unblur/lock events"""
        self.blur_callback = blur_callback
        self.unblur_callback = unblur_callback
        self.lock_callback = lock_callback

    def configure(
        self,
        blur_on_focus_loss: bool = True,
        blur_on_minimize: bool = True,
        blur_to_lock_seconds: Optional[int] = None,
    ):
        """Configure window security settings"""
        self.blur_on_focus_loss = blur_on_focus_loss
        self.blur_on_minimize = blur_on_minimize
        self.blur_to_lock_seconds = blur_to_lock_seconds

    # ─────────────────────────────────────────────────────────────────────
    # BLUR CONTROL
    # ─────────────────────────────────────────────────────────────────────

    def trigger_blur(self, reason: str = "focus_loss"):
        """Trigger blur state"""
        if self.is_blurred:
            return

        self.is_blurred = True
        self.blur_start_time = datetime.now()

        if self.blur_callback:
            self.blur_callback(reason)

    def trigger_unblur(self):
        """Remove blur state"""
        if not self.is_blurred:
            return

        self.is_blurred = False
        self.blur_start_time = None

        if self.unblur_callback:
            self.unblur_callback()

    def check_blur_timeout(self) -> bool:
        """Check if blur has exceeded timeout and should lock"""
        if not self.is_blurred or not self.blur_start_time:
            return False

        if self.blur_to_lock_seconds is None:
            return False

        elapsed = (datetime.now() - self.blur_start_time).total_seconds()
        if elapsed >= self.blur_to_lock_seconds:
            if self.lock_callback:
                self.lock_callback()
            return True

        return False

    def get_blur_time_remaining(self) -> Optional[int]:
        """Get seconds remaining before blur escalates to lock"""
        if not self.is_blurred or not self.blur_start_time:
            return None

        if self.blur_to_lock_seconds is None:
            return None

        elapsed = (datetime.now() - self.blur_start_time).total_seconds()
        remaining = self.blur_to_lock_seconds - elapsed
        return max(0, int(remaining))

    # ─────────────────────────────────────────────────────────────────────
    # WINDOW EVENTS
    # ─────────────────────────────────────────────────────────────────────

    def on_focus_out(self, event=None):
        """Handle window losing focus"""
        if self.blur_on_focus_loss:
            self.trigger_blur("focus_loss")

    def on_focus_in(self, event=None):
        """Handle window regaining focus"""
        self.trigger_unblur()

    def on_minimize(self, event=None):
        """Handle window minimization"""
        if self.blur_on_minimize:
            self.trigger_blur("minimize")

    def on_restore(self, event=None):
        """Handle window restoration from minimize"""
        self.trigger_unblur()

    # ─────────────────────────────────────────────────────────────────────
    # SCREENSHOT PROTECTION
    # ─────────────────────────────────────────────────────────────────────

    def enable_screenshot_protection(self, window_handle):
        """
        Enable Windows SetWindowDisplayAffinity to exclude from capture.
        This prevents the window from being captured by PrintScreen,
        screen recording software, and remote desktop.
        """
        if not self.is_windows:
            return False

        try:
            # WDA_EXCLUDEFROMCAPTURE = 0x00000011 (Windows 10 2004+)
            # WDA_MONITOR = 0x00000001 (older, shows black)
            WDA_EXCLUDEFROMCAPTURE = 0x00000011

            user32 = ctypes.windll.user32
            result = user32.SetWindowDisplayAffinity(
                window_handle, WDA_EXCLUDEFROMCAPTURE
            )

            if result == 0:
                # Fallback to WDA_MONITOR for older Windows
                WDA_MONITOR = 0x00000001
                result = user32.SetWindowDisplayAffinity(window_handle, WDA_MONITOR)

            return result != 0
        except Exception as e:
            print(f"Screenshot protection failed: {e}")
            return False

    def disable_screenshot_protection(self, window_handle):
        """Disable screenshot protection"""
        if not self.is_windows:
            return False

        try:
            WDA_NONE = 0x00000000
            user32 = ctypes.windll.user32
            result = user32.SetWindowDisplayAffinity(window_handle, WDA_NONE)
            return result != 0
        except Exception:
            return False

    def detect_screen_capture_software(self) -> List[str]:
        """Detect running screen capture/recording software"""
        detected = []

        try:
            import psutil

            for proc in psutil.process_iter(["name"]):
                try:
                    proc_name = proc.info["name"].lower() if proc.info["name"] else ""
                    for capture_name in self.capture_processes:
                        if capture_name in proc_name:
                            detected.append(proc.info["name"])
                            break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except ImportError:
            pass
        except Exception:
            pass

        return detected

    # ─────────────────────────────────────────────────────────────────────
    # STATUS
    # ─────────────────────────────────────────────────────────────────────

    def get_status(self) -> str:
        """Get current security status: unlocked, blurred, or locked"""
        if self.is_blurred:
            return "blurred"
        return "unlocked"


# Global instance
_window_security: Optional[WindowSecurity] = None


def get_window_security() -> WindowSecurity:
    """Get the singleton WindowSecurity instance"""
    global _window_security
    if _window_security is None:
        _window_security = WindowSecurity()
    return _window_security
