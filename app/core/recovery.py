"""
Recovery Phrase System for LockBox
Implements BIP39-style 24-word recovery phrase for master password recovery
"""

import base64
import hashlib
import json
import secrets
from pathlib import Path
from typing import Optional

from mnemonic import Mnemonic


class RecoverySystem:
    """Handles recovery phrase generation and validation"""

    def __init__(self, vault_path: Path):
        self.vault_path = vault_path
        self.recovery_file = vault_path.parent / ".recovery_hash"
        self.mnemo = Mnemonic("english")

    def generate_recovery_phrase(self) -> str:
        """
        Generate a 24-word BIP39 recovery phrase
        Returns: Space-separated 24 words
        """
        entropy = secrets.token_bytes(32)
        phrase = self.mnemo.to_mnemonic(entropy)
        return phrase

    def _normalize_phrase(self, phrase: str) -> str:
        """Normalize phrase by lowering case and collapsing whitespace."""
        return " ".join(phrase.lower().split())

    def _load_recovery_data(self) -> Optional[dict]:
        """Load recovery metadata if it exists."""
        if not self.recovery_file.exists():
            return None

        try:
            with open(self.recovery_file, "r") as f:
                return json.load(f)
        except Exception:
            return None

    def phrase_to_key(self, phrase: str, salt: bytes) -> bytes:
        """
        Convert recovery phrase to encryption key
        Uses same derivation as master password for compatibility
        """
        from app.core.crypto import derive_key

        normalized = self._normalize_phrase(phrase)

        if not self.mnemo.check(normalized):
            raise ValueError("Invalid recovery phrase")

        return derive_key(normalized, salt)

    def save_recovery_hash(self, phrase: str, vault_key: Optional[bytes] = None):
        """
        Save hash of recovery phrase and optionally encrypt the vault key so the
        phrase can actually unlock the vault.
        """
        from app.core.crypto import derive_key, encrypt

        normalized = self._normalize_phrase(phrase)
        phrase_hash = hashlib.sha256(normalized.encode()).hexdigest()

        # Store both normalized and legacy for compatibility
        legacy_hash = hashlib.sha256(phrase.encode()).hexdigest()

        recovery_data = {
            "hash": phrase_hash,
            "legacy_hash": legacy_hash,
            "created": (
                Path(self.vault_path).stat().st_mtime if self.vault_path.exists() else 0
            ),
        }

        if vault_key is not None:
            recovery_salt = secrets.token_bytes(16)
            phrase_key = derive_key(normalized, recovery_salt)
            encrypted_key = encrypt(bytes(vault_key), phrase_key)

            recovery_data.update(
                {
                    "recovery_salt": base64.b64encode(recovery_salt).decode(),
                    "encrypted_key": base64.b64encode(encrypted_key).decode(),
                    "version": 2,
                }
            )

        # Atomic, best-effort write for recovery metadata. On failure, disable recovery feature
        from app.core.metadata import get_metadata_manager

        metadata = get_metadata_manager()
        if not metadata.is_enabled("recovery"):
            return

        self.recovery_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            dirpath = self.recovery_file.parent
            tmp = dirpath / (self.recovery_file.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(recovery_data, f)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            os.replace(str(tmp), str(self.recovery_file))
        except (PermissionError, IOError, OSError) as e:
            metadata.disable("recovery", f"Could not write recovery metadata: {e}")
            return
        except Exception as e:
            metadata.disable(
                "recovery", f"Unexpected error writing recovery metadata: {e}"
            )
            return

    def verify_recovery_phrase(self, phrase: str) -> bool:
        """
        Verify if provided recovery phrase matches saved hash
        """
        recovery_data = self._load_recovery_data()
        if not recovery_data:
            return False

        try:
            normalized = self._normalize_phrase(phrase)
            normalized_hash = hashlib.sha256(normalized.encode()).hexdigest()
            raw_hash = hashlib.sha256(phrase.encode()).hexdigest()

            stored_hash = recovery_data.get("hash")
            legacy_hash = recovery_data.get("legacy_hash")

            # Primary check: normalized input vs normalized hash
            if stored_hash and normalized_hash == stored_hash:
                return True

            # Backward compatibility: some older files stored the raw hash in the
            # "hash" field. Accept it and upgrade the file on the fly.
            if stored_hash and raw_hash == stored_hash:
                recovery_data["hash"] = normalized_hash
                recovery_data["legacy_hash"] = raw_hash
                try:
                    with open(self.recovery_file, "w") as wf:
                        json.dump(recovery_data, wf)
                except Exception:
                    pass
                return True

            # Accept either normalized or raw hash against the legacy field if present
            if legacy_hash and (
                normalized_hash == legacy_hash or raw_hash == legacy_hash
            ):
                return True

            return False
        except Exception:
            return False

    def retrieve_vault_key(self, phrase: str) -> Optional[bytes]:
        """
        Return the decrypted vault key if it was stored with the recovery data.
        None is returned if no encrypted key is stored or the phrase is wrong.
        """
        from app.core.crypto import derive_key, decrypt

        recovery_data = self._load_recovery_data()
        if not recovery_data:
            return None

        normalized = self._normalize_phrase(phrase)
        enc_key_b64 = recovery_data.get("encrypted_key")
        recovery_salt_b64 = recovery_data.get("recovery_salt")

        if not enc_key_b64 or not recovery_salt_b64:
            return None

        try:
            recovery_salt = base64.b64decode(recovery_salt_b64)
            phrase_key = derive_key(normalized, recovery_salt)
            enc_key = base64.b64decode(enc_key_b64)
            return decrypt(enc_key, phrase_key)
        except Exception:
            return None

    def has_recovery_phrase(self) -> bool:
        """Check if recovery phrase has been set up"""
        return self.recovery_file.exists()

    def format_phrase_for_display(self, phrase: str) -> list:
        """
        Format phrase into numbered list for display
        Returns: List of tuples [(1, "word1"), (2, "word2"), ...]
        """
        words = phrase.split()
        return [(i + 1, word) for i, word in enumerate(words)]

    def validate_phrase_format(self, phrase: str) -> tuple:
        """
        Validate phrase format and word validity
        Returns: (is_valid: bool, error_message: str)
        """
        words = phrase.strip().split()

        if len(words) != 24:
            return False, f"Must be exactly 24 words (you entered {len(words)})"

        if not self.mnemo.check(" ".join(words)):
            return (
                False,
                "Invalid recovery phrase - contains invalid words or checksum mismatch",
            )

        return True, ""
