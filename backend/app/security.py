"""One strict v2 identity contract for HTTP and WebSocket access.

The bounded in-memory login guard is per process, not a shared rate limiter.
"""
from __future__ import annotations

import hashlib
import os
import threading
import time
from collections import OrderedDict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models
from app.account_access import access_state
from app.database import get_db

ALGORITHM = "HS256"
TOKEN_VERSION = 2
TOKEN_ISSUER = "health-new"
TOKEN_AUDIENCE = "health-new-api"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login", auto_error=False)


class SecurityConfigurationError(RuntimeError):
    """Messages contain variable names, never their values."""


def signing_key() -> str:
    key = os.environ.get("JWT_SECRET_KEY", "").strip()
    if (len(key.encode("utf-8")) < 32 or len(set(key)) < 12
            or any(word in key.lower() for word in ("change-me", "changeme", "your-secret", "example"))):
        raise SecurityConfigurationError("JWT_SECRET_KEY must be a unique random secret of at least 32 bytes")
    return key


def token_lifetime_minutes() -> int:
    try:
        minutes = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    except ValueError as exc:
        raise SecurityConfigurationError("ACCESS_TOKEN_EXPIRE_MINUTES must be an integer from 5 to 60") from exc
    if not 5 <= minutes <= 60:
        raise SecurityConfigurationError("ACCESS_TOKEN_EXPIRE_MINUTES must be from 5 to 60")
    return minutes


def cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    origins = list(dict.fromkeys(value.strip() for value in raw.split(",") if value.strip()))
    if not origins:
        raise SecurityConfigurationError("CORS_ALLOWED_ORIGINS requires an explicit HTTP(S) origin")
    for origin in origins:
        try:
            parsed = urlsplit(origin)
            port = parsed.port
        except ValueError as exc:
            raise SecurityConfigurationError("CORS_ALLOWED_ORIGINS contains an invalid origin") from exc
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or "*" in origin
                or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment or any(c.isspace() for c in origin)
                or (port is not None and not 1 <= port <= 65535)):
            raise SecurityConfigurationError("CORS_ALLOWED_ORIGINS must contain origins without paths or wildcards")
    return origins


def validate_security_configuration() -> None:
    signing_key()
    token_lifetime_minutes()
    cors_origins()


def _configuration_http_error() -> HTTPException:
    return HTTPException(status_code=503, detail="Authentication is unavailable: check server security configuration")


def authentication_error() -> HTTPException:
    return HTTPException(status_code=401, detail="Invalid or expired login credentials; please sign in again", headers={"WWW-Authenticate": "Bearer"})


def create_access_token(*, user_id: int, auth_epoch: int = 0) -> str:
    try:
        key = signing_key()
        lifetime = token_lifetime_minutes()
    except SecurityConfigurationError:
        raise _configuration_http_error() from None
    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        raise ValueError("Access tokens require a positive user ID")
    if isinstance(auth_epoch, bool) or not isinstance(auth_epoch, int) or auth_epoch < 0:
        raise ValueError("Access tokens require a nonnegative auth epoch")
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": str(user_id), "auth_epoch": auth_epoch, "ver": TOKEN_VERSION, "type": "access",
                       "iat": now, "exp": now + timedelta(minutes=lifetime),
                       "iss": TOKEN_ISSUER, "aud": TOKEN_AUDIENCE}, key, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        key = signing_key()
    except SecurityConfigurationError:
        raise _configuration_http_error() from None
    if not isinstance(token, str) or len(token) > 4096:
        raise authentication_error()
    try:
        payload = jwt.decode(token, key, algorithms=[ALGORITHM], issuer=TOKEN_ISSUER, audience=TOKEN_AUDIENCE,
                             options={"require": ["sub", "ver", "type", "iat", "exp", "iss", "aud"]})
        subject = payload.get("sub")
        if (type(payload.get("ver")) is not int or payload["ver"] != TOKEN_VERSION
                or payload.get("type") != "access" or not isinstance(subject, str)
                or not subject.isascii() or not subject.isdecimal() or int(subject) <= 0
                or subject != str(int(subject))
                or type(payload.get("iat")) not in (int, float)
                or type(payload.get("exp")) not in (int, float)
                or not 0 < payload["exp"] - payload["iat"] <= 3600):
            raise authentication_error()
        if "auth_epoch" in payload and (type(payload["auth_epoch"]) is not int or payload["auth_epoch"] < 0):
            raise authentication_error()
        return payload
    except (jwt.InvalidTokenError, TypeError, ValueError, OverflowError):
        raise authentication_error() from None


def resolve_access_user(token: str, db: Session) -> models.User:
    payload = decode_access_token(token)
    try:
        user = db.query(models.User).filter(models.User.id == int(payload["sub"])).first()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable") from None
    if user is None or user.role not in ("student", "teacher"):
        raise authentication_error()
    disabled, current_epoch = access_state(db, user.id)
    token_epoch = payload.get("auth_epoch", 0)
    if disabled or token_epoch != current_epoch:
        raise authentication_error()
    return user


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    return resolve_access_user(token, db)


def get_optional_user(token: str | None = Depends(optional_oauth2_scheme), db: Session = Depends(get_db)):
    return resolve_access_user(token, db) if token else None


def require_roles(*roles: str):
    allowed = frozenset(roles)

    def checker(current_user: models.User = Depends(get_current_user)) -> models.User:
        if current_user.role not in allowed:
            raise HTTPException(status_code=403, detail="This account cannot access this resource")
        return current_user

    return checker


def validate_new_password(password: str) -> None:
    try:
        encoded_length = len(password.encode("utf-8"))
    except UnicodeError:
        raise HTTPException(status_code=400, detail="Use valid Unicode password text") from None
    if (len(password) < 8 or encoded_length > 72
            or not any("a" <= c.lower() <= "z" for c in password) or not any("0" <= c <= "9" for c in password)):
        raise HTTPException(status_code=400, detail="Use at least 8 characters including a letter and a number, and at most 72 UTF-8 bytes")


class LoginGuard:
    def __init__(self):
        self._entries: OrderedDict[str, tuple[int, float]] = OrderedDict()
        self._lock = threading.Lock()
        self.window_seconds = 900
        self.max_entries = 10000

    def _keys(self, request: Request, identifier: str):
        ip = request.client.host if request.client else "unknown"
        return ("ip:" + hashlib.sha256(ip.encode()).hexdigest(),
                "account:" + hashlib.sha256(identifier.strip().casefold().encode()).hexdigest())

    def _prune(self, now: float):
        for key in [key for key, (_, expiry) in self._entries.items() if expiry <= now]:
            self._entries.pop(key, None)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def check(self, request: Request, identifier: str):
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            for key, limit in zip(self._keys(request, identifier), (20, 5), strict=True):
                count, expiry = self._entries.get(key, (0, now))
                if count >= limit and expiry > now:
                    raise HTTPException(status_code=429, detail="Too many sign-in attempts; try again later",
                                        headers={"Retry-After": str(max(1, int(expiry - now)))})

    def failure(self, request: Request, identifier: str):
        now = time.monotonic()
        with self._lock:
            self._prune(now)
            for key in self._keys(request, identifier):
                count, expiry = self._entries.get(key, (0, now + self.window_seconds))
                self._entries[key] = (count + 1, expiry)
                self._entries.move_to_end(key)
            self._prune(now)

    def success(self, request: Request, identifier: str):
        with self._lock:
            self._entries.pop(self._keys(request, identifier)[1], None)


login_guard = LoginGuard()
