"""Lazy engine setup from an explicit process environment; no .env discovery or DDL."""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

SQLALCHEMY_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
if not SQLALCHEMY_DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be explicitly configured before starting the application")

try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {},
    )
except Exception:
    raise RuntimeError("DATABASE_URL could not initialize the configured database driver") from None

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
