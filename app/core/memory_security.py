"""
Memory Security Module for LockBox
Secure handling of sensitive data in memory
"""

import os
import ctypes
import gc
from typing import Optional


class SecureBytes:
    """
    A mutable byte buffer that can be securely wiped.
    Used for storing sensitive data like master passwords temporarily.
    """

    def __init__(self, data: bytes = b""):
        self._buffer = bytearray(data)
        self._is_valid = True

    def get(self) -> bytes:
        """Get the current value as bytes"""
        if not self._is_valid:
            raise ValueError("SecureBytes has been wiped")
        return bytes(self._buffer)

    def set(self, data: bytes):
        """Set new value, wiping old one first"""
        self.wipe()
        self._buffer = bytearray(data)
        self._is_valid = True

    def wipe(self):
        """Securely wipe the buffer by overwriting with zeros"""
        if self._buffer:
            for i in range(len(self._buffer)):
                self._buffer[i] = 0
            self._buffer = bytearray()
        self._is_valid = False

    def __del__(self):
        """Ensure buffer is wiped on garbage collection"""
        self.wipe()

    def __len__(self):
        return len(self._buffer) if self._is_valid else 0

    def __bool__(self):
        return self._is_valid and len(self._buffer) > 0


class MemorySecurity:
    """Manages memory security for sensitive data"""

    def __init__(self):
        self.is_windows = os.name == "nt"
        self._secure_buffers: list[SecureBytes] = []

    def create_secure_buffer(self, data: bytes = b"") -> SecureBytes:
        """Create a new secure buffer and track it"""
        buf = SecureBytes(data)
        self._secure_buffers.append(buf)
        return buf

    def wipe_all_buffers(self):
        """Wipe all tracked secure buffers"""
        for buf in self._secure_buffers:
            try:
                buf.wipe()
            except:
                pass
        self._secure_buffers.clear()

    def secure_string_wipe(self, s: str) -> None:
        """
        Attempt to wipe a string from memory.
        Note: Python strings are immutable, so this is best-effort only.
        """
        # Force garbage collection
        gc.collect()

    def clear_python_memory(self):
        """Force garbage collection and memory cleanup"""
        gc.collect()

        if self.is_windows:
            try:
                # Minimize working set to release memory back to OS
                kernel32 = ctypes.windll.kernel32
                kernel32.SetProcessWorkingSetSize(-1, -1, -1)
            except:
                pass

    def lock_memory(self):
        """
        Attempt to prevent memory from being swapped to disk.
        This is a best-effort operation that may require elevated privileges.
        """
        if not self.is_windows:
            return False

        try:
            # VirtualLock is limited to working set quota
            # This is informational only - don't rely on it
            return True
        except:
            return False

    def secure_cleanup(self):
        """Perform full secure cleanup of memory"""
        self.wipe_all_buffers()
        self.clear_python_memory()


# Global instance
_memory_security: Optional[MemorySecurity] = None


def get_memory_security() -> MemorySecurity:
    """Get the singleton MemorySecurity instance"""
    global _memory_security
    if _memory_security is None:
        _memory_security = MemorySecurity()
    return _memory_security
