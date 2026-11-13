import hashlib
import json
import os
import random
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List

import bcrypt
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, insert, literal, select, update
from sqlalchemy.orm import Session, joinedload

from app.security import validate_new_password
from app.services.article_catalog import page_articles
from app.services.crisis_pending_service import (
    merge_pending_records,
    paginate_rows,
)
from app.services.rag_service import (
    add_document_to_rag,
    delete_document_from_rag,
    get_rag_status,
)
from app.student_access import assigned_student_ids, require_assigned_student
from app.support_workflow import append_event, require_support_schema
from app.upload_security import (
    DOCUMENT_TYPES,
    IMAGE_TYPES,
    MAX_IMAGE_BYTES,
    read_bounded_upload,
    read_image_upload,
    validate_document_content,
    validate_image_content,
)
from app.utils.websocket_manager import manager

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/teacher", tags=["Teacher"])
TEACHER_AVATAR_SUBDIR = "teacher_avatars"
TEACHER_AVATAR_DIR = Path("uploads") / TEACHER_AVATAR_SUBDIR
PICTURE_SOURCE_DIR = Path(r"D:\Muzee\develop\IDEA_code\health_new\picture")
ALLOWED_AVATAR_EXT = set(IMAGE_TYPES)


class CrisisReviewRequest(BaseModel):
    recordId: str
    action: str
    reason: str = Field(min_length=1, max_length=2000)


class CrisisDecisionRequest(BaseModel):
    action: str
    reason: str = Field(min_length=1, max_length=2000)


class FollowUpCreate(BaseModel):
    source_type: str
    source_id: int
    student_id: int
    due_at: datetime
    summary: str = Field(min_length=1, max_length=4000)


class FollowUpComplete(BaseModel):
    outcome: str = Field(min_length=1, max_length=4000)


class FollowUpCancel(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


def _serialize_real_warning_row(db: Session, warning: models.CrisisWarning,
                                message_content: str | None = None) -> dict:
    # message_content is supplied by the batched caller; the per-row lookup below only
    # runs when a caller passes nothing (single-record paths).
    if message_content is not None:
        msg_content = message_content
    else:
        msg_content = ""
        if warning.chat_message_id:
            msg = db.query(models.AIChatMessage).join(models.AIChatSession).filter(models.AIChatMessage.id == warning.chat_message_id, models.AIChatSession.user_id == warning.student_id).first()
            if msg:
                msg_content = msg.content or ""
    return {
        "id": f"real-{warning.id}",
        "createdAt": warning.created_at.strftime("%Y-%m-%d %H:%M:%S") if warning.created_at else None,
        "studentId": str(warning.student.student_id or warning.student_id) if warning.student else str(warning.student_id),
        "studentName": warning.student.name or warning.student.username if warning.student else "未知",
        "className": warning.student.class_name if warning.student else "未知",
        "riskLevel": warning.risk_level,
        "description": msg_content or "未知",
        "status": "pending" if warning.status == "pending" else "reviewed",
        "highlight": True,
    }

def check_teacher_role(user: models.User):
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Teacher role required")
    return user


def _build_avatar_url(request: Request | None, relative_path: str) -> str:
    clean = (relative_path or "").replace("\\", "/").strip("/")
    static_path = f"/static/{clean}"
    if request is None:
        return f"http://127.0.0.1:8000{static_path}"
    return str(request.base_url).rstrip("/") + static_path


def _safe_remove_file(path: Path):
    try:
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        # 文件清理失败不影响主流程
        pass


def _upsert_teacher_avatar_content(
    *,
    request: Request,
    db: Session,
    teacher_id: int,
    content: bytes,
    ext: str,
):
    image_hash = hashlib.sha256(content).hexdigest()
    conflict = (
        db.query(models.TeacherAvatar)
        .filter(
            models.TeacherAvatar.image_hash == image_hash,
            models.TeacherAvatar.teacher_id != teacher_id,
        )
        .first()
    )
    if conflict:
        raise HTTPException(status_code=409, detail="该头像已被其他教师使用，禁止共用图片")

    TEACHER_AVATAR_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"teacher_{teacher_id}_{uuid.uuid4().hex}{ext}"
    relative_path = f"{TEACHER_AVATAR_SUBDIR}/{filename}"
    abs_path = Path("uploads") / relative_path

    with abs_path.open("wb") as f:
        f.write(content)

    old_abs_path: Path | None = None
    avatar = db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id == teacher_id).first()
    if avatar:
        old_abs_path = Path("uploads") / avatar.relative_path
        avatar.file_name = filename
        avatar.relative_path = relative_path
        avatar.image_hash = image_hash
        avatar.file_size = len(content)
    else:
        avatar = models.TeacherAvatar(
            teacher_id=teacher_id,
            file_name=filename,
            relative_path=relative_path,
            image_hash=image_hash,
            file_size=len(content),
        )
        db.add(avatar)

    profile = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == teacher_id).first()
    avatar_url = _build_avatar_url(request, relative_path)
    if profile:
        profile.avatar = avatar_url
    else:
        db.add(models.TeacherProfile(user_id=teacher_id, avatar=avatar_url, time_slots="[]"))
    try:
        db.commit()
    except Exception:
        # The file was written before the row: roll it back so a failed commit cannot
        # leave an unreferenced image on disk. Only the file written just above is
        # removed; the previous avatar is untouched.
        db.rollback()
        _safe_remove_file(abs_path)
        raise

    if old_abs_path and old_abs_path != abs_path:
        _safe_remove_file(old_abs_path)

    return {
        "message": "头像上传成功",
        "teacher_id": teacher_id,
        "avatar_url": avatar_url,
        "relative_path": relative_path,
        "image_hash": image_hash,
        "file_size": len(content),
    }


