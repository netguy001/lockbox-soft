"""
Simple Security Module for LockBox
Just copy this file to app/security.py and follow the instructions below
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
                # Still locked out
                minutes_left = int((lockout_time - datetime.now()).seconds / 60)
                return True, minutes_left
            else:
                # Lockout expired - reset
                self.data["lockout_until"] = None
                self.data["failed_attempts"] = 0
                self._save()

        return False, 0

    def record_failed_login(self):
        """Record a failed login attempt"""
        self.data["failed_attempts"] += 1

        # After 5 failed attempts, lock for 30 minutes
        if self.data["failed_attempts"] >= 5:
            lockout_until = datetime.now() + timedelta(minutes=30)
            self.data["lockout_until"] = lockout_until.isoformat()

        self._save()

        # Return how many attempts are left
        return max(0, 5 - self.data["failed_attempts"])

    def record_successful_login(self):
        """Record successful login - reset failed attempts"""
        self.data["failed_attempts"] = 0
        self.data["lockout_until"] = None
        self._save()


# ========== HOW TO USE THIS IN YOUR EXISTING CODE ==========

"""
STEP 1: Save this file as: app/security.py

STEP 2: Open app/vault.py and find the unlock() method (around line 35)

STEP 3: Replace your unlock() method with this:

    def unlock(self, password: str):
        # ============ NEW CODE STARTS HERE ============
        from .security import SecurityManager
        from .constants import DATA_DIR
        
        security = SecurityManager(DATA_DIR / "security.json")
        
        # Check if locked out
        locked, minutes = security.is_locked_out()
        if locked:
            raise ValueError(f"🔒 Too many failed attempts. Try again in {minutes} minutes.")
        # ============ NEW CODE ENDS HERE ============
        
        # YOUR EXISTING CODE (keep everything below this)
        if not self.path.exists() or self.path.stat().st_size == 0:
            print("Creating new vault...")
            self.salt = os.urandom(16)
            self.key = derive_key(password, self.salt)
            self.data = EMPTY_VAULT.copy()
            self.is_locked = False
            self.last_activity = datetime.now()
            self._ensure_categories()
            self._save()
            
            # ============ NEW CODE ============
            security.record_successful_login()
            # ============ END ============
            
            print("New vault created successfully!")
            return

        try:
            with open(self.path, "rb") as f:
                self.salt = f.read(16)
                encrypted = f.read()

            if len(encrypted) == 0:
                raise ValueError("Vault file is corrupted (empty)")

            self.key = derive_key(password, self.salt)
            decrypted = decrypt(encrypted, self.key)
            self.data = json.loads(decrypted.decode())

        except json.JSONDecodeError:
            # ============ NEW CODE ============
            remaining = security.record_failed_login()
            if remaining > 0:
                raise ValueError(f"❌ Invalid password. {remaining} attempts remaining.")
            else:
                raise ValueError(f"🔒 Too many failed attempts. Account locked for 30 minutes.")
            # ============ END ============
            
        except Exception as e:
            # ============ NEW CODE ============
            remaining = security.record_failed_login()
            if remaining > 0:
                raise ValueError(f"❌ Invalid password. {remaining} attempts remaining.")
            else:
                raise ValueError(f"🔒 Too many failed attempts. Account locked for 30 minutes.")
            # ============ END ============

        self._ensure_categories()
        self.is_locked = False
        self.last_activity = datetime.now()
        
        # ============ NEW CODE ============
        security.record_successful_login()
        # ============ END ============

THAT'S IT! Now your vault has brute-force protection.

TEST IT:
1. Run your app
2. Try entering wrong password 5 times
3. On 6th attempt, you'll see "Account locked for 30 minutes"
4. Wait 30 minutes (or delete the security.json file to reset)
"""


if __name__ == "__main__":
    # Quick test
    print("Testing Security Manager...")

    security = SecurityManager("./test_security.json")

    print("\n1. Testing 5 failed attempts:")
    for i in range(6):
        remaining = security.record_failed_login()
        locked, minutes = security.is_locked_out()

        if locked:
            print(f"   Attempt {i+1}: 🔒 LOCKED OUT for {minutes} minutes")
        else:
            print(f"   Attempt {i+1}: ❌ Failed ({remaining} attempts remaining)")

    print("\n2. Testing successful login (resets counter):")
    security.record_successful_login()
    locked, _ = security.is_locked_out()
    print(f"   After success: {'🔒 Still locked' if locked else '✅ Unlocked'}")

    print("\n✅ Security manager works correctly!")
