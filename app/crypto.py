"""Compatibility shim that forwards to app.core.crypto."""

from app.core.crypto import (
    check_password_breach,
    check_password_strength,
    decrypt,
    derive_key,
    encrypt,
    generate_password,
    hash_for_verification,
)

__all__ = [
    "check_password_breach",
    "check_password_strength",
    "decrypt",
    "derive_key",
    "encrypt",
    "generate_password",
    "hash_for_verification",
]
