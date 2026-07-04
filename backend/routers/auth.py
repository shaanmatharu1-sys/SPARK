"""
routers/auth.py — signup, login, current-user profile (incl. theme).
"""
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import hash_password, verify_password, create_access_token, get_current_user
from config import SIGNUP_INVITE_CODE
from db import get_db
from models import User, Watchlist
from config import DEFAULT_WATCHLIST

router = APIRouter(prefix="/auth", tags=["auth"])

USERNAME_RE = re.compile(r"^[a-zA-Z0-9_]{3,32}$")
VALID_THEMES = {"midnight-brass", "amber-classic", "cool-blue", "monochrome-slate"}


class SignupBody(BaseModel):
    username: str
    password: str
    invite_code: str | None = None


class LoginBody(BaseModel):
    username: str
    password: str


class ThemeUpdate(BaseModel):
    theme: str


def _user_out(user: User) -> dict:
    return {"id": user.id, "username": user.username, "theme": user.theme}


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupBody, db: AsyncSession = Depends(get_db)):
    if SIGNUP_INVITE_CODE and body.invite_code != SIGNUP_INVITE_CODE:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid invite code")
    if not USERNAME_RE.match(body.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username must be 3-32 characters: letters, numbers, underscore",
        )
    if len(body.password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 8 characters")

    existing = await db.scalar(select(User).where(User.username == body.username))
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username already taken")

    user = User(username=body.username, password_hash=hash_password(body.password))
    db.add(user)
    await db.flush()  # populate user.id before creating the dependent row
    db.add(Watchlist(user_id=user.id, symbols=list(DEFAULT_WATCHLIST)))
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return {"token": token, "user": _user_out(user)}


@router.post("/login")
async def login(body: LoginBody, db: AsyncSession = Depends(get_db)):
    user = await db.scalar(select(User).where(User.username == body.username))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password")
    token = create_access_token(user.id)
    return {"token": token, "user": _user_out(user)}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)):
    return _user_out(current_user)


@router.patch("/me")
async def update_me(
    body: ThemeUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.theme not in VALID_THEMES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"theme must be one of {sorted(VALID_THEMES)}")
    current_user.theme = body.theme
    await db.commit()
    return _user_out(current_user)
