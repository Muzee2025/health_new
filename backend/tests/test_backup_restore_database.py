import importlib.util
import sqlite3
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backup-restore-database.py"
SPEC = importlib.util.spec_from_file_location("backup_restore_database", SCRIPT)
backup_restore = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(backup_restore)


def make_wal_database(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY, label TEXT NOT NULL)")
    connection.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))")
    connection.execute("INSERT INTO parent VALUES (1, 'synthetic')")
    connection.execute("INSERT INTO child VALUES (1, 1)")
    connection.commit()
    return connection


def test_backup_then_restore_preserves_wal_data_and_validates(tmp_path):
    source = tmp_path / "source.db"
    connection = make_wal_database(source)
    try:
        assert Path(str(source) + "-wal").exists()
        backup = tmp_path / "backup.db"
        restored = tmp_path / "restored.db"
        backup_summary = backup_restore.transfer_new_database(source, backup)
        restore_summary = backup_restore.transfer_new_database(backup, restored)
        assert backup_summary == {"quick_check": "ok", "table_count": 2, "foreign_key_violations": 0}
        assert restore_summary == backup_summary
        with sqlite3.connect(restored) as result:
            assert result.execute("SELECT label FROM parent").fetchone() == ("synthetic",)
            assert result.execute("SELECT parent_id FROM child").fetchone() == (1,)
    finally:
        connection.close()


def test_existing_foreign_key_orphan_is_reported_and_preserved(tmp_path):
    source = tmp_path / "orphan.db"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA foreign_keys=OFF")
        connection.execute("CREATE TABLE parent (id INTEGER PRIMARY KEY)")
        connection.execute("CREATE TABLE child (id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id))")
        connection.execute("INSERT INTO child VALUES (4, 404)")
    destination = tmp_path / "orphan-copy.db"
    summary = backup_restore.transfer_new_database(source, destination)
    assert summary["quick_check"] == "ok"
    assert summary["foreign_key_violations"] == 1
    with sqlite3.connect(destination) as connection:
        assert connection.execute("SELECT parent_id FROM child").fetchone() == (404,)


def test_destination_must_be_new_and_symlink_source_is_refused(tmp_path):
    source = tmp_path / "source.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE item (id INTEGER PRIMARY KEY)")
    existing = tmp_path / "existing.db"
    existing.write_bytes(b"keep")
    with pytest.raises(ValueError, match="new, nonexistent"):
        backup_restore.transfer_new_database(source, existing)
    assert existing.read_bytes() == b"keep"

    link = tmp_path / "source-link.db"
    try:
        link.symlink_to(source)
    except (OSError, NotImplementedError):
        pytest.skip("symlink creation is unavailable for this test account")
    with pytest.raises(ValueError, match="regular SQLite file"):
        backup_restore.transfer_new_database(link, tmp_path / "link-copy.db")
