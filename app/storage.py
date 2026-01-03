import os
import tempfile
import shutil
from pathlib import Path
from .constants import DATA_DIR, VAULT_FILE


def save_vault(data: bytes):
    """
    Atomically save vault data to disk.
    Uses temp file + rename to prevent corruption if app crashes during write.
    """
    DATA_DIR.mkdir(exist_ok=True, parents=True)

    # Create a temporary file in the same directory as the vault
    temp_fd, temp_path = tempfile.mkstemp(
        dir=DATA_DIR, prefix=".lockbox_temp_", suffix=".vault"
    )

    try:
        # Write to temporary file
        with os.fdopen(temp_fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (replaces old file)
        # On Windows, need to remove target first
        if os.name == "nt" and VAULT_FILE.exists():
            # Create backup before replacing
            backup_path = VAULT_FILE.with_suffix(".vault.bak")
            shutil.copy2(VAULT_FILE, backup_path)
            os.replace(temp_path, VAULT_FILE)
        else:
            # On Unix, os.replace is atomic
            os.replace(temp_path, VAULT_FILE)

    except Exception as e:
        # Clean up temp file if something went wrong
        try:
            os.unlink(temp_path)
        except:
            pass
        raise e


def load_vault() -> bytes:
    """
    Load vault data from disk.
    Attempts to load from backup if main file is corrupted.
    """
    if not VAULT_FILE.exists():
        return None

    try:
        return VAULT_FILE.read_bytes()
    except Exception as e:
        # Try to load from backup if main file is corrupted
        backup_path = VAULT_FILE.with_suffix(".vault.bak")
        if backup_path.exists():
            print(f"Warning: Main vault corrupted, loading from backup")
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

    if backup_name is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"lockbox_backup_{timestamp}.vault"

    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(exist_ok=True, parents=True)

    backup_path = backup_dir / backup_name
    shutil.copy2(VAULT_FILE, backup_path)

    return backup_path


def restore_from_backup(backup_path: Path):
    """
    Restore vault from a backup file.
    Creates a safety backup of current vault before restoring.
    """
    if not backup_path.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_path}")

    # Create safety backup of current vault
    if VAULT_FILE.exists():
        safety_backup = VAULT_FILE.with_suffix(".vault.before_restore")
        shutil.copy2(VAULT_FILE, safety_backup)

    # Restore from backup
    shutil.copy2(backup_path, VAULT_FILE)
