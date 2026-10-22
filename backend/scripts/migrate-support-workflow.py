"""Create audited support-workflow tables in an explicitly selected SQLite file.

Usage: python migrate-support-workflow.py --database EXISTING.sqlite --backup NEW-BACKUP.sqlite upgrade|check
Upgrade makes a SQLite backup at the explicitly chosen, nonexistent path before schema changes.
It only adds new tables and triggers; it never updates or drops existing tables or rows.
"""
import argparse
import json
import sqlite3
from pathlib import Path

NEW_TABLES = ("support_workflow_events", "support_follow_ups", "support_follow_up_events",
              "user_access_states", "operator_account_events")
TRIGGERS = {
    "support_workflow_events_no_update": "CREATE TRIGGER support_workflow_events_no_update BEFORE UPDATE ON support_workflow_events BEGIN SELECT RAISE(ABORT, 'support workflow events are append-only'); END",
    "support_workflow_events_no_delete": "CREATE TRIGGER support_workflow_events_no_delete BEFORE DELETE ON support_workflow_events BEGIN SELECT RAISE(ABORT, 'support workflow events are append-only'); END",
    "support_follow_up_events_no_update": "CREATE TRIGGER support_follow_up_events_no_update BEFORE UPDATE ON support_follow_up_events BEGIN SELECT RAISE(ABORT, 'follow-up events are append-only'); END",
    "support_follow_up_events_no_delete": "CREATE TRIGGER support_follow_up_events_no_delete BEFORE DELETE ON support_follow_up_events BEGIN SELECT RAISE(ABORT, 'follow-up events are append-only'); END",
    "operator_account_events_no_update": "CREATE TRIGGER operator_account_events_no_update BEFORE UPDATE ON operator_account_events BEGIN SELECT RAISE(ABORT, 'operator account events are append-only'); END",
    "operator_account_events_no_delete": "CREATE TRIGGER operator_account_events_no_delete BEFORE DELETE ON operator_account_events BEGIN SELECT RAISE(ABORT, 'operator account events are append-only'); END",
}
REQUIRED_COLUMNS = {
    "users": {"id", "role"},
    "questions": {"id", "user_id", "question_text", "answer_text", "status"},
    "crisis_warnings": {"id", "student_id", "status", "processed_at", "processed_by"},
    "teacher_student_assignments": {"id", "teacher_id", "student_id", "assigned_at"},
}
SOURCE_TYPES = {
    "users": {"id": "INTEGER", "role": "VARCHAR(20)"},
    "questions": {"id": "INTEGER", "user_id": "INTEGER", "question_text": "TEXT",
                  "answer_text": "TEXT", "status": "VARCHAR(20)"},
    "crisis_warnings": {"id": "INTEGER", "student_id": "INTEGER", "status": "VARCHAR(20)",
                         "processed_at": "DATETIME", "processed_by": "INTEGER"},
    "teacher_student_assignments": {"id": "INTEGER", "teacher_id": "INTEGER",
                                     "student_id": "INTEGER", "assigned_at": "DATETIME"},
}
SOURCE_FKS = {
    "questions": {("user_id", "users", "id")},
    "crisis_warnings": {("student_id", "users", "id")},
    "teacher_student_assignments": {("teacher_id", "users", "id"), ("student_id", "users", "id")},
}


