import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
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

    def hit_once():
        with _build_test_client(session_factory) as client:
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

    def hit_once(i):
        with _build_test_client(session_factory) as client:
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
