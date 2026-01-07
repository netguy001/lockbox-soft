"""Metadata failure manager

Tracks best-effort metadata write state for integrity, recovery and security
features. On persistent write failures the corresponding feature is disabled,
a one-time warning is recorded, and further write attempts are skipped.
"""

from typing import Dict, List


class MetadataManager:
    def __init__(self):
        # feature -> enabled (True means feature active)
        self._enabled = {
            "integrity": True,
            "recovery": True,
            "security": True,
        }
        self._warnings: List[str] = []
        self._warned = set()

    def is_enabled(self, feature: str) -> bool:
        return bool(self._enabled.get(feature, True))

    def disable(self, feature: str, message: str = ""):
        if not self._enabled.get(feature, True):
            return
        self._enabled[feature] = False
        if feature not in self._warned:
            warn_msg = (
                message or f"Metadata feature '{feature}' disabled due to write failure"
            )
            self._warnings.append(warn_msg)
            # one-time printed warning for visibility in logs
            try:
                print(f"[LockBox] WARNING: {warn_msg}")
            except Exception:
                pass
            self._warned.add(feature)

    def get_warnings(self):
        return list(self._warnings)


# module-level singleton
_manager = MetadataManager()


def get_metadata_manager() -> MetadataManager:
    return _manager
