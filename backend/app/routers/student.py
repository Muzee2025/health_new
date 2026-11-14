from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.services import qwen_service
from app.student_access import assigned_teacher_ids

from .. import models, schemas
from ..database import get_db
from . import student_report as student_report
from . import student_treehole as student_treehole
from .auth import get_current_user
from .student_content import (
    ARTICLE_VIEW_CACHE as ARTICLE_VIEW_CACHE,
)
from .student_content import (
    ARTICLE_VIEW_DEDUP_WINDOW_SECONDS as ARTICLE_VIEW_DEDUP_WINDOW_SECONDS,
)
from .student_content import (
    ARTICLE_VIEW_IDEMPOTENCY as ARTICLE_VIEW_IDEMPOTENCY,
)
from .student_content import (
    ARTICLE_VIEW_INIT_MAX as ARTICLE_VIEW_INIT_MAX,
)
from .student_content import (
    ARTICLE_VIEW_INIT_MIN as ARTICLE_VIEW_INIT_MIN,
)
from .student_content import (
    ARTICLE_VIEW_LOCK as ARTICLE_VIEW_LOCK,
)
from .student_content import (
    _build_viewer_key as _build_viewer_key,
)
from .student_content import (
    _cleanup_view_idempotency as _cleanup_view_idempotency,
)
from .student_content import (
    _consume_view_token as _consume_view_token,
)
from .student_content import (
    _consume_view_token_expiry as _consume_view_token_expiry,
)
from .student_content import (
    _ensure_article_views_initialized as _ensure_article_views_initialized,
)
from .student_content import (
    _generate_initial_article_views as _generate_initial_article_views,
)
from .student_content import (
    _increment_article_views_atomic as _increment_article_views_atomic,
)
from .student_content import (
    _is_sqlite_lock_error as _is_sqlite_lock_error,
)
from .student_content import (
    _read_article_views_cached as _read_article_views_cached,
)
from .student_content import (
    _release_view_token as _release_view_token,
)
from .student_content import (
    _touch_article_view_cache as _touch_article_view_cache,
)
from .student_content import (
    articles_router as _student_articles_router,
)
from .student_content import (
    get_article_detail as get_article_detail,
)
from .student_content import (
    get_articles as get_articles,
)
from .student_content import (
    get_articles_page as get_articles_page,
)
from .student_content import (
    get_teachers as get_teachers,
)
from .student_content import (
    teachers_router as _student_teachers_router,
)
from .student_content import (
    track_article_view as track_article_view,
)
from .student_dashboard import (
    _adjust_liming_emotion_index as _adjust_liming_emotion_index,
)
from .student_dashboard import (
    get_appointment_stats as get_appointment_stats,
)
from .student_dashboard import (
    get_dashboard_stats as get_dashboard_stats,
)
from .student_dashboard import (
    get_emotion_trend as get_emotion_trend,
)
from .student_dashboard import (
    get_emotion_trend_compare as get_emotion_trend_compare,
)
from .student_dashboard import (
    get_latest_scores as get_latest_scores,
)
from .student_dashboard import (
    get_red_energy as get_red_energy,
)
from .student_dashboard import (
    get_treehole_words as get_treehole_words,
)
from .student_report import (
    _ASSESSMENT_FORMS as _ASSESSMENT_FORMS,
)
from .student_report import (
    ASSESSMENT_QUESTION_BANK_SHA256 as ASSESSMENT_QUESTION_BANK_SHA256,
)
from .student_report import (
    ASSESSMENT_SUBMISSION_LOCK as ASSESSMENT_SUBMISSION_LOCK,
)
from .student_report import (
    DEFAULT_REPORT_TYPE as DEFAULT_REPORT_TYPE,
)
from .student_report import (
    METRIC_LOCK as METRIC_LOCK,
)
from .student_report import (
    REPORT_CACHE_TTL_SECONDS as REPORT_CACHE_TTL_SECONDS,
)
from .student_report import (
    REPORT_LOAD_METRICS as REPORT_LOAD_METRICS,
)
from .student_report import (
    REPORT_TYPE_PATTERN as REPORT_TYPE_PATTERN,
)
from .student_report import (
    TestAiAnalyzeRequest as TestAiAnalyzeRequest,
)
from .student_report import (
    _attach_report_meta as _attach_report_meta,
)
from .student_report import (
    _generate_report_analysis_payload as _generate_report_analysis_payload,
)
from .student_report import (
    _normalize_report_type as _normalize_report_type,
)
from .student_report import (
    _record_report_metric as _record_report_metric,
)
from .student_report import (
    _save_report_cache as _save_report_cache,
)
from .student_report import (
    _score_assessment as _score_assessment,
)
from .student_report import (
    _submission_id as _submission_id,
)
from .student_report import (
    _valid_interpretation_content as _valid_interpretation_content,
)
from .student_report import (
    ai_analyze_test_result as ai_analyze_test_result,
)
from .student_report import (
    get_report_analysis as get_report_analysis,
)
from .student_report import (
    get_report_cache_metrics as get_report_cache_metrics,
)
from .student_report import (
    get_test_history as get_test_history,
)
from .student_report import (
    refresh_report_analysis as refresh_report_analysis,
)
from .student_report import (
    submit_test as submit_test,
)
from .student_shared import (
    ASSESSMENT_ENGINE_VERSION as ASSESSMENT_ENGINE_VERSION,
)
from .student_shared import (
    _assessment_is_current as _assessment_is_current,
)
from .student_shared import (
    _assessment_provenance as _assessment_provenance,
)
from .student_shared import (
    _invalidate_user_report_cache as _invalidate_user_report_cache,
)
from .student_shared import (
    _json_object as _json_object,
)
from .student_shared import (
    check_student_role as check_student_role,
)
from .student_treehole import (
    EMOTION_KEYWORDS as EMOTION_KEYWORDS,
)
from .student_treehole import (
    _get_treehole_responses as _get_treehole_responses,
)
from .student_treehole import (
    _rule_based_treehole_summary as _rule_based_treehole_summary,
)
from .student_treehole import (
    _treehole_id_scope as _treehole_id_scope,
)
from .student_treehole import (
    add_comment as add_comment,
)
from .student_treehole import (
    create_treehole_post as create_treehole_post,
)
from .student_treehole import (
    generate_anonymous_id as generate_anonymous_id,
)
from .student_treehole import (
    get_comments as get_comments,
)
from .student_treehole import (
    get_treehole_by_word as get_treehole_by_word,
)
from .student_treehole import (
    get_treehole_posts as get_treehole_posts,
)
from .student_treehole import (
    toggle_favorite as toggle_favorite,
)
from .student_treehole import (
    toggle_like as toggle_like,
)

