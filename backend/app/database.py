"""Lazy engine setup from an explicit process environment; no .env discovery or DDL."""
import os

from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

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


if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):

    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
        """SQLite disables FK enforcement per connection by default.

        Without this the ``ondelete="CASCADE"/"RESTRICT"/"SET NULL"`` rules in
        models.py are inert: deletes never cascade and RESTRICT never blocks.
        Known residual: ``psychological_reports.id=8`` references user_id=101,
        which never existed (legacy seed data). It is left untouched on purpose
        so the enforcement change does not silently rewrite history.
        """
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
