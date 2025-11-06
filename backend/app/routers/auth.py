# app/routers/auth.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginIn, TokenPair, UserOut
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

@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return UserOut(id=user.id, email=user.email, is_active=user.is_active)

# Optional: a tiny helper to create a first user if you don't want a separate script.
@router.post("/_seed_demo_user", include_in_schema=False)
def _seed_demo_user(db: Session = Depends(get_db)):
    email = "demo@local"
    pwd = "demo123"
    u = db.query(User).filter_by(email=email).first()
    if not u:
        u = User(email=email, password_hash=hash_password(pwd))
        db.add(u)
        db.commit()
    return {"email": email, "password": pwd}