qwen_client = qwen_service.client

router = APIRouter(prefix="/api/student", tags=["Student"])


# Keep child APIRoutes flat: FastAPI 0.140 nested router wrappers omit some paths from OpenAPI.
router.routes.extend(student_treehole.search_router.routes)

router.routes.extend(_student_teachers_router.routes)



@router.post("/appointments", response_model=schemas.AppointmentResponse)
def create_appointment(app_data: schemas.AppointmentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    if app_data.teacher_id not in assigned_teacher_ids(db, current_user.id):
        raise HTTPException(status_code=403, detail="Only an explicitly assigned teacher can be booked; contact the school operator")

    existing = db.query(models.Appointment).filter(
        models.Appointment.teacher_id == app_data.teacher_id,
        models.Appointment.time_slot == app_data.time_slot,
        models.Appointment.status != 'cancelled'
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="该时间段已被预约")

    appointment = models.Appointment(
        student_id=current_user.id,
        teacher_id=app_data.teacher_id,
        time_slot=app_data.time_slot
    )
    db.add(appointment)
    try:
        db.commit()
    except IntegrityError:
        # Two students can pass the check above simultaneously; the partial unique
        # index is the real guard, so translate its rejection into the same answer.
        db.rollback()
        raise HTTPException(status_code=400, detail="该时间段已被预约") from None
    db.refresh(appointment)
    return appointment

@router.get("/appointments")
def get_appointments(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    appointments = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id).order_by(models.Appointment.created_at.desc()).all()
    if not appointments:
        return []
    # Two batched lookups instead of two per appointment; the response shape is unchanged.
    teacher_ids = {app.teacher_id for app in appointments}
    teachers = {
        teacher.id: teacher
        for teacher in db.query(models.User).filter(models.User.id.in_(teacher_ids)).all()
    }
    profiles = {
        profile.user_id: profile
        for profile in db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id.in_(teacher_ids)).all()
    }
    result = []
    for app in appointments:
        teacher = teachers.get(app.teacher_id)
        profile = profiles.get(app.teacher_id)
        result.append({
            "id": app.id,
            "time_slot": app.time_slot,
            "status": app.status,
            "teacher_name": teacher.name if teacher else "未知",
            "location": profile.location if profile else "未知"
        })
    return result

