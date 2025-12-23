from .constants import DATA_DIR, VAULT_FILE


def save_vault(data: bytes):
    DATA_DIR.mkdir(exist_ok=True)
    with open(VAULT_FILE, "wb") as f:
        f.write(data)


def load_vault() -> bytes:
    if not VAULT_FILE.exists():
        return None
    return VAULT_FILE.read_bytes()
