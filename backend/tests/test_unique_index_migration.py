"""Pin the explicit unique-index migration used to harden an existing database.

create_all never adds constraints to a table that already exists, so a database created
before these constraints needs a separate step. These tests pin that step: it adds
indexes only, refuses a source that already holds duplicates, and leaves cancelled
rows free so a released slot can be booked again.
"""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError

if os.environ.get("HEALTH_TEST_ISOLATED") != "1":
    raise RuntimeError("Run through scripts/run-backend-baseline.py")

from app.models import Base  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
MIGRATE = ROOT / "backend" / "scripts" / "migrate-unique-indexes.py"

LEGACY_INDEXES = ("uq_appointment_active_slot", "uq_treehole_like_post_user",
                  "uq_treehole_favorite_post_user")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run(*args):
    return subprocess.run(
        [sys.executable, str(MIGRATE), *map(str, args)],
        cwd=Path(args[0]).parent,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )


def _legacy_database(path):
    """A database shaped like one created before the constraints existed."""
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (id, username, password_hash, role, student_id, name) "
                 "VALUES (1, 'synthetic-teacher', 'unused', 'teacher', NULL, 'T')")
        )
        connection.execute(
            text("INSERT INTO users (id, username, password_hash, role, student_id, name) "
                 "VALUES (2, 'synthetic-student', 'unused', 'student', 'SYN-1', 'S')")
        )
        connection.execute(
            text("INSERT INTO appointments (student_id, teacher_id, time_slot, status) "
                 "VALUES (2, 1, 'legacy-slot', 'pending')")
        )
        connection.execute(text("INSERT INTO treehole_posts (id, user_id, anonymous_id, content) "
                                "VALUES (1, 2, 'anon', 'synthetic')"))
        connection.execute(text("INSERT INTO treehole_likes (post_id, user_id) VALUES (1, 2)"))
        connection.execute(text("INSERT INTO treehole_favorites (post_id, user_id) VALUES (1, 2)"))
    # Strip the constraints so the file matches a pre-constraint deployment.
    with engine.begin() as connection:
        for name in LEGACY_INDEXES:
            connection.execute(text(f"DROP INDEX IF EXISTS {name}"))
    engine.dispose()
    return path


def _uq_indexes(path):
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    with engine.connect() as connection:
        rows = connection.execute(text(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'uq_%'")).fetchall()
    engine.dispose()
    return {row[0] for row in rows}


def test_check_reports_missing_indexes_without_writing(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    before = _sha256(database)
    result = _run("--database", database, "check")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["action"] == "check"
    assert report["changed"] is False
    assert set(report["missingIndexes"]) == set(LEGACY_INDEXES)
    assert report["blocked"] == []
    assert _sha256(database) == before, "check must not modify the database"
    assert _uq_indexes(database) == set()


def test_upgrade_adds_indexes_and_preserves_rows(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    backup = tmp_path / "before.db"
    result = _run("--database", database, "--backup", backup, "upgrade")
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert set(report["createdIndexes"]) == set(LEGACY_INDEXES)
    assert report["changed"] is True
    assert report["rowCountsBefore"] == report["rowCountsAfter"]
    assert report["integrityCheck"] == "ok"
    assert _uq_indexes(database) == set(LEGACY_INDEXES)
    assert backup.is_file(), "upgrade must leave a backup of the pre-migration state"

    # The backup is the pre-migration state: same data, none of the new indexes.
    assert _uq_indexes(backup) == set()
    engine = create_engine(f"sqlite:///{backup.as_posix()}")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM appointments")).scalar() == 1
    engine.dispose()


def test_upgrade_is_idempotent(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    first = _run("--database", database, "--backup", tmp_path / "b1.db", "upgrade")
    assert first.returncode == 0, first.stderr
    second = _run("--database", database, "--backup", tmp_path / "b2.db", "upgrade")
    assert second.returncode == 0, second.stderr
    report = json.loads(second.stdout)
    assert report["createdIndexes"] == []
    assert report["changed"] is False


def test_upgrade_refuses_source_with_active_duplicates(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO appointments (student_id, teacher_id, time_slot, status) "
            "VALUES (2, 1, 'legacy-slot', 'pending')"))
    engine.dispose()
    before = _sha256(database)

    check = _run("--database", database, "check")
    assert check.returncode == 0, check.stderr
    assert json.loads(check.stdout)["blocked"] == ["uq_appointment_active_slot"]

    result = _run("--database", database, "--backup", tmp_path / "b.db", "upgrade")
    assert result.returncode == 2, result.stdout
    assert _sha256(database) == before, "a refused upgrade must not write"
    assert _uq_indexes(database) == set(), "a refused upgrade must not add indexes"


def test_cancelled_duplicates_do_not_block_the_upgrade(tmp_path):
    """The index is partial, so released slots may legitimately repeat."""
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        for _ in range(2):
            connection.execute(text(
                "INSERT INTO appointments (student_id, teacher_id, time_slot, status) "
                "VALUES (2, 1, 'released-slot', 'cancelled')"))
    engine.dispose()
    result = _run("--database", database, "--backup", tmp_path / "b.db", "upgrade")
    assert result.returncode == 0, result.stderr
    assert set(json.loads(result.stdout)["createdIndexes"]) == set(LEGACY_INDEXES)


def test_upgrade_requires_a_new_backup_path(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    existing = tmp_path / "already-there.db"
    existing.write_bytes(b"")
    result = _run("--database", database, "--backup", existing, "upgrade")
    assert result.returncode == 2
    assert _uq_indexes(database) == set()


def test_upgrade_enforces_the_index_afterwards(tmp_path):
    database = _legacy_database(tmp_path / "legacy.sqlite3")
    assert _run("--database", database, "--backup", tmp_path / "b.db", "upgrade").returncode == 0
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    with engine.begin() as connection:
        with pytest.raises(IntegrityError):
            connection.execute(text(
                "INSERT INTO appointments (student_id, teacher_id, time_slot, status) "
                "VALUES (2, 1, 'legacy-slot', 'pending')"))
    # A cancelled row for the same slot stays allowed, so rebooking works.
    with engine.begin() as connection:
        connection.execute(text("UPDATE appointments SET status='cancelled' "
                                "WHERE time_slot='legacy-slot'"))
        connection.execute(text(
            "INSERT INTO appointments (student_id, teacher_id, time_slot, status) "
            "VALUES (2, 1, 'legacy-slot', 'pending')"))
        assert connection.execute(text(
            "SELECT COUNT(*) FROM appointments WHERE time_slot='legacy-slot'")).scalar() == 2
    engine.dispose()
