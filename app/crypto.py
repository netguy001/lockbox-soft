import os
import secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from argon2.low_level import hash_secret_raw, Type
from cryptography.hazmat.primitives import hashes


def derive_key(password: str, salt: bytes) -> bytes:
    """Derive encryption key from password using Argon2id"""
    return hash_secret_raw(
        secret=password.encode(),
        salt=salt,
        time_cost=4,
        memory_cost=102400,  # 100 MB
        parallelism=4,
        hash_len=32,
        type=Type.ID,
    )


def encrypt(data: bytes, key: bytes) -> bytes:
    """Encrypt data using AES-256-GCM"""
    aes = AESGCM(key)
    nonce = secrets.token_bytes(12)
    encrypted = aes.encrypt(nonce, data, None)
    return nonce + encrypted


def decrypt(data: bytes, key: bytes) -> bytes:
    """Decrypt data using AES-256-GCM"""
    nonce = data[:12]
    ciphertext = data[12:]
    aes = AESGCM(key)
    return aes.decrypt(nonce, ciphertext, None)


def generate_password(
    length=16, use_uppercase=True, use_lowercase=True, use_digits=True, use_symbols=True
) -> str:
    """Generate cryptographically secure random password"""
    chars = ""
    if use_lowercase:
        chars += "abcdefghijklmnopqrstuvwxyz"
    if use_uppercase:
        chars += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if use_digits:
        chars += "0123456789"
    if use_symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    if not chars:
        chars = "abcdefghijklmnopqrstuvwxyz"

    # Ensure at least one character from each selected type
    password = []
    if use_lowercase:
        password.append(secrets.choice("abcdefghijklmnopqrstuvwxyz"))
    if use_uppercase:
        password.append(secrets.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    if use_digits:
        password.append(secrets.choice("0123456789"))
    if use_symbols:
        password.append(secrets.choice("!@#$%^&*()-_=+[]{}|;:,.<>?"))

    # Fill the rest randomly
    for _ in range(length - len(password)):
        password.append(secrets.choice(chars))

    # Shuffle to avoid predictable patterns
    secrets.SystemRandom().shuffle(password)
    return "".join(password)


def check_password_strength(password: str) -> dict:
    """Check password strength and return score + feedback"""
    score = 0
    feedback = []

    length = len(password)
    has_lower = any(c.islower() for c in password)
    has_upper = any(c.isupper() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)

    # Length scoring
    if length >= 16:
        score += 40
    elif length >= 12:
        score += 30
    elif length >= 8:
        score += 20
    else:
        score += 10
        feedback.append("Password too short (min 8 chars)")

    # Complexity scoring
    if has_lower:
        score += 15
    else:
        feedback.append("Add lowercase letters")

    if has_upper:
        score += 15
    else:
        feedback.append("Add uppercase letters")

    if has_digit:
        score += 15
    else:
        feedback.append("Add numbers")

    if has_symbol:
        score += 15
    else:
        feedback.append("Add symbols (!@#$...)")

    # Determine strength level
    if score >= 80:
        strength = "Strong"
        color = "#2ecc71"
    elif score >= 60:
        strength = "Good"
        color = "#f39c12"
    elif score >= 40:
        strength = "Fair"
        color = "#e67e22"
    else:
        strength = "Weak"
        color = "#e74c3c"

    return {"score": score, "strength": strength, "color": color, "feedback": feedback}


def hash_for_verification(data: str) -> str:
    """Create hash for verification (not encryption)"""
    h = hashes.Hash(hashes.SHA256())
    h.update(data.encode())
    return h.finalize().hex()
