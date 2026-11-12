"""Fail-closed account state checks used by both sign-in and every authenticated request."""
from fastapi import HTTPException
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app import models

ACCOUNT_TABLES = {"user_access_states", "operator_account_events"}
ACCOUNT_TRIGGERS = {
    "operator_account_events_no_update": "CREATE TRIGGER operator_account_events_no_update BEFORE UPDATE ON operator_account_events BEGIN SELECT RAISE(ABORT, 'operator account events are append-only'); END",
    "operator_account_events_no_delete": "CREATE TRIGGER operator_account_events_no_delete BEFORE DELETE ON operator_account_events BEGIN SELECT RAISE(ABORT, 'operator account events are append-only'); END",
}


def require_account_schema(db: Session) -> None:
    try:
        inspector = inspect(db.get_bind())
        if db.get_bind().dialect.name != "sqlite" or not ACCOUNT_TABLES.issubset(inspector.get_table_names()):
            raise ValueError("missing tables")
        expected = {
            "user_access_states": models.UserAccessState.__table__,
            "operator_account_events": models.OperatorAccountEvent.__table__,
        }
        expected_fks = {
            "user_access_states": {("user_id", "users", "id", "RESTRICT")},
            "operator_account_events": {("target_user_id", "users", "id", "RESTRICT")},
        }
        for table_name, table in expected.items():
            actual = {col["name"]: col for col in inspector.get_columns(table_name)}
            if set(actual) != set(table.columns.keys()):
                raise ValueError("columns")
            for column in table.columns:
                if str(actual[column.name]["type"]).upper() != str(column.type).upper():
                    raise ValueError("types")
            pk = inspector.get_pk_constraint(table_name).get("constrained_columns") or []
            expected_pk = ["user_id"] if table_name == "user_access_states" else ["id"]
            if pk != expected_pk:
                raise ValueError("primary key")
            fks = set()
            for item in inspector.get_foreign_keys(table_name):
                fks.add((item["constrained_columns"][0], item["referred_table"],
                    item["referred_columns"][0], (item.get("options") or {}).get("ondelete", "").upper()))
            if fks != expected_fks[table_name]:
                raise ValueError("foreign keys")
            wanted_indexes = {index.name for index in table.indexes}
            got_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
            if not wanted_indexes.issubset(got_indexes):
                raise ValueError("indexes")
            if table_name == "user_access_states":
                constraints = {" ".join(item["sqltext"].lower().split())
                               for item in inspector.get_check_constraints(table_name)}
                if not {"auth_epoch >= 0", "disabled in (0, 1)"}.issubset(constraints):
                    raise ValueError("account state constraints")
        trigger_rows = db.execute(text("SELECT name, sql FROM sqlite_master WHERE type='trigger'")).all()
        trigger_sql = {name: "".join((sql or "").upper().split()) for name, sql in trigger_rows}
        for name, sql in ACCOUNT_TRIGGERS.items():
            if trigger_sql.get(name) != "".join(sql.upper().split()):
                raise ValueError("triggers")
    except (SQLAlchemyError, KeyError, ValueError, IndexError, TypeError):
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable") from None


def access_state(db: Session, user_id: int) -> tuple[bool, int]:
    require_account_schema(db)
    try:
        row = db.query(models.UserAccessState).filter_by(user_id=user_id).first()
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable") from None
    # Existing accounts without a lifecycle row remain active at epoch 0.
    if row is None:
        return False, 0
    if type(row.auth_epoch) is not int or row.auth_epoch < 0 or type(row.disabled) is not bool:
        raise HTTPException(status_code=503, detail="Authentication is temporarily unavailable")
    return row.disabled, row.auth_epoch
