from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
import bcrypt
import secrets

from ..database import get_db
from .. import models, schemas
from ..security import (
    create_access_token, get_current_user, login_guard, signing_key,
    token_lifetime_minutes, SecurityConfigurationError, validate_new_password,
)

# Re-export the identical dependency callable for existing routes and test overrides.
router = APIRouter(prefix="/api", tags=["Auth"])
_DUMMY_PASSWORD_HASH = bcrypt.hashpw(secrets.token_bytes(32), bcrypt.gensalt())


def _ensure_auth_configuration():
    try:
        signing_key()
        token_lifetime_minutes()
    except SecurityConfigurationError:
        raise HTTPException(status_code=503, detail="Authentication is unavailable: check server security configuration") from None


@router.post("/register", response_model=schemas.Token)
def register(user: schemas.UserCreate, request: Request, db: Session = Depends(get_db)):
    _ensure_auth_configuration()
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Public registration is available to students only")
    validate_new_password(user.password)
    if not user.username.strip() or user.username != user.username.strip():
        raise HTTPException(status_code=400, detail="Username must not be empty or have surrounding spaces")
    login_guard.check(request, user.username)
    # Registration also consumes the per-IP CPU budget without storing credentials.
    login_guard.failure(request, user.username)
    try:
        if db.query(models.User).filter(models.User.username == user.username).first():
            raise HTTPException(status_code=400, detail="Unable to register this account")
        new_user = models.User(
            username=user.username,
            password_hash=bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8"),
            role="student", student_id=user.student_id, name=user.name, advisor=user.advisor,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(status_code=503, detail="Registration is temporarily unavailable") from None
    login_guard.success(request, user.username)
    return {"access_token": create_access_token(user_id=new_user.id), "token_type": "bearer", "user": new_user}


@router.post("/login", response_model=schemas.Token)
def login(user: schemas.UserLogin, request: Request, db: Session = Depends(get_db)):
    _ensure_auth_configuration()
    identifier = (user.username or "").strip()
    login_guard.check(request, identifier)
    try:
        db_user = db.query(models.User).filter(models.User.username == identifier).first() if identifier else None
        if not db_user and identifier:
            # Preserve username -> display name -> student number compatibility.
            db_user = db.query(models.User).filter(models.User.name == identifier).first()
        if not db_user and identifier:
            db_user = db.query(models.User).filter(models.User.student_id == identifier).first()
        principal = f"user-id:{db_user.id}" if db_user else identifier
        login_guard.check(request, principal)
        valid = False
        try:
            password_bytes = user.password.encode("utf-8")
            stored_hash = db_user.password_hash.encode("utf-8") if db_user and db_user.password_hash else _DUMMY_PASSWORD_HASH
            if len(password_bytes) <= 72:
                valid = bcrypt.checkpw(password_bytes, stored_hash) and db_user is not None
        except (ValueError, TypeError, UnicodeError):
            valid = False
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable") from None
    if not valid or db_user.role not in ("student", "teacher"):
        login_guard.failure(request, principal)
        raise HTTPException(status_code=401, detail="Invalid sign-in credentials", headers={"WWW-Authenticate": "Bearer"})
    login_guard.success(request, principal)
    return {"access_token": create_access_token(user_id=db_user.id), "token_type": "bearer", "user": db_user}


@router.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user
