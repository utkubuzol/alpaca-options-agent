"""Fernet symmetric encryption for secrets at rest (Alpaca keys, per-user
Telegram bot tokens). Key comes from APP_SECRET_KEY. Ciphertext is stored
in the `*_enc` columns; plaintext exists only in-process."""
from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from app.settings import get_settings

_PREFIX = "fernet:"


def _fernet() -> Fernet:
    key = get_settings().app_secret_key
    if not key:
        raise RuntimeError("APP_SECRET_KEY is not set — cannot encrypt/decrypt secrets")
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    if plaintext is None:
        raise ValueError("cannot encrypt None")
    return _PREFIX + _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    if not ciphertext:
        raise ValueError("cannot decrypt empty value")
    raw = ciphertext[len(_PREFIX):] if ciphertext.startswith(_PREFIX) else ciphertext
    try:
        return _fernet().decrypt(raw.encode()).decode()
    except InvalidToken as e:  # wrong key or corrupted row
        raise RuntimeError("failed to decrypt secret — APP_SECRET_KEY rotated?") from e


def mask(secret: str, show: int = 4) -> str:
    """UI-safe preview: last `show` chars only."""
    if not secret:
        return ""
    return "•" * max(0, len(secret) - show) + secret[-show:] if len(secret) > show else "•" * len(secret)
