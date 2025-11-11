from __future__ import annotations

import base64
import binascii
import hashlib
import json
from functools import lru_cache
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

DEV_SEED = "smartdata-dev"


def _normalize_key(raw_key: str | None) -> bytes:
    """Accept either a valid Fernet key or any string and derive a stable key."""
    if raw_key:
        trimmed = raw_key.strip()
        if trimmed:
            try:
                decoded = base64.urlsafe_b64decode(trimmed)
                if len(decoded) == 32:
                    return trimmed.encode("utf-8")
            except (ValueError, binascii.Error):
                pass
            digest = hashlib.sha256(trimmed.encode("utf-8")).digest()
            return base64.urlsafe_b64encode(digest)
    digest = hashlib.sha256(DEV_SEED.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _get_fernet() -> Fernet:
    settings = get_settings()
    key = _normalize_key(settings.APP_ENCRYPTION_KEY)
    return Fernet(key)


def encrypt_json(value: Any) -> str:
    """Serialize arbitrary JSON-able data and encrypt it."""
    token = _get_fernet().encrypt(json.dumps(value).encode("utf-8"))
    return token.decode("utf-8")


def decrypt_json(token: str) -> Any:
    """Decrypt payloads produced by `encrypt_json`."""
    data = _get_fernet().decrypt(token.encode("utf-8"))
    return json.loads(data.decode("utf-8"))


def try_decrypt(token: str) -> Any | None:
    """Best-effort decryption helper that returns None if the token is invalid."""
    try:
        return decrypt_json(token)
    except InvalidToken:
        return None


def reset_crypto_state() -> None:
    """Clear cached Fernet instances (used by tests when env changes)."""
    _get_fernet.cache_clear()
