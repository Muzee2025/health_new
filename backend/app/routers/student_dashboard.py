from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models
from ..database import get_db
from .auth import get_current_user
from .student_shared import (
    ASSESSMENT_ENGINE_VERSION,
    _assessment_is_current,
    _assessment_provenance,
    check_student_role,
)

router = APIRouter()

@router.get("/dashboard/stats")
def get_dashboard_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)

    test_candidates = db.query(models.TestResult).filter(
        models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])
    ).order_by(models.TestResult.created_at.desc()).all()
    latest_test = next((row for row in test_candidates if _assessment_is_current(row)), None)

    emotion_index = None
    if latest_test and latest_test.standard_score:
        emotion_index = max(0, min(100, 100 - (latest_test.standard_score - 20)))

    test_count = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id).count()

    pending_appointments = db.query(models.Appointment).filter(
        models.Appointment.student_id == current_user.id,
        models.Appointment.status == "pending"
    ).count()

    treeholes = db.query(models.TreeholePost.emotion_keywords).filter(
        models.TreeholePost.emotion_keywords.isnot(None)
    ).all()

    word_counts = {}
    for th in treeholes:
        if th.emotion_keywords:
            words = th.emotion_keywords.split(",")
            for w in words:
                w = w.strip()
                if w:
                    word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    word_cloud = [{"name": k, "value": v} for k, v in sorted_words]

    return {
        "emotion_index": int(emotion_index) if emotion_index is not None else None,
        "test_count": test_count,
        "red_energy": current_user.energy_points if current_user.energy_points > 0 else None,
        "pending_appointments": pending_appointments,
        "word_cloud": word_cloud
    }

def _adjust_liming_emotion_index(original_index: int, created_at: datetime, current_user: models.User) -> int:
    # Preserve the legacy response shape without user-specific fabricated adjustment.
    return int(original_index)

@router.get("/dashboard/emotion_trend")
def get_emotion_trend(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(30, ge=3, le=120),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    since_dt = datetime.now() - timedelta(days=days)
    tests = db.query(models.TestResult).filter(
        models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"]),
        models.TestResult.created_at >= since_dt
    ).order_by(models.TestResult.created_at.desc()).limit(limit).all()

    tests.reverse()
    trend_dates = {t.created_at.strftime("%Y-%m-%d") for t in tests if t.created_at}
    treehole_dates = set()
    if trend_dates:
        treeholes = db.query(models.TreeholePost.created_at).filter(
            models.TreeholePost.user_id == current_user.id
        ).all()
        for row in treeholes:
            if row.created_at:
                d = row.created_at.strftime("%Y-%m-%d")
                if d in trend_dates:
                    treehole_dates.add(d)

    result = []
    for t in tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if t.standard_score:
            original_index = max(0, min(100, 100 - (t.standard_score - 20)))
            date_key = t.created_at.strftime("%Y-%m-%d")
            index = _adjust_liming_emotion_index(original_index, t.created_at, current_user)
            events = []
            if date_key in treehole_dates:
                events.append("当日有树洞留言")
            events.append("当日完成量表测评")
            result.append({
                "date": t.created_at.strftime("%m-%d"),
                "date_key": date_key,
                "index": int(index),
                "original_index": int(original_index),
                "adjusted": int(index) != int(original_index),
                "test_id": t.id,
                "test_type": t.test_type,
                "events": events,
            })
    return result

@router.get("/dashboard/emotion_trend/compare")
def get_emotion_trend_compare(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    tests = db.query(models.TestResult).filter(
        models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])
    ).order_by(models.TestResult.created_at.asc()).all()

    compare = []
    for t in tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if not t.standard_score or not t.created_at:
            continue
        original_index = max(0, min(100, 100 - (t.standard_score - 20)))
        adjusted_index = _adjust_liming_emotion_index(original_index, t.created_at, current_user)
        compare.append({
            "date_key": t.created_at.strftime("%Y-%m-%d"),
            "original_index": int(original_index),
            "adjusted_index": int(adjusted_index),
            "changed": int(original_index) != int(adjusted_index),
        })
    return compare

@router.get("/dashboard/latest_scores")
def get_latest_scores(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)

    result = []
    sds = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.test_type == "SDS").order_by(models.TestResult.created_at.desc()).all()
    sds = next((row for row in sds if _assessment_is_current(row)), None)
    if sds:
        result.append({"name": "SDS", "score": sds.standard_score or sds.score, "norm": None})

    sas = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.test_type == "SAS").order_by(models.TestResult.created_at.desc()).all()
    sas = next((row for row in sas if _assessment_is_current(row)), None)
    if sas:
        result.append({"name": "SAS", "score": sas.standard_score or sas.score, "norm": None})

    return result


@router.get("/dashboard/red_energy")
def get_red_energy(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    today = date.today()
    result = []
    if current_user.energy_points > 0:
        result.append({"date": today.strftime("%m-%d"), "score": current_user.energy_points})
    return result

@router.get("/dashboard/treehole_words")
def get_treehole_words(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    treeholes = db.query(models.TreeholePost.emotion_keywords).filter(
        models.TreeholePost.emotion_keywords.isnot(None)
    ).all()

    word_counts = {}
    for th in treeholes:
        if th.emotion_keywords:
            words = th.emotion_keywords.split(",")
            for w in words:
                w = w.strip()
                if w:
                    word_counts[w] = word_counts.get(w, 0) + 1

    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)[:8]
    return [{"word": k, "count": v} for k, v in sorted_words]

@router.get("/dashboard/appointment_stats")
def get_appointment_stats(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    total = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id).count()
    completed = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id, models.Appointment.status == "completed").count()
    pending = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id, models.Appointment.status == "pending").count()
    cancelled = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id, models.Appointment.status == "cancelled").count()
    next_appointment = db.query(models.Appointment).filter(
        models.Appointment.student_id == current_user.id,
        models.Appointment.status == "pending"
    ).order_by(models.Appointment.created_at.asc()).first()
    return {
        "total": total,
        "completed": completed,
        "pending": pending,
        "cancelled": cancelled,
        "next_appointment": {
            "id": next_appointment.id,
            "time_slot": next_appointment.time_slot,
        } if next_appointment else None
    }