@router.get("/crisis/pending")
def get_pending_crisis_records(
    page: int = 1,
    pageSize: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    real_warnings = (
        db.query(models.CrisisWarning)
        .filter(models.CrisisWarning.status == "pending", models.CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id)))
        .options(joinedload(models.CrisisWarning.student))
        .order_by(models.CrisisWarning.created_at.desc())
        .all()
    )
    # One batched message lookup instead of one per warning row. Keyed by
    # (message id, owning student): the same message can be named by two warnings, so a
    # lookup keyed by message id alone would hand one student's message to the other.
    # The warnings are joined rather than passed as an IN list: a pending-warning list has
    # no upper bound, and SQLite rejects a statement once it binds more than 32766
    # variables (SQLITE_LIMIT_VARIABLE_NUMBER), which a per-row loop never did.
    pending_messages: dict[tuple[int, int], str] = {}
    if real_warnings:
        for message_id, content, owner in (
            db.query(models.AIChatMessage.id, models.AIChatMessage.content,
                     models.AIChatSession.user_id)
            .join(models.AIChatSession, models.AIChatSession.id == models.AIChatMessage.session_id)
            .join(models.CrisisWarning, models.CrisisWarning.chat_message_id == models.AIChatMessage.id)
            .filter(models.CrisisWarning.status == "pending",
                    models.CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id)))
            .all()
        ):
            pending_messages[(message_id, owner)] = content or ""
    real_rows = [_serialize_real_warning_row(
        db, warning,
        (pending_messages.get((warning.chat_message_id, warning.student_id), "")
         if warning.chat_message_id else ""),
    ) for warning in real_warnings]
    mock_rows = []  # Global synthetic records do not establish a trusted assignment.
    merged_rows = merge_pending_records(mock_rows, real_rows)
    data = paginate_rows(merged_rows, page=page, page_size=pageSize)
    return {"status": "success", "data": data}


@router.post("/crisis/review")
async def review_pending_crisis(
    payload: CrisisReviewRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    record_id = (payload.recordId or "").strip()
    if not record_id:
        raise HTTPException(status_code=400, detail="recordId is required")

    if record_id.startswith("mock-"):
        raise HTTPException(status_code=404, detail="Warning not found")

    if not record_id.startswith("real-"):
        raise HTTPException(status_code=400, detail="recordId must start with real- or mock-")

    source_id = record_id.removeprefix("real-")
    try:
        warning_id = int(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="real record id must be integer") from exc

    warning = db.query(models.CrisisWarning).filter(models.CrisisWarning.id == warning_id, models.CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")
    if payload.action not in {"pass", "reject", "escalate"}:
        raise HTTPException(status_code=422, detail="action must be pass, reject, or escalate")
    reason = payload.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    require_support_schema(db)
    result = db.execute(update(models.CrisisWarning)
        .where(models.CrisisWarning.id == warning_id, models.CrisisWarning.status == "pending",
            models.CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id)))
        .values(status="processed", processed_at=func.now(), processed_by=current_user.id))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Warning was already reviewed")
    append_event(db, subject_type="crisis_warning", subject_id=warning_id,
                 student_id=warning.student_id, actor_id=current_user.id,
                 action=payload.action, reason=reason)
    db.commit()
    db.refresh(warning)
    try:
        await manager.send_personal_message({
            "type": "warning_processed",
            "data": {"warning_id": warning.id, "status": "processed",
                     "message": "预警信息已由老师审阅"},
        }, warning.student_id, "student")
    except Exception:
        # The durable review must remain successful when a live socket is absent.
        pass
    return {"status": "success", "data": {"recordId": record_id, "action": payload.action,
        "reason": reason, "status": "processed", "reviewed_at": warning.processed_at,
        "reviewed_by": current_user.name or current_user.username}}


