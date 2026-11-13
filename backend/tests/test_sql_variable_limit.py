"""Batch endpoints must not build an IN(...) list that outgrows SQLite's limit.

Several endpoints were changed from one query per row to a single batched
``IN (...)``. That is the right fix for N+1, but it introduces a ceiling the
per-row version did not have: SQLite allows at most 32766 bound variables per
statement, so a list long enough raises ``too many SQL variables`` and the
endpoint returns 500 where the old code merely ran slowly. The threshold sits
four orders of magnitude above any realistic seed, which is exactly why the
existing suite could not see it.

The trick below is what makes this testable without a 30k-row fixture: SQLite
exposes ``sqlite3.Connection.setlimit`` (Python 3.11+), so the cap can be
lowered for the duration of one engine and a handful of rows is then enough to
overflow it. The assertions are about behaviour under a small cap, not about
the number 32766, so the test does not go stale if SQLite changes it.
"""
import os
import sqlite3
import sys
import tempfile
from contextlib import contextmanager

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.database import get_db
from app.routers import advanced_teacher, teacher
from app.routers import student as student_router
from app.routers.auth import get_current_user

# Small enough that a dozen rows overflow it, large enough that the ordinary
# bookkeeping queries these endpoints run on the way in still fit.
TIGHT_VARIABLE_LIMIT = 8
STUDENT_COUNT = 12


def _build_app():
    db_url = f"sqlite:///{tempfile.NamedTemporaryFile(prefix='varlimit_', suffix='.db', delete=False).name}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)
    models.Base.metadata.create_all(bind=engine)

    app = FastAPI()
    # teacher.router already carries prefix="/api/teacher"; advanced_teacher.router
    # carries none, so only the latter is mounted with a prefix here.
    app.include_router(teacher.router)
    app.include_router(student_router.router)
    app.include_router(advanced_teacher.router, prefix="/api/advanced-teacher")
    return app, SessionLocal, engine


@contextmanager
def tight_variable_limit(engine, limit=TIGHT_VARIABLE_LIMIT):
    """Lower SQLite's bound-variable cap on every connection this engine opens.

    The cap is per connection, so it is applied from the ``connect`` event, which
    receives the DBAPI connection itself. StaticPool reuses one connection, so
    the pool is disposed on the way out and nothing outside the block sees the
    lowered limit.
    """
    def apply(dbapi_connection, _record=None):
        if not hasattr(dbapi_connection, "setlimit"):
            pytest.skip("this Python's sqlite3 has no Connection.setlimit")
        dbapi_connection.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER, limit)

    event.listen(engine, "connect", apply)
    # The pooled connection may already be open, in which case the event will not
    # fire again for it; set the limit on it directly.
    with engine.connect() as conn:
        apply(conn.connection.dbapi_connection)
    try:
        yield
    finally:
        event.remove(engine, "connect", apply)
        engine.dispose()


@pytest.fixture()
def varlimit_context():
    app, SessionLocal, engine = _build_app()
    db = SessionLocal()
    teacher_user = models.User(id=201, username="tea", password_hash="x",
                               role="teacher", name="王老师")
    db.add(teacher_user)
    # More students than the lowered cap, so any endpoint that materialises one
    # variable per student cannot fit.
    students = [models.User(id=1000 + i, username=f"stu{i}", password_hash="x",
                            role="student", name=f"学生{i}") for i in range(STUDENT_COUNT)]
    db.add_all(students)
    db.commit()
    for student in students:
        db.add(models.TeacherStudentAssignment(teacher_id=teacher_user.id, student_id=student.id))
    db.commit()

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: teacher_user
    yield app, SessionLocal, engine, teacher_user, students
    db.close()
    engine.dispose()


def test_crisis_warning_list_survives_a_tight_variable_limit(varlimit_context):
    """Regression: this endpoint 500s once the assigned-student list is wide.

    The query filters ``CrisisWarning.student_id.in_(assigned_student_ids(...))``.
    Under the per-row implementation the width of that list did not matter; the
    batched version binds one variable per id.
    """
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    db = SessionLocal()
    for index, student in enumerate(students):
        db.add(models.CrisisWarning(id=5000 + index, student_id=student.id, status="pending",
                                    risk_level="high", trigger_keyword="test"))
    db.commit()
    db.close()

    client = TestClient(app)
    with tight_variable_limit(engine):
        response = client.get("/api/advanced-teacher/warnings")
    assert response.status_code == 200, response.text


def test_pending_crisis_survives_a_tight_variable_limit(varlimit_context):
    """The same shape in the teacher router, with the message id list on top."""
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    db = SessionLocal()
    # AIChatSession.id is a String(36) supplied by the application, not an
    # autoincrement integer, so it has to be set explicitly.
    for index, student in enumerate(students):
        session_row = models.AIChatSession(id=f"00000000-0000-0000-0000-{index:012d}",
                                           user_id=student.id, title=f"s{index}")
        db.add(session_row)
        db.flush()
        message_row = models.AIChatMessage(session_id=session_row.id, role="user", content="help")
        db.add(message_row)
        db.flush()
        db.add(models.CrisisWarning(student_id=student.id, status="pending",
                                    risk_level="high", trigger_keyword="test",
                                    chat_message_id=message_row.id))
        db.flush()
    db.commit()
    db.close()

    client = TestClient(app)
    with tight_variable_limit(engine):
        response = client.get("/api/teacher/crisis/pending")
    assert response.status_code == 200, response.text


