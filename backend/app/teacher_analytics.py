"""Measured teacher summaries; no demonstration students or global fallback."""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app import models
from app.student_access import assigned_student_ids


def dashboard_payload(db: Session, teacher_id: int) -> dict:
    student_ids = assigned_student_ids(db, teacher_id)
    students = db.query(models.User.id).filter(models.User.id.in_(student_ids)).count()
    sessions = db.query(models.AIChatSession).filter(models.AIChatSession.user_id.in_(student_ids)).all()
    session_ids = [session.id for session in sessions]
    messages = db.query(models.AIChatMessage).filter(models.AIChatMessage.session_id.in_(session_ids)).all() if session_ids else []
    warnings = db.query(models.CrisisWarning).filter(models.CrisisWarning.student_id.in_(student_ids)).all()
    interventions = (db.query(models.InterventionRecord.student_id)
                     .filter(models.InterventionRecord.teacher_id == teacher_id, models.InterventionRecord.student_id.in_(student_ids)).distinct().count())
    today = datetime.utcnow().date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    values = {day: [] for day in dates}
    for message in messages:
        if message.role != "ai" or not message.created_at or message.created_at.date().isoformat() not in values:
            continue
        try:
            tags = json.loads(message.emotion_tags or "{}")
            joy, anxiety = tags.get("joy"), tags.get("anxiety")
            if type(joy) in (int, float) and type(anxiety) in (int, float) and 0 <= joy <= 1 and 0 <= anxiety <= 1:
                values[message.created_at.date().isoformat()].append((joy, anxiety))
        except (ValueError, TypeError, AttributeError):
            continue
    return {
        "source": "assigned_students", "data_status": "measured" if students else "empty",
        "realtime_stats": {"pv": len(messages), "uv": students,
                           "avg_session_rounds": round(sum(message.role == "user" for message in messages) / len(sessions), 2) if sessions else 0,
                           "crisis_alerts": sum(warning.status == "pending" for warning in warnings)},
        "funnel_data": [{"name": "已分配学生", "value": students},
                        {"name": "有对话学生", "value": len({session.user_id for session in sessions})},
                        {"name": "产生预警学生", "value": len({warning.student_id for warning in warnings})},
                        {"name": "已有干预学生", "value": interventions}],
        "campus_heatmap": [],
        "emotion_trends_7d": {"dates": dates,
                              "joy": [round(sum(item[0] for item in values[day]) / len(values[day]), 4) if values[day] else None for day in dates],
                              "anxiety": [round(sum(item[1] for item in values[day]) / len(values[day]), 4) if values[day] else None for day in dates],
                              "sample_counts": [len(values[day]) for day in dates]},
    }


def audit_items(db: Session, teacher_id: int) -> list[dict]:
    warnings = (db.query(models.CrisisWarning).filter(models.CrisisWarning.student_id.in_(assigned_student_ids(db, teacher_id)))
                .order_by(models.CrisisWarning.created_at.desc()).all())
    if not warnings:
        return []
    # Two batched lookups instead of two per warning: the students behind the warnings,
    # and the triggering messages (joined so a message from another student cannot leak).
    students = {
        student.id: student
        for student in db.query(models.User).filter(
            models.User.id.in_({warning.student_id for warning in warnings}),
            models.User.role == "student",
        ).all()
    }
    message_ids = {warning.chat_message_id for warning in warnings if warning.chat_message_id}
    # message id -> (content, owning student). The owning student is fetched with the
    # message so the same guard as before holds: a message is only shown when it
    # belongs to the student the warning names. The warnings are joined rather than
    # passed as an IN list: the list has no upper bound, and SQLite rejects a statement
    # once it binds more than 32766 variables, which a per-row loop never did.
    message_rows = {}
    if message_ids:
        for message_id, content, owner in (
            db.query(models.AIChatMessage.id, models.AIChatMessage.content, models.AIChatSession.user_id)
            .join(models.AIChatSession, models.AIChatSession.id == models.AIChatMessage.session_id)
            .join(models.CrisisWarning, models.CrisisWarning.chat_message_id == models.AIChatMessage.id)
            .filter(models.CrisisWarning.student_id.in_(assigned_student_ids(db, teacher_id)))
            .all()
        ):
            message_rows[message_id] = (content, owner)

    output = []
    for warning in warnings:
        student = students.get(warning.student_id)
        message_content = ""
        if warning.chat_message_id:
            row = message_rows.get(warning.chat_message_id)
            if row is not None and row[1] == warning.student_id:
                message_content = row[0]
        output.append({"chat_id": f"warning-{warning.id}", "warning_id": warning.id,
                       "student_info": {"id": student.id, "name": student.name or student.username,
                                        "student_id": student.student_id, "grade": student.class_name, "gender": None, "age": None},
                       "trigger_msg": message_content, "ai_reply": "", "heatmap": [], "risk_radar": {},
                       "risk_type": warning.risk_level, "risk_score": None,
                       "abnormal_behavior_summary": warning.trigger_keyword, "status": warning.status,
                       "timestamp": warning.created_at.isoformat() if warning.created_at else None})
    return output