@router.get("/crisis/{warning_id}/reviews")
def get_crisis_review_history(warning_id: int, db: Session = Depends(get_db),
                              current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    warning = db.query(models.CrisisWarning).filter(
        models.CrisisWarning.id == warning_id,
        models.CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if warning is None:
        raise HTTPException(status_code=404, detail="Warning not found")
    events = (db.query(models.SupportWorkflowEvent)
        .filter_by(subject_type="crisis_warning", subject_id=warning_id)
        .order_by(models.SupportWorkflowEvent.id.asc()).all())
    # One lookup for every actor the events name, instead of one query per event. The
    # actor set is a subquery over the same events, not an IN list of the ids just
    # collected: an event list has no upper bound, and SQLite rejects a statement once it
    # binds more than 32766 variables, which the per-row loop never did.
    actor_ids = db.query(models.SupportWorkflowEvent.actor_id).filter_by(
        subject_type="crisis_warning", subject_id=warning_id)
    actor_names = {
        actor.id: (actor.name or actor.username)
        for actor in db.query(models.User).filter(
            models.User.id.in_(actor_ids.subquery().select())).all()
    }
    return {"status": "success", "data": [{"action": e.action, "reason": e.reason,
        "reviewed_at": e.created_at, "reviewed_by": actor_names.get(e.actor_id)} for e in events]}


def _support_actor_name(db: Session, actor_id: int | None):
    actor = db.query(models.User).filter_by(id=actor_id).first() if actor_id else None
    return (actor.name or actor.username) if actor else None


@router.get("/questions")
def list_assigned_questions(status: str | None = None, db: Session = Depends(get_db),
                            current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    if status not in (None, "pending", "answered"):
        raise HTTPException(status_code=422, detail="status must be pending or answered")
    query = (db.query(models.Question).join(models.User, models.User.id == models.Question.user_id)
        .filter(models.Question.user_id.in_(assigned_student_ids(db, current_user.id)))
        .options(joinedload(models.Question.user)))
    if status:
        query = query.filter(models.Question.status == status)
    questions = query.order_by(models.Question.created_at.desc()).all()
    if not questions:
        return {"status": "success", "data": []}
    # The newest answer event per question in one query, then one lookup for every
    # actor named by those events: two statements instead of two per question. Both are
    # joined to the question set rather than passed as an IN list, so a teacher with a very
    # long question list cannot exceed SQLite's 32766 bound-variable limit.
    assigned_questions = (
        db.query(models.Question.id)
        .filter(models.Question.user_id.in_(assigned_student_ids(db, current_user.id)))
    )
    if status:
        assigned_questions = assigned_questions.filter(models.Question.status == status)
    ranked_events = (
        db.query(
            models.SupportWorkflowEvent.id.label("event_id"),
            models.SupportWorkflowEvent.subject_id.label("subject_id"),
            func.row_number().over(
                partition_by=models.SupportWorkflowEvent.subject_id,
                order_by=models.SupportWorkflowEvent.id.desc(),
            ).label("position"),
        )
        .filter(
            models.SupportWorkflowEvent.subject_type == "question",
            models.SupportWorkflowEvent.subject_id.in_(assigned_questions.subquery().select()),
            models.SupportWorkflowEvent.action == "answer",
        )
        .subquery()
    )
    events_by_question = {
        event.subject_id: event
        for event in (
            db.query(models.SupportWorkflowEvent)
            .join(ranked_events, ranked_events.c.event_id == models.SupportWorkflowEvent.id)
            .filter(ranked_events.c.position == 1)
            .all()
        )
    }
    # The actors are referenced as a subquery over the same ranked events, not as an IN
    # list of the ids just collected: a question list has no upper bound, and SQLite
    # rejects a statement once it binds more than 32766 variables, which the per-row loop
    # this batching replaced never did. The join keeps the same rows as the dict above,
    # because it reads the same ranked events at position 1.
    actor_ids = (
        db.query(models.SupportWorkflowEvent.actor_id)
        .join(ranked_events, ranked_events.c.event_id == models.SupportWorkflowEvent.id)
        .filter(ranked_events.c.position == 1)
    )
    actors = {
        actor.id: actor
        for actor in db.query(models.User).filter(
            models.User.id.in_(actor_ids.subquery().select())).all()
    }

    output = []
    for question in questions:
        event = events_by_question.get(question.id)
        actor = actors.get(event.actor_id) if event and event.actor_id else None
        output.append({"id": question.id, "student_id": question.user_id,
            "student_name": question.user.name or question.user.username,
            "question_text": question.question_text, "status": question.status,
            "created_at": question.created_at, "answer_text": question.answer_text,
            "answered_at": event.created_at if event else None,
            "answered_by": (actor.name or actor.username) if actor else None})
    return {"status": "success", "data": output}


@router.post("/questions/{question_id}/answer")
def answer_assigned_question(question_id: int, payload: schemas.QuestionAnswer,
                             db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    answer_text = payload.answer_text.strip()
    if not answer_text:
        raise HTTPException(status_code=422, detail="answer_text is required")
    question = (db.query(models.Question)
        .filter(models.Question.id == question_id,
            models.Question.user_id.in_(assigned_student_ids(db, current_user.id))).first())
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    result = db.execute(update(models.Question).where(
        models.Question.id == question_id, models.Question.status == "pending",
        models.Question.user_id.in_(assigned_student_ids(db, current_user.id)),
        (models.Question.answer_text.is_(None) | (models.Question.answer_text == ""))
    ).values(answer_text=answer_text, status="answered"))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Question already has a response")
    event = append_event(db, subject_type="question", subject_id=question_id,
        student_id=question.user_id, actor_id=current_user.id, action="answer", result_text=answer_text)
    db.commit()
    db.refresh(event)
    return {"status": "success", "data": {"id": question_id, "status": "answered",
        "answer_text": answer_text, "answered_at": event.created_at,
        "answered_by": current_user.name or current_user.username}}


def _follow_up_dict(task: models.SupportFollowUp, db: Session):
    def as_utc(value):
        if value is None:
            return None
        normalized = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return normalized.isoformat().replace("+00:00", "Z")

    return {"id": task.id, "source_type": task.source_type, "source_id": task.source_id,
        "student_id": task.student_id, "due_at": as_utc(task.due_at), "summary": task.summary,
        "status": task.status, "created_by": task.created_by, "created_at": as_utc(task.created_at),
        "outcome": task.outcome, "completed_at": as_utc(task.completed_at),
        "cancelled_at": as_utc(task.cancelled_at)}


@router.get("/follow-ups")
def list_follow_ups(status: str | None = None, db: Session = Depends(get_db),
                    current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    if status not in (None, "open", "completed", "cancelled"):
        raise HTTPException(status_code=422, detail="Unsupported follow-up status")
    query = db.query(models.SupportFollowUp).filter(
        models.SupportFollowUp.created_by == current_user.id,
        models.SupportFollowUp.student_id.in_(assigned_student_ids(db, current_user.id)))
    if status:
        query = query.filter(models.SupportFollowUp.status == status)
    tasks = query.order_by(models.SupportFollowUp.due_at.asc()).all()
    return {"status": "success", "data": [_follow_up_dict(t, db) for t in tasks]}


@router.post("/follow-ups", status_code=201)
def create_follow_up(payload: FollowUpCreate, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    require_support_schema(db)
    student = require_assigned_student(db, current_user.id, payload.student_id)
    source_type = payload.source_type.strip()
    summary = payload.summary.strip()
    if not summary:
        raise HTTPException(status_code=422, detail="summary is required")
    if payload.due_at.tzinfo is None or payload.due_at.utcoffset() is None:
        raise HTTPException(status_code=422, detail="due_at must include a timezone offset")
    due_at_utc = payload.due_at.astimezone(timezone.utc).replace(tzinfo=None)
    if source_type == "question":
        source = db.query(models.Question).filter_by(id=payload.source_id, user_id=student.id).first()
    elif source_type == "crisis_warning":
        source = db.query(models.CrisisWarning).filter_by(id=payload.source_id, student_id=student.id).first()
    else:
        raise HTTPException(status_code=422, detail="source_type must be question or crisis_warning")
    if source is None:
        raise HTTPException(status_code=404, detail="Source record not found")
    assignment_exists = exists(select(1).select_from(models.TeacherStudentAssignment).where(
        models.TeacherStudentAssignment.teacher_id == current_user.id,
        models.TeacherStudentAssignment.student_id == student.id))
    if source_type == "question":
        source_exists = exists(select(1).select_from(models.Question).where(
            models.Question.id == payload.source_id, models.Question.user_id == models.User.id))
    else:
        source_exists = exists(select(1).select_from(models.CrisisWarning).where(
            models.CrisisWarning.id == payload.source_id, models.CrisisWarning.student_id == models.User.id))
    statement = insert(models.SupportFollowUp).from_select(
        ["source_type", "source_id", "student_id", "created_by", "due_at", "summary", "status"],
        select(literal(source_type), literal(payload.source_id), models.User.id, literal(current_user.id),
            literal(due_at_utc), literal(summary), literal("open")).where(
                models.User.id == student.id, models.User.role == "student", assignment_exists, source_exists)
    ).returning(models.SupportFollowUp.id)
    task_id = db.execute(statement).scalar_one_or_none()
    if task_id is None:
        db.rollback()
        raise HTTPException(status_code=404, detail="Student assignment or source record is no longer available")
    task = db.get(models.SupportFollowUp, task_id)
    db.add(models.SupportFollowUpEvent(follow_up_id=task_id, actor_id=current_user.id,
        action="created", note=summary))
    db.commit()
    db.refresh(task)
    return {"status": "success", "data": _follow_up_dict(task, db)}


def _transition_follow_up(task_id: int, action: str, note: str, db: Session, current_user: models.User):
    check_teacher_role(current_user)
    require_support_schema(db)
    task = db.query(models.SupportFollowUp).filter(
        models.SupportFollowUp.id == task_id, models.SupportFollowUp.created_by == current_user.id,
        models.SupportFollowUp.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if task is None:
        raise HTTPException(status_code=404, detail="Follow-up not found")
    fields = {"status": action, "outcome": note,
        "completed_at": func.now() if action == "completed" else None,
        "cancelled_at": func.now() if action == "cancelled" else None}
    result = db.execute(update(models.SupportFollowUp).where(
        models.SupportFollowUp.id == task_id, models.SupportFollowUp.status == "open",
        models.SupportFollowUp.created_by == current_user.id,
        models.SupportFollowUp.student_id.in_(assigned_student_ids(db, current_user.id))).values(**fields))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(status_code=409, detail="Follow-up is already closed")
    db.add(models.SupportFollowUpEvent(follow_up_id=task_id, actor_id=current_user.id,
        action=action, note=note))
    db.commit()
    db.refresh(task)
    return {"status": "success", "data": _follow_up_dict(task, db)}


@router.post("/follow-ups/{task_id}/complete")
def complete_follow_up(task_id: int, payload: FollowUpComplete, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    if not payload.outcome.strip():
        raise HTTPException(status_code=422, detail="outcome is required")
    return _transition_follow_up(task_id, "completed", payload.outcome.strip(), db, current_user)


@router.post("/follow-ups/{task_id}/cancel")
def cancel_follow_up(task_id: int, payload: FollowUpCancel, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    if not payload.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required")
    return _transition_follow_up(task_id, "cancelled", payload.reason.strip(), db, current_user)

@router.post("/upload")
async def upload_file(request: Request, file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    content = await read_bounded_upload(file)
    requested_ext = Path(file.filename or "").suffix.lower()
    is_document = requested_ext in DOCUMENT_TYPES
    if is_document:
        ext = validate_document_content(content, file.filename or "", file.content_type)
        directory = _article_document_directory()
    else:
        ext = validate_image_content(content, file.filename or "", file.content_type)
        directory = Path("uploads") / "public_images"
        directory.mkdir(parents=True, exist_ok=True)
        if directory.is_symlink():
            raise HTTPException(status_code=503, detail="Upload storage is unavailable")
    filename = f"{uuid.uuid4().hex}{ext}"
    try:
        with (directory / filename).open("xb") as stream:
            stream.write(content)
    except OSError:
        raise HTTPException(status_code=503, detail="Upload storage is unavailable") from None
    if is_document:
        return {"url": str(request.url_for("download_article_document", filename=filename))}
    return {"url": str(request.base_url).rstrip("/") + f"/static/public_images/{filename}"}


def _article_document_directory() -> Path:
    base = Path("uploads").resolve()
    directory = base / "article_documents"
    if directory.is_symlink():
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    directory.mkdir(parents=True, exist_ok=True)
    if directory.resolve().parent != base:
        raise HTTPException(status_code=503, detail="Document storage is unavailable")
    return directory


@router.get("/documents/{filename}")
def download_article_document(filename: str, current_user: models.User = Depends(get_current_user)):
    if current_user.role not in {"student", "teacher"}:
        raise HTTPException(status_code=403, detail="Sign in to download this document")
    if not re.fullmatch(r"[0-9a-f]{32}\.(?:pdf|docx)", filename):
        raise HTTPException(status_code=404, detail="Document not found")
    directory = _article_document_directory()
    path = directory / filename
    if path.is_symlink() or not path.is_file() or path.resolve().parent != directory.resolve():
        raise HTTPException(status_code=404, detail="Document not found")
    return FileResponse(path, media_type=DOCUMENT_TYPES[path.suffix], filename=f"document{path.suffix}",
                        headers={"X-Content-Type-Options": "nosniff", "Content-Security-Policy": "sandbox; default-src 'none'", "Cache-Control": "private, no-store"})


@router.post("/avatar")
async def upload_teacher_avatar(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    """
    教师头像上传（严格一对一）：
    1) teacher_id 在 teacher_avatars 唯一；
    2) image_hash 全局唯一，禁止共用同一张图；
    3) 上传新头像时自动删除旧头像文件并更新记录。
    """
    check_teacher_role(current_user)
    content, ext = await read_image_upload(file)

    return _upsert_teacher_avatar_content(
        request=request,
        db=db,
        teacher_id=current_user.id,
        content=content,
        ext=ext,
    )


class AvatarFromPictureRequest(BaseModel):
    filename: str


@router.post("/avatar/from-picture")
def set_teacher_avatar_from_picture(
    payload: AvatarFromPictureRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    filename = os.path.basename((payload.filename or "").strip())
    if not filename:
        raise HTTPException(status_code=400, detail="filename 不能为空")
    source_path = PICTURE_SOURCE_DIR / filename
    ext = source_path.suffix.lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail=f"仅支持 {sorted(ALLOWED_AVATAR_EXT)} 格式")
    if not source_path.exists() or not source_path.is_file():
        raise HTTPException(status_code=404, detail="指定图片不存在")
    if source_path.stat().st_size > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image must be at most 5 MiB")
    content = source_path.read_bytes()
    ext = validate_image_content(content, filename)
    return _upsert_teacher_avatar_content(
        request=request,
        db=db,
        teacher_id=current_user.id,
        content=content,
        ext=ext,
    )

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    # Risk distribution based on AI Chat sessions
    students = db.query(models.User).filter(models.User.role == "student", models.User.id.in_(assigned_student_ids(db, current_user.id))).all()
    total_students = len(students)
    risk_dist = {"green": 0, "yellow": 0, "red": 0, "untested": 0}
    high_risk_count = 0
    warnings = []

    # One statement for the whole roster: rank each student's tagged AI replies and keep
    # the newest five. This replaces two queries per student and keeps the original
    # per-student "latest 5 messages" window exactly (window functions need SQLite 3.25+).
    ranked_messages = (
        db.query(
            models.AIChatSession.user_id.label("user_id"),
            models.AIChatMessage.id.label("message_id"),
            func.row_number().over(
                partition_by=models.AIChatSession.user_id,
                order_by=models.AIChatMessage.created_at.desc(),
            ).label("position"),
        )
        .join(models.AIChatSession, models.AIChatSession.id == models.AIChatMessage.session_id)
        .filter(
            models.AIChatSession.user_id.in_(assigned_student_ids(db, current_user.id)),
            models.AIChatMessage.role == "ai",
            models.AIChatMessage.emotion_tags.is_not(None),
        )
        .subquery()
    )
    messages_by_student = {}
    latest_rows = (
        db.query(models.AIChatMessage, ranked_messages.c.user_id)
        .join(ranked_messages, ranked_messages.c.message_id == models.AIChatMessage.id)
        .filter(ranked_messages.c.position <= 5)
        .all()
    )
    for message, student_id in latest_rows:
        messages_by_student.setdefault(student_id, []).append(message)

    for s in students:
        latest_ai_msgs = messages_by_student.get(s.id, [])
        if latest_ai_msgs:
            # Calculate average stress from recent messages
            stress_sum = 0
            count = 0
            has_crisis = False
            for msg in latest_ai_msgs:
                if msg.is_crisis:
                    has_crisis = True
                try:
                    tags = json.loads(msg.emotion_tags)
                    stress_sum += (tags.get("sadness", 0) + tags.get("fear", 0) + tags.get("anger", 0)) / 3
                    count += 1
                except Exception:
                    # emotion_tags is a free-text JSON column: legacy rows may hold a
                    # list or null, so tags.get() can raise AttributeError as well as
                    # json.loads raising TypeError/ValueError. Skip such rows.
                    pass

            avg_stress = stress_sum / count if count > 0 else 0

            if has_crisis or avg_stress > 0.7:
                risk_dist["red"] += 1
                high_risk_count += 1
                warnings.append({
                    "id": s.id,
                    "student_id": s.student_id,
                    "name": s.name,
                    "score": round(avg_stress * 100),
                    "risk_level": "red"
                })
            elif avg_stress > 0.4:
                risk_dist["yellow"] += 1
            else:
                risk_dist["green"] += 1
        else:
            risk_dist["untested"] += 1

    # Appointments stats
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    today_appointments = db.query(models.Appointment).filter(models.Appointment.time_slot.like(f"%{today_str}%"), models.Appointment.teacher_id == current_user.id, models.Appointment.student_id.in_(assigned_student_ids(db, current_user.id))).count()
    
    week_ago = today - timedelta(days=7)
    week_completed = db.query(models.Appointment).filter(
        models.Appointment.status == "completed",
        models.Appointment.created_at >= week_ago,
        models.Appointment.teacher_id == current_user.id,
        models.Appointment.student_id.in_(assigned_student_ids(db, current_user.id))
    ).count()
    
    emotion_trend = []
    trend_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    trend_end = datetime.combine(today, datetime.min.time()) + timedelta(days=1)
    # One statement for the whole 7-day window; each message is bucketed by its own day
    # so the per-day averages and sample counts stay identical to the per-day queries.
    trend_messages = (db.query(models.AIChatMessage.created_at, models.AIChatMessage.emotion_tags)
                      .join(models.AIChatSession)
                      .filter(models.AIChatSession.user_id.in_(assigned_student_ids(db, current_user.id)),
                              models.AIChatMessage.created_at >= trend_start,
                              models.AIChatMessage.created_at < trend_end,
                              models.AIChatMessage.role == "ai").all())
    trend_values = {}
    for created_at, emotion_tags in trend_messages:
        day = created_at.date() if hasattr(created_at, "date") else created_at
        try:
            value = json.loads(emotion_tags or "{}").get("joy")
        except (ValueError, TypeError):
            continue
        if isinstance(value, (int, float)) and 0 <= value <= 1:
            trend_values.setdefault(day, []).append(value)

    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        values = trend_values.get(day, [])
        emotion_trend.append({"day": day.isoformat(), "score": round(sum(values) / len(values) * 100, 1) if values else None,
                              "sample_count": len(values)})

    # Word cloud from chat content (AIChatMessage no longer stores keywords field)
    chat_msgs = db.query(models.AIChatMessage.content).join(models.AIChatSession, models.AIChatSession.id == models.AIChatMessage.session_id).filter(models.AIChatSession.user_id.in_(assigned_student_ids(db, current_user.id)), models.AIChatMessage.content.is_not(None)).all()
    stop_words = {
        "今天", "就是", "这个", "那个", "我们", "你们", "他们", "然后", "因为", "所以", "自己",
        "可以", "如果", "现在", "老师", "学生", "心理", "感觉", "有点", "没有", "已经", "一个",
        "the", "and", "for", "with", "that", "this", "from",
    }
    counter = Counter()
    token_pattern = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z]{3,}")
    for row in chat_msgs:
        text = row[0] if isinstance(row, tuple) else getattr(row, "content", "")
        if not text:
            continue
        for token in token_pattern.findall(str(text)):
            t = token.lower()
            if t in stop_words:
                continue
            counter[t] += 1

    word_cloud = [{"name": k, "value": v} for k, v in counter.most_common(10)]
    return {
        "source": "assigned_students",
        "data_status": "measured" if total_students else "empty",
        "kpi": {
            "total_students": total_students,
            "high_risk_count": high_risk_count,
            "today_appointments": today_appointments,
            "week_completed": week_completed
        },
        "risk_distribution": [
            {"name": "正常 (绿)", "value": risk_dist["green"]},
            {"name": "关注 (黄)", "value": risk_dist["yellow"]},
            {"name": "预警 (红)", "value": risk_dist["red"]},
            {"name": "未测评", "value": risk_dist["untested"]}
        ],
        "emotion_trend": emotion_trend,
        "word_cloud": word_cloud,
        "warnings": warnings
    }

@router.get("/appointments")
def get_appointments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    
    # An ordinary teacher may only view their own appointments.
    appointments = db.query(models.Appointment).filter(models.Appointment.teacher_id == current_user.id, models.Appointment.student_id.in_(assigned_student_ids(db, current_user.id))).order_by(models.Appointment.created_at.desc()).all()
    if not appointments:
        return []
    # Prefetch the related rows in three statements instead of three per appointment.
    # The response shape is unchanged; only the lookup strategy differs.
    # The students are looked up through the appointments rather than passed as an IN
    # list of the ids just collected: an appointment list has no upper bound, and SQLite
    # rejects a statement once it binds more than 32766 variables, which the per-row
    # loop never did. The subquery starts from the same filtered appointments, so the
    # same rows come back. teacher_ids stays a plain IN list: every appointment above was
    # filtered on teacher_id == current_user.id, so it is a single id.
    # Both halves stay in one query, joined with OR, so a user that is somehow in both
    # sets is still read once, exactly as the single IN (student_ids | teacher_ids) did.
    # Merging two separate lookups into a dict would silently let one row win.
    teacher_ids = {app.teacher_id for app in appointments}
    appt_students = db.query(models.Appointment.student_id).filter(
        models.Appointment.teacher_id == current_user.id,
        models.Appointment.student_id.in_(assigned_student_ids(db, current_user.id)))
    users = {
        user.id: user
        for user in db.query(models.User).filter(
            models.User.id.in_(appt_students.subquery().select())
            | models.User.id.in_(teacher_ids)).all()
    }
    avatars = {
        avatar.teacher_id: avatar
        for avatar in db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id.in_(teacher_ids)).all()
    }
    result = []
    for app in appointments:
        student = users.get(app.student_id)
        teacher = users.get(app.teacher_id)
        teacher_avatar = avatars.get(app.teacher_id)
        result.append({
            "id": app.id,
            "student_name": student.name if student else "Unknown",
            "teacher_id": app.teacher_id,
            "teacher_name": teacher.name if teacher else "Unknown",
            "teacher_avatar": _build_avatar_url(request, teacher_avatar.relative_path) if teacher_avatar else "",
            "time_slot": app.time_slot,
            "status": app.status,
            "created_at": app.created_at
        })
    return result

@router.post("/appointments/{appointment_id}/status")
def update_appointment_status(appointment_id: int, status: str, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id, models.Appointment.teacher_id == current_user.id, models.Appointment.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    if status not in {"pending", "confirmed", "completed", "cancelled"}:
        raise HTTPException(status_code=400, detail="Invalid appointment status")
    appointment.status = status
    db.commit()
    return {"message": f"Appointment status updated to {status}"}

@router.get("/students", response_model=List[schemas.TeacherStudentList])
def get_students(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    students = db.query(models.User).filter(models.User.role == "student", models.User.id.in_(assigned_student_ids(db, current_user.id))).all()
    if not students:
        return []
    # Three batched lookups instead of four per student. The newest SDS/SAS result is
    # ranked per student in one window query, and the pending-warning count and newest
    # timestamp come from a single GROUP BY, so the per-row values are unchanged.
    # The assigned students are referenced as a subquery, not as an IN list of ids: a
    # teacher's student list has no upper bound, and SQLite rejects a statement once it
    # binds more than 32766 variables, which the per-row loop never did.
    assigned_ids = db.query(models.User.id).filter(
        models.User.role == "student",
        models.User.id.in_(assigned_student_ids(db, current_user.id)),
    )
    ranked_tests = (
        db.query(
            models.TestResult.user_id.label("user_id"),
            models.TestResult.id.label("test_id"),
            func.row_number().over(
                partition_by=models.TestResult.user_id,
                order_by=models.TestResult.created_at.desc(),
            ).label("position"),
        )
        .filter(
            models.TestResult.user_id.in_(assigned_ids.subquery().select()),
            models.TestResult.test_type.in_(["SDS", "SAS"]),
        )
        .subquery()
    )
    latest_tests = {
        result.user_id: result
        for result in (
            db.query(models.TestResult)
            .join(ranked_tests, ranked_tests.c.test_id == models.TestResult.id)
            .filter(ranked_tests.c.position == 1)
            .all()
        )
    }
    profiles = {
        profile.user_id: profile
        for profile in db.query(models.StudentProfile).filter(
            models.StudentProfile.user_id.in_(assigned_ids.subquery().select())
        ).all()
    }
    pending_crisis = {
        student_id: (count, newest)
        for student_id, count, newest in (
            db.query(
                models.CrisisWarning.student_id,
                func.count(models.CrisisWarning.id),
                func.max(models.CrisisWarning.created_at),
            )
            .filter(
                models.CrisisWarning.student_id.in_(assigned_ids.subquery().select()),
                models.CrisisWarning.status == "pending",
            )
            .group_by(models.CrisisWarning.student_id)
            .all()
        )
    }

    result = []
    for s in students:
        # A dialogue tag is not an independently measured clinical risk score.
        risk_level = None
        score = None
        latest_test = latest_tests.get(s.id)
        latest_time = latest_test.created_at if latest_test else None

        profile = profiles.get(s.id)
        pending_crisis_count, latest_warning_at = pending_crisis.get(s.id, (0, None))

        result.append(schemas.TeacherStudentList(
            id=s.id,
            student_id=s.student_id,
            name=s.name,
            class_name=s.class_name,
            advisor=s.advisor,
            gender=profile.gender if profile else None,
            parent_phone=profile.parent_phone if profile else None,
            remarks=profile.remarks if profile else None,
            risk_level=risk_level,
            latest_test_time=latest_time,
            latest_test_score=score,
            has_pending_crisis=pending_crisis_count > 0,
            pending_crisis_count=pending_crisis_count,
            latest_crisis_warning_at=latest_warning_at,
        ))
    return result


@router.post("/students")
def create_student(
    payload: schemas.TeacherStudentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    validate_new_password(payload.initial_password)

    name = (payload.name or "").strip()
    student_id = (payload.student_id or "").strip()
    class_name = (payload.class_name or "").strip() or None

    if not name:
        raise HTTPException(status_code=400, detail="姓名不能为空")
    if not student_id:
        raise HTTPException(status_code=400, detail="学号不能为空")

    exists = db.query(models.User).filter(models.User.student_id == student_id).first()
    if exists:
        raise HTTPException(status_code=400, detail="学号已存在")

    username = f"stu_{student_id}"
    while db.query(models.User).filter(models.User.username == username).first():
        username = f"{username}_{random.randint(1000, 9999)}"

    hashed_password = bcrypt.hashpw(payload.initial_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    new_user = models.User(
        username=username,
        password_hash=hashed_password,
        role="student",
        student_id=student_id,
        name=name,
        class_name=class_name,
        advisor=current_user.name or current_user.username,
    )
    db.add(new_user)
    db.flush()

    profile = models.StudentProfile(
        user_id=new_user.id,
        gender=(payload.gender or "").strip() or None,
        parent_phone=(payload.parent_phone or "").strip() or None,
        remarks=(payload.remarks or "").strip() or None,
    )
    db.add(profile)
    db.add(models.TeacherStudentAssignment(teacher_id=current_user.id, student_id=new_user.id))
    db.commit()
    db.refresh(new_user)
    db.refresh(profile)

    return {
        "id": new_user.id,
        "student_id": new_user.student_id,
        "name": new_user.name,
        "class_name": new_user.class_name,
        "advisor": new_user.advisor,
        "gender": profile.gender,
        "parent_phone": profile.parent_phone,
        "remarks": profile.remarks,
        "message": "学生添加成功",
    }

@router.get("/student/{student_id}")
def get_student_detail(student_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    student = require_assigned_student(db, current_user.id, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    test_history = db.query(models.TestResult).filter(models.TestResult.user_id == student_id).order_by(models.TestResult.created_at.asc()).all()
    
    appointments = db.query(models.Appointment).filter(models.Appointment.student_id == student_id, models.Appointment.teacher_id == current_user.id).order_by(models.Appointment.created_at.desc()).all()
    # Every row here is filtered to this teacher, so the name is already loaded on
    # current_user; the per-row User lookup it replaced was always the same row.
    app_result = []
    for app in appointments:
        app_result.append({
            "id": app.id,
            "teacher_name": current_user.name,
            "time_slot": app.time_slot,
            "status": app.status,
            "created_at": app.created_at
        })
        
    treehole_posts = db.query(models.TreeholePost).filter(models.TreeholePost.user_id == student_id).order_by(models.TreeholePost.created_at.desc()).all()
    treehole_summary = []
    for p in treehole_posts:
        treehole_summary.append({
            "id": p.id,
            "created_at": p.created_at,
            "emotion_keywords": p.emotion_keywords,
            "tags": p.tags
        })
        
    intervention_records = db.query(models.InterventionRecord).filter(models.InterventionRecord.student_id == student_id, models.InterventionRecord.teacher_id == current_user.id).order_by(models.InterventionRecord.created_at.desc()).all()
    
    # 获取脱敏聊天记录
    chat_sessions = db.query(models.AIChatSession).filter(models.AIChatSession.user_id == student_id).order_by(models.AIChatSession.created_at.desc()).limit(5).all()
    # One query for all five sessions' messages, grouped afterwards, instead of one
    # query per session. Ordering is kept per session exactly as before.
    messages_by_session = {}
    if chat_sessions:
        for message in (
            db.query(models.AIChatMessage)
            .filter(models.AIChatMessage.session_id.in_([session.id for session in chat_sessions]))
            .order_by(models.AIChatMessage.created_at.asc())
            .all()
        ):
            messages_by_session.setdefault(message.session_id, []).append(message)
    desensitized_chats = []
    for session in chat_sessions:
        msgs = messages_by_session.get(session.id, [])
        session_msgs = []
        for m in msgs:
            # 简单脱敏处理：替换可能的名字/数字（这里只是模拟，实际应调用更复杂的NER模型脱敏）
            content = m.content
            if m.role == "user":
                import re
                content = re.sub(r'1[3-9]\d{9}', '1***', content)
            
            session_msgs.append({
                "role": m.role,
                "content": content,
                "created_at": m.created_at,
                "is_crisis": m.is_crisis
            })
        desensitized_chats.append({
            "session_id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "messages": session_msgs
        })
    
    ai_summary = "尚未生成AI摘要，请结合原始记录进行专业判断。"

    profile = db.query(models.StudentProfile).filter(models.StudentProfile.user_id == student_id).first()

    return {
        "student_info": {
            "id": student.id,
            "name": student.name,
            "student_id": student.student_id,
            "advisor": student.advisor,
            "phone": profile.parent_phone if profile and profile.parent_phone else "暂无",
            "gender": profile.gender if profile else None,
            "remarks": profile.remarks if profile else None,
        },
        "test_history": test_history,
        "appointments": app_result,
        "treehole_summary": treehole_summary,
        "ai_analysis": ai_summary,
        "intervention_records": intervention_records,
        "desensitized_chats": desensitized_chats
    }

@router.post("/interventions")
def add_intervention(record: schemas.InterventionRecordCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    require_assigned_student(db, current_user.id, record.student_id)
    new_record = models.InterventionRecord(
        student_id=record.student_id,
        teacher_id=current_user.id,
        record_date=record.record_date,
        notes=record.notes
    )
    db.add(new_record)
    db.commit()
    db.refresh(new_record)
    return new_record

@router.get("/interventions")
def get_interventions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    records = db.query(models.InterventionRecord).filter(models.InterventionRecord.teacher_id == current_user.id, models.InterventionRecord.student_id.in_(assigned_student_ids(db, current_user.id))).order_by(models.InterventionRecord.created_at.desc()).all()
    if not records:
        return []
    # Two batched lookups instead of two per record. The students come from a subquery
    # over the same filtered records, not from an IN list of the ids just collected: a
    # record list has no upper bound, and SQLite rejects a statement once it binds more
    # than 32766 variables, which the per-row loop never did. teacher_ids stays a plain
    # IN list: every record above was filtered on teacher_id == current_user.id.
    # Both halves stay in one query, joined with OR, so a user that is somehow in both
    # sets is still read once, exactly as the single IN (student_ids | teacher_ids) did.
    teacher_ids = {r.teacher_id for r in records}
    record_students = db.query(models.InterventionRecord.student_id).filter(
        models.InterventionRecord.teacher_id == current_user.id,
        models.InterventionRecord.student_id.in_(assigned_student_ids(db, current_user.id)))
    users = {
        user.id: user
        for user in db.query(models.User).filter(
            models.User.id.in_(record_students.subquery().select())
            | models.User.id.in_(teacher_ids)).all()
    }
    result = []
    for r in records:
        student = users.get(r.student_id)
        teacher = users.get(r.teacher_id)
        result.append({
            "id": r.id,
            "student_name": student.name if student else "Unknown",
            "teacher_name": teacher.name if teacher else "Unknown",
            "record_date": r.record_date,
            "notes": r.notes,
            "created_at": r.created_at
        })
    return result

# Content Management: Articles
@router.get("/articles/page", response_model=schemas.ArticlePage)
def get_articles_page(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    q: str = Query("", max_length=100),
    category: str = Query("", max_length=50),
    sort: str = Query("newest", pattern="^(newest|most-read)$"),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    return page_articles(db, page=page, page_size=page_size, q=q.strip(),
                         category=category.strip(), sort=sort)


@router.get("/articles")
def get_articles(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    return db.query(models.Article).order_by(models.Article.created_at.desc()).all()

@router.get("/articles/{article_id}")
def get_article_detail(article_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    return article

@router.post("/articles")
def create_article(article: schemas.ArticleCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    payload = article.model_dump()
    payload["views"] = 0
    new_article = models.Article(**payload)
    db.add(new_article)
    db.commit()
    db.refresh(new_article)
    return new_article

@router.delete("/articles/{article_id}")
def delete_article(article_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    db.delete(article)
    db.commit()
    return {"message": "Deleted"}

# Content Management: Knowledge Base

@router.get("/knowledge", response_model=List[schemas.KnowledgeBaseResponse])
def get_knowledge_base(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    return db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.created_at.desc()).all()

@router.post("/knowledge", response_model=schemas.KnowledgeBaseResponse)
def create_knowledge(knowledge: schemas.KnowledgeBaseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    new_knowledge = models.KnowledgeBase(**knowledge.model_dump())
    db.add(new_knowledge)
    # Index before committing: the SQL row stays authoritative, so a half-written
    # pair (row without vectors) must never be committed silently. flush() assigns
    # the primary key without ending the transaction, so the row can still be
    # rolled back if the optional index refuses the document.
    db.flush()
    if get_rag_status()["enabled"]:
        if not add_document_to_rag(new_knowledge.id, new_knowledge.title, new_knowledge.content):
            db.rollback()
            raise HTTPException(status_code=503, detail="Knowledge indexing is unavailable")
    db.commit()
    db.refresh(new_knowledge)
    return new_knowledge

@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    knowledge = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    # Remove the vectors first. If that fails, the row is kept so the record stays
    # visible and retryable -- a deleted row with surviving vectors would still be
    # retrievable by students, which is a disclosure rather than a dirty row.
    if get_rag_status()["enabled"]:
        if not delete_document_from_rag(knowledge_id):
            raise HTTPException(status_code=503, detail="Knowledge index removal is unavailable")
    db.delete(knowledge)
    db.commit()
    return {"message": "Deleted"}
@router.get("/teachers_profiles")
def get_teachers_profiles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    teachers = db.query(models.User).filter(models.User.role == "teacher").all()
    if not teachers:
        return []
    # Two batched lookups instead of two per teacher. The teacher set is referenced as a
    # subquery over the same role filter, not as an IN list of the ids just collected: the
    # teacher table has no upper bound, and SQLite rejects a statement once it binds more
    # than 32766 variables, which the per-row loop this batching replaced never did.
    # Measured before this change: 32767 teachers raised "too many SQL variables".
    teacher_ids = db.query(models.User.id).filter(models.User.role == "teacher")
    profiles = {
        profile.user_id: profile
        for profile in db.query(models.TeacherProfile).filter(
            models.TeacherProfile.user_id.in_(teacher_ids.subquery().select())).all()
    }
    avatars = {
        avatar.teacher_id: avatar
        for avatar in db.query(models.TeacherAvatar).filter(
            models.TeacherAvatar.teacher_id.in_(teacher_ids.subquery().select())).all()
    }
    result = []
    for t in teachers:
        profile = profiles.get(t.id)
        avatar = avatars.get(t.id)
        result.append({
            "user_id": t.id,
            "username": t.username,
            "name": t.name,
            "title": profile.title if profile else "",
            "intro": profile.intro if profile else "",
            "location": profile.location if profile else "",
            "avatar": _build_avatar_url(request, avatar.relative_path) if avatar else (profile.avatar if profile else ""),
            "time_slots": json.loads(profile.time_slots) if profile and profile.time_slots else []
        })
    return result

@router.post("/teachers_profiles")
def create_teacher_profile(profile: schemas.TeacherProfileCreateUpdate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    if profile.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only your own teacher profile may be changed")
    existing = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == profile.user_id).first()
    time_slots_str = json.dumps(profile.time_slots) if profile.time_slots else "[]"
    
    if existing:
        existing.title = profile.title
        existing.intro = profile.intro
        existing.location = profile.location
        existing.time_slots = time_slots_str
    else:
        new_prof = models.TeacherProfile(
            user_id=profile.user_id,
            title=profile.title,
            intro=profile.intro,
            location=profile.location,
            time_slots=time_slots_str
        )
        db.add(new_prof)
    db.commit()
    return {"message": "Profile updated"}

@router.delete("/teachers_profiles/{user_id}")
def delete_teacher_profile(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    # The former implementation deleted User and its cascaded records.
    raise HTTPException(status_code=403, detail="Account deletion is unavailable through teacher profiles")
