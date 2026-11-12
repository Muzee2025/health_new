import hashlib
import json
import os
import random
import re
import sqlite3
import string
import time
from datetime import date, datetime, timedelta, timezone
from threading import Lock
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, inspect
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.security import get_optional_user, require_roles
from app.services.article_catalog import page_articles
from app.services.qwen_service import client as qwen_client
from app.student_access import assigned_teacher_ids

from .. import models, schemas
from ..database import get_db
from .auth import get_current_user

router = APIRouter(prefix="/api/student", tags=["Student"])


def _json_object(raw):
    """Parse legacy JSON defensively; only object payloads are trusted metadata."""
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _assessment_provenance(row):
    detail = _json_object(getattr(row, "result_json", None))
    provenance = detail.get("provenance")
    return provenance if isinstance(provenance, dict) else {}

def check_student_role(user: models.User):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user

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


def _assessment_is_current(row):
    return _assessment_provenance(row).get("scoring_version") == ASSESSMENT_ENGINE_VERSION

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


@router.get("/treehole/search_by_word")
def get_treehole_by_word(
    word: str = Query(..., min_length=1, max_length=20),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    posts = db.query(models.TreeholePost).filter(
        models.TreeholePost.user_id == current_user.id,
        models.TreeholePost.content.like(f"%{word}%")
    ).order_by(models.TreeholePost.created_at.desc()).limit(20).all()
    return [
        {
            "id": post.id,
            "content": post.content,
            "created_at": post.created_at,
        } for post in posts
    ]

@router.get("/teachers")
def get_teachers(request: Request, db: Session = Depends(get_db), current_user: Optional[models.User] = Depends(get_optional_user)):
    bookable = assigned_teacher_ids(db, current_user.id) if current_user and current_user.role == "student" else set()
    teachers = db.query(models.User).filter(models.User.role == "teacher").all()
    result = []
    for t in teachers:
        profile = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == t.id).first()
        avatar_row = db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id == t.id).first()
        time_slots = []
        if profile and profile.time_slots:
            try:
                time_slots = json.loads(profile.time_slots)
            except Exception:
                # time_slots is an unvalidated TEXT column; a malformed or deeply
                # nested value must not break the teacher list for the student.
                pass

        appointments = db.query(models.Appointment).filter(
            models.Appointment.teacher_id == t.id,
            models.Appointment.status != 'cancelled'
        ).all()
        booked_slots = [a.time_slot for a in appointments]

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
    db.commit()
    db.refresh(appointment)
    return appointment

@router.get("/appointments")
def get_appointments(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    appointments = db.query(models.Appointment).filter(models.Appointment.student_id == current_user.id).order_by(models.Appointment.created_at.desc()).all()
    result = []
    for app in appointments:
        teacher = db.query(models.User).filter(models.User.id == app.teacher_id).first()
        profile = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == app.teacher_id).first()
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

ASSESSMENT_ENGINE_VERSION = "health-new-muzee2025-assessment-engine-2026-10-31-v1"
ASSESSMENT_QUESTION_BANK_SHA256 = "ab811c96af47cb88e76a842beac42984aa6ab23d0047fb59386cd11dbc2822f8"
ASSESSMENT_SUBMISSION_LOCK = Lock()
_ASSESSMENT_FORMS = {
    "SDS": {"count": 20, "version": "question-bank-2026-10-31-v1", "reverse": {2, 5, 6, 11, 12, 14, 16, 17, 18, 20}},
    "SAS": {"count": 20, "version": "question-bank-2026-10-31-v1", "reverse": {5, 9, 13, 17, 19}},
    "MBTI": {"count": 28, "version": "question-bank-2026-10-31-v1", "groups": ["EI"] * 7 + ["SN"] * 7 + ["TF"] * 7 + ["JP"] * 7},
    "MentalAge": {"count": 15, "version": "question-bank-2026-10-31-v1"},
}