@router.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)

    appointment = db.query(models.Appointment).filter(
        models.Appointment.id == appointment_id,
        models.Appointment.student_id == current_user.id
    ).first()

    if not appointment:
        raise HTTPException(status_code=404, detail="预约记录不存在或无权操作")

    if appointment.status == 'cancelled':
        raise HTTPException(status_code=400, detail="该预约已取消")

    appointment.status = 'cancelled'
    db.commit()
    return {"message": "预约已取消"}

router.routes.extend(student_report.router.routes)

router.routes.extend(_student_articles_router.routes)
































router.routes.extend(student_treehole.router.routes)


@router.post("/questions/ask", response_model=schemas.QuestionResponse)
@router.post("/questions", response_model=schemas.QuestionResponse)
def ask_question(q_data: schemas.QuestionCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    question = models.Question(
        user_id=current_user.id,
        question_text=q_data.question_text
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    teacher_count = len(assigned_teacher_ids(db, current_user.id))
    return {"id": question.id, "user_id": question.user_id, "question_text": question.question_text,
        "answer_text": question.answer_text, "status": question.status, "created_at": question.created_at,
        "response_state": "pending" if teacher_count else "unassigned", "assigned_teacher_count": teacher_count}

@router.get("/questions", response_model=List[schemas.QuestionResponse])
def get_questions(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    teacher_count = len(assigned_teacher_ids(db, current_user.id))
    questions = db.query(models.Question).filter(models.Question.user_id == current_user.id).order_by(models.Question.created_at.desc()).all()
    has_events = "support_workflow_events" in inspect(db.get_bind()).get_table_names()
    if questions and has_events:
        # The newest answer event per question in one query, plus one lookup for every
        # actor it names, instead of two statements per question.
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
                models.SupportWorkflowEvent.subject_id.in_(
                    db.query(models.Question.id)
                    .filter(models.Question.user_id == current_user.id)
                    .subquery().select()
                ),
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
        # The actors are referenced as a subquery over the same ranked events, not as an
        # IN list of the ids just collected: a question list has no upper bound, and
        # SQLite rejects a statement once it binds more than 32766 variables, which the
        # per-row loop this batching replaced never did.
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
    else:
        events_by_question = {}
        actors = {}
    output = []
    for question in questions:
        event = None
        if has_events and question.answer_text:
            event = events_by_question.get(question.id)
        actor = actors.get(event.actor_id) if event and event.actor_id else None
        output.append({"id": question.id, "user_id": question.user_id, "question_text": question.question_text,
            "answer_text": question.answer_text, "status": question.status, "created_at": question.created_at,
            "response_state": "answered" if question.answer_text else ("pending" if teacher_count else "unassigned"),
            "assigned_teacher_count": teacher_count, "answered_at": event.created_at if event else None,
            "answered_by": (actor.name or actor.username) if actor else None})
    return output
