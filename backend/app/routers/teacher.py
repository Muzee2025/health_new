from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Request
import shutil
import os
import bcrypt
import hashlib
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func
from ..database import get_db
from .. import models, schemas
from .auth import get_current_user
from typing import List
from datetime import datetime, timedelta
import json
import re
import random
from pathlib import Path
from collections import Counter
from pydantic import BaseModel
from app.utils.websocket_manager import manager
from app.services.crisis_pending_service import (
    load_mock_records,
    mark_mock_reviewed,
    merge_pending_records,
    paginate_rows,
)

router = APIRouter(prefix="/api/teacher", tags=["Teacher"])
TEACHER_AVATAR_SUBDIR = "teacher_avatars"
TEACHER_AVATAR_DIR = Path("uploads") / TEACHER_AVATAR_SUBDIR
PICTURE_SOURCE_DIR = Path(r"D:\Muzee\develop\IDEA_code\health_new\picture")
ALLOWED_AVATAR_EXT = {".png", ".jpg", ".jpeg", ".svg", ".webp"}


class CrisisReviewRequest(BaseModel):
    recordId: str
    action: str = "pass"


def _serialize_real_warning_row(db: Session, warning: models.CrisisWarning) -> dict:
    msg_content = ""
    if warning.chat_message_id:
        msg = db.query(models.AIChatMessage).filter(models.AIChatMessage.id == warning.chat_message_id).first()
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
    db.commit()

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
        .filter(models.CrisisWarning.status == "pending")
        .order_by(models.CrisisWarning.created_at.desc())
        .all()
    )
    real_rows = [_serialize_real_warning_row(db, warning) for warning in real_warnings]
    mock_rows = load_mock_records(include_reviewed=False)
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
        mock_id = record_id.removeprefix("mock-")
        ok = mark_mock_reviewed(mock_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Mock warning not found")
        return {"status": "success", "data": {"recordId": record_id, "status": "reviewed"}}

    if not record_id.startswith("real-"):
        raise HTTPException(status_code=400, detail="recordId must start with real- or mock-")

    source_id = record_id.removeprefix("real-")
    try:
        warning_id = int(source_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="real record id must be integer") from exc

    warning = db.query(models.CrisisWarning).filter(models.CrisisWarning.id == warning_id).first()
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")
    if warning.status != "pending":
        return {"status": "success", "data": {"recordId": record_id, "status": "reviewed"}}

    warning.status = "processed"
    warning.processed_at = func.now()
    warning.processed_by = current_user.id
    db.commit()
    db.refresh(warning)

    await manager.send_personal_message(
        {
            "type": "warning_processed",
            "data": {
                "warning_id": warning.id,
                "message": "老师已收到您的预警信息，正在处理中，请保持通讯畅通。",
            },
        },
        warning.student_id,
        "student",
    )
    return {"status": "success", "data": {"recordId": record_id, "status": "reviewed"}}

@router.post("/upload")
async def upload_file(file: UploadFile = File(...), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    upload_dir = "uploads"
    if not os.path.exists(upload_dir):
        os.makedirs(upload_dir)
    
    # Simple secure filename
    filename = f"{int(datetime.now().timestamp())}_{file.filename}"
    file_location = os.path.join(upload_dir, filename)
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    return {"url": f"http://127.0.0.1:8000/static/{filename}"}


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
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_AVATAR_EXT:
        raise HTTPException(status_code=400, detail=f"仅支持 {sorted(ALLOWED_AVATAR_EXT)} 格式")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="头像文件不能为空")

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
    content = source_path.read_bytes()
    if not content:
        raise HTTPException(status_code=400, detail="图片文件为空")
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
    
    total_students = db.query(models.User).filter(models.User.role == "student").count()
    
    # Risk distribution based on AI Chat sessions
    students = db.query(models.User).filter(models.User.role == "student").all()
    risk_dist = {"green": 0, "yellow": 0, "red": 0, "untested": 0}
    high_risk_count = 0
    warnings = []
    
    for s in students:
        # Get latest chat messages for the student
        latest_sessions = db.query(models.AIChatSession).filter(models.AIChatSession.user_id == s.id).all()
        if latest_sessions:
            session_ids = [session.id for session in latest_sessions]
            latest_ai_msgs = db.query(models.AIChatMessage).filter(
                models.AIChatMessage.session_id.in_(session_ids),
                models.AIChatMessage.role == "ai",
                models.AIChatMessage.emotion_tags != None
            ).order_by(models.AIChatMessage.created_at.desc()).limit(5).all()
            
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
                    except:
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
        else:
            risk_dist["untested"] += 1
            
    # Appointments stats
    today = datetime.now().date()
    today_str = today.strftime("%Y-%m-%d")
    today_appointments = db.query(models.Appointment).filter(models.Appointment.time_slot.like(f"%{today_str}%")).count()
    
    week_ago = today - timedelta(days=7)
    week_completed = db.query(models.Appointment).filter(
        models.Appointment.status == "completed",
        models.Appointment.created_at >= week_ago
    ).count()
    
    # 7 days emotion trend based on AI Chat
    emotion_trend = []
    days_map = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        d_str = days_map[d.weekday()]
        
        # Mock average joy score for the day
        emotion_trend.append({"day": d_str, "score": 75})
    
    # Word cloud from chat content (AIChatMessage no longer stores keywords field)
    chat_msgs = db.query(models.AIChatMessage.content).filter(models.AIChatMessage.content != None).all()
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
    if not word_cloud:
        word_cloud = [
            {"name": "压力", "value": 10}, {"name": "焦虑", "value": 8},
            {"name": "学业", "value": 6}, {"name": "迷茫", "value": 4}
        ]

    return {
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
    
    # Return all appointments for admin view, or filter by teacher?
    # Prompt: "Teacher can modify appointment status". Let's show all.
    appointments = db.query(models.Appointment).order_by(models.Appointment.created_at.desc()).all()
    result = []
    for app in appointments:
        student = db.query(models.User).filter(models.User.id == app.student_id).first()
        teacher = db.query(models.User).filter(models.User.id == app.teacher_id).first()
        teacher_avatar = db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id == app.teacher_id).first()
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
    
    appointment = db.query(models.Appointment).filter(models.Appointment.id == appointment_id).first()
    if not appointment:
        raise HTTPException(status_code=404, detail="Appointment not found")
        
    appointment.status = status # "completed", "cancelled", etc.
    db.commit()
    return {"message": f"Appointment status updated to {status}"}

@router.get("/students", response_model=List[schemas.TeacherStudentList])
def get_students(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    
    students = db.query(models.User).filter(models.User.role == "student").all()
    result = []
    for s in students:
        # Get latest AI chat to calculate risk
        latest_session = db.query(models.AIChatSession).filter(models.AIChatSession.user_id == s.id).order_by(models.AIChatSession.created_at.desc()).first()
        
        risk_level = None
        latest_time = None
        score = None
        
        if latest_session:
            latest_ai_msg = db.query(models.AIChatMessage).filter(
                models.AIChatMessage.session_id == latest_session.id,
                models.AIChatMessage.role == "ai",
                models.AIChatMessage.emotion_tags != None
            ).order_by(models.AIChatMessage.created_at.desc()).first()
            
            if latest_ai_msg:
                latest_time = latest_ai_msg.created_at
                try:
                    tags = json.loads(latest_ai_msg.emotion_tags)
                    stress = (tags.get("sadness", 0) + tags.get("fear", 0) + tags.get("anger", 0)) / 3
                    score = round(stress * 100)
                    
                    if latest_ai_msg.is_crisis or stress > 0.7:
                        risk_level = "red"
                    elif stress > 0.4:
                        risk_level = "yellow"
                    else:
                        risk_level = "green"
                except:
                    pass
        
        profile = db.query(models.StudentProfile).filter(models.StudentProfile.user_id == s.id).first()
        pending_crisis_query = db.query(models.CrisisWarning).filter(
            models.CrisisWarning.student_id == s.id,
            models.CrisisWarning.status == "pending",
        )
        pending_crisis_count = pending_crisis_query.count()
        latest_pending_warning = pending_crisis_query.order_by(models.CrisisWarning.created_at.desc()).first()

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
            latest_crisis_warning_at=latest_pending_warning.created_at if latest_pending_warning else None,
        ))
    return result


