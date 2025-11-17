from __future__ import annotations

from sqlalchemy import Column, Integer, create_engine, text
from sqlalchemy.orm import declarative_base, Session
from sqlalchemy.pool import StaticPool

from app.db.types import EncryptedJSON

Base = declarative_base()


class Secret(Base):
    __tablename__ = "secrets"
    id = Column(Integer, primary_key=True)
    payload = Column(EncryptedJSON, nullable=True)


def _engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )


def test_encrypted_json_roundtrip():
    engine = _engine()
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        rec = Secret(payload={"hello": "world", "n": 7})
        session.add(rec)
        session.commit()
        session.refresh(rec)

        fetched = session.get(Secret, rec.id)
        assert fetched.payload == {"hello": "world", "n": 7}


def test_encrypted_json_legacy_value():
    engine = _engine()
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO secrets (id, payload) VALUES (:id, :payload)"),
            {"id": 1, "payload": '{"plain": true}'},
        )

    with Session(engine) as session:
        rec = session.get(Secret, 1)
        assert rec.payload == {"plain": True}


def test_encrypted_json_process_result_plain_dict():
    typ = EncryptedJSON()
    legacy_value = {"plain": "yes"}
    assert typ.process_result_value(legacy_value, None) == legacy_value


def test_encrypted_json_bind_none():
    typ = EncryptedJSON()
    assert typ.process_bind_param(None, None) is None


def test_encrypted_json_process_invalid_ciphertext_returns_original():
    typ = EncryptedJSON()
    invalid = {"ciphertext": "not-valid"}
    assert typ.process_result_value(invalid, None) == invalid


def test_encrypted_json_process_valid_ciphertext(monkeypatch):
    from app.security import crypto
    from app import config

    monkeypatch.delenv("APP_ENCRYPTION_KEY", raising=False)
    config.get_settings.cache_clear()
    crypto.reset_crypto_state()

    typ = EncryptedJSON()
    payload = {"secret": 123}
    token = crypto.encrypt_json(payload)
    assert typ.process_result_value({"ciphertext": token}, None) == payload
