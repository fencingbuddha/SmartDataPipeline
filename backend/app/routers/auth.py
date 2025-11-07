# app/routers/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, SignupIn, TokenPair, UserOut
from app.core.security import (
    verify_password,
    hash_password,
    create_access,
    create_refresh,
    decode_token,
    get_current_user,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

class RefreshIn(BaseModel):
    refresh_token: str

@router.post("/login", response_model=TokenPair)
def login(body: LoginIn, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenPair(
        access_token=create_access(user.email),
        refresh_token=create_refresh(user.email),
    )


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == body.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=body.email, password_hash=hash_password(body.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    return TokenPair(
        access_token=create_access(user.email),
        refresh_token=create_refresh(user.email),
    )

@router.post("/refresh", response_model=TokenPair)
def refresh(body: RefreshIn):
    # NOTE: Public endpoint. Validates refresh token from body.
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("typ") != "refresh":
            raise ValueError("Not a refresh token")
        email = payload.get("sub")
        if not email:
            raise ValueError("Missing subject")
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    return TokenPair(
        access_token=create_access(email),
        refresh_token=create_refresh(email),
    )
