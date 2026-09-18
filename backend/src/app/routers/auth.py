"""Signup, login, and current-user endpoints."""

from __future__ import annotations

import logging
import uuid

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.db import get_pool
from app.rate_limit import limiter
from app.schemas import LoginRequest, SignupRequest, TokenResponse, UserOut
from app.services import auth as auth_service

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


@router.post("/signup", response_model=TokenResponse, status_code=201)
@limiter.limit("5/minute")
async def signup(request: Request, payload: SignupRequest, pool: asyncpg.Pool = Depends(get_pool)):
    password_hash = auth_service.hash_password(payload.password)
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "INSERT INTO users (email, password_hash) VALUES ($1, $2) RETURNING id",
                payload.email.lower(),
                password_hash,
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="An account with that email already exists.")
    except Exception:
        log.exception("Signup failed")
        raise HTTPException(status_code=500, detail="Could not create account. Please try again.")

    token = auth_service.create_access_token(str(row["id"]))
    return {"access_token": token, "token_type": "bearer"}


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, payload: LoginRequest, pool: asyncpg.Pool = Depends(get_pool)):
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, password_hash FROM users WHERE email = $1", payload.email.lower()
            )
    except Exception:
        log.exception("Login lookup failed")
        raise HTTPException(status_code=500, detail="Could not log in. Please try again.")

    # Same error for missing user and wrong password (no email enumeration via login).
    if not row or not auth_service.verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Incorrect email or password.")

    token = auth_service.create_access_token(str(row["id"]))
    return {"access_token": token, "token_type": "bearer"}


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    pool: asyncpg.Pool = Depends(get_pool),
) -> dict:
    payload = auth_service.decode_access_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token.")

    try:
        user_id = uuid.UUID(payload.get("sub", ""))
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, created_at FROM users WHERE id = $1", user_id
        )
    if not row:
        raise HTTPException(status_code=401, detail="User not found.")

    return {"id": str(row["id"]), "email": row["email"], "created_at": row["created_at"]}


@router.get("/me", response_model=UserOut)
async def me(current_user: dict = Depends(get_current_user)):
    return current_user
