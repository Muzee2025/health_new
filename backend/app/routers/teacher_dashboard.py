import json
import re
from collections import Counter
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models, schemas
from ..database import get_db
from ..student_access import assigned_student_ids
from .auth import get_current_user
from .teacher_shared import _build_avatar_url, check_teacher_role

router = APIRouter(prefix="/api/teacher")
profiles_router = APIRouter(prefix="/api/teacher")

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

@profiles_router.get("/teachers_profiles")
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

@profiles_router.post("/teachers_profiles")
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

@profiles_router.delete("/teachers_profiles/{user_id}")
def delete_teacher_profile(user_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    # The former implementation deleted User and its cascaded records.
    raise HTTPException(status_code=403, detail="Account deletion is unavailable through teacher profiles")
