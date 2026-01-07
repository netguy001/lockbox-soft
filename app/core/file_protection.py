"""
File Protection Module for LockBox
Handles NTFS permissions, file hiding, and integrity checks
"""

import os
import stat
import hashlib
import json
from pathlib import Path
from typing import Optional


class FileProtection:
    """Protects vault files from unauthorized access"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.integrity_file = self.data_dir / ".integrity"

    def protect_directory(self):
        """Apply NTFS permissions to restrict access to current user + admin only"""
        if os.name != "nt":
            return False

        try:
            import win32security
            import ntsecuritycon as con
            import win32api

            # Get current user SID
            username = win32api.GetUserName()
            user_sid, _, _ = win32security.LookupAccountName(None, username)

            # Get Administrators group SID
            admin_sid, _, _ = win32security.LookupAccountName(None, "Administrators")

            # Get SYSTEM SID (needed for Windows operations)
            system_sid, _, _ = win32security.LookupAccountName(None, "SYSTEM")

            # Create new DACL with inheritance flags
            dacl = win32security.ACL()

            # Inheritance flags for files and subdirectories
            inherit_flags = con.OBJECT_INHERIT_ACE | con.CONTAINER_INHERIT_ACE

            # Add current user - Full Control with inheritance
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION, inherit_flags, con.FILE_ALL_ACCESS, user_sid
            )

            # Add Administrators - Full Control with inheritance
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION,
                inherit_flags,
                con.FILE_ALL_ACCESS,
                admin_sid,
            )

            # Add SYSTEM - Full Control with inheritance (required for Windows)
            dacl.AddAccessAllowedAceEx(
                win32security.ACL_REVISION,
                inherit_flags,
                con.FILE_ALL_ACCESS,
                system_sid,
            )

            # Get security descriptor
            sd = win32security.GetFileSecurity(
                str(self.data_dir), win32security.DACL_SECURITY_INFORMATION
            )

            # Set new DACL (protected = don't inherit from parent)
            sd.SetSecurityDescriptorDacl(1, dacl, 0)
            win32security.SetFileSecurity(
                str(self.data_dir), win32security.DACL_SECURITY_INFORMATION, sd
            )

            return True

        except ImportError:
            print("Warning: pywin32 not installed, file protection unavailable")
            return False
        except Exception as e:
            print(f"Warning: Could not set file permissions: {e}")
            return False

    def hide_sensitive_files(self):
        """Hide sensitive files using Windows hidden attribute"""
        if os.name != "nt":
            return

        sensitive_files = [
            self.data_dir / ".recovery_hash",
            self.data_dir / "security.json",
            self.data_dir / ".integrity",
        ]

        try:
            import ctypes

            FILE_ATTRIBUTE_HIDDEN = 0x02

            for file_path in sensitive_files:
                if file_path.exists():
                    ctypes.windll.kernel32.SetFileAttributesW(
                        str(file_path), FILE_ATTRIBUTE_HIDDEN
                    )
        except Exception as e:
            print(f"Warning: Could not hide files: {e}")

    def calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        if not file_path.exists():
            return ""

        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def save_integrity_data(self, vault_path: Path):
        """Save integrity hashes of critical files"""
        integrity_data = {
            "vault_hash": self.calculate_file_hash(vault_path),
            "recovery_hash": self.calculate_file_hash(self.data_dir / ".recovery_hash"),
            "security_hash": self.calculate_file_hash(self.data_dir / "security.json"),
        }

        # Use atomic write to avoid partial writes; disable integrity feature on failure
        from app.core.metadata import get_metadata_manager

        metadata = get_metadata_manager()
        if not metadata.is_enabled("integrity"):
            return

        self.integrity_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            dirpath = self.integrity_file.parent
            tmp = dirpath / (self.integrity_file.name + ".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(integrity_data, f)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            # atomic replace
            os.replace(str(tmp), str(self.integrity_file))

            # Hide integrity file (best-effort)
            if os.name == "nt":
                try:
                    import ctypes

                    ctypes.windll.kernel32.SetFileAttributesW(
                        str(self.integrity_file), 0x02
                    )
                except Exception:
                    print("Warning: Could not hide integrity file; continuing")

        except (PermissionError, IOError, OSError) as e:
            metadata.disable("integrity", f"Could not write integrity metadata: {e}")
            return
        except Exception as e:
            metadata.disable(
                "integrity", f"Unexpected error writing integrity metadata: {e}"
            )
            return

    def check_integrity(self, vault_path: Path) -> dict:
        """Check if files have been tampered with"""
        if not self.integrity_file.exists():
            return {"tampered": False, "message": "No integrity data"}

        try:
            with open(self.integrity_file, "r") as f:
                stored_data = json.load(f)

            current_vault = self.calculate_file_hash(vault_path)
            current_recovery = self.calculate_file_hash(
                self.data_dir / ".recovery_hash"
            )
            current_security = self.calculate_file_hash(self.data_dir / "security.json")

            tampered_files = []

            if (
                stored_data.get("vault_hash")
                and current_vault != stored_data["vault_hash"]
            ):
                tampered_files.append("vault")

            if (
                stored_data.get("recovery_hash")
                and current_recovery != stored_data["recovery_hash"]
            ):
                tampered_files.append("recovery")

            if (
                stored_data.get("security_hash")
                and current_security != stored_data["security_hash"]
            ):
                tampered_files.append("security")

            if tampered_files:
                return {
                    "tampered": True,
                    "files": tampered_files,
                    "message": f"⚠️ Files modified externally: {', '.join(tampered_files)}",
                }

            return {"tampered": False, "message": "All files intact"}

        except Exception as e:
            return {"tampered": False, "message": f"Could not verify: {e}"}

    def secure_delete(self, file_path: Path, passes: int = 3):
        """Securely delete file by overwriting before deletion"""
        if not file_path.exists():
            return

        try:
            file_size = file_path.stat().st_size

            # Overwrite with random data
            with open(file_path, "rb+") as f:
                for _ in range(passes):
                    f.seek(0)
                    f.write(os.urandom(file_size))
                    f.flush()
                    os.fsync(f.fileno())

            # Finally delete
            file_path.unlink()

        except Exception as e:
            print(f"Secure delete failed: {e}")
            # Fallback to normal delete
            try:
                file_path.unlink()
            except:
                pass

    def lock_file_while_open(self, file_path: Path) -> Optional[object]:
        """Lock file to prevent external access while vault is open"""
        if os.name != "nt":
            return None

        try:
            import msvcrt

            handle = open(file_path, "rb+")
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, os.path.getsize(file_path))
            return handle
        except Exception:
            return None

    def unlock_file(self, handle):
        """Unlock previously locked file"""
        if handle:
            try:
                import msvcrt

                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                handle.close()
            except:
                pass
