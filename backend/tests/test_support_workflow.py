"""Synthetic support workflow ACL, audit, state-transition, and migration checks."""
from __future__ import annotations

import importlib.util
import io
import json
import sqlite3
import subprocess
import sys
import time
import zipfile
from pathlib import Path

import bcrypt
import jwt
import pytest
from docx import Document
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app


KEY = "support-workflow-test-only-key-2f3a9e6b8c1d4a70"


def _headers(user_id: int):
    now = int(time.time())
    token = jwt.encode({"sub": str(user_id), "ver": 2, "type": "access", "iat": now,
        "exp": now + 900, "iss": "health-new", "aud": "health-new-api"}, KEY, algorithm="HS256")
    return {"Authorization": f"Bearer {token}"}


def _password_hash():
    return bcrypt.hashpw(b"SyntheticPass123", bcrypt.gensalt()).decode("ascii")


@pytest.fixture()
def workflow_client(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", KEY)
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
    engine = create_engine(f"sqlite:///{(tmp_path / 'support.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    with engine.connect() as connection:
        trigger_names = {row[0] for row in connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='trigger'")}
    assert trigger_names == {"support_workflow_events_no_update", "support_workflow_events_no_delete",
        "support_follow_up_events_no_update", "support_follow_up_events_no_delete",
        "operator_account_events_no_update", "operator_account_events_no_delete"}
    sessions = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    with sessions() as db:
        db.add_all([
            models.User(id=101, username="teacher-a", password_hash=_password_hash(), role="teacher", name="Teacher A"),
            models.User(id=102, username="teacher-b", password_hash=_password_hash(), role="teacher", name="Teacher B"),
            models.User(id=103, username="teacher-c", password_hash=_password_hash(), role="teacher", name="Teacher C"),
            models.User(id=201, username="student-a", password_hash=_password_hash(), role="student", name="Student A", student_id="S-A"),
            models.User(id=202, username="student-b", password_hash=_password_hash(), role="student", name="Student B", student_id="S-B"),
            models.User(id=203, username="student-free", password_hash=_password_hash(), role="student", name="Student Free", student_id="S-free"),
        ])
        db.flush()
        db.add_all([models.TeacherStudentAssignment(teacher_id=101, student_id=201),
                    models.TeacherStudentAssignment(teacher_id=102, student_id=202)])
        db.add_all([models.Question(id=301, user_id=201, question_text="synthetic question A"),
                    models.Question(id=302, user_id=202, question_text="synthetic question B"),
                    models.CrisisWarning(id=401, student_id=201, trigger_keyword="synthetic", risk_level="high"),
                    models.CrisisWarning(id=402, student_id=202, trigger_keyword="synthetic", risk_level="high")])
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


def test_questions_are_assignment_scoped_and_answer_has_first_writer_protection(workflow_client):
    client, sessions = workflow_client
    student_a, student_b, student_free = _headers(201), _headers(202), _headers(203)
    teacher_a, teacher_b, teacher_c = _headers(101), _headers(102), _headers(103)
    unassigned = client.post("/api/student/questions/ask", headers=student_free,
                             json={"question_text": "kept without response promise"})
    assert unassigned.status_code == 200
    assert unassigned.json()["response_state"] == "unassigned"
    assert unassigned.json()["assigned_teacher_count"] == 0
    assert client.get("/api/student/questions", headers=student_b).json()[0]["id"] == 302
    assert client.get("/api/teacher/questions", headers=teacher_a).json()["data"][0]["id"] == 301
    assert client.get("/api/teacher/questions", headers=teacher_b).json()["data"][0]["id"] == 302
    assert client.get("/api/teacher/questions", headers=teacher_c).json()["data"] == []
    assert client.get("/api/teacher/questions", headers=student_a).status_code == 403
    with sessions() as db:
        db.get(models.Question, 302).answer_text = ""
        db.commit()
    assert client.post("/api/teacher/questions/302/answer", headers=teacher_a,
                       json={"answer_text": "foreign"}).status_code == 404
    assert client.post("/api/teacher/questions/302/answer", headers=teacher_b,
                       json={"answer_text": "legacy pending row answered"}).status_code == 200
    with sessions() as db:
        db.add(models.TeacherStudentAssignment(teacher_id=103, student_id=201))
        db.commit()
    answer = client.post("/api/teacher/questions/301/answer", headers=teacher_a,
                         json={"answer_text": "synthetic answer"})
    assert answer.status_code == 200
    assert answer.json()["data"]["answered_by"] == "Teacher A"
    assert client.post("/api/teacher/questions/301/answer", headers=teacher_a,
                       json={"answer_text": "overwrite attempt"}).status_code == 409
    assert client.post("/api/teacher/questions/301/answer", headers=teacher_c,
                       json={"answer_text": "competing teacher"}).status_code == 409
    assert client.get("/api/student/questions", headers=student_a).json()[0]["answer_text"] == "synthetic answer"
    with sessions() as db:
        question = db.get(models.Question, 301)
        assert question.status == "answered" and question.answer_text == "synthetic answer"
        event = db.query(models.SupportWorkflowEvent).filter_by(subject_type="question", subject_id=301).one()
        assert event.actor_id == 101 and event.action == "answer" and event.result_text == "synthetic answer"


def test_student_question_input_is_trimmed_and_bounded_before_insert(workflow_client):
    client, sessions = workflow_client
    headers = _headers(203)
    valid = client.post("/api/student/questions", headers=headers,
                        json={"question_text": "  synthetic valid question  "})
    assert valid.status_code == 200
    assert valid.json()["question_text"] == "synthetic valid question"
    with sessions() as db:
        assert db.query(models.Question).filter_by(user_id=203).count() == 1
    for invalid in (" \t\n ", "x" * 2001):
        response = client.post("/api/student/questions/ask", headers=headers,
                               json={"question_text": invalid})
        assert response.status_code == 422
    with sessions() as db:
        assert db.query(models.Question).filter_by(user_id=203).count() == 1


def test_crisis_decisions_require_reason_are_distinct_and_legacy_path_is_audited(workflow_client):
    client, sessions = workflow_client
    teacher_a, teacher_b = _headers(101), _headers(102)
    assert client.post("/api/teacher/crisis/review", headers=teacher_a,
        json={"recordId": "real-401", "action": "maybe", "reason": "test"}).status_code == 422
    assert client.post("/api/teacher/crisis/review", headers=teacher_a,
        json={"recordId": "real-401", "action": "pass", "reason": "  "}).status_code == 422
    assert client.post("/api/teacher/crisis/review", headers=teacher_b,
        json={"recordId": "real-401", "action": "pass", "reason": "foreign"}).status_code == 404
    reviewed = client.post("/api/teacher/crisis/review", headers=teacher_a,
        json={"recordId": "real-401", "action": "escalate", "reason": "synthetic escalation"})
    assert reviewed.status_code == 200 and reviewed.json()["data"]["action"] == "escalate"
    assert client.post("/api/teacher/crisis/review", headers=teacher_a,
        json={"recordId": "real-401", "action": "reject", "reason": "second"}).status_code == 409
    history = client.get("/api/teacher/crisis/401/reviews", headers=teacher_a).json()["data"]
    assert len(history) == 1 and history[0]["action"] == "escalate"
    assert history[0]["reason"] == "synthetic escalation" and history[0]["reviewed_by"] == "Teacher A"
    assert client.post("/api/advanced-teacher/warnings/402/process", headers=teacher_b).status_code == 422
    legacy = client.post("/api/advanced-teacher/warnings/402/process", headers=teacher_b,
        json={"action": "reject", "reason": "synthetic rejection"})
    assert legacy.status_code == 200 and legacy.json()["data"]["action"] == "reject"
    with sessions() as db:
        assert db.get(models.CrisisWarning, 401).status == "processed"
        assert db.get(models.CrisisWarning, 402).status == "processed"
        actions = [row.action for row in db.query(models.SupportWorkflowEvent)
                   .filter_by(subject_type="crisis_warning").order_by(models.SupportWorkflowEvent.id)]
        assert actions == ["escalate", "reject"]


def test_follow_up_source_acl_transitions_and_revoked_assignment(workflow_client):
    client, sessions = workflow_client
    teacher_a, teacher_b, student_a = _headers(101), _headers(102), _headers(201)
    body = {"source_type": "question", "source_id": 301, "student_id": 201,
            "due_at": "2026-10-25T12:00:00Z", "summary": "synthetic follow up"}
    assert client.post("/api/teacher/follow-ups", headers=teacher_b, json=body).status_code == 404
    wrong_source = {**body, "source_id": 302}
    assert client.post("/api/teacher/follow-ups", headers=teacher_a, json=wrong_source).status_code == 404
    created = client.post("/api/teacher/follow-ups", headers=teacher_a, json=body)
    assert created.status_code == 201
    task_id = created.json()["data"]["id"]
    assert client.get("/api/teacher/follow-ups", headers=student_a).status_code == 403
    assert client.post(f"/api/teacher/follow-ups/{task_id}/complete", headers=teacher_a,
                       json={"outcome": "synthetic completed"}).status_code == 200
    assert client.post(f"/api/teacher/follow-ups/{task_id}/cancel", headers=teacher_a,
                       json={"reason": "conflict after complete"}).status_code == 409
    assert client.get("/api/teacher/follow-ups?status=completed", headers=teacher_a).json()["data"][0]["outcome"] == "synthetic completed"
    cancelled = client.post("/api/teacher/follow-ups", headers=teacher_a,
        json={**body, "summary": "synthetic cancellation"})
    cancelled_id = cancelled.json()["data"]["id"]
    cancelled_result = client.post(f"/api/teacher/follow-ups/{cancelled_id}/cancel", headers=teacher_a,
        json={"reason": "synthetic cancellation reason"})
    assert cancelled_result.status_code == 200
    assert cancelled_result.json()["data"]["status"] == "cancelled"
    assert cancelled_result.json()["data"]["outcome"] == "synthetic cancellation reason"
    with sessions() as db:
        task = db.get(models.SupportFollowUp, task_id)
        assert task.status == "completed" and task.outcome == "synthetic completed"
        assert [e.action for e in db.query(models.SupportFollowUpEvent).filter_by(follow_up_id=task_id).order_by(models.SupportFollowUpEvent.id)] == ["created", "completed"]
        db.query(models.TeacherStudentAssignment).filter_by(teacher_id=101, student_id=201).delete()
        db.commit()
    assert client.get("/api/teacher/follow-ups", headers=teacher_a).json()["data"] == []
    assert client.post(f"/api/teacher/follow-ups/{task_id}/complete", headers=teacher_a,
                       json={"outcome": "after revoke"}).status_code == 404


def test_question_assignment_revoked_at_answer_cas_is_denied(workflow_client):
    client, sessions = workflow_client
    with sessions() as db:
        db.add(models.Question(id=303, user_id=201, question_text="synthetic revoke race"))
        db.add(models.TeacherStudentAssignment(teacher_id=103, student_id=201))
        db.commit()
    engine = sessions.kw["bind"]
    state = {"done": False}

    def revoke_before_update(connection, _cursor, statement, _parameters, _context, _executemany):
        if not state["done"] and statement.lstrip().upper().startswith("UPDATE QUESTIONS"):
            state["done"] = True
            connection.exec_driver_sql("DELETE FROM teacher_student_assignments WHERE student_id=201")

    event.listen(engine, "before_cursor_execute", revoke_before_update)
    try:
        response = client.post("/api/teacher/questions/303/answer", headers=_headers(101),
                               json={"answer_text": "must not persist after revoke"})
    finally:
        event.remove(engine, "before_cursor_execute", revoke_before_update)
    assert state["done"] is True
    assert response.status_code == 409
    with sessions() as db:
        assert db.get(models.Question, 303).answer_text is None


def test_follow_up_assignment_revoked_before_insert_is_denied(workflow_client):
    client, sessions = workflow_client
    engine = sessions.kw["bind"]
    state = {"done": False}

    def revoke_before_insert(connection, _cursor, statement, _parameters, _context, _executemany):
        if not state["done"] and statement.lstrip().upper().startswith("INSERT INTO SUPPORT_FOLLOW_UPS"):
            state["done"] = True
            connection.exec_driver_sql("DELETE FROM teacher_student_assignments WHERE teacher_id=101 AND student_id=201")

    event.listen(engine, "before_cursor_execute", revoke_before_insert)
    try:
        response = client.post("/api/teacher/follow-ups", headers=_headers(101), json={
            "source_type": "question", "source_id": 301, "student_id": 201,
            "due_at": "2026-10-25T12:00:00+08:00", "summary": "synthetic insert race"})
    finally:
        event.remove(engine, "before_cursor_execute", revoke_before_insert)
    assert state["done"] is True
    assert response.status_code == 404
    with sessions() as db:
        assert db.query(models.SupportFollowUp).count() == 0


def test_follow_up_requires_utc_offset_and_nonblank_summary(workflow_client):
    client, _ = workflow_client
    body = {"source_type": "question", "source_id": 301, "student_id": 201,
            "due_at": "2026-10-25T12:00:00", "summary": "synthetic"}
    assert client.post("/api/teacher/follow-ups", headers=_headers(101), json=body).status_code == 422
    assert client.post("/api/teacher/follow-ups", headers=_headers(101),
        json={**body, "due_at": "2026-10-25T12:00:00Z", "summary": "   "}).status_code == 422
    created = client.post("/api/teacher/follow-ups", headers=_headers(101),
        json={**body, "due_at": "2026-10-25T12:00:00+08:00", "summary": "synthetic"})
    assert created.status_code == 201
    assert created.json()["data"]["due_at"] == "2026-10-25T04:00:00Z"


def test_individual_docx_is_assigned_and_contains_only_one_student(workflow_client):
    client, _ = workflow_client
    teacher_a, teacher_b = _headers(101), _headers(102)
    own = client.get("/api/advanced-teacher/students/201/export/docx", headers=teacher_a)
    assert own.status_code == 200
    text = "\n".join(p.text for p in Document(io.BytesIO(own.content)).paragraphs)
    assert "Student A" in text and "S-A" in text and "Student B" not in text and "S-B" not in text
    foreign = client.get("/api/advanced-teacher/students/202/export/docx", headers=teacher_a)
    assert foreign.status_code == 404
    teacher_b_doc = client.get("/api/advanced-teacher/students/202/export/docx", headers=teacher_b)
    assert teacher_b_doc.status_code == 200
    teacher_b_text = "\n".join(p.text for p in Document(io.BytesIO(teacher_b_doc.content)).paragraphs)
    assert "Student B" in teacher_b_text and "Student A" not in teacher_b_text


def test_offline_support_migration_is_idempotent_and_preserves_existing_rows(tmp_path):
    migration_path = Path(__file__).parents[1] / "scripts" / "migrate-support-workflow.py"
    spec = importlib.util.spec_from_file_location("support_migration_test", migration_path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    db_path = tmp_path / "migration.sqlite3"
    raw = __import__("sqlite3").connect(db_path)
    raw.executescript("""
      CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR(20) NOT NULL);
      CREATE TABLE questions (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), question_text TEXT, answer_text TEXT, status VARCHAR(20));
      CREATE TABLE crisis_warnings (id INTEGER PRIMARY KEY, student_id INTEGER REFERENCES users(id), status VARCHAR(20), processed_at DATETIME, processed_by INTEGER);
      CREATE TABLE teacher_student_assignments (id INTEGER PRIMARY KEY, teacher_id INTEGER REFERENCES users(id), student_id INTEGER REFERENCES users(id), assigned_at DATETIME, UNIQUE(teacher_id,student_id));
      INSERT INTO users VALUES (7,'student');
      INSERT INTO questions VALUES (9,7,'synthetic old question',NULL,'pending');
    """)
    before = raw.execute("SELECT * FROM questions").fetchall()
    assert migration.migrate(raw, "upgrade")["changed"] is True
    # Simulate an earlier three-table support deployment before the incremental
    # account-lifecycle extension; the operator explicitly adds the last two.
    raw.executescript("""
      DROP TRIGGER operator_account_events_no_update;
      DROP TRIGGER operator_account_events_no_delete;
      DROP TABLE operator_account_events;
      DROP TABLE user_access_states;
    """)
    assert migration.migrate(raw, "check")["exists"] is False
    assert migration.migrate(raw, "upgrade")["changed"] is True
    assert migration.migrate(raw, "upgrade")["changed"] is False
    check = migration.migrate(raw, "check")
    assert check["exists"] is True and check["append_only"] is True and check["changed"] is False
    assert set(check["tables"]) == set(migration.NEW_TABLES)
    assert raw.execute("SELECT * FROM questions").fetchall() == before
    raw.execute("INSERT INTO support_workflow_events(subject_type,subject_id,student_id,action) VALUES ('question',9,7,'answer')")
    with pytest.raises(Exception, match="append-only"):
        raw.execute("UPDATE support_workflow_events SET action='changed'")
    raw.commit()
    raw.execute("DROP TRIGGER support_workflow_events_no_update")
    assert migration.migrate(raw, "check")["append_only"] is False
    assert migration.migrate(raw, "upgrade")["changed"] is True
    assert migration.migrate(raw, "check")["append_only"] is True
    raw.close()


def test_missing_workflow_schema_returns_sanitized_503(tmp_path, monkeypatch):
    monkeypatch.setenv("JWT_SECRET_KEY", KEY)
    engine = create_engine(f"sqlite:///{(tmp_path / 'old-schema.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine, tables=[models.User.__table__,
        models.TeacherStudentAssignment.__table__, models.Question.__table__])
    sessions = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    with sessions() as db:
        db.add(models.User(id=501, username="old-teacher", password_hash=_password_hash(), role="teacher"))
        db.commit()
    previous = dict(app.dependency_overrides)

    def override_get_db():
        with sessions() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            response = client.get("/api/teacher/questions", headers=_headers(501))
        assert response.status_code == 503
        assert response.json() == {"detail": "Authentication is temporarily unavailable"}
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def test_missing_append_only_trigger_fails_closed(workflow_client):
    client, sessions = workflow_client
    with sessions() as db:
        db.connection().exec_driver_sql("DROP TRIGGER support_workflow_events_no_update")
        db.commit()
    response = client.get("/api/teacher/questions", headers=_headers(101))
    assert response.status_code == 503
    assert response.json() == {"detail": "Support workflow schema is not enabled"}


def test_migration_cli_backs_up_before_upgrade_and_refuses_symlink_target(tmp_path):
    migration_path = Path(__file__).parents[1] / "scripts" / "migrate-support-workflow.py"
    database = tmp_path / "operator-selected.sqlite3"
    backup = tmp_path / "new-backup.sqlite3"
    with sqlite3.connect(database) as db:
        db.executescript("""
          CREATE TABLE users (id INTEGER PRIMARY KEY, role VARCHAR(20) NOT NULL);
          CREATE TABLE questions (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), question_text TEXT, answer_text TEXT, status VARCHAR(20));
          CREATE TABLE crisis_warnings (id INTEGER PRIMARY KEY, student_id INTEGER REFERENCES users(id), status VARCHAR(20), processed_at DATETIME, processed_by INTEGER);
          CREATE TABLE teacher_student_assignments (id INTEGER PRIMARY KEY, teacher_id INTEGER REFERENCES users(id), student_id INTEGER REFERENCES users(id), assigned_at DATETIME, UNIQUE(teacher_id,student_id));
          INSERT INTO users VALUES (8,'student');
          INSERT INTO questions VALUES (10,8,'old synthetic question',NULL,'pending');
        """)
    result = subprocess.run([sys.executable, str(migration_path), "--database", str(database),
        "--backup", str(backup), "upgrade"], capture_output=True, text=True, check=False)
    assert result.returncode == 0
    upgraded = json.loads(result.stdout)
    assert upgraded["exists"] is True and upgraded["append_only"] is True and upgraded["changed"] is True
    assert len(upgraded["tables"]) == 5
    with sqlite3.connect(backup) as saved:
        assert saved.execute("SELECT question_text FROM questions WHERE id=10").fetchone()[0] == "old synthetic question"
        assert saved.execute("SELECT name FROM sqlite_master WHERE name='support_workflow_events'").fetchone() is None

    protected = tmp_path / "protected-marker.txt"
    protected.write_text("keep", encoding="utf-8")
    link = tmp_path / "backup-link.sqlite3"
    try:
        link.symlink_to(protected)
    except OSError:
        pytest.skip("Symlink creation is unavailable in this Windows environment")
    refused = subprocess.run([sys.executable, str(migration_path), "--database", str(database),
        "--backup", str(link), "upgrade"], capture_output=True, text=True, check=False)
    assert refused.returncode == 2
    assert protected.read_text(encoding="utf-8") == "keep"
    assert "keep" not in refused.stderr


def _load_account_cli():
    cli_path = Path(__file__).parents[1] / "scripts" / "manage-teacher-accounts.py"
    spec = importlib.util.spec_from_file_location("teacher_account_cli_test", cli_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _account_cli_args(operation, username, **extra):
    from types import SimpleNamespace
    return SimpleNamespace(operation=operation, username=username, operator="Synthetic Operator",
                           reason="synthetic approved account action", **extra)


def test_teacher_account_cli_create_refuses_promotion_and_keeps_password_out_of_audit(workflow_client, monkeypatch):
    _, sessions = workflow_client
    cli = _load_account_cli()
    synthetic_password = "SyntheticPass123"
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: synthetic_password)
    db_path = Path(sessions.kw["bind"].url.database)
    with sqlite3.connect(db_path) as raw:
        raw.execute("BEGIN IMMEDIATE")
        with pytest.raises(ValueError, match="already exists"):
            cli._create_teacher(raw, _account_cli_args("create-teacher", "student-a", name="Wrong"))
        assert raw.execute("SELECT role FROM users WHERE username='student-a'").fetchone()[0] == "student"
        created = cli._create_teacher(raw, _account_cli_args("create-teacher", "teacher-new", name="Synthetic Teacher"))
        raw.commit()
        assert created["username"] == "teacher-new"
        user_id = created["user_id"]
        stored_hash = raw.execute("SELECT password_hash FROM users WHERE id=?", (user_id,)).fetchone()[0]
        assert bcrypt.checkpw(synthetic_password.encode(), stored_hash.encode())
        audit = raw.execute("SELECT operator_name,action,reason FROM operator_account_events WHERE target_user_id=?",
                            (user_id,)).fetchone()
        assert audit == ("Synthetic Operator", "create_teacher", "synthetic approved account action")
        dump = " ".join(str(value) for value in audit)
        assert synthetic_password not in dump and stored_hash not in dump


def test_teacher_disable_revokes_old_tokens_and_enable_does_not_restore_them(workflow_client, tmp_path):
    client, sessions = workflow_client
    db_path = Path(sessions.kw["bind"].url.database)
    cli_path = Path(__file__).parents[1] / "scripts" / "manage-teacher-accounts.py"
    backup = tmp_path / "account-backup.sqlite3"

    def operate(action, backup_path):
        return subprocess.run([sys.executable, str(cli_path), "--database", str(db_path), "--backup",
            str(backup_path), "--operator", "Synthetic Operator", "--reason", "synthetic disable/enable check",
            action, "--username", "teacher-a"], capture_output=True, text=True, check=False)

    old_token = _headers(101)
    disabled = operate("disable-teacher", backup)
    assert disabled.returncode == 0, disabled.stderr
    assert client.get("/api/me", headers=old_token).status_code == 401
    assert client.post("/api/login", json={"username": "teacher-a", "password": "SyntheticPass123"}).status_code == 401
    with sessions() as db:
        state = db.get(models.UserAccessState, 101)
        assert state.disabled is True and state.auth_epoch == 1
        assert db.query(models.TeacherStudentAssignment).filter_by(teacher_id=101).count() == 0
        assert [row.action for row in db.query(models.OperatorAccountEvent).filter_by(target_user_id=101)
                .order_by(models.OperatorAccountEvent.id)] == ["disable_teacher"]
    enabled = operate("enable-teacher", tmp_path / "enable-backup.sqlite3")
    assert enabled.returncode == 0, enabled.stderr
    assert client.get("/api/me", headers=old_token).status_code == 401
    login = client.post("/api/login", json={"username": "teacher-a", "password": "SyntheticPass123"})
    assert login.status_code == 200
    new_token = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/me", headers=new_token).status_code == 200
    with sessions() as db:
        state = db.get(models.UserAccessState, 101)
        assert state.disabled is False and state.auth_epoch == 1
        assert db.query(models.TeacherStudentAssignment).filter_by(teacher_id=101).count() == 0
        assert [row.action for row in db.query(models.OperatorAccountEvent).filter_by(target_user_id=101)
                .order_by(models.OperatorAccountEvent.id)] == ["disable_teacher", "enable_teacher"]
    with sqlite3.connect(backup) as saved:
        assert saved.execute("SELECT role FROM users WHERE id=101").fetchone()[0] == "teacher"
        assert saved.execute("SELECT count(*) FROM operator_account_events").fetchone()[0] == 0