def _score_assessment(test_type: str, answers: dict):
    form = _ASSESSMENT_FORMS.get(test_type)
    if not form:
        raise HTTPException(status_code=422, detail="未知测评工具")
    expected = {str(i) for i in range(form["count"])}
    if set(answers) != expected:
        raise HTTPException(status_code=422, detail="答题题数或题目编号不匹配")
    normalized = {}
    for key in sorted(expected, key=int):
        value = answers[key]
        if isinstance(value, bool):
            raise HTTPException(status_code=422, detail="答题选项无效")
        normalized[key] = value
    result_level = None
    standard_score = None
    risk_level = None
    if test_type in ("SDS", "SAS"):
        if any(type(normalized[str(i)]) is not int or normalized[str(i)] not in (1, 2, 3, 4) for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        score = sum((5 - normalized[str(i)]) if (i + 1) in form["reverse"] else normalized[str(i)] for i in range(form["count"]))
        standard_score = int(score * 1.25)
        eligibility = "pending_professional_review"
        result_level = "待专业复核"
        explanation = "已按当前登记题本完成工程计分；正式解释和界值尚待专业复核。"
    elif test_type == "MBTI":
        if any(type(normalized[str(i)]) is not str or normalized[str(i)] not in form["groups"][i] for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        dimensions = []
        for offset, (left, right) in zip((0, 7, 14, 21), (("E", "I"), ("S", "N"), ("T", "F"), ("J", "P")), strict=True):
            vals = [normalized[str(i)] for i in range(offset, offset + 7)]
            dimensions.append(left if vals.count(left) > vals.count(right) else right)
        score, result_level, eligibility = 100, "".join(dimensions), "entertainment_only"
        explanation = "此为娱乐性自我探索结果，不是心理测量或诊断。"
    else:
        allowed = {1, 3, 5}
        if any(type(normalized[str(i)]) is not int or normalized[str(i)] not in allowed for i in range(form["count"])):
            raise HTTPException(status_code=422, detail="答题选项超出题本范围")
        score = sum(normalized.values())
        result_level = "纯真孩童" if score <= 25 else "青春少年" if score <= 50 else "成熟青年" if score <= 65 else "稳重长者"
        eligibility = "entertainment_only"
        explanation = "此为娱乐性自我探索结果，不是心理测量或诊断。"
    form_snapshot = {key: value for key, value in form.items()}
    form_hash = hashlib.sha256(json.dumps(form_snapshot, sort_keys=True, ensure_ascii=False,
        default=lambda value: sorted(value) if isinstance(value, set) else str(value)).encode("utf-8")).hexdigest()
    provenance = {"instrument_id": test_type, "form_version": form["version"], "form_hash": form_hash,
        "question_bank_source_sha256": ASSESSMENT_QUESTION_BANK_SHA256,
        "scoring_version": ASSESSMENT_ENGINE_VERSION, "eligibility": eligibility}
    detail = {"desc": explanation, "provenance": provenance, "scoring": {"score": score, "standard_score": standard_score}}
    return score, standard_score, result_level, risk_level, eligibility, detail, normalized


@router.post("/tests/submit")
def submit_test(test_data: schemas.TestSubmit, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    score, standard_score, result_level, risk_level, eligibility, detail, normalized = _score_assessment(test_data.test_type, test_data.answers)
    detail["provenance"]["submission_id"] = test_data.submission_id
    with ASSESSMENT_SUBMISSION_LOCK:
        prior = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.test_type == test_data.test_type).order_by(models.TestResult.id.desc()).limit(200).all()
        test_result = next((row for row in prior if _submission_id(row.result_json) == test_data.submission_id), None)
        if test_result is not None and (test_result.answers or "") != json.dumps(normalized, ensure_ascii=False):
            raise HTTPException(status_code=409, detail="submission_id 已用于不同答卷")
        if test_result is None:
            test_result = models.TestResult(user_id=current_user.id, test_type=test_data.test_type, score=score,
                standard_score=standard_score, result_level=result_level, answers=json.dumps(normalized, ensure_ascii=False),
                result_json=json.dumps(detail, ensure_ascii=False), risk_level=risk_level)
            db.add(test_result)
            db.commit()
            db.refresh(test_result)
    _invalidate_user_report_cache(db, current_user.id)
    return {"id": test_result.id, "test_id": test_result.id, "user_id": test_result.user_id,
        "test_type": test_result.test_type, "score": score, "standard_score": standard_score,
        "result_level": result_level, "risk_level": risk_level, "answers": test_result.answers,
        "result_json": test_result.result_json, "assessment_status": eligibility,
        "scoring": detail["provenance"], "created_at": test_result.created_at}


def _submission_id(result_json):
    provenance = _json_object(result_json).get("provenance")
    return provenance.get("submission_id") if isinstance(provenance, dict) else None

@router.get("/tests/history", response_model=List[schemas.TestResponse])
def get_test_history(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)
    return db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id).order_by(models.TestResult.created_at.asc()).all()


class TestAiAnalyzeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    test_id: int = Field(strict=True, gt=0)


@router.post("/tests/ai-analyze")
async def ai_analyze_test_result(
    req: TestAiAnalyzeRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)

    test_row = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id, models.TestResult.id == req.test_id).first()

    if not test_row:
        raise HTTPException(status_code=404, detail="未找到可分析的测评结果")

    provenance = _assessment_provenance(test_row)
    sources = [{"type": "scoring_provenance", "label": "本地计分规则记录（非外部文献）",
        "tool_id": test_row.test_type, "form_version": provenance.get("form_version"),
        "scoring_version": provenance.get("scoring_version"), "form_hash": provenance.get("form_hash"),
        "question_bank_source_sha256": provenance.get("question_bank_source_sha256"), "external": False}]
    if test_row.test_type not in _ASSESSMENT_FORMS or provenance.get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
        content = {"summary": "这条历史记录的题本或计分版本未知，资料不足，暂不能生成可靠解读。", "observations": [], "limitations": ["历史版本未登记；不推断正式心理结论。"], "next_steps": ["如需了解当前状态，请使用已登记题本重新作答或联系校内专业人员。"]}
    elif test_row.test_type in ("SDS", "SAS"):
        content = {"summary": "本次结果仅为当前题本的工程计分，正式解释尚待专业复核。", "observations": [f"服务器记录的原始分为 {test_row.score}。"], "limitations": ["当前未配置经批准的界值和解释规则；此结果不是诊断。"], "next_steps": ["如有困扰，可主动向校内心理服务人员咨询。"]}
    else:
        content = {"summary": "这是娱乐性自我探索结果，可作为轻松的自我观察话题。", "observations": [f"工具给出的类型为 {test_row.result_level}。"], "limitations": ["该工具不具备心理风险筛查或诊断用途。"], "next_steps": ["结合自身体验自行参考，不据此作重要决定。"]}
    enabled = os.getenv("AI_EXTERNAL_ENABLED", "").strip().lower() in {"1", "true", "yes"}
    if enabled and qwen_client is not None:
        try:
            response = await qwen_client.chat.completions.create(
                model="qwen-plus", temperature=0.2, max_tokens=500,
                messages=[
                    {"role": "system", "content": "你提供非诊断性的自我观察说明。仅输出JSON，字段 summary:string, observations:string[], limitations:string[], next_steps:string[]。没有依据时明确写资料不足，不推断风险，不建议诊断。"},
                    {"role": "user", "content": json.dumps({"tool": test_row.test_type, "score": test_row.score if test_row.test_type in ("SDS", "SAS") else None,
                        "standard_score": test_row.standard_score if test_row.test_type in ("SDS", "SAS") else None,
                        "eligibility": provenance.get("eligibility", "unknown"),
                        "rule_summary": content}, ensure_ascii=False)},
                ],
            )
            parsed = _json_object(response.choices[0].message.content)
            if _valid_interpretation_content(parsed):
                content = parsed
                model_id = getattr(response, "model", None)
                if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120:
                    model_id = None
                return {"status": "completed", "source": "provider", "model_id": model_id, "test_id": test_row.id,
                    "content": content, "sources": sources, "notice": "模型生成的非诊断性说明；未发送逐题答卷、姓名、学号或树洞原文。"}
        except Exception:
            # Provider errors and malformed output degrade to the explicit local result.
            pass
    return {"status": "fallback", "source": "local_rule", "model_id": None, "test_id": test_row.id,
        "content": content, "sources": sources, "notice": "本地规则说明，非大模型生成；当前无可用且获准的模型响应。"}


