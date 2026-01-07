import os
import json
import base64
import secrets
import zipfile
import shutil
from datetime import datetime
from pathlib import Path
from app.core.crypto import derive_key, encrypt, decrypt, check_password_strength
from app.constants import EMPTY_VAULT, MAX_PASSWORD_HISTORY, BACKUP_DIR


class Vault:
    def __init__(self, path: str):
        self.path = Path(path)
        self.key = None
        self.salt = None
        self.data = None
        self.is_locked = True
        self.last_activity = None

    def unlock(self, password: str):
        """Unlock vault with master password"""
        from app.core.security import SecurityManager
        from app.constants import DATA_DIR

        security = SecurityManager(DATA_DIR / "security.json")

        locked, minutes = security.is_locked_out()
        if locked:
            raise ValueError(f"🔒 Too many attempts. Try again in {minutes} minutes.")

        if not self.path.exists() or self.path.stat().st_size == 0:
            print("Creating new vault...")
            self.salt = os.urandom(16)
            self.key = derive_key(password, self.salt)
            self.data = EMPTY_VAULT.copy()

            from app.core.recovery import RecoverySystem

            recovery = RecoverySystem(self.path)
            self.recovery_phrase = recovery.generate_recovery_phrase()
            recovery.save_recovery_hash(self.recovery_phrase, vault_key=self.key)
            self.show_recovery_phrase = True

            self.is_locked = False
            self.last_activity = datetime.now()
            self._ensure_categories()
            self._save()
            security.record_successful_login()
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
            remaining = security.record_failed_login()
            if remaining > 0:
                raise ValueError(
                    f"❌ Invalid password. {remaining} attempts remaining."
                )
            raise ValueError(
                "🔒 Too many failed attempts. Account locked for 30 minutes."
            )

        except Exception:
            remaining = security.record_failed_login()
            if remaining > 0:
                raise ValueError(
                    f"❌ Invalid password. {remaining} attempts remaining."
                )
            raise ValueError(
                "🔒 Too many failed attempts. Account locked for 30 minutes."
            )

        self._ensure_categories()
        self.is_locked = False
        self.last_activity = datetime.now()
        security.record_successful_login()

    def unlock_with_recovery(self, recovery_phrase: str):
        """Unlock vault using recovery phrase instead of password"""
        from app.core.recovery import RecoverySystem

        recovery = RecoverySystem(self.path)

        if not recovery.has_recovery_phrase():
            raise ValueError("No recovery phrase set for this vault")

        with open(self.path, "rb") as f:
            self.salt = f.read(16)
            encrypted = f.read()

        recovered_key = recovery.retrieve_vault_key(recovery_phrase)

        if recovered_key:
            self.key = recovered_key
        else:
            if not recovery.verify_recovery_phrase(recovery_phrase):
                raise ValueError("Invalid recovery phrase")
            self.key = recovery.phrase_to_key(recovery_phrase, self.salt)

        try:
            decrypted = decrypt(encrypted, self.key)
            self.data = json.loads(decrypted.decode())
        except Exception:
            raise ValueError("Recovery phrase doesn't match this vault")

        # If we successfully unlocked but had no stored encrypted key, store it now
        if recovered_key is None:
            try:
                recovery.save_recovery_hash(recovery_phrase, vault_key=self.key)
            except Exception:
                pass

        self._ensure_categories()
        self.is_locked = False
        self.last_activity = datetime.now()
        return True

    def _create_verification_hash(self, password: str) -> str:
        """Create a verification hash for password checking"""
        from app.core.crypto import hash_for_verification

        return hash_for_verification(password + self.salt.hex())

    def verify_password(self, password: str) -> bool:
        """Verify password without full decryption"""
        if not self.path.exists():
            return False

        try:
            with open(self.path, "rb") as f:
                self.salt = f.read(16)
                encrypted = f.read()

            key = derive_key(password, self.salt)
            decrypt(encrypted, key)
            return True
        except Exception:
            return False

    def _ensure_categories(self):
        """Ensure all categories exist in vault data"""
        for category in [
            "passwords",
            "api_keys",
            "notes",
            "ssh_keys",
            "files",
            "encrypted_folders",
            "password_history",
            "totp_codes",
        ]:
            if category not in self.data:
                self.data[category] = []

    def lock(self):
        """Lock the vault and clear sensitive data from memory"""
        self.key = None
        self.data = None
        self.is_locked = True
        self.last_activity = None

    def _save(self):
        """Encrypt and save vault to disk with auto-backup"""
        if self.is_locked:
            raise ValueError("Vault is locked")

        if self.path.exists() and self.path.stat().st_size > 0:
            try:
                backup_dir = self.path.parent / "backups" / "auto"
                backup_dir.mkdir(parents=True, exist_ok=True)

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = backup_dir / f"auto_backup_{timestamp}.vault"

                shutil.copy2(self.path, backup_path)

                backups = sorted(backup_dir.glob("auto_backup_*.vault"))
                if len(backups) > 5:
                    for old_backup in backups[:-5]:
                        old_backup.unlink()
            except Exception as e:
                print(f"Warning: Auto-backup failed: {e}")

        raw = json.dumps(self.data, indent=2).encode()
        encrypted = encrypt(raw, self.key)

        from app.core.storage import save_vault

        save_vault(self.salt + encrypted)

        self.last_activity = datetime.now()

        # Update security integrity hashes after save
        try:
            from app.core.security_manager import get_security

            security = get_security()
            security.on_vault_saved()
        except Exception as e:
            print(f"Warning: Could not update integrity hashes: {e}")

    def _check_unlocked(self):
        """Helper to ensure vault is unlocked"""
        if self.is_locked or self.key is None:
            raise ValueError("Vault is locked")

    def _generate_id(self):
        """Generate unique ID for entries"""
        return secrets.token_hex(8)

    def change_master_password(self, old_password: str, new_password: str):
        """Change the master password and re-encrypt vault"""
        self._check_unlocked()

        try:
            with open(self.path, "rb") as f:
                old_salt = f.read(16)
                encrypted = f.read()

            old_key = derive_key(old_password, old_salt)
            decrypt(encrypted, old_key)
        except Exception:
            raise ValueError("Current password is incorrect")

        self.salt = os.urandom(16)
        self.key = derive_key(new_password, self.salt)
        self._save()
        return True

    # ========== PASSWORD METHODS ===========

    def add_password(
        self,
        title: str,
        username: str,
        password: str,
        url: str = "",
        notes: str = "",
        tags: list = None,
    ):
        """Add a new password entry"""
        self._check_unlocked()
        entry = {
            "id": self._generate_id(),
            "title": title,
            "username": username,
            "password": password,
            "url": url,
            "notes": notes,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
            "favorite": False,
        }
        self.data["passwords"].append(entry)
        self._save()
        return entry["id"]

    def list_passwords(self):
        """Get all password entries"""
        self._check_unlocked()
        return self.data.get("passwords", [])

    def get_password(self, entry_id: str):
        """Get specific password entry by ID"""
        self._check_unlocked()
        for entry in self.data.get("passwords", []):
            if entry.get("id") == entry_id:
                return entry
        return None

    def update_password(self, entry_id: str, **kwargs):
        """Update password entry with history tracking"""
        self._check_unlocked()
        for entry in self.data.get("passwords", []):
            if entry.get("id") == entry_id:
                if "password" in kwargs and kwargs["password"] != entry.get("password"):
                    self._add_password_history(
                        entry_id, entry.get("password"), entry.get("title", "Unknown")
                    )

                entry.update(kwargs)
                entry["modified"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    def delete_password(self, entry_id: str):
        """Delete password entry"""
        self._check_unlocked()
        self.data["passwords"] = [
            p for p in self.data.get("passwords", []) if p.get("id") != entry_id
        ]
        self.data["password_history"] = [
            h
            for h in self.data.get("password_history", [])
            if h.get("password_id") != entry_id
        ]
        self._save()

    def _add_password_history(self, password_id: str, old_password: str, title: str):
        """Add password to history"""
        history_entry = {
            "id": self._generate_id(),
            "password_id": password_id,
            "title": title,
            "old_password": old_password,
            "changed_at": datetime.now().isoformat(),
        }

        if "password_history" not in self.data:
            self.data["password_history"] = []

        self.data["password_history"].append(history_entry)

        password_histories = [
            h for h in self.data["password_history"] if h["password_id"] == password_id
        ]
        if len(password_histories) > MAX_PASSWORD_HISTORY:
            password_histories.sort(key=lambda x: x["changed_at"])
            to_remove = password_histories[0]
            self.data["password_history"] = [
                h for h in self.data["password_history"] if h["id"] != to_remove["id"]
            ]

    def get_password_history(self, password_id: str):
        """Get password change history"""
        self._check_unlocked()
        histories = [
            h
            for h in self.data.get("password_history", [])
            if h["password_id"] == password_id
        ]
        histories.sort(key=lambda x: x["changed_at"], reverse=True)
        return histories

    # ========== BACKUP & RESTORE ==========

    def backup_vault(self, backup_path: str = None):
        """Create encrypted backup of vault"""
        self._check_unlocked()

        if backup_path is None:
            BACKUP_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = BACKUP_DIR / f"lockbox_backup_{timestamp}.vault"

        shutil.copy2(self.path, backup_path)
        return str(backup_path)

    def restore_vault(self, backup_path: str, password: str):
        """Restore vault from backup"""
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise ValueError("Backup file not found")

        try:
            with open(backup_file, "rb") as f:
                salt = f.read(16)
                encrypted = f.read()

            key = derive_key(password, salt)
            decrypted = decrypt(encrypted, key)
            data = json.loads(decrypted.decode())
        except Exception:
            raise ValueError("Invalid backup file or password")

        shutil.copy2(backup_file, self.path)
        self.unlock(password)
        return True

    def export_json(self, export_path: str):
        """Export vault as unencrypted JSON (WARNING: Insecure)"""
        self._check_unlocked()
        with open(export_path, "w") as f:
            json.dump(self.data, f, indent=2)

    # ========== SECURITY DASHBOARD ==========

    def import_from_csv(self, csv_path: str):
        """Import passwords from CSV (format: title,username,password,url,notes)"""
        self._check_unlocked()
        import csv

        imported = 0
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    self.add_password(
                        title=row.get("title", row.get("name", "Imported")),
                        username=row.get("username", row.get("login", "")),
                        password=row.get("password", ""),
                        url=row.get("url", row.get("website", "")),
                        notes=row.get("notes", row.get("note", "")),
                    )
                    imported += 1
                except Exception as e:
                    print(f"Failed to import row: {e}")

        return imported

    def export_to_csv(self, csv_path: str):
        """Export passwords to CSV"""
        self._check_unlocked()
        import csv

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=["title", "username", "password", "url", "notes", "created"],
            )
            writer.writeheader()

            for pwd in self.data.get("passwords", []):
                writer.writerow(
                    {
                        "title": pwd.get("title", ""),
                        "username": pwd.get("username", ""),
                        "password": pwd.get("password", ""),
                        "url": pwd.get("url", ""),
                        "notes": pwd.get("notes", ""),
                        "created": pwd.get("created", ""),
                    }
                )

    def get_security_report(self):
        """Generate security dashboard data"""
        self._check_unlocked()

        passwords = self.data.get("passwords", [])
        weak_passwords = []
        reused_passwords = []
        old_passwords = []
        password_map = {}

        for pwd_entry in passwords:
            pwd = pwd_entry.get("password", "")
            pwd_id = pwd_entry.get("id")
            title = pwd_entry.get("title", "Unknown")

            strength = check_password_strength(pwd)
            # Use normalized score (1-4) for weak check, percent for display
            if strength["score"] < 3:
                weak_passwords.append(
                    {
                        "id": pwd_id,
                        "title": title,
                        "score": strength.get("percent", strength["score"]),
                    }
                )

            if pwd in password_map:
                if pwd not in [r["password"] for r in reused_passwords]:
                    reused_passwords.append(
                        {"password": pwd, "used_in": [password_map[pwd], title]}
                    )
                else:
                    for r in reused_passwords:
                        if r["password"] == pwd:
                            r["used_in"].append(title)
            else:
                password_map[pwd] = title

            modified = pwd_entry.get("modified", pwd_entry.get("created"))
            if modified:
                age_days = (datetime.now() - datetime.fromisoformat(modified)).days
                if age_days > 365:
                    old_passwords.append(
                        {"id": pwd_id, "title": title, "age_days": age_days}
                    )

        return {
            "total_passwords": len(passwords),
            "weak_passwords": weak_passwords,
            "reused_passwords": reused_passwords,
            "old_passwords": old_passwords,
            "average_strength": (
                sum(
                    [
                        check_password_strength(p.get("password", "")).get("percent", 0)
                        for p in passwords
                    ]
                )
                / len(passwords)
                if passwords
                else 0
            ),
        }

    # ========== API KEY METHODS ==========

    def add_api_key(
        self, service: str, key: str, description: str = "", tags: list = None
    ):
        """Add API key"""
        self._check_unlocked()
        entry = {
            "id": self._generate_id(),
            "service": service,
            "key": key,
            "description": description,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        }
        self.data["api_keys"].append(entry)
        self._save()
        return entry["id"]

    def list_api_keys(self):
        """Get all API keys"""
        self._check_unlocked()
        return self.data.get("api_keys", [])

    def delete_api_key(self, entry_id: str):
        """Delete API key"""
        self._check_unlocked()
        self.data["api_keys"] = [
            k for k in self.data.get("api_keys", []) if k.get("id") != entry_id
        ]
        self._save()

    def update_api_key(
        self, entry_id: str, service: str, key: str, description: str = ""
    ):
        """Update API key entry"""
        self._check_unlocked()
        for entry in self.data.get("api_keys", []):
            if entry.get("id") == entry_id:
                entry["service"] = service
                entry["key"] = key
                entry["description"] = description
                entry["modified"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    # ========== SECURE NOTES METHODS ==========

    def add_note(self, title: str, content: str, tags: list = None):
        """Add secure note"""
        self._check_unlocked()
        entry = {
            "id": self._generate_id(),
            "title": title,
            "content": content,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        }
        self.data["notes"].append(entry)
        self._save()
        return entry["id"]

    def list_notes(self):
        """Get all notes"""
        self._check_unlocked()
        return self.data.get("notes", [])

    def delete_note(self, entry_id: str):
        """Delete note"""
        self._check_unlocked()
        self.data["notes"] = [
            n for n in self.data.get("notes", []) if n.get("id") != entry_id
        ]
        self._save()

    def update_note(self, entry_id: str, title: str, content: str):
        """Update note entry"""
        self._check_unlocked()
        for entry in self.data.get("notes", []):
            if entry.get("id") == entry_id:
                entry["title"] = title
                entry["content"] = content
                entry["modified"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    # ========== SSH KEY METHODS ==========

    def add_ssh_key(
        self,
        name: str,
        private_key: str,
        public_key: str = "",
        passphrase: str = "",
        tags: list = None,
    ):
        """Add SSH key pair"""
        self._check_unlocked()
        entry = {
            "id": self._generate_id(),
            "name": name,
            "private_key": private_key,
            "public_key": public_key,
            "passphrase": passphrase,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
            "modified": datetime.now().isoformat(),
        }
        self.data["ssh_keys"].append(entry)
        self._save()
        return entry["id"]

    def list_ssh_keys(self):
        """Get all SSH keys"""
        self._check_unlocked()
        return self.data.get("ssh_keys", [])

    def delete_ssh_key(self, entry_id: str):
        """Delete SSH key"""
        self._check_unlocked()
        self.data["ssh_keys"] = [
            k for k in self.data.get("ssh_keys", []) if k.get("id") != entry_id
        ]
        self._save()

    def update_ssh_key(
        self, entry_id: str, name: str, private_key: str, public_key: str = ""
    ):
        """Update SSH key entry"""
        self._check_unlocked()
        for entry in self.data.get("ssh_keys", []):
            if entry.get("id") == entry_id:
                entry["name"] = name
                entry["private_key"] = private_key
                entry["public_key"] = public_key
                entry["modified"] = datetime.now().isoformat()
                self._save()
                return True
        return False

    # ========== TOTP/2FA METHODS ==========

    def add_totp(self, name: str, secret: str, issuer: str = "", tags: list = None):
        """Add TOTP/2FA authenticator"""
        self._check_unlocked()

        if "totp_codes" not in self.data:
            self.data["totp_codes"] = []

        entry = {
            "id": self._generate_id(),
            "name": name,
            "secret": secret,
            "issuer": issuer,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
        }
        self.data["totp_codes"].append(entry)
        self._save()
        return entry["id"]

    def list_totp(self):
        """Get all TOTP codes"""
        self._check_unlocked()
        return self.data.get("totp_codes", [])

    def get_totp_code(self, entry_id: str):
        """Generate current TOTP code"""
        self._check_unlocked()
        import pyotp

        for entry in self.data.get("totp_codes", []):
            if entry.get("id") == entry_id:
                totp = pyotp.TOTP(entry["secret"])
                return {
                    "code": totp.now(),
                    "remaining": 30 - (int(datetime.now().timestamp()) % 30),
                    "name": entry.get("name"),
                }
        return None

    def delete_totp(self, entry_id: str):
        """Delete TOTP entry"""
        self._check_unlocked()
        self.data["totp_codes"] = [
            t for t in self.data.get("totp_codes", []) if t.get("id") != entry_id
        ]
        self._save()

    # ========== FILE METHODS ==========

    def add_file(
        self, filename: str, file_data: bytes, description: str = "", tags: list = None
    ):
        """Add encrypted file"""
        self._check_unlocked()
        entry = {
            "id": self._generate_id(),
            "filename": filename,
            "data": base64.b64encode(file_data).decode(),
            "size": len(file_data),
            "description": description,
            "tags": tags or [],
            "created": datetime.now().isoformat(),
        }
        self.data["files"].append(entry)
        self._save()
        return entry["id"]

    def list_files(self):
        """Get all files (metadata only, not data)"""
        self._check_unlocked()
        return [
            {k: v for k, v in f.items() if k != "data"}
            for f in self.data.get("files", [])
        ]

    def get_file(self, entry_id: str):
        """Get file data"""
        self._check_unlocked()
        for entry in self.data.get("files", []):
            if entry.get("id") == entry_id:
                return base64.b64decode(entry["data"])
        return None

    def delete_file(self, entry_id: str):
        """Delete file"""
        self._check_unlocked()
        self.data["files"] = [
            f for f in self.data.get("files", []) if f.get("id") != entry_id
        ]
        self._save()

    # ========== FOLDER STORAGE METHODS ==========

    def add_encrypted_folder(self, folder_path: str, description: str = ""):
        """Store folder metadata for secure tracking"""
        self._check_unlocked()

        folder_path = Path(folder_path)
        if not folder_path.exists() or not folder_path.is_dir():
            raise ValueError("Invalid folder path")

        file_list = []
        total_size = 0
        for file_path in folder_path.rglob("*"):
            if file_path.is_file():
                rel_path = str(file_path.relative_to(folder_path))
                file_list.append(rel_path)
                total_size += file_path.stat().st_size

        entry = {
            "id": self._generate_id(),
            "folder_name": folder_path.name,
            "original_path": str(folder_path),
            "file_list": file_list,
            "size": total_size,
            "file_count": len(file_list),
            "description": description,
            "created": datetime.now().isoformat(),
        }

        self.data["encrypted_folders"].append(entry)
        self._save()
        return entry["id"]

    def list_encrypted_folders(self):
        """Get all folder metadata"""
        self._check_unlocked()
        return [
            {k: v for k, v in f.items() if k != "file_list"}
            for f in self.data.get("encrypted_folders", [])
        ]

    def download_folder_as_zip(self, entry_id: str, output_zip_path: str):
        """Create zip from original folder location"""
        self._check_unlocked()

        for entry in self.data.get("encrypted_folders", []):
            if entry.get("id") == entry_id:
                original_path = Path(entry["original_path"])

                if not original_path.exists():
                    raise ValueError(
                        "Original folder no longer exists at that location"
                    )

                with zipfile.ZipFile(
                    output_zip_path, "w", zipfile.ZIP_DEFLATED
                ) as zipf:
                    for file_path in original_path.rglob("*"):
                        if file_path.is_file():
                            arcname = file_path.relative_to(original_path.parent)
                            zipf.write(file_path, arcname)

                return True

        return False

    def set_folder_password(self, entry_id: str, password: str):
        """Set password protection for folder ZIP downloads"""
        self._check_unlocked()
        for entry in self.data.get("encrypted_folders", []):
            if entry.get("id") == entry_id:
                entry["zip_password"] = password
                self._save()
                return True
        return False

    def delete_encrypted_folder(self, entry_id: str):
        """Delete folder metadata"""
        self._check_unlocked()
        self.data["encrypted_folders"] = [
            f for f in self.data.get("encrypted_folders", []) if f.get("id") != entry_id
        ]
        self._save()

    # ========== SEARCH & UTILITY ==========

    def search(self, query: str, category: str = "all"):
        """Search across all entries"""
        self._check_unlocked()
        query = query.lower()
        results = []

        categories = (
            ["passwords", "api_keys", "notes", "ssh_keys", "files", "encrypted_folders"]
            if category == "all"
            else [category]
        )

        for cat in categories:
            for entry in self.data.get(cat, []):
                searchable = json.dumps(entry).lower()
                if query in searchable:
                    results.append({"category": cat, "entry": entry})

        return results

    def get_vault_stats(self):
        """Get vault statistics"""
        self._check_unlocked()
        return {
            "passwords": len(self.data.get("passwords", [])),
            "api_keys": len(self.data.get("api_keys", [])),
            "notes": len(self.data.get("notes", [])),
            "ssh_keys": len(self.data.get("ssh_keys", [])),
            "files": len(self.data.get("files", [])),
            "encrypted_folders": len(self.data.get("encrypted_folders", [])),
            "totp_codes": len(self.data.get("totp_codes", [])),
            "total": sum(len(v) for v in self.data.values() if isinstance(v, list)),
        }
