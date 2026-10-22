"""Create, disable, or re-enable teacher accounts in an explicitly selected SQLite file.

The command is offline. It requires a new backup destination and never reads .env.
Passwords are entered twice through getpass and are never accepted as arguments or printed.
Example: python manage-teacher-accounts.py --database copy.sqlite --backup new-backup.sqlite
  --operator "Operator name" --reason "Approved request" disable-teacher --username teacher-name
"""
import argparse
import getpass
import importlib.util
import json
from pathlib import Path
import re
import sqlite3
import sys

import bcrypt


def _migration_module():
    path = Path(__file__).with_name("migrate-support-workflow.py")
    spec = importlib.util.spec_from_file_location("support_workflow_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_password(password: str) -> bool:
    try:
        encoded = password.encode("utf-8")
    except UnicodeError:
        return False
    return (8 <= len(password) and len(encoded) <= 72
            and any("a" <= char.lower() <= "z" for char in password)
            and any("0" <= char <= "9" for char in password))


def _make_backup(source: sqlite3.Connection, backup_path: Path):
    if backup_path.is_symlink() or backup_path.exists():
        raise ValueError("Backup target must be new")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if backup_path.is_symlink():
        raise ValueError("Backup target must be a regular new path")
    with backup_path.open("xb"):
        pass
    destination = sqlite3.connect(backup_path, isolation_level=None)
    try:
        source.backup(destination)
        destination.commit()
    finally:
        destination.close()


def _event(db, operator: str, action: str, target_user_id: int, reason: str):
    db.execute("""INSERT INTO operator_account_events
        (operator_name, action, target_user_id, reason, created_at)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)""", (operator, action, target_user_id, reason))


def _create_teacher(db, args):
    username = args.username
    if not username or username != username.strip() or len(username) > 50:
        raise ValueError("Username must be a nonempty value of at most 50 characters without surrounding spaces")
    if db.execute("SELECT 1 FROM users WHERE username=? LIMIT 1", (username,)).fetchone():
        raise ValueError("Username already exists; existing accounts are never promoted or overwritten")
    password = getpass.getpass("New teacher password: ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation or not _valid_password(password):
        raise ValueError("Password confirmation or strength check failed")
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("ascii")
    cursor = db.execute("INSERT INTO users(username,password_hash,role,name) VALUES(?,?,?,?)",
                        (username, password_hash, "teacher", args.name.strip() or None))
    user_id = cursor.lastrowid
    db.execute("INSERT INTO user_access_states(user_id,disabled,auth_epoch,updated_at) VALUES(?,0,0,CURRENT_TIMESTAMP)",
               (user_id,))
    _event(db, args.operator, "create_teacher", user_id, args.reason.strip())
    return {"action": "create_teacher", "username": username, "user_id": user_id}


def _change_teacher_state(db, args, enabled: bool):
    user = db.execute("SELECT id, role FROM users WHERE username=?", (args.username,)).fetchone()
    if user is None or user[1] != "teacher":
        raise ValueError("A matching teacher account is required; student accounts cannot be changed")
    user_id = user[0]
    state = db.execute("SELECT disabled,auth_epoch FROM user_access_states WHERE user_id=?", (user_id,)).fetchone()
    if enabled:
        if state is None or state[0] != 1:
            raise ValueError("Teacher account is not disabled")
        db.execute("UPDATE user_access_states SET disabled=0,updated_at=CURRENT_TIMESTAMP WHERE user_id=?", (user_id,))
        action = "enable_teacher"
    else:
        if state is not None and state[0] == 1:
            raise ValueError("Teacher account is already disabled")
        if state is None:
            db.execute("INSERT INTO user_access_states(user_id,disabled,auth_epoch,updated_at) VALUES(?,1,1,CURRENT_TIMESTAMP)",
                       (user_id,))
        else:
            db.execute("UPDATE user_access_states SET disabled=1,auth_epoch=auth_epoch+1,updated_at=CURRENT_TIMESTAMP WHERE user_id=?",
                       (user_id,))
        db.execute("DELETE FROM teacher_student_assignments WHERE teacher_id=?", (user_id,))
        action = "disable_teacher"
    _event(db, args.operator, action, user_id, args.reason.strip())
    epoch_row = db.execute("SELECT auth_epoch FROM user_access_states WHERE user_id=?", (user_id,)).fetchone()
    return {"action": action, "username": args.username, "user_id": user_id, "auth_epoch": epoch_row[0]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--backup", required=True, type=Path)
    parser.add_argument("--operator", required=True)
    parser.add_argument("--reason", required=True)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    create = subparsers.add_parser("create-teacher")
    create.add_argument("--username", required=True)
    create.add_argument("--name", default="")
    for operation in ("disable-teacher", "enable-teacher"):
        command = subparsers.add_parser(operation)
        command.add_argument("--username", required=True)
    args = parser.parse_args()
    if args.database.is_symlink() or not args.database.is_file():
        parser.error("An existing SQLite file is required")
    if args.backup.is_symlink() or args.backup.exists() or args.backup.resolve() == args.database.resolve():
        parser.error("Backup path must be new and distinct from the database")
    if not args.operator.strip() or len(args.operator.strip()) > 128 or not args.reason.strip():
        parser.error("Operator and reason are required")
    try:
        database = sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw", uri=True, isolation_level=None)
        database.execute("PRAGMA foreign_keys=ON")
        migration = _migration_module()
        readiness = migration.migrate(database, "check")
        if not readiness["exists"] or not readiness["append_only"]:
            raise ValueError("The selected database requires the support/account schema migration")
        _make_backup(database, args.backup)
        database.execute("BEGIN IMMEDIATE")
        try:
            readiness = migration.migrate(database, "check")
            if not readiness["exists"] or not readiness["append_only"]:
                raise ValueError("Database schema changed during account operation")
            args.operator = args.operator.strip()
            args.reason = args.reason.strip()
            if args.operation == "create-teacher":
                result = _create_teacher(database, args)
            else:
                result = _change_teacher_state(database, args, args.operation == "enable-teacher")
            database.commit()
        except Exception:
            database.rollback()
            raise
        database.close()
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (ValueError, sqlite3.Error, OSError, RuntimeError):
        parser.exit(2, "Teacher account operation failed; verify the selected schema, backup path, operator input and permissions\n")


if __name__ == "__main__":
    raise SystemExit(main())
