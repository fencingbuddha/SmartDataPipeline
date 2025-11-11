from __future__ import annotations

from typing import Any

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON, TypeDecorator

from app.security.crypto import encrypt_json, try_decrypt


JSON_PAYLOAD = JSON().with_variant(JSONB(), "postgresql")


class EncryptedJSON(TypeDecorator):
    """Store encrypted JSON blobs while presenting decrypted objects to the ORM."""

    impl = JSON_PAYLOAD
    cache_ok = True

    def process_bind_param(self, value: Any, dialect) -> Any:  # noqa: ANN001
        if value is None:
            return None
        ciphertext = encrypt_json(value)
        return {"ciphertext": ciphertext}

    def process_result_value(self, value: Any, dialect) -> Any:  # noqa: ANN001
        if value is None:
            return None
        if isinstance(value, dict) and "ciphertext" in value:
            decrypted = try_decrypt(value["ciphertext"])
            if decrypted is not None:
                return decrypted
        # Legacy fallback: return the raw JSON value (pre-encryption rows)
        return value
