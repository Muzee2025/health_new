"""One treehole response must describe one database state.

``_get_treehole_responses`` used to run its five aggregates against a *live*
subquery over the filter that produced the post list. Every statement re-evaluated
that subquery, so a concurrent write could change the id set between statements:
the post was already loaded and stayed in the response, while its like and comment
counts silently became 0 and ``is_liked`` flipped to false. That was reported as a
P2 regression in the independent review
(``docs/test/treehole第9处独立评审_20261113.md``) and fixed by binding the ids of
the posts actually loaded.

This test reproduces the interleaving deterministically: a second connection
removes the viewer's favourite after the post list has been read but before the
first aggregate runs. The post must stay in the response *with its real counts*.

The window is only reachable through the engine, so the delete is hooked onto
``before_cursor_execute``. It fires on the first aggregate statement, which is the
first point after the post SELECT has completed. The test asserts the delete
really happened, so it cannot pass by never reaching the interleaving.
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
from app.routers.auth import get_current_user

VIEWER_ID = 201
OTHER_ID = 301
FAVOURITED_POST = 103


def _seed(db):
    """Two users, three favourites, and one post with likes and comments.

    Post 103 is the interesting one: two likes, two comments, favourited by both
    users. Removing only the viewer's favourite leaves the post favourited by
    someone else, so "favourites_count went to 1" and "is_favorited became false"
    are two different, checkable facts.
    """
    db.add_all([
        models.User(id=VIEWER_ID, username="consistency_viewer", role="student", password_hash="x"),
        models.User(id=OTHER_ID, username="consistency_other", role="student", password_hash="x"),
    ])
    db.flush()
    for post_id in (101, 102, FAVOURITED_POST):
        db.add(models.TreeholePost(id=post_id, user_id=VIEWER_ID,
                                   anonymous_id=f"anon{post_id}",
                                   content=f"post {post_id}", tags="t", is_deep=False))
    db.flush()
    db.add_all([
        models.TreeholeLike(post_id=FAVOURITED_POST, user_id=VIEWER_ID),
        models.TreeholeLike(post_id=FAVOURITED_POST, user_id=OTHER_ID),
        models.TreeholeFavorite(post_id=FAVOURITED_POST, user_id=VIEWER_ID),
        models.TreeholeFavorite(post_id=FAVOURITED_POST, user_id=OTHER_ID),
        models.TreeholeComment(id=1, post_id=FAVOURITED_POST, user_id=VIEWER_ID,
                               anonymous_id="a", content="a"),
        models.TreeholeComment(id=2, post_id=FAVOURITED_POST, user_id=OTHER_ID,
                               anonymous_id="b", content="b", parent_id=1),
    ])
    db.commit()


def _is_aggregate(statement):
    """True for the five batched count/lookup statements, not the post SELECT.

    The post SELECT for the favourites tab also mentions ``treehole_favorites``
    (inside its ``IN (SELECT ...)`` filter), so matching on the table name alone
    would fire the hook too early. Only the aggregates contain ``count(``.
    """
    lowered = statement.lower()
    return "count(" in lowered and "treehole_" in lowered


def test_favourite_counts_survive_a_concurrent_unfavourite():
    db_url = f"sqlite:///{tempfile.NamedTemporaryFile(prefix='treehole_consistency_', suffix='.db', delete=False).name}"
    engine = create_engine(db_url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    models.Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)

    viewer = models.User(id=VIEWER_ID, username="consistency_viewer", role="student", password_hash="x")
    db = SessionLocal()
    _seed(db)
    db.close()

    # A separate engine, so the write happens on its own connection and commits
    # while the request's read is in flight.
    writer = create_engine(db_url)
    fired = []

    def unfavourite_mid_response(conn, _cursor, statement, _parameters, _context, _executemany):
        if fired or not _is_aggregate(statement):
            return
        with writer.begin() as other:
            deleted = other.execute(models.TreeholeFavorite.__table__.delete().where(
                models.TreeholeFavorite.post_id == FAVOURITED_POST,
                models.TreeholeFavorite.user_id == VIEWER_ID,
            ))
            # Recorded inside the hook: if the row was already gone the interleaving
            # did not happen and the assertions below would prove nothing.
            fired.append(deleted.rowcount)

    event.listen(engine, "before_cursor_execute", unfavourite_mid_response)

    app = FastAPI()
    app.include_router(student_router.router)

    def override_get_db():
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: viewer

    try:
        response = TestClient(app).get("/api/student/treehole/posts?tab=favorites")
    finally:
        event.remove(engine, "before_cursor_execute", unfavourite_mid_response)
        writer.dispose()
        engine.dispose()

    assert response.status_code == 200, response.text
    assert fired == [1], f"the concurrent unfavourite did not run exactly once: {fired}"

    body = response.json()
    # The post was loaded before the delete, so it stays in the response either way.
    # That is precisely why the counts, not the membership, are what regressed.
    post = next((item for item in body if item["id"] == FAVOURITED_POST), None)
    assert post is not None, [item["id"] for item in body]
    assert post["likes_count"] == 2, post
    assert post["comments_count"] == 2, post
    # One favourite is left: the other user's.
    assert post["favorites_count"] == 1, post
    assert post["is_liked"] is True, post
    # The viewer's own favourite is gone by the time the lookups run.
    assert post["is_favorited"] is False, post
