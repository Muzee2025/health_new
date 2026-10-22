"""Shared fail-closed helpers for audited support workflows."""
from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models


SUPPORT_TABLES = {"support_workflow_events", "support_follow_ups", "support_follow_up_events"}
APPEND_ONLY_TRIGGERS = {
    "support_workflow_events_no_update", "support_workflow_events_no_delete",
    "support_follow_up_events_no_update", "support_follow_up_events_no_delete",
}


def require_support_schema(db: Session) -> None:
    try:
        inspector = inspect(db.get_bind())
        present = set(inspector.get_table_names())
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Support workflow schema is not enabled") from None
    if not SUPPORT_TABLES.issubset(present):
        raise HTTPException(status_code=503, detail="Support workflow schema is not enabled")
    if db.get_bind().dialect.name != "sqlite":
        raise HTTPException(status_code=503, detail="Support workflow schema is not enabled")
    expected_fks = {
        "support_workflow_events": {
            ("student_id", "users", "id", "RESTRICT"),
            ("actor_id", "users", "id", "RESTRICT"),
        },
        "support_follow_ups": {
            ("student_id", "users", "id", "RESTRICT"),
            ("created_by", "users", "id", "RESTRICT"),
        },
        "support_follow_up_events": {
            ("follow_up_id", "support_follow_ups", "id", "RESTRICT"),
            ("actor_id", "users", "id", "RESTRICT"),
        },
    }
    try:
        for table in SUPPORT_TABLES:
            expected_columns = models.Base.metadata.tables[table]
            actual_columns = {column["name"]: column for column in inspector.get_columns(table)}
            if set(actual_columns) != set(expected_columns.columns.keys()):
                raise ValueError("column set")
            for column in expected_columns.columns:
                actual = actual_columns[column.name]
                if str(actual["type"]).upper() != str(column.type).upper():
                    raise ValueError("column type")
            primary_key = inspector.get_pk_constraint(table).get("constrained_columns") or []
            if primary_key != ["id"]:
                raise ValueError("primary key")
            actual_fks = set()
            for foreign_key in inspector.get_foreign_keys(table):
                actual_fks.add((foreign_key["constrained_columns"][0], foreign_key["referred_table"],
                    foreign_key["referred_columns"][0], (foreign_key.get("options") or {}).get("ondelete", "").upper()))
            if actual_fks != expected_fks[table]:
                raise ValueError("foreign keys")
            expected_indexes = {index.name for index in expected_columns.indexes}
            actual_indexes = {index["name"] for index in inspector.get_indexes(table)}
            if not expected_indexes.issubset(actual_indexes):
                raise ValueError("indexes")
        trigger_names = {row[0] for row in db.execute(
            text("SELECT name FROM sqlite_master WHERE type='trigger'")).all()}
        if not APPEND_ONLY_TRIGGERS.issubset(trigger_names):
            raise ValueError("append-only triggers")
    except (SQLAlchemyError, KeyError, ValueError, IndexError, TypeError):
        raise HTTPException(status_code=503, detail="Support workflow schema is not enabled") from None


def append_event(db: Session, *, subject_type: str, subject_id: int, student_id: int,
                 actor_id: int, action: str, reason: str | None = None,
                 result_text: str | None = None) -> models.SupportWorkflowEvent:
    event = models.SupportWorkflowEvent(
        subject_type=subject_type, subject_id=subject_id, student_id=student_id,
        actor_id=actor_id, action=action, reason=reason, result_text=result_text,
    )
    db.add(event)
    return event
