"""Make or restore a SQLite database into a new path using SQLite's backup API."""

import argparse
import os
import sqlite3
import sys
from pathlib import Path


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri = path.resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True, timeout=30)


def _check(connection: sqlite3.Connection) -> tuple[str, int, int]:
    quick = connection.execute("PRAGMA quick_check").fetchone()
    quick_result = str(quick[0]) if quick else "no result"
    tables = connection.execute(
        "SELECT count(*) FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
    ).fetchone()[0]
    foreign_keys = sum(1 for _ in connection.execute("PRAGMA foreign_key_check"))
    return quick_result, int(tables), foreign_keys


def transfer_new_database(source: Path, destination: Path) -> dict[str, int | str]:
    source = source.expanduser().absolute()
    destination = destination.expanduser().absolute()
    if source.is_symlink() or not source.is_file():
        raise ValueError("source must be an existing regular SQLite file")
    if destination.is_symlink() or destination.exists():
        raise ValueError("destination must be a new, nonexistent path")
    if source.resolve() == destination.resolve():
        raise ValueError("source and destination must be different")
    if not destination.parent.is_dir():
        raise ValueError("destination parent directory must already exist")

    # Exclusive creation prevents following a link or overwriting a file created
    # between the preflight check and opening the destination.
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(destination, flags, 0o600)
    os.close(descriptor)

    source_connection = None
    destination_connection = None
    try:
        source_connection = _connect_read_only(source)
        source_check, source_tables, source_fk = _check(source_connection)
        if source_check.lower() != "ok":
            raise ValueError("source SQLite quick_check did not pass")

        destination_connection = sqlite3.connect(destination, timeout=30)
        source_connection.backup(destination_connection)
        destination_connection.commit()
        destination_check, destination_tables, destination_fk = _check(destination_connection)
        if destination_check.lower() != "ok":
            raise ValueError("destination SQLite quick_check did not pass")
        if source_tables != destination_tables or source_fk != destination_fk:
            raise ValueError("source and destination validation summaries differ")
        return {
            "quick_check": destination_check,
            "table_count": destination_tables,
            "foreign_key_violations": destination_fk,
        }
    finally:
        if destination_connection is not None:
            destination_connection.close()
        if source_connection is not None:
            source_connection.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    for operation in ("backup", "restore"):
        command = subparsers.add_parser(operation, help=f"{operation} to a new SQLite path")
        command.add_argument("--source", required=True, type=Path, help="Existing SQLite file (read-only)")
        command.add_argument("--destination", required=True, type=Path, help="New path; existing paths are refused")
    arguments = parser.parse_args()
    try:
        summary = transfer_new_database(arguments.source, arguments.destination)
    except (OSError, sqlite3.Error, ValueError):
        print("FAILED: SQLite operation or safety validation did not pass; inspect the selected files locally.", file=sys.stderr)
        return 2
    status = "PASS" if summary["foreign_key_violations"] == 0 else "PASS WITH EXISTING FOREIGN-KEY VIOLATIONS"
    print(
        f"{status}: operation={arguments.operation}; quick_check={summary['quick_check']}; "
        f"tables={summary['table_count']}; foreign_key_violations={summary['foreign_key_violations']}. "
        "Foreign-key violations are reported and were not changed. No row contents or connection strings were read to output."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
