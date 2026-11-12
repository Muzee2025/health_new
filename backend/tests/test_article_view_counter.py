import os
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.database import get_db
from app.routers import student


def _build_test_db():
    db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    db_file.close()
    engine = create_engine(
        f"sqlite:///{db_file.name}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)
    return engine, TestingSessionLocal


def _seed_article(session_factory, views=100):
    db = session_factory()
    try:
        article = models.Article(
            title="测试文章",
            summary="摘要",
            content="<p>content</p>",
            category="心理科普",
            views=views,
        )
        db.add(article)
        db.commit()
        db.refresh(article)
        return article.id
    finally:
        db.close()


def _build_test_client(session_factory):
    app = FastAPI()
    app.include_router(student.router)

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def _clear_view_runtime_cache():
    student.ARTICLE_VIEW_CACHE.clear()
    student.ARTICLE_VIEW_IDEMPOTENCY.clear()


def test_new_article_views_are_zero_and_legacy_counts_remain_unchanged():
    assert student._generate_initial_article_views() == 0
    _, session_factory = _build_test_db()
    article_id = _seed_article(session_factory, views=87)
    db = session_factory()
    try:
        student._ensure_article_views_initialized(db)
        assert db.query(models.Article).filter_by(id=article_id).one().views == 87
    finally:
        db.close()


def test_atomic_increment_logic():
    _, session_factory = _build_test_db()
    _clear_view_runtime_cache()
    article_id = _seed_article(session_factory, views=80)
    db = session_factory()
    try:
        after = student._increment_article_views_atomic(db, article_id)
        assert after == 81
    finally:
        db.close()


def test_idempotent_intercept_logic():
    _clear_view_runtime_cache()
    article_id = 7
    viewer = "viewer:user-1"
    assert student._consume_view_token(viewer, article_id, now_ts=1000.0) is True
    assert student._consume_view_token(viewer, article_id, now_ts=1001.0) is False
    assert student._consume_view_token(viewer, article_id, now_ts=1301.0) is True


def test_api_concurrent_same_user_only_plus_one():
    _, session_factory = _build_test_db()
    _clear_view_runtime_cache()
    article_id = _seed_article(session_factory, views=100)

    with _build_test_client(session_factory) as client:
        def hit_once():
            return client.post(
                f"/api/student/articles/{article_id}/view",
                json={"viewer_id": "same-user"},
            )

        with ThreadPoolExecutor(max_workers=20) as executor:
            responses = list(executor.map(lambda _: hit_once(), range(100)))

    assert all(r.status_code == 200 for r in responses)

    db = session_factory()
    try:
        article = db.query(models.Article).filter(models.Article.id == article_id).first()
        assert article.views == 101
    finally:
        db.close()


def test_api_concurrent_different_user_plus_hundred():
    _, session_factory = _build_test_db()
    _clear_view_runtime_cache()
    article_id = _seed_article(session_factory, views=100)

    with _build_test_client(session_factory) as client:
        def hit_once(i):
            return client.post(
                f"/api/student/articles/{article_id}/view",
                json={"viewer_id": f"user-{i}"},
            )

        with ThreadPoolExecutor(max_workers=20) as executor:
            responses = list(executor.map(hit_once, range(100)))

    assert all(r.status_code == 200 for r in responses)

    db = session_factory()
    try:
        article = db.query(models.Article).filter(models.Article.id == article_id).first()
        assert article.views == 200
    finally:
        db.close()


def _lock_update_event(engine, *, failures):
    attempts = {"count": 0}

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE ARTICLES"):
            attempts["count"] += 1
            if attempts["count"] <= failures:
                raise OperationalError(statement, parameters, sqlite3.OperationalError("database is locked"))

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    return attempts, before_cursor_execute


def test_sqlite_locked_update_retries_and_succeeds():
    engine, session_factory = _build_test_db()
    _clear_view_runtime_cache()
    article_id = _seed_article(session_factory, views=10)
    attempts, listener = _lock_update_event(engine, failures=1)
    try:
        with _build_test_client(session_factory) as client:
            response = client.post(
                f"/api/student/articles/{article_id}/view",
                json={"viewer_id": "retry-once"},
            )
        assert response.status_code == 200
        assert response.json()["views"] == 11
        assert attempts["count"] == 2
    finally:
        if event.contains(engine, "before_cursor_execute", listener):
            event.remove(engine, "before_cursor_execute", listener)


def test_article_view_counter_executes_no_sql_after_commit():
    engine, session_factory = _build_test_db()
    article_id = _seed_article(session_factory, views=10)
    db = session_factory()
    committed = {"value": False}
    post_commit_sql = {"count": 0}

    def mark_committed(session):
        committed["value"] = True

    def reject_sql_after_commit(conn, cursor, statement, parameters, context, executemany):
        if committed["value"]:
            post_commit_sql["count"] += 1
            raise AssertionError("SQL executed after the article view counter committed")

    event.listen(db, "after_commit", mark_committed)
    event.listen(engine, "before_cursor_execute", reject_sql_after_commit)
    try:
        assert student._increment_article_views_atomic(db, article_id) == 11
        assert committed["value"] is True
        assert post_commit_sql["count"] == 0
    finally:
        event.remove(db, "after_commit", mark_committed)
        event.remove(engine, "before_cursor_execute", reject_sql_after_commit)
        db.close()


def test_sqlite_locked_update_exhaustion_returns_503_and_releases_token():
    engine, session_factory = _build_test_db()
    _clear_view_runtime_cache()
    article_id = _seed_article(session_factory, views=10)
    attempts, listener = _lock_update_event(engine, failures=99)
    try:
        with _build_test_client(session_factory) as client:
            response = client.post(
                f"/api/student/articles/{article_id}/view",
                json={"viewer_id": "retry-exhausted"},
            )
        assert response.status_code == 503
        assert response.headers["retry-after"] == "1"
        assert attempts["count"] == 5
        assert "viewer:retry-exhausted:" + str(article_id) not in student.ARTICLE_VIEW_IDEMPOTENCY
        if event.contains(engine, "before_cursor_execute", listener):
            event.remove(engine, "before_cursor_execute", listener)
        with _build_test_client(session_factory) as client:
            retried = client.post(
                f"/api/student/articles/{article_id}/view",
                json={"viewer_id": "retry-exhausted"},
            )
        assert retried.status_code == 200
        assert retried.json()["views"] == 11
    finally:
        if event.contains(engine, "before_cursor_execute", listener):
            event.remove(engine, "before_cursor_execute", listener)


def test_non_lock_sqlite_operational_error_is_not_retried():
    engine, session_factory = _build_test_db()
    article_id = _seed_article(session_factory, views=10)
    attempts = {"count": 0}

    def fail_update(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE ARTICLES"):
            attempts["count"] += 1
            raise OperationalError(statement, parameters, sqlite3.OperationalError("disk I/O error"))

    event.listen(engine, "before_cursor_execute", fail_update)
    db = session_factory()
    try:
        with pytest.raises(OperationalError):
            student._increment_article_views_atomic(db, article_id)
        assert attempts["count"] == 1
    finally:
        db.close()
        event.remove(engine, "before_cursor_execute", fail_update)
