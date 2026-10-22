"""Minimal liveness and sanitized database readiness endpoints."""

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app import models  # noqa: F401 - register mapped tables in Base.metadata
from app.database import Base, get_db


router = APIRouter(tags=["health"])
SERVICE_NAME = "health-new"


@router.get("/api/health")
def liveness():
    """Report that the process can serve requests without touching the database."""
    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/api/health/ready")
def readiness(db: Session = Depends(get_db)):
    """Check connectivity and the complete currently mapped application schema."""
    try:
        db.execute(text("SELECT 1")).scalar_one()
        schema_inspector = inspect(db.connection())
        for table in Base.metadata.sorted_tables:
            if not schema_inspector.has_table(table.name):
                return _not_ready()
            existing_columns = {
                column["name"] for column in schema_inspector.get_columns(table.name)
            }
            if not {column.name for column in table.columns}.issubset(existing_columns):
                return _not_ready()
    except Exception:
        # Deliberately do not expose driver, SQL, paths, or exception details.
        return _not_ready()

    return {"status": "ok", "service": SERVICE_NAME, "schema_ready": True}


def _not_ready():
    return JSONResponse(
        status_code=503,
        content={"status": "not_ready", "service": SERVICE_NAME, "schema_ready": False},
    )