def _valid_interpretation_content(value):
    if not isinstance(value, dict) or set(value) != {"summary", "observations", "limitations", "next_steps"} or not isinstance(value.get("summary"), str):
        return False
    if not value["summary"].strip() or len(value["summary"]) > 500:
        return False
    for key in ("observations", "limitations", "next_steps"):
        items = value.get(key)
        if not isinstance(items, list) or len(items) > 8:
            return False
        if any(not isinstance(item, str) or not item.strip() or len(item) > 240 for item in items):
            return False
    return True

DEFAULT_REPORT_TYPE = "student_mental_report"
REPORT_CACHE_TTL_SECONDS = 15 * 60
REPORT_TYPE_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")
REPORT_LOAD_METRICS = {"report:load:hit_rate": 0, "report:load:miss": 0}
METRIC_LOCK = Lock()
ARTICLE_VIEW_LOCK = Lock()
ARTICLE_VIEW_CACHE = {}
ARTICLE_VIEW_IDEMPOTENCY = {}
ARTICLE_VIEW_DEDUP_WINDOW_SECONDS = 5 * 60
ARTICLE_VIEW_INIT_MIN = 0
ARTICLE_VIEW_INIT_MAX = 0


def _normalize_report_type(report_type: str) -> str:
    report_type = (report_type or DEFAULT_REPORT_TYPE).strip()
    if not REPORT_TYPE_PATTERN.match(report_type):
        raise HTTPException(status_code=400, detail="Invalid report_type")
    return report_type


