"""Offline operator-only SQLite ACL maintenance. No app/.env import or public API."""
import argparse
import json
from pathlib import Path
import sqlite3


def require_role(connection, user_id, role):
    if not connection.execute("SELECT 1 FROM users WHERE id=? AND role=?", (user_id, role)).fetchone():
        raise ValueError("The supplied ID does not have the required role")


def execute(connection, action, teacher_id=None, student_id=None):
    if action not in {"list", "grant", "revoke"}:
        raise ValueError("Unknown assignment operation")
    if action != "list" and (teacher_id is None or student_id is None):
        raise ValueError("Grant/revoke require both IDs")
    if any(value is not None and (type(value) is not int or value <= 0) for value in (teacher_id, student_id)):
        raise ValueError("IDs must be positive integers")
    if not connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='teacher_student_assignments'").fetchone():
        raise ValueError("Run the explicit assignment-schema migration before this command")
    connection.execute("BEGIN IMMEDIATE" if action != "list" else "BEGIN")
    try:
        if teacher_id is not None:
            require_role(connection, teacher_id, "teacher")
        if student_id is not None:
            require_role(connection, student_id, "student")
        if action == "list":
            sql = "SELECT teacher_id,student_id,assigned_at FROM teacher_student_assignments"
            params = []
            filters = []
            if teacher_id is not None:
                filters.append("teacher_id=?"); params.append(teacher_id)
            if student_id is not None:
                filters.append("student_id=?"); params.append(student_id)
            if filters:
                sql += " WHERE " + " AND ".join(filters)
            rows = connection.execute(sql + " ORDER BY teacher_id,student_id", params).fetchall()
            result = {"assignments": [{"teacher_id": row[0], "student_id": row[1], "assigned_at": row[2]} for row in rows]}
        elif action == "grant":
            cursor = connection.execute("INSERT INTO teacher_student_assignments (teacher_id,student_id) VALUES (?,?) ON CONFLICT(teacher_id,student_id) DO NOTHING", (teacher_id, student_id))
            result = {"action": action, "changed": cursor.rowcount == 1}
        else:
            cursor = connection.execute("DELETE FROM teacher_student_assignments WHERE teacher_id=? AND student_id=?", (teacher_id, student_id))
            result = {"action": action, "changed": cursor.rowcount == 1}
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="Operator-selected existing SQLite file")
    parser.add_argument("action", choices=("list", "grant", "revoke"))
    parser.add_argument("--teacher-id", type=int)
    parser.add_argument("--student-id", type=int)
    args = parser.parse_args()
    if not args.database.is_file():
        parser.error("An existing SQLite file is required")
    if args.action != "list" and (args.teacher_id is None or args.student_id is None):
        parser.error("Grant/revoke require --teacher-id and --student-id")
    if any(value is not None and value <= 0 for value in (args.teacher_id, args.student_id)):
        parser.error("IDs must be positive integers")
    try:
        with sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None) as connection:
            connection.execute("PRAGMA foreign_keys=ON")
            print(json.dumps(execute(connection, args.action, args.teacher_id, args.student_id)))
    except ValueError as exc:
        parser.exit(2, str(exc) + "\n")
    except sqlite3.Error:
        parser.exit(2, "Assignment operation failed; verify schema, IDs and permissions\n")


if __name__ == "__main__":
    main()
