"""Exercise local database preparation and launcher guards with synthetic SQLite only."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

if os.environ.get("HEALTH_TEST_ISOLATED") != "1":
    raise RuntimeError("Run through scripts/run-backend-baseline.py")

from app.models import Base  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
PREPARE = ROOT / "backend" / "scripts" / "prepare-local-database.py"
LAUNCHER = ROOT / "backend" / "scripts" / "run-local-backend.py"
MIGRATION = ROOT / "backend" / "migrations" / "20261022-student-assignments.py"


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _child_env(**overrides):
    env = os.environ.copy()
    env.update(overrides)
    return env


def _prepare(tmp_path, *args):
    return subprocess.run(
        [sys.executable, str(PREPARE), *map(str, args)],
        cwd=tmp_path,
        env=_child_env(
            DATABASE_URL="sqlite:///inherited-must-not-be-used.db",
            JWT_SECRET_KEY="synthetic-parent-key-only",
            RAG_ENABLED="true",
            RAG_ALLOW_MODEL_DOWNLOAD="true",
        ),
        capture_output=True,
        text=True,
    )


def _synthetic_source(path):
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            text("INSERT INTO users (username, password_hash, role, student_id, name) "
                 "VALUES ('synthetic-student', 'synthetic-hash', 'student', 'SYN-001', 'Synthetic Student')")
        )
        connection.execute(
            text("INSERT INTO articles (title, content, views) VALUES ('Synthetic only', 'Fixture body', 3)")
        )
        connection.execute(text("DROP TABLE teacher_student_assignments"))
    engine.dispose()


def _run_migration(database, action):
    return subprocess.run(
        [sys.executable, str(MIGRATION), "--database", str(database), action],
        cwd=database.parent,
        env=_child_env(),
        capture_output=True,
        text=True,
    )


def test_prepare_copies_synthetic_source_without_touching_it_or_copying_provider_keys(tmp_path):
    source = tmp_path / "source.sqlite3"
    _synthetic_source(source)
    source_hash = _sha256(source)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=sqlite:///cwd-decoy.sqlite3\nEXTERNAL_MODEL_API_KEY=synthetic-decoy-only\n",
        encoding="utf8",
    )

    result = _prepare(tmp_path, "--source", source, "--output", tmp_path / "deployment")

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["status"] == "prepared"
    assert report["sourceChanged"] is False
    assert report["createdAssignments"] == 0
    assert _sha256(source) == source_hash
    with create_engine(f"sqlite:///{(tmp_path / 'deployment' / 'health.db').as_posix()}").connect() as connection:
        assert connection.execute(text("SELECT username, student_id FROM users")).one() == (
            "synthetic-student", "SYN-001"
        )
        assert connection.execute(text("SELECT title, content, views FROM articles")).one() == (
            "Synthetic only", "Fixture body", 3
        )
        assert connection.execute(text("SELECT COUNT(*) FROM teacher_student_assignments")).scalar_one() == 0
    env_text = (tmp_path / "deployment" / ".env").read_text(encoding="utf8")
    env_keys = {line.split("=", 1)[0] for line in env_text.splitlines() if "=" in line}
    assert env_keys == {
        "DATABASE_URL", "JWT_SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES",
        "CORS_ALLOWED_ORIGINS", "RAG_ENABLED", "RAG_ALLOW_MODEL_DOWNLOAD",
    }
    assert "cwd-decoy" not in env_text
    assert "synthetic-decoy-only" not in env_text
    assert "inherited-must-not-be-used" not in env_text


def test_prepare_empty_creates_schema_and_refuses_existing_output(tmp_path):
    output = tmp_path / "empty-deployment"

    result = _prepare(tmp_path, "--empty", "--output", output)

    assert result.returncode == 0
    with create_engine(f"sqlite:///{(output / 'health.db').as_posix()}").connect() as connection:
        assert connection.execute(text("PRAGMA quick_check")).scalar_one() == "ok"
        assert connection.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='teacher_student_assignments'")
        ).scalar_one() == 1
        assert connection.execute(text("SELECT COUNT(*) FROM teacher_student_assignments")).scalar_one() == 0
    before = _sha256(output / "health.db")
    repeated = _prepare(tmp_path, "--empty", "--output", output)
    assert repeated.returncode == 2
    assert _sha256(output / "health.db") == before


def test_prepare_refuses_missing_columns_and_retains_only_the_new_failed_output(tmp_path):
    source = tmp_path / "missing-column.sqlite3"
    with create_engine(f"sqlite:///{source.as_posix()}").begin() as connection:
        connection.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    source_hash = _sha256(source)
    output = tmp_path / "rejected-deployment"

    result = _prepare(tmp_path, "--source", source, "--output", output)

    assert result.returncode == 2
    assert _sha256(source) == source_hash
    assert (output / "source-backup.db").is_file()
    assert (output / "health.db").is_file()
    assert not (output / ".env").exists()


def test_assignment_migration_is_idempotent_and_never_auto_assigns(tmp_path):
    database = tmp_path / "migration-synthetic.sqlite3"
    _synthetic_source(database)
    source_hash = _sha256(database)

    before = _run_migration(database, "check")
    assert before.returncode == 0
    assert json.loads(before.stdout) == {"exists": False, "rows": 0, "changed": False}
    assert _sha256(database) == source_hash

    upgrade = _run_migration(database, "upgrade")
    assert upgrade.returncode == 0
    assert json.loads(upgrade.stdout)["changed"] is True
    repeated = _run_migration(database, "upgrade")
    assert repeated.returncode == 0
    assert json.loads(repeated.stdout)["changed"] is False
    with create_engine(f"sqlite:///{database.as_posix()}").begin() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM teacher_student_assignments")).scalar_one() == 0
        assert len(connection.exec_driver_sql("PRAGMA foreign_key_list(teacher_student_assignments)").all()) == 2
        assert any(
            row[2] for row in connection.exec_driver_sql("PRAGMA index_list(teacher_student_assignments)")
        )

    with create_engine(f"sqlite:///{database.as_posix()}").begin() as connection:
        teacher = connection.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES ('synthetic-teacher','x','teacher')")
        ).lastrowid
        student = connection.execute(
            text("INSERT INTO users (username, password_hash, role) VALUES ('synthetic-student-2','x','student')")
        ).lastrowid
        connection.execute(
            text("INSERT INTO teacher_student_assignments (teacher_id,student_id) VALUES (:teacher,:student)"),
            {"teacher": teacher, "student": student},
        )
    blocked = _run_migration(database, "downgrade")
    assert blocked.returncode == 2
    with create_engine(f"sqlite:///{database.as_posix()}").connect() as connection:
        assert connection.execute(text("SELECT COUNT(*) FROM teacher_student_assignments")).scalar_one() == 1
    with create_engine(f"sqlite:///{database.as_posix()}").begin() as connection:
        connection.execute(text("DELETE FROM teacher_student_assignments"))
    downgrade = _run_migration(database, "downgrade")
    assert downgrade.returncode == 0
    with create_engine(f"sqlite:///{database.as_posix()}").connect() as connection:
        assert connection.execute(
            text("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='teacher_student_assignments'")
        ).scalar_one() == 0


def _invoke_launcher(tmp_path, settings):
    envfile = tmp_path / "launcher-deployment" / ".env"
    envfile.parent.mkdir()
    database = envfile.parent / "health.db"
    database.touch()
    values = {
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "JWT_SECRET_KEY": "synthetic-launcher-key-only",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173",
        "RAG_ENABLED": "false",
        "RAG_ALLOW_MODEL_DOWNLOAD": "false",
    }
    values.update(settings)
    envfile.write_text("".join(f"{key}={value}\n" for key, value in values.items()), encoding="utf8")
    code = r'''
import json, os, runpy, sys, types
captured = {}
uvicorn = types.ModuleType("uvicorn")
def fake_run(*args, **kwargs):
    captured["kwargs"] = kwargs
    captured["env"] = dict(os.environ)
uvicorn.run = fake_run
sys.modules["uvicorn"] = uvicorn
sys.argv = [sys.argv[1], "--env-file", sys.argv[2], "--port", "18080"]
runpy.run_path(sys.argv[0], run_name="__main__")
values = captured["env"]
print(json.dumps({"called": "kwargs" in captured,
                  "host": captured.get("kwargs", {}).get("host"),
                  "port": captured.get("kwargs", {}).get("port"),
                  "database": values.get("DATABASE_URL"),
                  "rag": values.get("RAG_ENABLED"),
                  "parent_marker_present": "PARENT_PROVIDER_MARKER" in values,
                  "parent_database_present": "inherited-parent-db" in values.get("DATABASE_URL", ""),
                  "env_keys": sorted(k for k in values if k in {"DATABASE_URL", "JWT_SECRET_KEY", "ACCESS_TOKEN_EXPIRE_MINUTES", "CORS_ALLOWED_ORIGINS", "RAG_ENABLED", "RAG_ALLOW_MODEL_DOWNLOAD"})}))
'''
    child = _child_env(
        DATABASE_URL="sqlite:///inherited-parent-db",
        JWT_SECRET_KEY="synthetic-parent-key-only",
        PARENT_PROVIDER_MARKER="synthetic-inherited-provider-only",
        RAG_ENABLED="true",
        RAG_ALLOW_MODEL_DOWNLOAD="true",
    )
    result = subprocess.run(
        [sys.executable, "-c", code, str(LAUNCHER), str(envfile)],
        cwd=tmp_path,
        env=child,
        capture_output=True,
        text=True,
    )
    return result, values


def test_launcher_uses_explicit_env_and_clears_parent_database_and_provider_values(tmp_path):
    result, expected = _invoke_launcher(tmp_path, {})

    assert result.returncode == 0
    report = json.loads(result.stdout)
    assert report["called"] is True
    assert report["host"] == "127.0.0.1"
    assert report["port"] == 18080
    assert report["database"] == expected["DATABASE_URL"]
    assert report["rag"] == "false"
    assert report["parent_marker_present"] is False
    assert report["parent_database_present"] is False


@pytest.mark.parametrize(
    "settings",
    [
        {"DATABASE_URL": ""},
        {"DATABASE_URL": "sqlite:///other-database.sqlite3"},
        {"DATABASE_URL": "sqlite:///health.db?mode=ro"},
        {"RAG_ENABLED": "true"},
        {"RAG_ALLOW_MODEL_DOWNLOAD": "true"},
    ],
)
def test_launcher_fails_closed_for_missing_or_unsafe_local_settings(tmp_path, settings):
    result, _ = _invoke_launcher(tmp_path, settings)

    assert result.returncode == 2
    assert "startup refused" in result.stderr.lower()


def test_removed_settings_import_option_is_rejected(tmp_path):
    result = _prepare(
        tmp_path, "--empty", "--output", tmp_path / "should-not-exist",
        "--settings-from", tmp_path / "synthetic-settings.fixture",
    )

    assert result.returncode == 2
    assert not (tmp_path / "should-not-exist").exists()
