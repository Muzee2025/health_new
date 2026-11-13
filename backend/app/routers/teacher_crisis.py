from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import exists, func, insert, literal, select, update
from sqlalchemy.orm import Session, joinedload

from app.services.crisis_pending_service import merge_pending_records, paginate_rows
from app.student_access import assigned_student_ids, require_assigned_student
from app.support_workflow import append_event, require_support_schema
from app.utils.websocket_manager import manager

from .. import models
from ..database import get_db
from .auth import get_current_user
from .teacher_shared import check_teacher_role

router = APIRouter(prefix="/api/teacher")
follow_up_router = APIRouter(prefix="/api/teacher")

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

@follow_up_router.get("/follow-ups")
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

@follow_up_router.post("/follow-ups", status_code=201)
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

@follow_up_router.post("/follow-ups/{task_id}/complete")
def complete_follow_up(task_id: int, payload: FollowUpComplete, db: Session = Depends(get_db),
                        current_user: models.User = Depends(get_current_user)):
    if not payload.outcome.strip():
        raise HTTPException(status_code=422, detail="outcome is required")
    return _transition_follow_up(task_id, "completed", payload.outcome.strip(), db, current_user)

@follow_up_router.post("/follow-ups/{task_id}/cancel")
def cancel_follow_up(task_id: int, payload: FollowUpCancel, db: Session = Depends(get_db),
                     current_user: models.User = Depends(get_current_user)):
    if not payload.reason.strip():
        raise HTTPException(status_code=422, detail="reason is required")
    return _transition_follow_up(task_id, "cancelled", payload.reason.strip(), db, current_user)