@router.post("/students")
def create_student(
    payload: schemas.TeacherStudentCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)

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

    hashed_password = bcrypt.hashpw(student_id.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")
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
    
    student = db.query(models.User).filter(models.User.id == student_id, models.User.role == "student").first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
        
    test_history = db.query(models.TestResult).filter(models.TestResult.user_id == student_id).order_by(models.TestResult.created_at.asc()).all()
    
    appointments = db.query(models.Appointment).filter(models.Appointment.student_id == student_id).order_by(models.Appointment.created_at.desc()).all()
    app_result = []
    for app in appointments:
        t = db.query(models.User).filter(models.User.id == app.teacher_id).first()
        app_result.append({
            "id": app.id,
            "teacher_name": t.name if t else "Unknown",
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
        
    intervention_records = db.query(models.InterventionRecord).filter(models.InterventionRecord.student_id == student_id).order_by(models.InterventionRecord.created_at.desc()).all()
    
    # 获取脱敏聊天记录
    chat_sessions = db.query(models.AIChatSession).filter(models.AIChatSession.user_id == student_id).order_by(models.AIChatSession.created_at.desc()).limit(5).all()
    desensitized_chats = []
    for session in chat_sessions:
        msgs = db.query(models.AIChatMessage).filter(models.AIChatMessage.session_id == session.id).order_by(models.AIChatMessage.created_at.asc()).all()
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
    
    # Mock AI analysis based on chats
    ai_summary = "该学生近期心理状态稳定，未发现明显心理风险信号。"
    if desensitized_chats:
        ai_summary = "根据最近的对话记录分析，该学生目前情绪较为稳定，但在学业方面存在轻度压力，建议关注其近期的学习负担。"
    
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
    records = db.query(models.InterventionRecord).order_by(models.InterventionRecord.created_at.desc()).all()
    result = []
    for r in records:
        student = db.query(models.User).filter(models.User.id == r.student_id).first()
        teacher = db.query(models.User).filter(models.User.id == r.teacher_id).first()
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
    payload["views"] = random.randint(50, 200)
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
from ..services.rag_service import add_document_to_rag, delete_document_from_rag

@router.get("/knowledge", response_model=List[schemas.KnowledgeBaseResponse])
def get_knowledge_base(db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    return db.query(models.KnowledgeBase).order_by(models.KnowledgeBase.created_at.desc()).all()

@router.post("/knowledge", response_model=schemas.KnowledgeBaseResponse)
def create_knowledge(knowledge: schemas.KnowledgeBaseCreate, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    new_knowledge = models.KnowledgeBase(**knowledge.model_dump())
    db.add(new_knowledge)
    db.commit()
    db.refresh(new_knowledge)
    
    # 异步或同步写入 RAG 向量库
    add_document_to_rag(new_knowledge.id, new_knowledge.title, new_knowledge.content)
    
    return new_knowledge

@router.delete("/knowledge/{knowledge_id}")
def delete_knowledge(knowledge_id: int, db: Session = Depends(get_db), current_user: models.User = Depends(get_current_user)):
    check_teacher_role(current_user)
    knowledge = db.query(models.KnowledgeBase).filter(models.KnowledgeBase.id == knowledge_id).first()
    if not knowledge:
        raise HTTPException(status_code=404, detail="Knowledge not found")
        
    db.delete(knowledge)
    db.commit()
    
    # 从 RAG 向量库删除
    delete_document_from_rag(knowledge_id)
    
    return {"message": "Deleted"}
@router.get("/teachers_profiles")
def get_teachers_profiles(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    check_teacher_role(current_user)
    teachers = db.query(models.User).filter(models.User.role == "teacher").all()
    result = []
    for t in teachers:
        profile = db.query(models.TeacherProfile).filter(models.TeacherProfile.user_id == t.id).first()
        avatar = db.query(models.TeacherAvatar).filter(models.TeacherAvatar.teacher_id == t.id).first()
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
    # Just update or create
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
    user = db.query(models.User).filter(models.User.id == user_id, models.User.role == "teacher").first()
    if not user:
        raise HTTPException(status_code=404, detail="Teacher not found")
    # Actually just delete the user, cascade deletes profile
    db.delete(user)
    db.commit()
    return {"message": "Deleted"}