def test_assigned_question_list_survives_a_tight_variable_limit(varlimit_context):
    """The teacher question list builds one id per question for its event lookup."""
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    db = SessionLocal()
    for index in range(STUDENT_COUNT):
        db.add(models.Question(id=7000 + index, user_id=students[index].id,
                              question_text=f"q{index}", status="answered"))
    db.commit()
    db.close()

    client = TestClient(app)
    with tight_variable_limit(engine):
        response = client.get("/api/teacher/questions")
    assert response.status_code == 200, response.text


def test_student_question_list_survives_a_tight_variable_limit(varlimit_context):
    """Same shape from the student side, over that student's own questions.

    The actor lookup is what binds one variable per row here, so the seed has to
    give each question an answer event naming a *different* actor. Without those
    events the actor set is empty and the endpoint passes under any cap, which is
    exactly the hole this test used to have: it asserted nothing about the list it
    was written for.
    """
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    db = SessionLocal()
    # One distinct answering teacher per question, so a materialised actor list
    # holds STUDENT_COUNT entries rather than collapsing to a single id.
    actors = [models.User(id=2000 + index, username=f"ans{index}", password_hash="x",
                          role="teacher", name=f"答题老师{index}")
              for index in range(STUDENT_COUNT)]
    db.add_all(actors)
    db.commit()
    for index in range(STUDENT_COUNT):
        db.add(models.Question(id=7100 + index, user_id=students[0].id,
                              question_text=f"q{index}", answer_text=f"a{index}",
                              status="answered"))
    db.flush()
    for index in range(STUDENT_COUNT):
        db.add(models.SupportWorkflowEvent(
            subject_type="question", subject_id=7100 + index, student_id=students[0].id,
            actor_id=actors[index].id, action="answer", result_text=f"a{index}",
        ))
    db.commit()
    db.close()

    client = TestClient(app)
    app.dependency_overrides[get_current_user] = lambda: students[0]
    with tight_variable_limit(engine):
        response = client.get("/api/student/questions")
    assert response.status_code == 200, response.text
    # The events must actually reach the response, otherwise a fix that ignores
    # actors altogether would satisfy the cap assertion above.
    body = response.json()
    assert len(body) == STUDENT_COUNT, len(body)
    answerers = {item.get("answered_by") for item in body}
    assert None not in answerers, answerers
    assert len(answerers) > 1, answerers


def test_audit_list_survives_a_tight_variable_limit(varlimit_context):
    """The audit list batched its trigger-message lookup by message id."""
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    db = SessionLocal()
    for index in range(STUDENT_COUNT):
        session_row = models.AIChatSession(id=f"10000000-0000-0000-0000-{index:012d}",
                                           user_id=students[index].id, title=f"s{index}")
        db.add(session_row)
        db.flush()
        message_row = models.AIChatMessage(session_id=session_row.id, role="user", content="help")
        db.add(message_row)
        db.flush()
        db.add(models.CrisisWarning(id=5200 + index, student_id=students[index].id,
                                    status="pending", risk_level="high",
                                    trigger_keyword="test", chat_message_id=message_row.id))
        db.flush()
    db.commit()
    db.close()

    client = TestClient(app)
    with tight_variable_limit(engine):
        response = client.get("/api/advanced-teacher/audit/list")
    assert response.status_code == 200, response.text


def test_teacher_student_list_survives_a_tight_variable_limit(varlimit_context):
    """The roster batches three lookups by student id, one variable per student."""
    app, SessionLocal, engine, teacher_user, students = varlimit_context
    client = TestClient(app)
    with tight_variable_limit(engine):
        response = client.get("/api/teacher/students")
    assert response.status_code == 200, response.text


def test_the_cap_actually_applies(varlimit_context):
    """Guard the guard: if setlimit silently did nothing, the tests above would
    pass for the wrong reason and prove nothing."""
    _app, _SessionLocal, engine, _teacher, _students = varlimit_context
    with tight_variable_limit(engine):
        with engine.connect() as conn:
            raw = conn.connection.dbapi_connection
            assert raw.getlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER) == TIGHT_VARIABLE_LIMIT
            placeholders = ",".join("?" * (TIGHT_VARIABLE_LIMIT + 1))
            # SQLAlchemy wraps the DBAPI error, so match on its message rather
            # than on sqlite3.OperationalError.
            with pytest.raises(OperationalError, match="too many SQL variables"):
                conn.exec_driver_sql(f"select 1 where 1 in ({placeholders})",
                                     tuple(range(TIGHT_VARIABLE_LIMIT + 1)))
