import random
from typing import List

import bcrypt
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, update
from sqlalchemy.orm import Session, joinedload

from app.security import validate_new_password
from app.student_access import assigned_student_ids, require_assigned_student
from app.support_workflow import append_event, require_support_schema

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user
from .teacher_shared import check_teacher_role

router = APIRouter(prefix="/api/teacher")
questions_router = APIRouter(prefix="/api/teacher")

def _support_actor_name(db: Session, actor_id: int | None):
    actor = db.query(models.User).filter_by(id=actor_id).first() if actor_id else None
    return (actor.name or actor.username) if actor else None

@questions_router.get("/questions")
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

@questions_router.post("/questions/{question_id}/answer")
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