def _record_report_metric(metric_key: str):
    with METRIC_LOCK:
        REPORT_LOAD_METRICS[metric_key] = REPORT_LOAD_METRICS.get(metric_key, 0) + 1


def _invalidate_user_report_cache(db: Session, user_id: int):
    caches = db.query(models.ReportAnalysisCache).filter(models.ReportAnalysisCache.user_id == user_id).all()
    if not caches:
        return
    now = datetime.now(timezone.utc) - timedelta(seconds=1)
    for cache in caches:
        cache.expires_at = now
    db.commit()


def _generate_report_analysis_payload(db: Session, current_user: models.User):
    candidate_tests = db.query(models.TestResult).filter(models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])).order_by(models.TestResult.created_at.desc()).all()
    latest_test = next((row for row in candidate_tests if _assessment_is_current(row)), None)
    recent_treehole = db.query(models.TreeholePost).filter(models.TreeholePost.user_id == current_user.id).order_by(models.TreeholePost.created_at.desc()).first()

    all_tests = db.query(models.TestResult).filter(
        models.TestResult.user_id == current_user.id,
        models.TestResult.test_type.in_(["SDS", "SAS"])
    ).order_by(models.TestResult.created_at.desc()).all()

    score_distribution = {"SDS": [], "SAS": []}
    for t in all_tests:
        try:
            provenance = _assessment_provenance(t)
        except (TypeError, ValueError):
            provenance = {}
        if t.test_type in score_distribution and provenance.get("scoring_version") == ASSESSMENT_ENGINE_VERSION:
            score_distribution[t.test_type].append({
                "date": t.created_at.strftime("%Y-%m-%d"),
                "score": t.standard_score or t.score,
                "level": t.result_level,
                "risk": t.risk_level
            })

    risk_stats = {"red": 0, "yellow": 0, "green": 0}
    for t in all_tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if t.risk_level in risk_stats:
            risk_stats[t.risk_level] += 1

    category_scores = {}
    for t in all_tests:
        try:
            if _assessment_provenance(t).get("scoring_version") != ASSESSMENT_ENGINE_VERSION:
                continue
        except (TypeError, ValueError):
            continue
        if t.test_type not in category_scores:
            category_scores[t.test_type] = []
        category_scores[t.test_type].append(t.standard_score or t.score)

    avg_scores = {}
    for cat, scores in category_scores.items():
        if scores:
            avg_scores[cat] = round(sum(scores) / len(scores), 1)

    analysis_basis = {
        "data_sources": [],
        "key_parameters": [],
        "logic_path": []
    }

    if latest_test:
        analysis_basis["data_sources"].append(f"最新{latest_test.test_type}测评（标准分：{latest_test.standard_score or latest_test.score}）")
        analysis_basis["key_parameters"].append(f"评估等级：{latest_test.result_level}，风险级别：{latest_test.risk_level}")
        analysis_basis["logic_path"].append(f"按当前登记规则完成{latest_test.test_type}工程计分；常模与解释待专业复核")

    if recent_treehole:
        analysis_basis["data_sources"].append("树洞倾诉记录")
        if recent_treehole.emotion_keywords:
            analysis_basis["key_parameters"].append(f"情绪关键词：{recent_treehole.emotion_keywords}")
            analysis_basis["logic_path"].append(f"从树洞内容中提取到「{recent_treehole.emotion_keywords}」等情绪关键词")

    rag_context = ""

    user_context = "用户基本情况：\n"
    if latest_test:
        user_context += f"最新测评({latest_test.test_type})结果：标准分 {latest_test.standard_score or latest_test.score}，评估等级：{latest_test.result_level}，风险级别：{latest_test.risk_level}\n"
    if recent_treehole:
        if recent_treehole.emotion_keywords:
            user_context += f"提取的情绪关键词：{recent_treehole.emotion_keywords}\n"

    rag_context = ""
    try:
        from ..services.rag_service import query_rag
        rag_context = query_rag(query=user_context, n_results=3)
    except Exception:
        pass
    if rag_context:
        analysis_basis["data_sources"].append("心理知识库检索结果（存在返回内容）")
        analysis_basis["logic_path"].append("检索返回相关片段，尚未逐条专业核验；不代表临床依据")

    # This legacy aggregate endpoint is a local summary. Per-assessment model
    # explanation has its own explicit, ID-bound and minimized-input endpoint.
    generation = {"source": "local_rules", "status": "fallback" if latest_test or recent_treehole else "insufficient", "model_id": None}
    ai_analysis_text = (f"当前有{sum(len(rows) for rows in score_distribution.values())}条带计分版本的自我观察记录。"
                        "这里显示本地汇总说明，未调用外部模型。分数和关键词不能判断疾病或排除困扰；"
                        "可在本次测评结果页查看辅助说明，或根据需要选择人工求助。")

    treehole_analysis = db.query(models.TreeholeAnalysis).filter(models.TreeholeAnalysis.user_id == current_user.id).order_by(models.TreeholeAnalysis.created_at.desc()).all()

    recent_themes = []
    if treehole_analysis:
        theme_counts = {}
        for ta in treehole_analysis:
            if ta.core_values:
                words = ta.core_values.split(",")
                for w in words:
                    w = w.strip()
                    if w:
                        theme_counts[w] = theme_counts.get(w, 0) + 1
        sorted_themes = sorted(theme_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        recent_themes = [{"word": k, "count": v} for k, v in sorted_themes]

    deep_moments = db.query(models.TreeholePost).filter(
        models.TreeholePost.user_id == current_user.id,
        models.TreeholePost.is_deep.is_(True)
    ).order_by(func.random()).first()

    deep_moment_data = None
    if deep_moments:
        deep_moment_data = {
            "content": deep_moments.content,
            "created_at": deep_moments.created_at.strftime("%Y-%m-%d")
        }

    payload = {
        "ai_analysis": ai_analysis_text,
        "generation": generation,
        "data_status": "available" if latest_test or recent_treehole else "insufficient",
        "analysis_basis": analysis_basis,
        "recent_themes": recent_themes,
        "deep_moment": deep_moment_data,
        "score_distribution": score_distribution,
        "risk_stats": risk_stats,
        "avg_scores": avg_scores
    }

    fingerprint_parts = [
        str(latest_test.id if latest_test else 0),
        str(recent_treehole.id if recent_treehole else 0),
        str(len(all_tests)),
        str(len(treehole_analysis)),
    ]
    source_times = [
        t for t in [
            latest_test.created_at if latest_test else None,
            recent_treehole.created_at if recent_treehole else None,
        ] if t is not None
    ]
    source_updated_at = max(source_times) if source_times else None
    data_fingerprint = "|".join(fingerprint_parts)
    return payload, data_fingerprint, source_updated_at


def _save_report_cache(
    db: Session,
    *,
    user_id: int,
    report_type: str,
    payload: dict,
    data_fingerprint: str,
    source_updated_at,
):
    cache = db.query(models.ReportAnalysisCache).filter(
        models.ReportAnalysisCache.user_id == user_id,
        models.ReportAnalysisCache.report_type == report_type,
    ).first()
    if not cache:
        cache = models.ReportAnalysisCache(
            user_id=user_id,
            report_type=report_type,
            payload_json="{}",
        )
        db.add(cache)
    cache.payload_json = json.dumps(payload, ensure_ascii=False)
    cache.data_fingerprint = data_fingerprint
    cache.source_updated_at = source_updated_at
    cache.expires_at = datetime.now(timezone.utc) + timedelta(seconds=REPORT_CACHE_TTL_SECONDS)
    db.commit()
    db.refresh(cache)
    return cache


def _attach_report_meta(payload: dict, *, report_type: str, from_cache: bool, cache_status: str, refreshed_at: str):
    payload_with_meta = dict(payload)
    payload_with_meta["_meta"] = {
        "report_type": report_type,
        "from_cache": from_cache,
        "cache_status": cache_status,
        "refreshed_at": refreshed_at,
        "ttl_seconds": REPORT_CACHE_TTL_SECONDS,
    }
    return payload_with_meta


@router.get("/report/analysis")
def get_report_analysis(
    request: Request,
    response: Response,
    report_type: str = Query(DEFAULT_REPORT_TYPE),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    report_type = _normalize_report_type(report_type)

    cache = db.query(models.ReportAnalysisCache).filter(
        models.ReportAnalysisCache.user_id == current_user.id,
        models.ReportAnalysisCache.report_type == report_type,
    ).first()

    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=30"
    if cache and cache.payload_json:
        etag = f'W/"{hashlib.md5(cache.payload_json.encode()).hexdigest()}"'
        if request.headers.get("If-None-Match") == etag:
            response.status_code = 304
            return Response(status_code=304)
        
        response.headers["ETag"] = etag
        response.headers["Last-Modified"] = cache.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

        try:
            payload = json.loads(cache.payload_json)
            cache_status = "fresh"
            if cache.expires_at and cache.expires_at <= datetime.now(timezone.utc):
                cache_status = "stale"
            _record_report_metric("report:load:hit_rate")
            return _attach_report_meta(
                payload,
                report_type=report_type,
                from_cache=True,
                cache_status=cache_status,
                refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
            )
        except json.JSONDecodeError:
            pass

    _record_report_metric("report:load:miss")
    payload, data_fingerprint, source_updated_at = _generate_report_analysis_payload(db, current_user)
    cache = _save_report_cache(
        db,
        user_id=current_user.id,
        report_type=report_type,
        payload=payload,
        data_fingerprint=data_fingerprint,
        source_updated_at=source_updated_at,
    )
    return _attach_report_meta(
        payload,
        report_type=report_type,
        from_cache=False,
        cache_status="miss",
        refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
    )


@router.get("/report/cache/metrics")
def get_report_cache_metrics(current_user: models.User = Depends(require_roles("teacher"))):
    total = REPORT_LOAD_METRICS["report:load:hit_rate"] + REPORT_LOAD_METRICS["report:load:miss"]
    hit_ratio = (REPORT_LOAD_METRICS["report:load:hit_rate"] / total) if total else 1.0
    return {
        "metrics": REPORT_LOAD_METRICS,
        "hit_ratio": round(hit_ratio, 4),
        "alert": "hit_ratio < 0.95",
        "recommended_scrape_interval_seconds": 15,
    }


@router.get("/report/analysis/refresh")
def refresh_report_analysis(
    response: Response,
    report_type: str = Query(DEFAULT_REPORT_TYPE),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_student_role(current_user)
    report_type = _normalize_report_type(report_type)
    payload, data_fingerprint, source_updated_at = _generate_report_analysis_payload(db, current_user)
    cache = _save_report_cache(
        db,
        user_id=current_user.id,
        report_type=report_type,
        payload=payload,
        data_fingerprint=data_fingerprint,
        source_updated_at=source_updated_at,
    )
    
    if cache and cache.payload_json:
        etag = f'W/"{hashlib.md5(cache.payload_json.encode()).hexdigest()}"'
        response.headers["ETag"] = etag
        if cache.updated_at:
            response.headers["Last-Modified"] = cache.updated_at.strftime("%a, %d %b %Y %H:%M:%S GMT")

    return _attach_report_meta(
        payload,
        report_type=report_type,
        from_cache=False,
        cache_status="refreshed",
        refreshed_at=(cache.updated_at.isoformat() if cache.updated_at else ""),
    )


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


@router.get("/articles/page", response_model=schemas.ArticlePage)
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


@router.get("/articles", response_model=List[schemas.ArticleResponse])
def get_articles(db: Session = Depends(get_db)):
    _ensure_article_views_initialized(db)
    rows = db.query(models.Article).order_by(models.Article.created_at.desc()).all()
    for article in rows:
        article.views = _read_article_views_cached(article.id, article.views or 0)
    return rows

@router.get("/articles/{article_id}", response_model=schemas.ArticleResponse)
def get_article_detail(article_id: int, db: Session = Depends(get_db)):
    _ensure_article_views_initialized(db)
    article = db.query(models.Article).filter(models.Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")
    article.views = _read_article_views_cached(article.id, article.views or 0)
    return article


@router.post("/articles/{article_id}/view", response_model=schemas.ArticleViewTrackResponse)
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

EMOTION_KEYWORDS = ["焦虑", "失眠", "压力", "崩溃", "难过", "抑郁", "想哭"]

def generate_anonymous_id():
    return "深海旅人_" + ''.join(random.choices(string.digits, k=4))

def _rule_based_treehole_summary(content: str, tags: list):
    emotion = "平静"
    if any(kw in content for kw in ["焦虑", "压力", "紧张"]):
        emotion = "焦虑"
    elif any(kw in content for kw in ["难过", "崩溃", "哭"]):
        emotion = "低落"
    elif any(kw in content for kw in ["开心", "希望", "美好"]):
        emotion = "积极"
    elif any(kw in content for kw in ["迷茫", "不知道", "未来"]):
        emotion = "迷茫"

    keywords = []
    if "人生意义" in tags or "意义" in content:
        keywords.append("人生意义")
    if "自我成长" in tags or "成长" in content or "学习" in content:
        keywords.append("成长")
    if "红色精神与我" in tags or "责任" in content:
        keywords.append("责任与担当")
    if "人际关系" in tags or "朋友" in content or "室友" in content:
        keywords.append("人际关系")
    if "未来规划" in tags or "未来" in content:
        keywords.append("未来探索")

    if not keywords:
        keywords = ["日常随想", "自我探索"]

    return emotion, ",".join(keywords)

@router.post("/treehole/post", response_model=schemas.TreeholeResponse)
def create_treehole_post(post_data: schemas.TreeholeCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_student_role(current_user)

    content = post_data.content
    matched_keywords = [kw for kw in EMOTION_KEYWORDS if kw in content]

    reply_tip = None
    if matched_keywords:
        reply_tip = "看到你提到了一些不容易的感受。关键词提示仅供参考，不代表风险判断；如果你需要支持，可以通过学校公布的官方渠道联系心理服务人员。"

    tags_str = ",".join(post_data.tags) if post_data.tags else ""
    is_deep = len(content) > 100 or ("#人生意义" in tags_str) or ("#自我成长" in tags_str) or ("#红色精神与我" in tags_str)

    prior_energy = current_user.energy_points
    if is_deep:
        current_user.energy_points += 5

    post = models.TreeholePost(
        anonymous_id=generate_anonymous_id(),
        content=content,
        tags=tags_str,
        is_deep=is_deep,
        emotion_keywords=",".join(matched_keywords) if matched_keywords else None,
        reply_tip=reply_tip,
        user_id=current_user.id if current_user.real_identity_flag else None
    )
    db.add(post)
    try:
        db.flush()
        emotion, core_values = _rule_based_treehole_summary(content, post_data.tags or [])
        analysis = models.TreeholeAnalysis(post_id=post.id, user_id=current_user.id,
            emotion_category=emotion, core_values=core_values)
        db.add(analysis)
        db.commit()
        db.refresh(post)
    except Exception:
        db.rollback()
        current_user.energy_points = prior_energy
        raise
    _invalidate_user_report_cache(db, current_user.id)

    return schemas.TreeholeResponse(
        id=post.id,
        anonymous_id=post.anonymous_id,
        content=post.content,
        tags=post.tags,
        is_deep=post.is_deep,
        emotion_keywords=post.emotion_keywords,
        reply_tip=post.reply_tip,
        created_at=post.created_at,
        likes_count=0,
        comments_count=0,
        favorites_count=0,
        is_liked=False,
        is_favorited=False
    )

def _get_treehole_response(post, user_id, db):
    likes_count = db.query(models.TreeholeLike).filter(models.TreeholeLike.post_id == post.id).count()
    comments_count = db.query(models.TreeholeComment).filter(models.TreeholeComment.post_id == post.id).count()
    favorites_count = db.query(models.TreeholeFavorite).filter(models.TreeholeFavorite.post_id == post.id).count()

    is_liked = db.query(models.TreeholeLike).filter(models.TreeholeLike.post_id == post.id, models.TreeholeLike.user_id == user_id).first() is not None if user_id else False
    is_favorited = db.query(models.TreeholeFavorite).filter(models.TreeholeFavorite.post_id == post.id, models.TreeholeFavorite.user_id == user_id).first() is not None if user_id else False

    return schemas.TreeholeResponse(
        id=post.id,
        anonymous_id=post.anonymous_id,
        content=post.content,
        tags=post.tags,
        is_deep=post.is_deep,
        emotion_keywords=post.emotion_keywords,
        reply_tip=post.reply_tip,
        created_at=post.created_at,
        likes_count=likes_count,
        comments_count=comments_count,
        favorites_count=favorites_count,
        is_liked=is_liked,
        is_favorited=is_favorited
    )

@router.get("/treehole/posts", response_model=List[schemas.TreeholeResponse])
def get_treehole_posts(tab: str = "home", tag: str = None, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    query = db.query(models.TreeholePost)

    if tab == "my":
        query = query.filter(models.TreeholePost.user_id == current_user.id)
    elif tab == "favorites":
        fav_post_ids = db.query(models.TreeholeFavorite.post_id).filter(models.TreeholeFavorite.user_id == current_user.id)
        query = query.filter(models.TreeholePost.id.in_(fav_post_ids))
    elif tab == "hot":
        query = query.order_by(models.TreeholePost.is_deep.desc())

    if tag:
        query = query.filter(models.TreeholePost.tags.like(f"%{tag}%"))

    if tab != "hot":
        query = query.order_by(models.TreeholePost.created_at.desc())

    posts = query.all()
    return [_get_treehole_response(p, current_user.id, db) for p in posts]

@router.post("/treehole/{post_id}/like")
def toggle_like(post_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.TreeholeLike).filter(models.TreeholeLike.post_id == post_id, models.TreeholeLike.user_id == current_user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unliked"}
    else:
        like = models.TreeholeLike(post_id=post_id, user_id=current_user.id)
        db.add(like)
        db.commit()
        return {"status": "liked"}

@router.post("/treehole/{post_id}/favorite")
def toggle_favorite(post_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    existing = db.query(models.TreeholeFavorite).filter(models.TreeholeFavorite.post_id == post_id, models.TreeholeFavorite.user_id == current_user.id).first()
    if existing:
        db.delete(existing)
        db.commit()
        return {"status": "unfavorited"}
    else:
        fav = models.TreeholeFavorite(post_id=post_id, user_id=current_user.id)
        db.add(fav)
        db.commit()
        return {"status": "favorited"}

@router.post("/treehole/{post_id}/comment", response_model=schemas.TreeholeCommentResponse)
def add_comment(post_id: int, comment_data: schemas.TreeholeCommentCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    comment = models.TreeholeComment(
        post_id=post_id,
        user_id=current_user.id,
        anonymous_id=generate_anonymous_id(),
        content=comment_data.content,
        parent_id=comment_data.parent_id
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.get("/treehole/{post_id}/comments", response_model=List[schemas.TreeholeCommentResponse])
def get_comments(post_id: int, db: Session = Depends(get_db)):
    return db.query(models.TreeholeComment).filter(models.TreeholeComment.post_id == post_id).order_by(models.TreeholeComment.created_at.asc()).all()

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
    output = []
    for question in questions:
        event = None
        if has_events and question.answer_text:
            event = (db.query(models.SupportWorkflowEvent)
                .filter_by(subject_type="question", subject_id=question.id, action="answer")
                .order_by(models.SupportWorkflowEvent.id.desc()).first())
        actor = db.query(models.User).filter_by(id=event.actor_id).first() if event and event.actor_id else None
        output.append({"id": question.id, "user_id": question.user_id, "question_text": question.question_text,
            "answer_text": question.answer_text, "status": question.status, "created_at": question.created_at,
            "response_state": "answered" if question.answer_text else ("pending" if teacher_count else "unassigned"),
            "assigned_teacher_count": teacher_count, "answered_at": event.created_at if event else None,
            "answered_by": (actor.name or actor.username) if actor else None})
    return output
