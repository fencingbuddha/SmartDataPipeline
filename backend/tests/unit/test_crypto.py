from __future__ import annotations

from cryptography.fernet import Fernet

from app.security import crypto
from app import config


def test_encrypt_decrypt_roundtrip(monkeypatch):
    """Short keys should be derived into valid Fernet secrets automatically."""
    monkeypatch.setenv("APP_ENCRYPTION_KEY", "short-key")
    config.get_settings.cache_clear()
    crypto.reset_crypto_state()

    payload = {"foo": "bar", "n": 42}
    token = crypto.encrypt_json(payload)
    assert isinstance(token, str)
    assert crypto.decrypt_json(token) == payload


def test_accepts_pre_encoded_keys(monkeypatch):
    """Base64 keys that decode to 32 bytes should be used as-is."""
    key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("APP_ENCRYPTION_KEY", key)
    config.get_settings.cache_clear()
    crypto.reset_crypto_state()

    data = [1, 2, 3]
    token = crypto.encrypt_json(data)
    assert crypto.decrypt_json(token) == data


def test_try_decrypt_invalid_returns_none(monkeypatch):
    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    config.get_settings.cache_clear()
    crypto.reset_crypto_state()
    assert crypto.try_decrypt("not-a-token") is None
