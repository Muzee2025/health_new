import hashlib
import json
import random
import sqlite3
import time
from datetime import datetime, timezone
from threading import Lock
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.security import get_optional_user
from app.services.article_catalog import page_articles
from app.student_access import assigned_teacher_ids

from .. import models, schemas
from ..database import get_db

teachers_router = APIRouter(prefix="/api/student", tags=["Student"])
articles_router = APIRouter(prefix="/api/student", tags=["Student"])

ARTICLE_VIEW_LOCK = Lock()
ARTICLE_VIEW_CACHE = {}
ARTICLE_VIEW_IDEMPOTENCY = {}
ARTICLE_VIEW_DEDUP_WINDOW_SECONDS = 5 * 60
ARTICLE_VIEW_INIT_MIN = 0
ARTICLE_VIEW_INIT_MAX = 0


def _generate_initial_article_views(rng: Optional[random.Random] = None) -> int:
    """New articles start with zero measured reads; rng is retained for callers."""
    return 0

def _touch_article_view_cache(article_id: int, views: int):
    with ARTICLE_VIEW_LOCK:
        ARTICLE_VIEW_CACHE[int(article_id)] = int(views)

def _read_article_views_cached(article_id: int, default: int) -> int:
    # The current database result wins over a possibly stale process-local cache.
    value = int(default or 0)
    _touch_article_view_cache(article_id, value)
    return value

def _cleanup_view_idempotency(now_ts: float):
    expired_keys = [k for k, exp in ARTICLE_VIEW_IDEMPOTENCY.items() if exp <= now_ts]
    for key in expired_keys:
        ARTICLE_VIEW_IDEMPOTENCY.pop(key, None)

def _consume_view_token(viewer_key: str, article_id: int, now_ts: Optional[float] = None) -> bool:
    """
    返回 True 表示本次点击应计数；False 表示命中 5 分钟幂等窗口，不再重复计数。
    """
    now = float(now_ts if now_ts is not None else datetime.now(timezone.utc).timestamp())
    dedup_key = f"{viewer_key}:{article_id}"
    with ARTICLE_VIEW_LOCK:
        expires_at = ARTICLE_VIEW_IDEMPOTENCY.get(dedup_key, 0)
        if expires_at > now:
            return False
        ARTICLE_VIEW_IDEMPOTENCY[dedup_key] = now + ARTICLE_VIEW_DEDUP_WINDOW_SECONDS
        if len(ARTICLE_VIEW_IDEMPOTENCY) > 4096:
            _cleanup_view_idempotency(now)
    return True

def _consume_view_token_expiry(viewer_key: str, article_id: int) -> Optional[float]:
    """Consume a token and return its expiry so a failed write can release only this token."""
    now = datetime.now(timezone.utc).timestamp()
    dedup_key = f"{viewer_key}:{article_id}"
    with ARTICLE_VIEW_LOCK:
        expires_at = ARTICLE_VIEW_IDEMPOTENCY.get(dedup_key, 0)
        if expires_at > now:
            return None
        token_expiry = now + ARTICLE_VIEW_DEDUP_WINDOW_SECONDS
        ARTICLE_VIEW_IDEMPOTENCY[dedup_key] = token_expiry
        if len(ARTICLE_VIEW_IDEMPOTENCY) > 4096:
            _cleanup_view_idempotency(now)
        return token_expiry

def _release_view_token(viewer_key: str, article_id: int, expected_expiry: float):
    dedup_key = f"{viewer_key}:{article_id}"
    with ARTICLE_VIEW_LOCK:
        if ARTICLE_VIEW_IDEMPOTENCY.get(dedup_key) == expected_expiry:
            ARTICLE_VIEW_IDEMPOTENCY.pop(dedup_key, None)

def _is_sqlite_lock_error(exc: OperationalError) -> bool:
    original = exc.orig
    if not isinstance(original, sqlite3.OperationalError):
        return False
    code = getattr(original, "sqlite_errorcode", None)
    if code is not None and code & 0xFF in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
        return True
    message = str(original).lower()
    return "database is locked" in message or "database table is locked" in message or "database is busy" in message

def _build_viewer_key(request: Request, viewer_id: Optional[str] = None) -> str:
    raw = (viewer_id or "").strip()
    if not raw:
        raw = (
            request.headers.get("x-viewer-id", "")
            or request.headers.get("x-user-id", "")
            or request.headers.get("x-device-id", "")
        ).strip()
    if raw:
        return f"viewer:{raw[:128]}"
    client_ip = getattr(request.client, "host", "") if request.client else ""
    ua = request.headers.get("user-agent", "")
    fallback_raw = f"{client_ip}|{ua}"
    fallback_hash = hashlib.sha256(fallback_raw.encode("utf-8")).hexdigest()[:24]
    return f"anon:{fallback_hash}"

def _ensure_article_views_initialized(db: Session):
    """Compatibility hook: reads must not backfill or overwrite historical data."""
    return None

