"""Explicit SQLite schema migration. Does not import the app or discover .env.

Usage: python this-file.py --database /operator/chosen/database.db upgrade|check|downgrade
Downgrade refuses a nonempty assignment table; existing user data is never deleted.
"""
import argparse
import json
from pathlib import Path
import sqlite3

TABLE = "teacher_student_assignments"


def table_exists(connection):
    return connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (TABLE,)).fetchone() is not None


def verify_schema(connection):
    columns = {row[1] for row in connection.execute(f"PRAGMA table_info({TABLE})")}
    if columns != {"id", "teacher_id", "student_id", "assigned_at"}:
        raise ValueError("Assignment schema is incompatible")
    unique_pair = False
    for index in connection.execute(f"PRAGMA index_list({TABLE})"):
        if index[2]:
            name = index[1].replace('"', '""')
            if [row[2] for row in connection.execute(f'PRAGMA index_info("{name}")')] == ["teacher_id", "student_id"]:
                unique_pair = True
    if not unique_pair:
        raise ValueError("Assignment schema requires a unique teacher/student pair")


def migrate(connection, action):
    if action not in {"check", "upgrade", "downgrade"}:
        raise ValueError("Unknown migration operation")
    if action == "check":
        exists = table_exists(connection)
        if exists:
            verify_schema(connection)
        return {"exists": exists, "rows": connection.execute(f"SELECT COUNT(*) FROM {TABLE}").fetchone()[0] if exists else 0, "changed": False}
    connection.execute("BEGIN IMMEDIATE")
    try:
        exists = table_exists(connection)
        if exists:
            verify_schema(connection)
        if action == "upgrade" and not exists:
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone():
                raise ValueError("The existing users table is required")
            connection.execute("""CREATE TABLE teacher_student_assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                teacher_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                student_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_teacher_student_assignment UNIQUE (teacher_id, student_id))""")
            connection.execute("CREATE INDEX ix_teacher_student_assignments_teacher_id ON teacher_student_assignments (teacher_id)")
            connection.execute("CREATE INDEX ix_teacher_student_assignments_student_id ON teacher_student_assignments (student_id)")
        elif action == "downgrade" and exists:
            if connection.execute(f"SELECT 1 FROM {TABLE} LIMIT 1").fetchone():
                raise ValueError("Downgrade refused: assignment table is not empty; preserve/revoke assignments explicitly first")
            connection.execute(f"DROP TABLE {TABLE}")
        connection.commit()
        return {"changed": (action == "upgrade" and not exists) or (action == "downgrade" and exists), "action": action}
    except Exception:
        connection.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="Explicit existing SQLite file; never a connection string or .env")
    parser.add_argument("action", choices=("upgrade", "check", "downgrade"))
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("An existing SQLite database file is required")
    try:
        with sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            print(json.dumps(migrate(connection, args.action)))
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
    except sqlite3.Error:
        parser.exit(2, "Migration failed; verify the selected SQLite schema and permissions\n")


if __name__ == "__main__":
    main()
