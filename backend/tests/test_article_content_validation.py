"""Article creation checks using synthetic identities and a fresh SQLite file."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers.auth import get_current_user


@pytest.fixture()
def article_client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'articles.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    actor = models.User(id=7101, username="synthetic-content-teacher", role="teacher",
                        password_hash="not-a-login-credential")
    with sessions() as db:
        db.add(actor)
        db.commit()
    # The existing role dependency still executes; only identity resolution is
    # replaced. No JWT, real account, provider or listening server is used.
    identity = {"role": "teacher"}

    def current_user():
        return models.User(id=7101, username="synthetic-content-user", role=identity["role"])

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


@pytest.mark.parametrize("field,value", [
    ("title", " \n\t "), ("content", "\u3000\n "),
    ("title", "文" * 201), ("summary", "摘" * 501),
    ("content", "字" * 100_001), ("category", "类" * 51),
    ("source", "源" * 101), ("cover_url", "/" + "x" * 255),
], ids=["blank-title", "blank-content", "long-title", "long-summary",
        "long-content", "long-category", "long-source", "long-cover"])
def test_invalid_article_never_reaches_database(article_client, field, value):
    client, sessions, _ = article_client
    response = client.post("/api/teacher/articles", json={"title": "Synthetic title",
        "content": "Synthetic body", field: value})
    assert response.status_code == 422
    with sessions() as db:
        assert db.query(models.Article).count() == 0


def test_article_trims_edges_preserves_paragraphs_and_starts_at_zero(article_client):
    client, sessions, identity = article_client
    payload = {"title": "  使用指南  ", "summary": "  摘要  ",
        "content": "  第一段\n\n第二段  ", "category": "  平台指南 ", "source": " 原创 ",
        "cover_url": "  ", "views": 99999}
    response = client.post("/api/teacher/articles", json=payload)
    assert response.status_code == 200
    article = response.json()
    assert (article["title"], article["summary"], article["content"]) == (
        "使用指南", "摘要", "第一段\n\n第二段")
    assert article["category"] == "平台指南" and article["source"] == "原创"
    assert article["cover_url"] == "" and article["views"] == 0
    with sessions() as db:
        assert db.query(models.Article).count() == 1
    identity["role"] = "student"
    assert client.post("/api/teacher/articles", json=payload).status_code == 403
    assert client.delete(f"/api/teacher/articles/{article['id']}").status_code == 403
    detail = client.get(f"/api/student/articles/{article['id']}")
    assert detail.status_code == 200 and detail.json()["content"] == "第一段\n\n第二段"
