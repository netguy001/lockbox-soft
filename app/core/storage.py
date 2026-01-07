import os
import tempfile
import shutil
from pathlib import Path
from app.constants import (
    DATA_DIR,
    VAULT_FILE,
    ENABLE_FILE_PROTECTION,
    ENABLE_INTEGRITY_CHECKS,
    BACKUP_DIR,
    CONFIG_FILE,
)


def save_vault(data: bytes):
    """
    Atomically save vault data to disk.
    Uses temp file + rename to prevent corruption if app crashes during write.
    """
    DATA_DIR.mkdir(exist_ok=True, parents=True)

    temp_fd, temp_path = tempfile.mkstemp(
        dir=DATA_DIR, prefix=".lockbox_temp_", suffix=".vault"
    )

    try:
        with os.fdopen(temp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

        if os.name == "nt" and VAULT_FILE.exists():
            backup_path = VAULT_FILE.with_suffix(".vault.bak")
            shutil.copy2(VAULT_FILE, backup_path)
            os.replace(temp_path, VAULT_FILE)
        else:
            os.replace(temp_path, VAULT_FILE)

        # Apply file protection after saving
        if ENABLE_FILE_PROTECTION:
            try:
                from app.core.file_protection import FileProtection

                fp = FileProtection(DATA_DIR)
                fp.protect_directory()
                fp.hide_sensitive_files()
            except Exception as e:
                print(f"Warning: File protection failed: {e}")

        # Save integrity data
        if ENABLE_INTEGRITY_CHECKS:
            try:
                from app.core.file_protection import FileProtection

                fp = FileProtection(DATA_DIR)
                fp.save_integrity_data(VAULT_FILE)
            except Exception as e:
                print(f"Warning: Integrity save failed: {e}")

    except Exception as e:
        try:
            os.unlink(temp_path)
        except Exception:
            pass
        raise e


def load_vault() -> bytes:
    """
    Load vault data from disk.
    Attempts to load from backup if main file is corrupted.
    """
    if not VAULT_FILE.exists():
        return None

    # Check integrity before loading
    if ENABLE_INTEGRITY_CHECKS:
        try:
            from app.core.file_protection import FileProtection

            fp = FileProtection(DATA_DIR)
            result = fp.check_integrity(VAULT_FILE)
            if result.get("tampered"):
                print(f"WARNING: {result['message']}")
        except Exception as e:
            print(f"Warning: Integrity check failed: {e}")

    try:
        return VAULT_FILE.read_bytes()
    except Exception as e:
        backup_path = VAULT_FILE.with_suffix(".vault.bak")
        if backup_path.exists():
            print("Warning: Main vault corrupted, loading from backup")
            return backup_path.read_bytes()
        raise e


def create_backup(backup_name: str = None) -> Path:
    """
    Create a timestamped backup of the current vault.
    Returns path to backup file.
    """
    if not VAULT_FILE.exists():
        raise FileNotFoundError("No vault file to backup")

    from datetime import datetime
    import json

    # Determine backup directory and retention from config if present
    backup_dir = BACKUP_DIR
    retention = 10
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r", encoding="utf-8") as cf:
                cfg = json.load(cf)
                bdir = cfg.get("backup_dir")
                if bdir:
                    backup_dir = Path(bdir)
                retention = int(cfg.get("backup_retention", retention))
    except Exception:
        # on any failure, fall back to defaults
        backup_dir = BACKUP_DIR

    backup_dir.mkdir(exist_ok=True, parents=True)

    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"lockbox_backup_{timestamp}.vault"

    # Write backup atomically: write to tmp then replace
    backup_path = backup_dir / backup_name
    tmp_path = backup_dir / (backup_name + ".tmp")
    try:
        data = VAULT_FILE.read_bytes()
        with open(tmp_path, "wb") as tf:
            tf.write(data)
            try:
                tf.flush()
                os.fsync(tf.fileno())
            except Exception:
                pass
        os.replace(str(tmp_path), str(backup_path))

        # Prune older backups, keep last `retention` files
        backups = sorted(backup_dir.glob("lockbox_backup_*.vault"))
        if len(backups) > retention:
            for old in backups[:-retention]:
                try:
                    old.unlink()
                except Exception:
                    pass

        return backup_path
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass


def restore_from_backup(backup_path: Path):
    """
    Restore vault from a backup file.
    Creates a safety backup of current vault before restoring.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    if VAULT_FILE.exists():
        safety_backup = VAULT_FILE.with_suffix(".vault.before_restore")
        shutil.copy2(VAULT_FILE, safety_backup)

    shutil.copy2(backup_path, VAULT_FILE)
