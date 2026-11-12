"""Database-level uniqueness for bookings, likes and favorites, plus avatar cleanup.

These paths used check-then-insert, so two concurrent requests could both pass the
application check and insert. The unique indexes are the real guard; these tests pin
that behaviour and the compensating actions around it.
"""
from __future__ import annotations

import threading

import pytest
from fastapi import Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from app import models
from app.database import Base, get_db
from app.main import app
from app.routers import teacher
from app.routers.auth import get_current_user


def _make_engine(tmp_path, name):
    return create_engine(f"sqlite:///{(tmp_path / name).as_posix()}",
                         connect_args={"check_same_thread": False, "timeout": 30})


def _seed(Sessions):
    with Sessions() as db:
        db.add_all([
            models.User(id=1, username="synthetic-teacher", password_hash="unused", role="teacher", name="T"),
            models.User(id=2, username="synthetic-student-a", password_hash="unused", role="student",
                        name="A", student_id="S-A"),
            models.User(id=3, username="synthetic-student-b", password_hash="unused", role="student",
                        name="B", student_id="S-B"),
        ])
        db.flush()
        db.add_all([models.TeacherStudentAssignment(teacher_id=1, student_id=2),
                    models.TeacherStudentAssignment(teacher_id=1, student_id=3),
                    models.TreeholePost(id=1, user_id=2, anonymous_id="anon", content="synthetic")])
        db.commit()


@pytest.fixture()
def client_bundle(tmp_path):
    engine = _make_engine(tmp_path, "unique.sqlite3")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(bind=engine)
    _seed(Sessions)

    # Read the acting user from a header so concurrent requests in different threads
    # do not share one mutable identity (a shared dict races under TestClient).
    def current_user(request: Request):
        return models.User(id=int(request.headers["X-Probe-User"]),
                           username="synthetic", role="student")

    def database():
        with Sessions() as db:
            yield db

    previous = dict(app.dependency_overrides)
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_current_user] = current_user
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            yield client, Sessions, engine
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        engine.dispose()


def test_unique_indexes_exist_after_create_all(tmp_path):
    """A fresh deployment must carry the constraints without a separate migration."""
    engine = _make_engine(tmp_path, "schema.sqlite3")
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    names = {index["name"] for index in inspector.get_indexes("appointments")}
    assert "uq_appointment_active_slot" in names
    for table in ("treehole_likes", "treehole_favorites"):
        constraints = {c["name"] for c in inspector.get_unique_constraints(table)}
        assert any("post_user" in name for name in constraints), table
    engine.dispose()


def test_appointment_index_is_partial_so_cancelled_slots_free_up(tmp_path):
    """A plain UNIQUE would let a cancellation hold the slot forever."""
    engine = _make_engine(tmp_path, "partial.sqlite3")
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        ddl = conn.execute(text(
            "SELECT sql FROM sqlite_master WHERE name='uq_appointment_active_slot'")).scalar()
    assert ddl and "WHERE" in ddl.upper()
    engine.dispose()


def _as(user_id):
    return {"X-Probe-User": str(user_id)}


def test_cancelled_appointment_allows_rebooking(client_bundle):
    client, Sessions, _ = client_bundle
    first = client.post("/api/student/appointments", headers=_as(2),
                        json={"teacher_id": 1, "time_slot": "slot-A"})
    assert first.status_code == 200
    with Sessions() as db:
        db.query(models.Appointment).filter(models.Appointment.id == first.json()["id"]).update(
            {"status": "cancelled"})
        db.commit()
    again = client.post("/api/student/appointments", headers=_as(3),
                        json={"teacher_id": 1, "time_slot": "slot-A"})
    assert again.status_code == 200