def _tables(db):
    return {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _validate_source(db):
    tables = _tables(db)
    missing = set(REQUIRED_COLUMNS) - tables
    if missing:
        raise ValueError("Selected database is missing required project tables")
    for table, required in REQUIRED_COLUMNS.items():
        info = db.execute(f'PRAGMA table_info("{table}")').fetchall()
        actual = {row[1] for row in info}
        if not required.issubset(actual):
            raise ValueError("Selected database has an incompatible project schema")
        fields = {row[1]: row for row in info}
        for name, sql_type in SOURCE_TYPES[table].items():
            if fields[name][2].upper() != sql_type or (name == "id" and fields[name][5] != 1):
                raise ValueError("Selected database has an incompatible project schema")
        actual_fks = {(row[3], row[2], row[4]) for row in db.execute(f'PRAGMA foreign_key_list("{table}")')}
        if not SOURCE_FKS.get(table, set()).issubset(actual_fks):
            raise ValueError("Selected database has incompatible project references")
    if "questions" not in tables or "users" not in tables:
        raise ValueError("Selected database is not a recognized project schema")
    unique_assignment = False
    for index in db.execute('PRAGMA index_list("teacher_student_assignments")'):
        if index[2]:
            name = index[1].replace('"', '""')
            if tuple(row[2] for row in db.execute(f'PRAGMA index_info("{name}")')) == ("teacher_id", "student_id"):
                unique_assignment = True
    if not unique_assignment:
        raise ValueError("Selected database has incompatible assignment constraints")


def _verify_existing(db):
    tables = _tables(db)
    existing = tables.intersection(NEW_TABLES)
    expected = {
        "support_workflow_events": {
            "id": ("INTEGER", 1), "subject_type": ("VARCHAR(32)", 0), "subject_id": ("INTEGER", 0),
            "student_id": ("INTEGER", 0), "actor_id": ("INTEGER", 0), "action": ("VARCHAR(32)", 0),
            "reason": ("TEXT", 0), "result_text": ("TEXT", 0), "created_at": ("DATETIME", 0)},
        "support_follow_ups": {
            "id": ("INTEGER", 1), "source_type": ("VARCHAR(32)", 0), "source_id": ("INTEGER", 0),
            "student_id": ("INTEGER", 0), "created_by": ("INTEGER", 0), "due_at": ("DATETIME", 0),
            "summary": ("TEXT", 0), "status": ("VARCHAR(16)", 0), "outcome": ("TEXT", 0),
            "created_at": ("DATETIME", 0), "completed_at": ("DATETIME", 0), "cancelled_at": ("DATETIME", 0)},
        "support_follow_up_events": {
            "id": ("INTEGER", 1), "follow_up_id": ("INTEGER", 0), "actor_id": ("INTEGER", 0),
            "action": ("VARCHAR(16)", 0), "note": ("TEXT", 0), "created_at": ("DATETIME", 0)},
        "user_access_states": {
            "user_id": ("INTEGER", 1), "disabled": ("BOOLEAN", 0), "auth_epoch": ("INTEGER", 0),
            "updated_at": ("DATETIME", 0)},
        "operator_account_events": {
            "id": ("INTEGER", 1), "operator_name": ("VARCHAR(128)", 0),
            "action": ("VARCHAR(32)", 0), "target_user_id": ("INTEGER", 0),
            "reason": ("TEXT", 0), "created_at": ("DATETIME", 0)},
    }
    expected_fks = {
        "support_workflow_events": {("student_id", "users", "id", "RESTRICT"), ("actor_id", "users", "id", "RESTRICT")},
        "support_follow_ups": {("student_id", "users", "id", "RESTRICT"), ("created_by", "users", "id", "RESTRICT")},
        "support_follow_up_events": {("follow_up_id", "support_follow_ups", "id", "RESTRICT"), ("actor_id", "users", "id", "RESTRICT")},
        "user_access_states": {("user_id", "users", "id", "RESTRICT")},
        "operator_account_events": {("target_user_id", "users", "id", "RESTRICT")},
    }
    expected_indexes = {
        "support_workflow_events": {("subject_type",), ("subject_id",), ("student_id",)},
        "support_follow_ups": {("student_id",), ("created_by",), ("status",)},
        "support_follow_up_events": {("follow_up_id",)},
        "user_access_states": set(),
        "operator_account_events": {("target_user_id",)},
    }
    for table in existing:
        columns = expected[table]
        info = db.execute(f'PRAGMA table_info("{table}")').fetchall()
        actual = {row[1]: (row[2].upper(), row[5]) for row in info}
        if actual != columns:
            raise ValueError("Existing support-workflow schema is incompatible")
        actual_fks = set()
        for foreign_key in db.execute(f'PRAGMA foreign_key_list("{table}")'):
            actual_fks.add((foreign_key[3], foreign_key[2], foreign_key[4], foreign_key[6].upper()))
        if actual_fks != expected_fks[table]:
            raise ValueError("Existing support-workflow foreign keys are incompatible")
        if table == "user_access_states":
            create_sql = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()[0]
            normalized = "".join(create_sql.upper().split())
            if "CHECK(DISABLEDIN(0,1))" not in normalized or "CHECK(AUTH_EPOCH>=0)" not in normalized:
                raise ValueError("Existing account-state constraints are incompatible")
        indexes = set()
        for index in db.execute(f'PRAGMA index_list("{table}")'):
            index_name = index[1].replace('"', '""')
            indexes.add(tuple(row[2] for row in db.execute(f'PRAGMA index_info("{index_name}")')))
        if not expected_indexes[table].issubset(indexes):
            raise ValueError("Existing support-workflow indexes are incompatible")
    return existing


def _missing_triggers(db):
    existing = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='trigger'")}
    return {name for name in TRIGGERS if name not in existing}


def _invalid_triggers(db):
    rows = {row[0]: "".join((row[1] or "").upper().split())
            for row in db.execute("SELECT name, sql FROM sqlite_master WHERE type='trigger'")}
    return {name for name, sql in TRIGGERS.items()
            if name in rows and rows[name] != "".join(sql.upper().split())}


TABLE_DDL = {
    "support_workflow_events": [
        "CREATE TABLE support_workflow_events (id INTEGER PRIMARY KEY AUTOINCREMENT, subject_type VARCHAR(32) NOT NULL, subject_id INTEGER NOT NULL, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT, actor_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, action VARCHAR(32) NOT NULL, reason TEXT, result_text TEXT, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX ix_support_workflow_events_subject_type ON support_workflow_events(subject_type)",
        "CREATE INDEX ix_support_workflow_events_subject_id ON support_workflow_events(subject_id)",
        "CREATE INDEX ix_support_workflow_events_student_id ON support_workflow_events(student_id)",
    ],
    "support_follow_ups": [
        "CREATE TABLE support_follow_ups (id INTEGER PRIMARY KEY AUTOINCREMENT, source_type VARCHAR(32) NOT NULL, source_id INTEGER NOT NULL, student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT, created_by INTEGER REFERENCES users(id) ON DELETE RESTRICT, due_at DATETIME NOT NULL, summary TEXT NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'open', outcome TEXT, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, completed_at DATETIME, cancelled_at DATETIME)",
        "CREATE INDEX ix_support_follow_ups_student_id ON support_follow_ups(student_id)",
        "CREATE INDEX ix_support_follow_ups_created_by ON support_follow_ups(created_by)",
        "CREATE INDEX ix_support_follow_ups_status ON support_follow_ups(status)",
    ],
    "support_follow_up_events": [
        "CREATE TABLE support_follow_up_events (id INTEGER PRIMARY KEY AUTOINCREMENT, follow_up_id INTEGER NOT NULL REFERENCES support_follow_ups(id) ON DELETE RESTRICT, actor_id INTEGER REFERENCES users(id) ON DELETE RESTRICT, action VARCHAR(16) NOT NULL, note TEXT, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX ix_support_follow_up_events_follow_up_id ON support_follow_up_events(follow_up_id)",
    ],
    "user_access_states": [
        "CREATE TABLE user_access_states (user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE RESTRICT, disabled BOOLEAN NOT NULL DEFAULT 0 CHECK (disabled IN (0, 1)), auth_epoch INTEGER NOT NULL DEFAULT 0 CHECK (auth_epoch >= 0), updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)",
    ],
    "operator_account_events": [
        "CREATE TABLE operator_account_events (id INTEGER PRIMARY KEY AUTOINCREMENT, operator_name VARCHAR(128) NOT NULL, action VARCHAR(32) NOT NULL, target_user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE RESTRICT, reason TEXT NOT NULL, created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP)",
        "CREATE INDEX ix_operator_account_events_target_user_id ON operator_account_events(target_user_id)",
    ],
}


def migrate(db, action):
    if action not in {"upgrade", "check"}:
        raise ValueError("Unknown migration operation")
    _validate_source(db)
    existing = _verify_existing(db)
    missing_tables = set(NEW_TABLES) - existing
    invalid_triggers = _invalid_triggers(db)
    if action == "check":
        missing_triggers = _missing_triggers(db)
        complete = not missing_tables
        return {"exists": complete, "tables": sorted(existing),
                "append_only": complete and not missing_triggers and not invalid_triggers, "changed": False}
    if invalid_triggers:
        raise ValueError("Existing append-only trigger is incompatible")
    if not missing_tables and not _missing_triggers(db):
        return {"exists": True, "tables": sorted(existing), "append_only": True, "changed": False}
    db.execute("BEGIN IMMEDIATE")
    try:
        _validate_source(db)
        existing = _verify_existing(db)
        for table in NEW_TABLES:
            if table not in existing:
                for statement in TABLE_DDL[table]:
                    db.execute(statement)
        for trigger_name in _missing_triggers(db):
            db.execute(TRIGGERS[trigger_name])
        db.commit()
    except Exception:
        db.rollback()
        raise
    final_tables = _verify_existing(db)
    return {"exists": not (set(NEW_TABLES) - final_tables), "tables": sorted(final_tables),
            "append_only": not _missing_triggers(db) and not _invalid_triggers(db), "changed": True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="Explicit existing SQLite database file")
    parser.add_argument("--backup", type=Path, help="Required new backup path for upgrade")
    parser.add_argument("action", choices=("upgrade", "check"))
    args = parser.parse_args()
    if args.database.is_symlink() or not args.database.is_file():
        parser.error("An existing SQLite file is required")
    if args.database.resolve() == Path(__file__).resolve():
        parser.error("Database path is invalid")
    if args.action == "upgrade":
        if args.backup is None or args.backup.exists() or args.backup.is_symlink():
            parser.error("upgrade requires --backup pointing to a new, nonexistent file")
        if args.backup.resolve() == args.database.resolve():
            parser.error("Backup and database paths must differ")
    try:
        source = sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None)
        source.execute("PRAGMA foreign_keys=ON")
        _validate_source(source)
        if args.action == "upgrade":
            args.backup.parent.mkdir(parents=True, exist_ok=True)
            if args.backup.is_symlink():
                raise ValueError("Backup target is not a regular file path")
            with args.backup.open("xb"):
                pass
            destination = sqlite3.connect(args.backup, isolation_level=None)
            try:
                source.backup(destination)
                destination.commit()
            finally:
                destination.close()
        result = migrate(source, args.action)
        source.close()
        print(json.dumps(result))
    except (ValueError, sqlite3.Error, OSError):
        parser.exit(2, "Support schema migration failed; verify the selected schema, backup path and file permissions\n")


if __name__ == "__main__":
    main()
