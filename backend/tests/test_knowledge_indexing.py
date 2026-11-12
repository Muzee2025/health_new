"""Knowledge base write path: SQL row and optional vector index must not diverge.

The service layer is already covered by test_rag_optional.py; these tests cover the
endpoint, which previously committed the row and then called the index without
checking its result, so a disabled or failing index left a silent half-write.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers import teacher
from app.routers.auth import get_current_user


@pytest.fixture()
def knowledge_client(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_ENABLED", "false")
    engine = create_engine(f"sqlite:///{(tmp_path / 'knowledge.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    actor = models.User(id=7201, username="synthetic-knowledge-teacher", role="teacher",
                        password_hash="not-a-login-credential")
    with sessions() as db:
        db.add(actor)
        db.commit()
    identity = {"role": "teacher"}

    def current_user():
        return models.User(id=7201, username="synthetic-knowledge-teacher", role=identity["role"])

    def database():
        with sessions() as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    try:
        with TestClient(app) as client:
            yield client, sessions, identity
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def _rows(sessions):
    with sessions() as db:
        return db.query(models.KnowledgeBase).count()


def test_disabled_index_still_commits_without_calling_it(knowledge_client, monkeypatch):
    """RAG off is the state of every current deployment: behaviour must not change."""
    client, sessions, _ = knowledge_client
    calls = []
    monkeypatch.setattr(teacher, "add_document_to_rag", lambda *a: calls.append(a) or True)
    monkeypatch.setattr(teacher, "delete_document_from_rag", lambda *a: calls.append(a) or True)

    created = client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"})
    assert created.status_code == 200
    assert _rows(sessions) == 1
    assert calls == [], "a disabled index must not be invoked at all"

    deleted = client.delete(f"/api/teacher/knowledge/{created.json()['id']}")
    assert deleted.status_code == 200
    assert _rows(sessions) == 0
    assert calls == []


def test_enabled_index_failure_rolls_back_and_reports_503(knowledge_client, monkeypatch):
    """A refused index must not leave a row that has no vectors."""
    client, sessions, _ = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setattr(teacher, "add_document_to_rag", lambda *a: False)

    response = client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"})
    assert response.status_code == 503
    assert "index" in response.json()["detail"].lower()
    assert _rows(sessions) == 0, "the rolled-back row must not survive"


def test_enabled_index_success_commits_the_row(knowledge_client, monkeypatch):
    client, sessions, _ = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    seen = {}

    def record(doc_id, title, content):
        seen.update(id=doc_id, title=title, content=content)
        return True

    monkeypatch.setattr(teacher, "add_document_to_rag", record)

    response = client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"})
    assert response.status_code == 200
    assert _rows(sessions) == 1
    # The row must already have its primary key when the index is written, and the
    # index must receive the same values that were persisted.
    assert seen["id"] == response.json()["id"]
    assert (seen["title"], seen["content"]) == ("Synthetic", "Synthetic body")


def test_enabled_index_removal_failure_keeps_the_row(knowledge_client, monkeypatch):
    """Vectors that survive a deleted row stay retrievable, so the row is kept."""
    client, sessions, _ = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    monkeypatch.setattr(teacher, "add_document_to_rag", lambda *a: True)
    monkeypatch.setattr(teacher, "delete_document_from_rag", lambda *a: False)

    created = client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"})
    assert created.status_code == 200
    response = client.delete(f"/api/teacher/knowledge/{created.json()['id']}")
    assert response.status_code == 503
    assert _rows(sessions) == 1, "the row must stay visible and retryable"


def test_enabled_index_removal_success_deletes_the_row(knowledge_client, monkeypatch):
    client, sessions, _ = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    removed = []
    monkeypatch.setattr(teacher, "add_document_to_rag", lambda *a: True)
    monkeypatch.setattr(teacher, "delete_document_from_rag", lambda doc_id: removed.append(doc_id) or True)

    created = client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"})
    assert client.delete(f"/api/teacher/knowledge/{created.json()['id']}").status_code == 200
    assert _rows(sessions) == 0
    assert removed == [created.json()["id"]]


def test_missing_knowledge_returns_404_without_touching_the_index(knowledge_client, monkeypatch):
    client, sessions, _ = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    calls = []
    monkeypatch.setattr(teacher, "delete_document_from_rag", lambda *a: calls.append(a) or True)

    assert client.delete("/api/teacher/knowledge/999999").status_code == 404
    assert calls == [], "a missing row must not trigger a vector removal"


def test_student_role_is_rejected_before_any_write(knowledge_client, monkeypatch):
    client, sessions, identity = knowledge_client
    monkeypatch.setenv("RAG_ENABLED", "true")
    calls = []
    monkeypatch.setattr(teacher, "add_document_to_rag", lambda *a: calls.append(a) or True)
    identity["role"] = "student"

    assert client.post("/api/teacher/knowledge", json={"title": "Synthetic", "content": "Synthetic body"}).status_code == 403
    assert _rows(sessions) == 0 and calls == []
