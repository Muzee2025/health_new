"""Explicit teacher/student ACL and offline operator-tool checks."""
from __future__ import annotations

import asyncio
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

import bcrypt
import jwt
import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.websocket_manager import ConnectionManager  # noqa: E402

KEY = "W2-security-test-only-key-7f41a2d9c03e8b65"


def _token(user_id: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "ver": 2, "type": "access", "iat": now,
                       "exp": now + 900, "iss": "health-new", "aud": "health-new-api"},
                      KEY, algorithm="HS256")


def _headers(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {_token(user_id)}"}


def _hash():
    return bcrypt.hashpw(b"SyntheticPass123", bcrypt.gensalt()).decode("ascii")


@pytest.fixture()
def acl_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", KEY)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    engine = create_engine(f"sqlite:///{(tmp_path / 'acl.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with sessions() as db:
        db.add_all([
            models.User(id=101, username="teacher-a", password_hash=_hash(), role="teacher", name="Teacher A"),
            models.User(id=102, username="teacher-b", password_hash=_hash(), role="teacher", name="Teacher B"),
            models.User(id=103, username="teacher-unassigned", password_hash=_hash(), role="teacher", name="Teacher C"),
            models.User(id=201, username="student-a", password_hash=_hash(), role="student", name="Student A", student_id="S-A"),
            models.User(id=202, username="student-b", password_hash=_hash(), role="student", name="Student B", student_id="S-B"),
        ])
        db.flush()
        db.add_all([models.TeacherStudentAssignment(teacher_id=101, student_id=201),
                    models.TeacherStudentAssignment(teacher_id=102, student_id=202)])
        db.add_all([
            models.TeacherProfile(user_id=101, title="Counselor", time_slots='["A-slot"]'),
            models.TeacherProfile(user_id=102, title="Counselor", time_slots='["B-slot"]'),
            models.TeacherProfile(user_id=103, title="Counselor", time_slots='["C-slot"]'),
            models.Appointment(student_id=201, teacher_id=101, time_slot="A-slot"),
            models.Appointment(student_id=202, teacher_id=102, time_slot="B-slot"),
            models.InterventionRecord(student_id=201, teacher_id=101, record_date="2026-10-22", notes="scope-A"),
            models.InterventionRecord(student_id=202, teacher_id=102, record_date="2026-10-22", notes="scope-B"),
            models.CrisisWarning(student_id=201, trigger_keyword="synthetic-a", risk_level="high", status="pending"),
            models.CrisisWarning(student_id=202, trigger_keyword="synthetic-b", risk_level="high", status="pending"),
        ])
        db.commit()

    previous = dict(app.dependency_overrides)

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client, sessions
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def test_assignment_acl_filters_routes_and_allows_only_assigned_booking(acl_client):
    client, sessions = acl_client
    student_a, student_b = _headers(201), _headers(202)
    teacher_a, teacher_b, teacher_c = _headers(101), _headers(102), _headers(103)

    teachers_a = {item["id"]: item for item in client.get("/api/student/teachers", headers=student_a).json()}
    teachers_b = {item["id"]: item for item in client.get("/api/student/teachers", headers=student_b).json()}
    assert teachers_a[101]["can_book"] is True and teachers_a[102]["can_book"] is False
    assert teachers_b[102]["can_book"] is True and teachers_b[101]["can_book"] is False
    assert teachers_a[103]["can_book"] is teachers_b[103]["can_book"] is False
    assert client.post("/api/student/appointments", headers=student_a,
                       json={"teacher_id": 102, "time_slot": "B-slot"}).status_code == 403
    assert client.post("/api/student/appointments", headers=student_a,
                       json={"teacher_id": 101, "time_slot": "A-next"}).status_code == 200

    for teacher_id, expected_student, foreign_student in ((101, 201, 202), (102, 202, 201), (103, None, 201)):
        headers = _headers(teacher_id)
        students = client.get("/api/teacher/students", headers=headers)
        assert students.status_code == 200
        assert {row["id"] for row in students.json()} == ({expected_student} if expected_student else set())
        if expected_student:
            assert client.get(f"/api/teacher/student/{expected_student}", headers=headers).status_code == 200
        assert client.get(f"/api/teacher/student/{foreign_student}", headers=headers).status_code == 404

    own = client.get("/api/teacher/appointments", headers=teacher_a).json()
    assert len(own) == 2 and all(row["teacher_id"] == 101 and row["student_name"] == "Student A" for row in own)
    assert client.get("/api/teacher/appointments", headers=teacher_c).json() == []
    with sessions() as db:
        foreign_appointment = db.query(models.Appointment.id).filter_by(student_id=202).scalar()
    assert client.post(f"/api/teacher/appointments/{foreign_appointment}/status?status=completed",
                       headers=teacher_a).status_code == 404

    interventions = client.get("/api/teacher/interventions", headers=teacher_a).json()
    assert [row["notes"] for row in interventions] == ["scope-A"]
    assert client.post("/api/teacher/interventions", headers=teacher_a,
                       json={"student_id": 202, "record_date": "2026-10-22", "notes": "cross"}).status_code == 404
    assert client.post("/api/teacher/interventions", headers=teacher_a,
                       json={"student_id": 201, "record_date": "2026-10-22", "notes": "own-new"}).status_code == 200

    pending = client.get("/api/teacher/crisis/pending", headers=teacher_a).json()["data"]["items"]
    assert {row.get("studentId") for row in pending} == {"S-A"}
    warnings_a = client.get("/api/advanced-teacher/warnings", headers=teacher_a).json()["data"]
    warnings_b = client.get("/api/advanced-teacher/warnings", headers=teacher_b).json()["data"]
    assert {row["student_id"] for row in warnings_a} == {201}
    assert {row["student_id"] for row in warnings_b} == {202}
    assert client.get("/api/advanced-teacher/dashboard/metrics", headers=teacher_a).json()["realtime_stats"]["uv"] == 1
    assert client.get("/api/advanced-teacher/audit/list", headers=teacher_a).json()["data"][0]["student_info"]["id"] == 201
    foreign_warning = warnings_b[0]["id"]
    assert client.post(f"/api/advanced-teacher/warnings/{foreign_warning}/process", headers=teacher_a,
                       json={"action": "pass", "reason": "Synthetic human review"}).status_code == 404
    own_warning = warnings_a[0]["id"]
    assert client.post(f"/api/advanced-teacher/warnings/{own_warning}/process", headers=teacher_a,
                       json={"action": "pass", "reason": "Synthetic human review"}).status_code == 200

    response = client.post("/api/advanced-teacher/export/compliance-report", headers=teacher_a, json={})
    assert response.status_code == 200
    exported = Document(io.BytesIO(response.content))
    export_text = "\n".join(p.text for p in exported.paragraphs)
    assert "Student A" in export_text and "Student B" not in export_text


def test_teacher_created_student_is_assigned_to_creator(acl_client):
    client, sessions = acl_client
    response = client.post("/api/teacher/students", headers=_headers(103), json={
        "name": "Created Synthetic", "student_id": "S-CREATED", "initial_password": "NewStudentPass123",
    })
    assert response.status_code == 200
    student_id = response.json()["id"]
    with sessions() as db:
        assert db.query(models.TeacherStudentAssignment).filter_by(teacher_id=103, student_id=student_id).count() == 1
    assert client.get(f"/api/teacher/student/{student_id}", headers=_headers(103)).status_code == 200


class _Socket:
    def __init__(self):
        self.messages = []

    async def send_text(self, text):
        self.messages.append(json.loads(text))


def test_websocket_teacher_broadcast_uses_explicit_assignments(acl_client):
    _, sessions = acl_client
    manager = ConnectionManager()
    sockets = {teacher_id: _Socket() for teacher_id in (101, 102, 103)}
    manager.teacher_connections = {teacher_id: [socket] for teacher_id, socket in sockets.items()}
    with sessions() as db:
        asyncio.run(manager.broadcast_to_teachers({"type": "student_update", "student_id": 201}, db=db, student_id=201))
    assert sockets[101].messages == [{"type": "student_update", "student_id": 201}]
    assert sockets[102].messages == sockets[103].messages == []


def _load_script(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _invoke_cli(module, monkeypatch, argv):
    monkeypatch.setattr(sys, "argv", [module.__file__, *map(str, argv)])
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        module.main()
    return json.loads(out.getvalue())


def test_offline_migration_is_idempotent_and_downgrade_refuses_data(tmp_path):
    migration = _load_script(Path(__file__).parents[1] / "migrations" / "20261022-student-assignments.py",
                            f"migration_{uuid.uuid4().hex}")
    database = tmp_path / "operator.sqlite3"
    import sqlite3
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.commit()
    with sqlite3.connect(database) as connection:
        assert migration.migrate(connection, "upgrade")["changed"] is True
        assert migration.migrate(connection, "upgrade")["changed"] is False
        assert migration.migrate(connection, "check") == {"exists": True, "rows": 0, "changed": False}
        connection.execute("INSERT INTO users(id) VALUES (1), (2)")
        connection.execute("INSERT INTO teacher_student_assignments(teacher_id,student_id) VALUES (1,2)")
        connection.commit()
        with pytest.raises(ValueError, match="not empty"):
            migration.migrate(connection, "downgrade")
        assert migration.table_exists(connection)
        connection.execute("DELETE FROM teacher_student_assignments")
        connection.commit()
        assert migration.migrate(connection, "downgrade")["changed"] is True
        assert migration.migrate(connection, "downgrade")["changed"] is False


def test_operator_cli_is_idempotent_rejects_role_mix_and_revokes(tmp_path, monkeypatch):
    cli = _load_script(Path(__file__).parents[1] / "scripts" / "manage-student-assignments.py",
                       f"assign_cli_{uuid.uuid4().hex}")
    database = tmp_path / "operator-cli.sqlite3"
    import sqlite3
    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, role TEXT NOT NULL)")
        connection.execute("CREATE TABLE teacher_student_assignments (id INTEGER PRIMARY KEY, teacher_id INTEGER NOT NULL REFERENCES users(id), student_id INTEGER NOT NULL REFERENCES users(id), assigned_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(teacher_id,student_id))")
        connection.execute("INSERT INTO users(id,role) VALUES (101,'teacher'),(201,'student'),(102,'student')")
        connection.commit()
    assert _invoke_cli(cli, monkeypatch, ["--database", database, "grant", "--teacher-id", 101, "--student-id", 201])["changed"] is True
    assert _invoke_cli(cli, monkeypatch, ["--database", database, "grant", "--teacher-id", 101, "--student-id", 201])["changed"] is False
    with pytest.raises(SystemExit) as wrong_role:
        _invoke_cli(cli, monkeypatch, ["--database", database, "grant", "--teacher-id", 102, "--student-id", 201])
    assert wrong_role.value.code == 2
    assert _invoke_cli(cli, monkeypatch, ["--database", database, "revoke", "--teacher-id", 101, "--student-id", 201])["changed"] is True
    assert _invoke_cli(cli, monkeypatch, ["--database", database, "revoke", "--teacher-id", 101, "--student-id", 201])["changed"] is False


def _isolated_child_env(tmp_path: Path, database: Path) -> dict[str, str]:
    env = {
        "PATH": os.environ.get("PATH", ""),
        "SYSTEMROOT": os.environ.get("SYSTEMROOT", ""),
        "WINDIR": os.environ.get("WINDIR", ""),
        "TEMP": str(tmp_path),
        "TMP": str(tmp_path),
        "PYTHONPATH": str(Path(__file__).parents[1]),
        "PYTHON_DOTENV_DISABLED": "1",
        "DATABASE_URL": "sqlite:///" + database.as_posix(),
        "RAG_ENABLED": "false",
        "RAG_ALLOW_MODEL_DOWNLOAD": "false",
        "CHROMA_DIR": str(tmp_path / "chroma"),
        "JWT_SECRET_KEY": "w2-import-child-test-secret-3f67b19c",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "30",
        "CORS_ALLOWED_ORIGINS": "http://127.0.0.1:5173",
        "PYTHONUTF8": "1",
    }
    return {key: value for key, value in env.items() if value}


def test_importing_main_in_child_does_not_connect_or_create_database(tmp_path):
    database = tmp_path / "import-must-not-create.sqlite3"
    code = (
        "import os, socket, sys\n"
        "def deny_network(event, args):\n"
        "    if event in {'socket.connect', 'socket.getaddrinfo'}: raise RuntimeError('network blocked in import probe')\n"
        "sys.addaudithook(deny_network)\n"
        "import sys; sys.path.insert(0, os.environ['PYTHONPATH'])\n"
        "import app.main\n"
        "from app.database import engine\n"
        "from pathlib import Path\n"
        "target = Path(engine.url.database).resolve()\n"
        "assert target == Path(os.environ['EXPECTED_DB']).resolve()\n"
        "assert not target.exists()\n"
        "print('main-import-ok; database-created=false')\n"
    )
    env = _isolated_child_env(tmp_path, database)
    env["EXPECTED_DB"] = str(database)
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=env,
                            capture_output=True, text=True, timeout=45, check=False)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "main-import-ok; database-created=false"
    assert not database.exists()