def test_duplicate_active_booking_returns_400_not_500(client_bundle):
    """The index rejects the second row; the endpoint must translate that to 400."""
    client, Sessions, _ = client_bundle
    assert client.post("/api/student/appointments", headers=_as(2),
                       json={"teacher_id": 1, "time_slot": "slot-B"}).status_code == 200
    # Bypass the application check by inserting the conflicting row directly.
    with Sessions() as db:
        db.add(models.Appointment(student_id=3, teacher_id=1, time_slot="slot-C", status="pending"))
        db.commit()
    response = client.post("/api/student/appointments", headers=_as(3),
                           json={"teacher_id": 1, "time_slot": "slot-C"})
    assert response.status_code == 400, response.text
    assert "已被预约" in response.json()["detail"]


def test_concurrent_booking_inserts_exactly_one_row(client_bundle):
    client, Sessions, _ = client_bundle
    barrier = threading.Barrier(2)
    statuses = []

    def book(user_id):
        barrier.wait()
        statuses.append(client.post("/api/student/appointments", headers=_as(user_id),
                                    json={"teacher_id": 1, "time_slot": "race"}).status_code)

    threads = [threading.Thread(target=book, args=(uid,)) for uid in (2, 3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with Sessions() as db:
        rows = db.query(models.Appointment).filter(models.Appointment.time_slot == "race").count()
    assert rows == 1
    assert 500 not in statuses, statuses


def test_concurrent_like_never_creates_two_rows(client_bundle):
    """Two taps in flight: exactly one row, and neither request may fail with 500."""
    client, Sessions, _ = client_bundle
    barrier = threading.Barrier(2)
    results = []

    def like():
        barrier.wait()
        response = client.post("/api/student/treehole/1/like", headers=_as(2))
        results.append((response.status_code, response.json().get("status")))

    threads = [threading.Thread(target=like) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with Sessions() as db:
        rows = db.query(models.TreeholeLike).filter(
            models.TreeholeLike.post_id == 1, models.TreeholeLike.user_id == 2).count()
    assert rows <= 1
    assert all(status == 200 for status, _ in results), results


def test_concurrent_favorite_never_creates_two_rows(client_bundle):
    client, Sessions, _ = client_bundle
    barrier = threading.Barrier(2)
    results = []

    def favorite():
        barrier.wait()
        response = client.post("/api/student/treehole/1/favorite", headers=_as(2))
        results.append(response.status_code)

    threads = [threading.Thread(target=favorite) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    with Sessions() as db:
        rows = db.query(models.TreeholeFavorite).filter(
            models.TreeholeFavorite.post_id == 1, models.TreeholeFavorite.user_id == 2).count()
    assert rows <= 1
    assert all(status == 200 for status in results), results


def test_avatar_file_is_removed_when_the_commit_fails(tmp_path):
    """The image is written before the row, so a failed commit must clean it up."""
    work = tmp_path / "cwd"
    work.mkdir()
    engine = _make_engine(tmp_path, "avatar.sqlite3")
    Base.metadata.create_all(engine)
    Sessions = sessionmaker(bind=engine)
    with Sessions() as db:
        db.add(models.User(id=1, username="synthetic-teacher", password_hash="unused",
                           role="teacher", name="T"))
        db.commit()

    import os

    previous = os.getcwd()
    os.chdir(work)
    try:
        payload = b"\x89PNG\r\n\x1a\n" + b"synthetic"

        class CommitFails:
            def __init__(self, inner):
                self._inner = inner

            def __getattr__(self, name):
                return getattr(self._inner, name)

            def commit(self):
                raise RuntimeError("simulated commit failure")

        with Sessions() as db:
            with pytest.raises(RuntimeError):
                teacher._upsert_teacher_avatar_content(request=None, db=CommitFails(db),
                                                       teacher_id=1, content=payload, ext=".png")
        avatar_dir = work / "uploads" / "teacher_avatars"
        remaining = list(avatar_dir.glob("*")) if avatar_dir.is_dir() else []
        assert remaining == [], f"orphan files left behind: {remaining}"
        with Sessions() as db:
            assert db.query(models.TeacherAvatar).count() == 0
    finally:
        os.chdir(previous)
        engine.dispose()
