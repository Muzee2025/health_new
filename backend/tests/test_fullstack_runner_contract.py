"""Exercise the frozen full-stack runner contracts against a fresh SQLite app."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app


ROOT = Path(__file__).resolve().parents[2]
RUNNER_PATH = ROOT / "scripts" / "verify-fullstack.py"
BACKUP_SCRIPT = ROOT / "scripts" / "backup-restore-database.py"
SPEC = importlib.util.spec_from_file_location("verify_fullstack_contract", RUNNER_PATH)
verify_fullstack = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(verify_fullstack)


def _readonly_counts(path: Path, username: str, marker: str, second: str) -> dict:
    connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        return {
            "quick_check": connection.execute("PRAGMA quick_check").fetchone()[0],
            "tables": connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchone()[0],
            "triggers": connection.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='trigger'"
            ).fetchone()[0],
            "foreign_key_violations": sum(1 for _ in connection.execute("PRAGMA foreign_key_check")),
            "old_question": connection.execute(
                "SELECT count(*) FROM questions q JOIN users u ON u.id=q.user_id "
                "WHERE u.username=? AND q.question_text=?", (username, marker)
            ).fetchone()[0],
            "second_question": connection.execute(
                "SELECT count(*) FROM questions q JOIN users u ON u.id=q.user_id "
                "WHERE u.username=? AND q.question_text=?", (username, second)
            ).fetchone()[0],
        }
    finally:
        connection.close()


def test_runner_http_and_backup_restore_against_real_testclient_and_sqlite(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", "W3-contract-fake-key-7a3c9d5e1f0b2468")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    monkeypatch.setenv("RAG_ENABLED", "false")
    database = tmp_path / "runner-contract.sqlite3"
    engine = create_engine(f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    assert len(Base.metadata.tables) == 27
    with engine.connect() as connection:
        assert connection.execute(
            __import__("sqlalchemy").text("SELECT count(*) FROM sqlite_master WHERE type='trigger'")
        ).scalar_one() == 6
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    previous = dict(app.dependency_overrides)

    def isolated_get_db():
        with sessions() as session:
            yield session

    app.dependency_overrides[get_db] = isolated_get_db
    client = TestClient(app)
    runner = verify_fullstack.Runner(ROOT, port=4188, timeout=10, run=True)
    original_request = runner.request

    def testclient_request(method, path, payload=None, token=None):
        if path == "/":
            return 200, "text/html", b'<html><script type="module" src="/assets/qa.js"></script></html>'
        if path == "/assets/qa.js":
            return 200, "application/javascript", b"export const qa = true;"
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        response = client.request(method, path, json=payload, headers=headers)
        return response.status_code, response.headers.get("content-type", ""), response.content

    runner.request = testclient_request
    try:
        with client:
            result = runner.http_smoke()
        assert result["health_ready"] is True
        assert result["registration"] and result["login"]
        assert result["me_role"] == "student"
        assert result["teacher_registration_422"] and result["teacher_route_403"]
        assert result["unassigned_question_200"] and result["blank_question_422"]

        live = database
        backup = tmp_path / f"{runner.project}-backup.db"
        restored = tmp_path / f"{runner.project}-restored.db"
        marker = runner.summary["synthetic"]["message_marker"]
        username = runner.summary["synthetic"]["username"]

        def execute_container_script(script: str, name: str) -> str:
            # Translate only the fixed container paths to this test's fresh DB
            # files and the real repository backup utility, then run the exact
            # generated Python body with the selected interpreter. No Docker.
            translated = script.replace(
                "/var/lib/health-new/database/health.db", live.as_posix()
            ).replace(
                f"/var/lib/health-new/database/{runner.project}-backup.db", backup.as_posix()
            ).replace(
                f"/var/lib/health-new/database/{runner.project}-restored.db", restored.as_posix()
            )
            translated = translated.replace(
                '"python","scripts/backup-restore-database.py"',
                f"{sys.executable!r},{str(BACKUP_SCRIPT)!r}",
            )
            child_env = {key: value for key, value in os.environ.items()
                         if key.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOME"}}
            completed = subprocess.run(
                [sys.executable, "-c", translated], cwd=tmp_path, env=child_env,
                capture_output=True, text=True, timeout=30, shell=False,
            )
            assert completed.returncode == 0, f"generated backup/restore script failed (exit {completed.returncode})"
            return completed.stdout

        runner.exec_python = execute_container_script
        backup_summary = runner.backup_restore()
        assert backup_summary["tables"] == 27
        assert backup_summary["triggers"] == 6
        assert backup_summary["quick_check"] == "ok"
        assert backup_summary["foreign_key_violations"] == 0
        assert backup_summary["backup_kept_original_message"] is True
        assert backup_summary["backup_excludes_second_message"] is True
        assert backup_summary["runtime_kept_second_message"] is True
        assert backup.is_file() and restored.is_file()

        second = "qa-second-" + runner.project
        live_counts = _readonly_counts(live, username, marker, second)
        restored_counts = _readonly_counts(restored, username, marker, second)
        assert live_counts == {"quick_check": "ok", "tables": 27, "triggers": 6,
                               "foreign_key_violations": 0, "old_question": 1, "second_question": 1}
        assert restored_counts == {"quick_check": "ok", "tables": 27, "triggers": 6,
                                   "foreign_key_violations": 0, "old_question": 1, "second_question": 0}
    finally:
        runner.request = original_request
        client.close()
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()
