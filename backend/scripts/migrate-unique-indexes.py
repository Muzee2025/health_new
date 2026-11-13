"""Add the booking/like/favorite unique indexes to an existing SQLite database.

Usage: python migrate-unique-indexes.py --database EXISTING.sqlite [--backup NEW-BACKUP.sqlite] check|upgrade

create_all only creates absent tables, so a database created before these constraints
never picks them up on its own. This script adds the indexes only: it never updates,
deletes or reorders rows. A database that already holds duplicates is refused instead
of silently dropping or merging rows.

The index definitions are read from prepare-local-database.py so a freshly prepared
deployment and an upgraded one cannot drift apart.

upgrade requires --backup pointing at a new, nonexistent file; the backup is written
and verified before the indexes are created.
"""
import argparse
import importlib.util
import json
import sqlite3
from pathlib import Path


def _prepare_module():
    path = Path(__file__).resolve().with_name('prepare-local-database.py')
    spec = importlib.util.spec_from_file_location('prepare_local_database', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REQUIRED_UNIQUE_INDEXES = _prepare_module().REQUIRED_UNIQUE_INDEXES


def _table_of(statement):
    return statement.split(' ON ')[1].split(' ')[0]


def _tables(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _indexes(db):
    return {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='index'")}


def _duplicates(db, duplicate_check):
    return db.execute(duplicate_check).fetchone()[0]


def inspect_database(db):
    """Report what would change, without writing anything."""
    tables = _tables(db)
    indexes = _indexes(db)
    missing = []
    duplicates = {}
    for name, statement, duplicate_check in REQUIRED_UNIQUE_INDEXES:
        if name in indexes:
            continue
        table = _table_of(statement)
        if table not in tables:
            # A database that predates the table entirely has nothing to protect yet.
            continue
        missing.append(name)
        duplicates[name] = _duplicates(db, duplicate_check)
    return {"missing": missing, "duplicates": duplicates,
            "blocked": sorted(name for name, count in duplicates.items() if count)}


def apply_indexes(db):
    """Create the missing indexes in one transaction; refuse duplicates first."""
    report = inspect_database(db)
    if report["blocked"]:
        raise ValueError(
            "Selected database already holds rows that violate: " + ", ".join(report["blocked"]))
    if not report["missing"]:
        return report
    db.execute("BEGIN IMMEDIATE")
    try:
        for name, statement, _ in REQUIRED_UNIQUE_INDEXES:
            if name in report["missing"]:
                db.execute(statement)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return report


def _row_counts(db, tables):
    return {table: db.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}


def migrate(db, action):
    if action not in {"upgrade", "check"}:
        raise ValueError("Unknown migration operation")
    tables = _tables(db)
    watched = sorted({_table_of(statement) for _, statement, _ in REQUIRED_UNIQUE_INDEXES} & tables)
    before_counts = _row_counts(db, watched)
    # Recorded so a later regression that breaks either check is attributable to this
    # migration rather than to pre-existing data.
    before_foreign_keys = len(db.execute("PRAGMA foreign_key_check").fetchall())
    if action == "check":
        report = inspect_database(db)
        return {"action": "check", "missingIndexes": report["missing"],
                "duplicateGroups": report["duplicates"], "blocked": report["blocked"],
                "existingIndexes": sorted(_indexes(db) & {n for n, _, _ in REQUIRED_UNIQUE_INDEXES}),
                "rowCounts": before_counts, "changed": False}
    report = apply_indexes(db)
    after_counts = _row_counts(db, watched)
    if after_counts != before_counts:
        raise ValueError("Row counts changed during index creation; restore the backup")
    after_integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
    if after_integrity != "ok":
        raise ValueError("SQLite integrity check failed after index creation")
    after_foreign_keys = len(db.execute("PRAGMA foreign_key_check").fetchall())
    if after_foreign_keys != before_foreign_keys:
        raise ValueError("Foreign key violations changed during index creation")
    return {"action": "upgrade", "createdIndexes": report["missing"],
            "existingIndexes": sorted(_indexes(db) & {n for n, _, _ in REQUIRED_UNIQUE_INDEXES}),
            "rowCountsBefore": before_counts, "rowCountsAfter": after_counts,
            "integrityCheck": after_integrity,
            "foreignKeyViolationsBefore": before_foreign_keys,
            "foreignKeyViolationsAfter": after_foreign_keys,
            "changed": bool(report["missing"])}


def _write_backup(database, backup):
    if backup.exists() or backup.is_symlink():
        raise ValueError("Backup path must be a new, nonexistent file")
    if backup.resolve() == database.resolve():
        raise ValueError("Backup and database paths must differ")
    backup.parent.mkdir(parents=True, exist_ok=True)
    with backup.open("xb"):
        pass
    source = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    destination = sqlite3.connect(backup, isolation_level=None)
    try:
        source.backup(destination)
        destination.commit()
        if destination.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Backup failed its integrity check")
    finally:
        destination.close()
        source.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path, help="Explicit existing SQLite database file")
    parser.add_argument("--backup", type=Path, help="Required new backup path for upgrade")
    parser.add_argument("action", choices=("upgrade", "check"))
    args = parser.parse_args()
    if args.database.is_symlink() or not args.database.is_file():
        parser.error("An existing SQLite file is required")
    if args.action == "upgrade" and args.backup is None:
        parser.error("upgrade requires --backup pointing to a new, nonexistent file")
    try:
        if args.action == "upgrade":
            _write_backup(args.database, args.backup)
        # Only the explicit target is opened read-write; no .env discovery, no app import.
        source = sqlite3.connect(args.database.resolve().as_uri() + "?mode=rw",
                                 uri=True, isolation_level=None)
        try:
            result = migrate(source, args.action)
        finally:
            source.close()
        print(json.dumps(result))
    except (ValueError, sqlite3.Error, OSError):
        parser.exit(2, "Unique index migration failed; verify the selected database, backup path and duplicates\n")


if __name__ == "__main__":
    main()
