"""Paged article catalog API contract on a fresh synthetic SQLite database."""
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers.auth import get_current_user


@pytest.fixture()
def article_catalog_client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'catalog.sqlite3').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine)
    with sessions() as db:
        db.add_all([
            models.User(id=7201, username="synthetic-student", role="student", password_hash="unused"),
            models.User(id=7202, username="synthetic-teacher", role="teacher", password_hash="unused"),
        ])
        db.commit()
    identity = {"role": "student"}

    def current_user():
        return models.User(id=7201 if identity["role"] == "student" else 7202,
                           username="synthetic-actor", role=identity["role"])

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


def add_article(sessions, title, *, summary="", source="", category="A", views=0,
                created_at=None, content="synthetic body"):
    with sessions() as db:
        article = models.Article(title=title, summary=summary, source=source,
                                 category=category, views=views,
                                 created_at=created_at or datetime(2026, 1, 1),
                                 content=content)
        db.add(article)
        db.commit()
        db.refresh(article)
        return article.id


def test_pagination_validation_and_page_boundaries(article_catalog_client):
    client, sessions, _ = article_catalog_client
    ids = [add_article(sessions, f"Item {i}", created_at=datetime(2026, 1, 1) + timedelta(days=i))
           for i in range(5)]
    page = client.get("/api/student/articles/page?page_size=2&page=2").json()
    assert (page["total"], page["page"], page["page_size"]) == (5, 2, 2)
    assert [item["id"] for item in page["items"]] == [ids[2], ids[1]]
    assert client.get("/api/student/articles/page?page=99&page_size=2").json()["page"] == 3
    empty = client.get("/api/student/articles/page?q=missing").json()
    assert empty["total"] == 0 and empty["page"] == 1 and empty["items"] == []
    for params in ("page=0", "page_size=0", "page_size=51", "q=" + "x" * 101,
                   "category=" + "x" * 51, "sort=popular"):
        assert client.get("/api/student/articles/page?" + params).status_code == 422


def test_search_covers_fields_and_treats_like_metacharacters_literally(article_catalog_client):
    client, sessions, _ = article_catalog_client
    add_article(sessions, "plain title", summary="plain summary", source="plain source")
    add_article(sessions, "marker%_\\ in title", summary="", source="")
    add_article(sessions, "other", summary="marker%_\\ in summary", source="")
    add_article(sessions, "third", summary="", source="marker%_\\ in source")
    results = client.get("/api/student/articles/page?q=%25_%5C").json()
    assert results["total"] == 3
    by_text = {
        "title": client.get("/api/student/articles/page?q=marker%25_%5C").json(),
        "summary": client.get("/api/student/articles/page?q=marker%25_%5C%20in%20summary").json(),
        "source": client.get("/api/student/articles/page?q=marker%25_%5C%20in%20source").json(),
    }
    assert by_text["title"]["total"] == 3  # the literal token occurs in all three fields
    assert by_text["summary"]["total"] == 1 and by_text["source"]["total"] == 1


def test_categories_are_global_and_filters_combine(article_catalog_client):
    client, sessions, identity = article_catalog_client
    add_article(sessions, "A1", category="Alpha")
    add_article(sessions, "A2", category="Beta")
    add_article(sessions, "A3", category="", summary="needle")
    add_article(sessions, "A5", category="   ", summary="needle")
    add_article(sessions, "A6", category="\t\r\n\v\f", summary="needle")
    add_article(sessions, "A7", category=" Alpha ", summary="needle")
    null_category_id = add_article(sessions, "A4", category=None, summary="needle")
    with sessions() as db:
        db.query(models.Article).filter(models.Article.id == null_category_id).update(
            {models.Article.category: None})
        db.commit()
    identity["role"] = "teacher"
    response = client.get("/api/teacher/articles/page?q=needle&category=%20").json()
    assert response["total"] == 5
    assert response["categories"] == ["Alpha", "Beta"]
    filtered = client.get("/api/teacher/articles/page?q=needle&category=Beta").json()
    assert filtered["total"] == 0 and filtered["categories"] == ["Alpha", "Beta"]
    normalized = client.get("/api/teacher/articles/page?category=Alpha").json()
    assert normalized["total"] == 2
    assert {item["title"] for item in normalized["items"]} == {"A1", "A7"}


def test_stable_newest_and_most_read_sort_normalize_negative_and_null(article_catalog_client):
    client, sessions, _ = article_catalog_client
    same = datetime(2026, 2, 2)
    lower_id = add_article(sessions, "same-1", views=7, created_at=same)
    higher_id = add_article(sessions, "same-2", views=7, created_at=same)
    negative = add_article(sessions, "negative", views=-4, created_at=same)
    null_id = add_article(sessions, "null", views=0, created_at=same)
    with sessions() as db:
        db.query(models.Article).filter(models.Article.id == null_id).update({models.Article.views: None})
        db.commit()
    newest = client.get("/api/student/articles/page").json()
    assert [item["id"] for item in newest["items"]] == [null_id, negative, higher_id, lower_id]
    assert {item["id"]: item["views"] for item in newest["items"]} == {
        null_id: 0, negative: 0, higher_id: 7, lower_id: 7,
    }
    most_read = client.get("/api/student/articles/page?sort=most-read").json()
    assert [item["id"] for item in most_read["items"]] == [higher_id, lower_id, null_id, negative]


def test_page_sql_projection_never_selects_article_content(article_catalog_client):
    client, sessions, _ = article_catalog_client
    add_article(sessions, "Projection check", content="private synthetic body")
    engine = sessions.kw["bind"]
    statements = []

    def capture(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.lower())

    event.listen(engine, "before_cursor_execute", capture)
    try:
        response = client.get("/api/student/articles/page")
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    assert response.status_code == 200
    article_selects = [sql for sql in statements if "articles" in sql]
    assert article_selects
    assert all("articles.content" not in sql for sql in article_selects)


def test_summary_only_and_legacy_endpoints_and_roles(article_catalog_client):
    client, sessions, identity = article_catalog_client
    article_id = add_article(sessions, "Legacy title", summary="Summary", source="Source",
                             content="legacy body")
    page = client.get("/api/student/articles/page").json()
    assert set(page["items"][0]) == {
        "id", "title", "summary", "cover_url", "category", "source", "views",
        "created_at", "source_url",
    }
    assert "content" not in page["items"][0]
    legacy = client.get("/api/student/articles").json()
    detail = client.get(f"/api/student/articles/{article_id}").json()
    assert legacy[0]["content"] == "legacy body" and detail["content"] == "legacy body"

    # The new student listing preserves the existing public-read policy.
    identity["role"] = "teacher"
    assert client.get("/api/student/articles/page").status_code == 200
    assert client.get("/api/teacher/articles/page").status_code == 200
    identity["role"] = "student"
    assert client.get("/api/teacher/articles/page").status_code == 403
