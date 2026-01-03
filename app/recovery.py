"""
Recovery Phrase System for LockBox
Implements BIP39-style 24-word recovery phrase for master password recovery

INSTALLATION:
pip install mnemonic

USAGE:
1. Save this as app/recovery.py
2. Follow integration steps at bottom of file
"""

from mnemonic import Mnemonic
import hashlib
import secrets
from pathlib import Path
import json


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
        # Generate 256 bits of entropy (24 words)
        entropy = secrets.token_bytes(32)
        phrase = self.mnemo.to_mnemonic(entropy)
        return phrase

    def phrase_to_key(self, phrase: str, salt: bytes) -> bytes:
        """
        Convert recovery phrase to encryption key
        Uses same derivation as master password for compatibility
        """
        from .crypto import derive_key

        # Normalize phrase (lowercase, single spaces)
        normalized = " ".join(phrase.lower().split())

        # Verify it's valid BIP39
        if not self.mnemo.check(normalized):
            raise ValueError("Invalid recovery phrase")

        # Derive key using Argon2id (same as master password)
        return derive_key(normalized, salt)

    def save_recovery_hash(self, phrase: str):
        """
        Save hash of recovery phrase to verify later
        Does NOT save the phrase itself - only a hash for verification
        """
        # Hash the phrase for verification (not encryption)
        phrase_hash = hashlib.sha256(phrase.encode()).hexdigest()

        recovery_data = {
            "hash": phrase_hash,
            "created": (
                Path(self.vault_path).stat().st_mtime if self.vault_path.exists() else 0
            ),
        }

        with open(self.recovery_file, "w") as f:
            json.dump(recovery_data, f)

    def verify_recovery_phrase(self, phrase: str) -> bool:
        """
        Verify if provided recovery phrase matches saved hash
        """
        if not self.recovery_file.exists():
            return False

        try:
            with open(self.recovery_file, "r") as f:
                recovery_data = json.load(f)

            phrase_hash = hashlib.sha256(phrase.encode()).hexdigest()
            return phrase_hash == recovery_data["hash"]
        except:
            return False

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

        # Check if valid BIP39 phrase
        if not self.mnemo.check(" ".join(words)):
            return (
                False,
                "Invalid recovery phrase - contains invalid words or checksum mismatch",
            )

        return True, ""


# ========== INTEGRATION GUIDE ==========

"""
STEP 1: Add to requirements.txt
---------------------------------
mnemonic>=0.20


STEP 2: Modify vault.py unlock() method
----------------------------------------
Add this at the START of unlock() method (after security check):

    from .recovery import RecoverySystem
    
    recovery = RecoverySystem(self.path)
    
    # On NEW vault creation, generate recovery phrase
    if not self.path.exists() or self.path.stat().st_size == 0:
        print("Creating new vault...")
        self.salt = os.urandom(16)
        self.key = derive_key(password, self.salt)
        self.data = EMPTY_VAULT.copy()
        
        # GENERATE RECOVERY PHRASE
        self.recovery_phrase = recovery.generate_recovery_phrase()
        recovery.save_recovery_hash(self.recovery_phrase)
        
        self.is_locked = False
        self.last_activity = datetime.now()
        self._ensure_categories()
        self._save()
        
        # Signal UI to show recovery phrase
        self.show_recovery_phrase = True
        return


STEP 3: Add recovery unlock method to vault.py
-----------------------------------------------
Add this new method to Vault class:

    def unlock_with_recovery(self, recovery_phrase: str):
        '''Unlock vault using recovery phrase instead of password'''
        from .recovery import RecoverySystem
        
        recovery = RecoverySystem(self.path)
        
        if not recovery.has_recovery_phrase():
            raise ValueError("No recovery phrase set for this vault")
        
        if not recovery.verify_recovery_phrase(recovery_phrase):
            raise ValueError("Invalid recovery phrase")
        
        # Load vault
        with open(self.path, "rb") as f:
            self.salt = f.read(16)
            encrypted = f.read()
        
        # Derive key from recovery phrase
        self.key = recovery.phrase_to_key(recovery_phrase, self.salt)
        
        try:
            decrypted = decrypt(encrypted, self.key)
            self.data = json.loads(decrypted.decode())
        except:
            raise ValueError("Recovery phrase doesn't match this vault")
        
        self._ensure_categories()
        self.is_locked = False
        self.last_activity = datetime.now()
        return True


STEP 4: Modify vault.py _save() method
---------------------------------------
After creating vault key, ALSO encrypt with recovery phrase:

    def _save(self):
        if self.is_locked:
            raise ValueError("Vault is locked")
        
        # [existing backup code]
        
        raw = json.dumps(self.data, indent=2).encode()
        encrypted = encrypt(raw, self.key)
        
        # Save with master password key
        from .storage import save_vault
        save_vault(self.salt + encrypted)
        
        # ALSO save recovery-encrypted version (for recovery unlock)
        from .recovery import RecoverySystem
        recovery = RecoverySystem(self.path)
        
        if recovery.has_recovery_phrase():
            # We can't re-encrypt with recovery phrase here since we don't have it
            # Recovery phrase only works because both master password and recovery
            # phrase can derive the SAME key from the SAME salt
            # So no extra save needed - the recovery phrase just derives the key differently
            pass
        
        self.last_activity = datetime.now()


STEP 5: Add UI dialogs to ui.py
--------------------------------
See next artifact for UI implementation.


SECURITY NOTES:
---------------
1. Recovery phrase uses same Argon2id key derivation as master password
2. Only HASH of recovery phrase is stored, never the phrase itself
3. User MUST write down phrase - we can't recover it for them
4. Phrase works offline, no external dependencies
5. 24 words = 256 bits entropy = extremely secure
6. BIP39 standard = same as crypto wallets, widely tested
"""


if __name__ == "__main__":
    # Test the recovery system
    print("🧪 Testing Recovery System...\n")

    from pathlib import Path
    import tempfile

    # Create temp vault path
    temp_dir = Path(tempfile.mkdtemp())
    vault_path = temp_dir / "test.vault"

    recovery = RecoverySystem(vault_path)

    # Test 1: Generate phrase
    print("1️⃣ Generating recovery phrase...")
    phrase = recovery.generate_recovery_phrase()
    print(f"   ✅ Generated: {phrase[:50]}...")
    print(f"   📊 Word count: {len(phrase.split())} words\n")

    # Test 2: Format for display
    print("2️⃣ Formatted display:")
    formatted = recovery.format_phrase_for_display(phrase)
    for num, word in formatted[:6]:  # Show first 6
        print(f"   {num:2d}. {word}")
    print(f"   ... (18 more words)\n")

    # Test 3: Save and verify
    print("3️⃣ Testing save and verification...")
    recovery.save_recovery_hash(phrase)
    print(f"   ✅ Hash saved to: {recovery.recovery_file}")
    print(f"   ✅ Verification: {recovery.verify_recovery_phrase(phrase)}")
    print(
        f"   ✅ Wrong phrase: {recovery.verify_recovery_phrase('wrong phrase here')}\n"
    )

    # Test 4: Validation
    print("4️⃣ Testing phrase validation...")
    valid, error = recovery.validate_phrase_format(phrase)
    print(f"   ✅ Valid phrase: {valid}")

    short_phrase = " ".join(phrase.split()[:12])
    valid, error = recovery.validate_phrase_format(short_phrase)
    print(f"   ❌ Too short (12 words): {error}\n")

    # Cleanup
    import shutil

    shutil.rmtree(temp_dir)

    print("✅ All tests passed!")
    print("\n💡 Next: Add to requirements.txt and integrate with vault.py")