def _increment_article_views_atomic(db: Session, article_id: int) -> int:
    # End the preceding read phase before writing; every retry also starts with
    # a fresh transaction instead of retaining a failed SQLite transaction.
    db.rollback()
    max_attempts = 5
    for attempt in range(max_attempts):
        try:
            affected = db.query(models.Article).filter(models.Article.id == article_id).update(
                {models.Article.views: func.coalesce(models.Article.views, 0) + 1},
                synchronize_session=False,
            )
            if not affected:
                raise HTTPException(status_code=404, detail="Article not found")
            row = db.query(models.Article.views).filter(models.Article.id == article_id).first()
            updated = int(row[0]) if row else 0
            db.commit()
            break
        except OperationalError as exc:
            db.rollback()
            if db.bind.dialect.name != "sqlite" or not _is_sqlite_lock_error(exc):
                raise
            if attempt + 1 >= max_attempts:
                raise HTTPException(
                    status_code=503,
                    detail="文章阅读量暂时无法更新，请稍后重试",
                    headers={"Retry-After": "1"},
                ) from exc
            time.sleep(min(0.01 * (2 ** attempt), 0.08))
    _touch_article_view_cache(article_id, updated)
    return updated

@teachers_router.get("/teachers")
def get_teachers(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(get_optional_user)):
    bookable = assigned_teacher_ids(db, current_user.id) if current_user and current_user.role == "student" else set()
    teachers = db.query(models.User).filter(models.User.role == "teacher").all()
    if not teachers:
        return []
    # Three batched lookups instead of three per teacher. Only non-cancelled bookings
    # count as taken, exactly as before; the response shape is unchanged.
    teacher_ids = [t.id for t in teachers]
    profiles = {
        profile.user_id: profile
        for profile in db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id.in_(teacher_ids)).all()
    }
    avatar_rows = {
        avatar.teacher_id: avatar
        for avatar in db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id.in_(teacher_ids)).all()
    }
    booked_by_teacher = {}
    for teacher_id, time_slot in (
        db.query(models.Appointment.teacher_id, models.Appointment.time_slot)
        .filter(
            models.Appointment.teacher_id.in_(teacher_ids),
            models.Appointment.status != "cancelled",
        )
        .all()
    ):
        booked_by_teacher.setdefault(teacher_id, []).append(time_slot)

    result = []
    for t in teachers:
        profile = profiles.get(t.id)
        avatar_row = avatar_rows.get(t.id)
        time_slots = []
        if profile and profile.time_slots:
            try:
                time_slots = json.loads(profile.time_slots)
            except Exception:
                # time_slots is an unvalidated TEXT column; a malformed or deeply
                # nested value must not break the teacher list for the student.
                pass

        booked_slots = booked_by_teacher.get(t.id, [])

        avatar_url = ""
        if avatar_row and avatar_row.relative_path:
            avatar_url = str(request.base_url).rstrip("/") + f"/static/{avatar_row.relative_path.replace('\\', '/')}"
        elif profile and profile.avatar:
            avatar_url = profile.avatar

        result.append({
            "id": t.id,
            "name": t.name or t.username,
            "title": profile.title if profile else "",
            "intro": profile.intro if profile else "",
            "location": profile.location if profile else "",
            "avatar": avatar_url,
            "consultation_direction": profile.consultation_direction if profile else "",
            "time_slots": time_slots,
            "booked_slots": booked_slots,
            "can_book": t.id in bookable
        })
    return result

@articles_router.get("/articles/page", response_model=schemas.ArticlePage)
def get_articles_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    q: str = Query("", max_length=100),
    category: str = Query("", max_length=50),
    sort: str = Query("newest", pattern="^(newest|most-read)$"),
    db: Session = Depends(get_db),
):
    return page_articles(db, page=page, page_size=page_size, q=q.strip(),
                         category=category.strip(), sort=sort)

@articles_router.get("/articles", response_model=List[schemas.ArticleResponse])
def get_articles(db: Session = Depends(get_db)):
    _ensure_article_views_initialized(db)
    rows = db.query(models.Article).order_by(models.Article.created_at.desc()).all()
    for article in rows:
        article.views = _read_article_views_cached(article.id, article.views or 0)
    return rows

@articles_router.get("/articles/{article_id}", response_model=schemas.ArticleResponse)
def get_article_detail(article_id: int, db: Session = Depends(get_db)):
    _ensure_article_views_initialized(db)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.views = _read_article_views_cached(article.id, article.views or 0)
    return article

@articles_router.post("/articles/{article_id}/view", response_model=schemas.ArticleViewTrackResponse)
def track_article_view(
    article_id: int,
    payload: schemas.ArticleViewTrackRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    _ensure_article_views_initialized(db)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    viewer_key = _build_viewer_key(request, payload.viewer_id)
    token_expiry = _consume_view_token_expiry(viewer_key, article_id)
    should_count = token_expiry is not None
    if should_count:
        try:
            views = _increment_article_views_atomic(db, article_id)
        except Exception:
            _release_view_token(viewer_key, article_id, token_expiry)
            raise
    else:
        article = db.query(models.Article).filter(models.Article.id == article_id).first()
        views = _read_article_views_cached(article_id, article.views if article else 0)

    return schemas.ArticleViewTrackResponse(
        article_id=article_id,
        views=views,
        counted=should_count,
        dedup_window_seconds=ARTICLE_VIEW_DEDUP_WINDOW_SECONDS,
    )