def test_empty_database_initializer_creates_only_new_file_and_preserves_existing(tmp_path):
    script = Path(__file__).parents[1] / "scripts" / "init-empty-database.py"
    env = _isolated_child_env(tmp_path, tmp_path / "explicit-temp.sqlite3")

    new_db = tmp_path / "fresh.sqlite3"
    created = subprocess.run([sys.executable, str(script), "--database", str(new_db)],
                             cwd=tmp_path, env=env, capture_output=True, text=True,
                             timeout=45, check=False)
    assert created.returncode == 0, created.stderr
    assert created.stdout.strip() == "Created a new empty SQLite schema; no existing database was opened"
    import sqlite3
    with sqlite3.connect(f"file:{new_db.as_posix()}?mode=ro", uri=True) as connection:
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "teacher_student_assignments"} <= tables

    empty_existing = tmp_path / "already-empty.sqlite3"
    empty_existing.touch()
    empty_hash = __import__("hashlib").sha256(empty_existing.read_bytes()).hexdigest()
    refused_empty = subprocess.run([sys.executable, str(script), "--database", str(empty_existing)],
                                   cwd=tmp_path, env=env, capture_output=True, text=True,
                                   timeout=45, check=False)
    assert refused_empty.returncode == 2
    assert __import__("hashlib").sha256(empty_existing.read_bytes()).hexdigest() == empty_hash
    assert empty_existing.stat().st_size == 0

    existing_schema = tmp_path / "already-schema.sqlite3"
    with sqlite3.connect(existing_schema) as connection:
        connection.execute("CREATE TABLE preserved (id INTEGER PRIMARY KEY, marker TEXT NOT NULL)")
        connection.execute("INSERT INTO preserved(marker) VALUES ('synthetic')")
        connection.commit()
    schema_hash = __import__("hashlib").sha256(existing_schema.read_bytes()).hexdigest()
    refused_schema = subprocess.run([sys.executable, str(script), "--database", str(existing_schema)],
                                    cwd=tmp_path, env=env, capture_output=True, text=True,
                                    timeout=45, check=False)
    assert refused_schema.returncode == 2
    assert __import__("hashlib").sha256(existing_schema.read_bytes()).hexdigest() == schema_hash
    with sqlite3.connect(f"file:{existing_schema.as_posix()}?mode=ro", uri=True) as connection:
        assert connection.execute("SELECT marker FROM preserved").fetchone() == ("synthetic",)
