"""Statement counts must not grow with the number of rows returned.

The static gate (``scripts/check-n1-queries.py``) finds most N+1 patterns, but it
has a blind spot it reports as ``helper``: a loop that calls a local helper which
queries on the caller's behalf. The scanner cannot decide whether that query is
actually reached, so its findings are advisory and one of them is a known false
positive. These tests are the runtime half: they count the statements the engine
really issues and assert the count is flat as the row count grows.

That distinction matters. ``get_pending_crisis_records`` looks like an N+1 to the
scanner because ``_serialize_real_warning_row`` contains a ``db.query``, but the
query sits in the branch the batched caller never takes. Measuring is the only
way to tell that apart from a real per-row query.

A statement count is compared across two seed sizes rather than pinned to an
absolute number, so unrelated changes to a fixed number of setup queries do not
make these tests stale.
"""
import os
import sys
import tempfile

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import models
from app.database import get_db
from app.routers import student as student_router
from app.routers import teacher
from app.routers.auth import get_current_user

SMALL = 4
LARGE = 16


def _count_statements(seed, call, rows, role="teacher"):
    """Seed a throwaway database with ``rows`` records, make one request.

    Returns (status, statements). The row count is a parameter, not a module
    constant: seeding the same size twice would make every comparison vacuous.
    """
    db_url = f"sqlite:///{tempfile.NamedTemporaryFile(prefix='growth_', suffix='.db', delete=False).name}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    db = SessionLocal()
    teacher_user = models.User(id=201, username="growth_teacher", password_hash="x",
                               role="teacher", name="T")
    student_user = models.User(id=301, username="growth_student", password_hash="x",
                               role="student", name="S")
    db.add_all([teacher_user, student_user])
    db.commit()
    db.add(models.TeacherStudentAssignment(teacher_id=teacher_user.id, student_id=student_user.id))
    db.commit()
    seed(db, teacher_user, student_user, rows)
    db.commit()
    db.close()

    statements = []

    @event.listens_for(engine, "before_cursor_execute")
    def record(_conn, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement)

    app = FastAPI()
    app.include_router(teacher.router)
    app.include_router(student_router.router)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = (
        lambda: teacher_user if role == "teacher" else student_user
    )
    response = TestClient(app).get(call)
    engine.dispose()
    return response.status_code, len(statements)


def _assert_flat(seed, call, role="teacher"):
    small_status, small = _count_statements(seed, call, SMALL, role)
    large_status, large = _count_statements(seed, call, LARGE, role)
    assert small_status == 200, small_status
    assert large_status == 200, large_status
    # Four times the rows must not cost more statements. One extra is tolerated for
    # a bounded second pass; anything that scales with rows shows up immediately.
    assert large <= small + 1, (
        f"{call}: {SMALL} rows cost {small} statements but {LARGE} rows cost {large}. "
        "The count grows with the row count, so this is a per-row query."
    )


def test_pending_crisis_statements_do_not_grow_with_warnings():
    """The scanner flags this one; measurement says it is a false positive.

    ``_serialize_real_warning_row`` only queries when ``message_content`` is None,
    and the batched caller always passes a value. If that ever changes, this test
    starts failing and the scanner finding becomes real.
    """
    def seed(db, teacher_user, student_user, rows):
        for index in range(rows):
            db.add(models.CrisisWarning(id=9000 + index, student_id=student_user.id,
                                        status="pending", risk_level="high",
                                        trigger_keyword="test"))

    _assert_flat(seed, "/api/teacher/crisis/pending?pageSize=100")


def test_crisis_review_statements_do_not_grow_with_events():
    """Was one query per event until the actor lookup was batched."""
    def seed(db, teacher_user, student_user, rows):
        db.add(models.CrisisWarning(id=9500, student_id=student_user.id, status="pending",
                                    risk_level="high", trigger_keyword="test"))
        db.flush()
        for index in range(rows):
            db.add(models.SupportWorkflowEvent(
                subject_type="crisis", subject_id=9500, student_id=student_user.id,
                actor_id=teacher_user.id, action="review", reason=f"r{index}",
            ))

    _assert_flat(seed, "/api/teacher/crisis/9500/reviews")


def test_treehole_post_statements_do_not_grow_with_posts():
    """The gate reports this one too, and here the finding was real.

    ``_get_treehole_response`` used to run five counts per post (likes, comments,
    favorites, is_liked, is_favorited) and the route has no limit, so the cost was
    5N+1: measured 6 / 26 / 101 statements for 1 / 5 / 20 posts, and 21 / 81 on
    the 4 / 16 seeds used here. It is a fixed number of batched queries now, and
    this test is what keeps it that way.
    """
    def seed(db, teacher_user, student_user, rows):
        for index in range(rows):
            db.add(models.TreeholePost(id=8000 + index, user_id=student_user.id,
                                       anonymous_id=f"anon{index}",
                                       content=f"post {index}", tags="t", is_deep=False))

    _assert_flat(seed, "/api/student/treehole/posts", role="student")
