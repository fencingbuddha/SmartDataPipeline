# app/core/security.py
from __future__ import annotations

import datetime as dt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.session import get_db
from app.models.user import User

settings = get_settings()
pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer = HTTPBearer()

# Use UPPERCASE names from Settings
JWT_SECRET = settings.JWT_SECRET
JWT_ALG = settings.JWT_ALG
ACCESS_MIN = settings.JWT_ACCESS_MIN
REFRESH_DAYS = settings.JWT_REFRESH_DAYS

def _utc_now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)

def _ts(d: dt.datetime) -> int:
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    else:
        d = d.astimezone(dt.timezone.utc)
    return int(d.timestamp())

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)

def _encode(sub: str, *, minutes: int | None = None, days: int | None = None, typ: str = "access") -> str:
    now = _utc_now()
    if minutes is None and days is None:
        minutes = 15
    exp_dt = now + (dt.timedelta(minutes=minutes) if minutes is not None else dt.timedelta(days=days))
    payload = {
        "sub": sub,
        "typ": typ,
        "iat": _ts(now),
        "exp": _ts(exp_dt),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)

def create_access(sub: str) -> str:
    return _encode(sub, minutes=ACCESS_MIN, typ="access")

def create_refresh(sub: str) -> str:
    return _encode(sub, days=REFRESH_DAYS, typ="refresh")

def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
    except JWTError as e:
        raise ValueError(str(e))

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    """FastAPI dependency that validates an access token and returns an active user."""
    try:
        payload = decode_token(creds.credentials)
        if payload.get("typ") != "access":
            raise ValueError("Not an access token")
        email = payload.get("sub")
        if not email:
            raise ValueError("Missing subject")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = db.query(User).filter(User.email == email, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return user
