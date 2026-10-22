import base64
import io
import os
import asyncio
import uuid
from pathlib import Path
from starlette.background import BackgroundTask
from datetime import datetime
from typing import Any, Dict, List

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ChatHistoryArchive, AIChatSession, AIChatMessage, CrisisWarning
from app.routers.auth import get_current_user
from app.routers.teacher import check_teacher_role
from app.utils.websocket_manager import manager
from app.security import require_roles
from app.student_access import assigned_student_ids
from app.teacher_analytics import dashboard_payload, audit_items
from app.upload_security import validate_image_content, MAX_IMAGE_BYTES, IMAGE_TYPES

router = APIRouter()

# --- 教师端大屏看板与审核工作台 API ---

class AuditAdjustment(BaseModel):
    chat_id: str
    original_risk: Dict[str, int]
    adjusted_risk: Dict[str, int]
    action: str # "pass", "reject", "escalate"


class ChartSnapshot(BaseModel):
    title: str = Field(max_length=120)
    image_data_url: str = Field(max_length=7 * 1024 * 1024)


class ComplianceReportExportRequest(BaseModel):
    chart_snapshots: List[ChartSnapshot] = Field(default_factory=list, max_length=8)


def _dashboard_metrics_payload(db: Session, teacher_id: int) -> Dict[str, Any]:
    return dashboard_payload(db, teacher_id)


def _audit_items_payload(db: Session, teacher_id: int) -> List[Dict[str, Any]]:
    return audit_items(db, teacher_id)


def _intervention_level(risk_score: int) -> str:
    if risk_score >= 90:
        return "紧急干预"
    if risk_score >= 80:
        return "重点关注"
    return "持续观察"


def _decode_data_url_image(image_data_url: str) -> io.BytesIO:
    if len(image_data_url) > 7 * 1024 * 1024 or "," not in image_data_url:
        raise HTTPException(status_code=400, detail="Invalid chart image")
    header, encoded = image_data_url.split(",", 1)
    mime_to_ext = {value: key for key, value in IMAGE_TYPES.items()}
    mime = header.removeprefix("data:").removesuffix(";base64")
    if header != f"data:{mime};base64" or mime not in mime_to_ext:
        raise HTTPException(status_code=415, detail="Unsupported chart image")
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, TypeError):
        raise HTTPException(status_code=400, detail="Invalid chart image encoding") from None
    validate_image_content(raw, "chart" + mime_to_ext[mime], mime)
    return io.BytesIO(raw)


def _set_run_font(run, size: int = 11, bold: bool = False):
    run.bold = bold
    run.font.name = "Microsoft YaHei"
    run.font.size = Pt(size)
    r_fonts = run._element.get_or_add_rPr().get_or_add_rFonts()
    r_fonts.set(qn("w:ascii"), "Microsoft YaHei")
    r_fonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    r_fonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    r_fonts.set(qn("w:cs"), "Microsoft YaHei")


def _set_doc_styles(doc: Document):
    normal = doc.styles["Normal"]
    normal.font.name = "Microsoft YaHei"
    normal.font.size = Pt(11)
    normal._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    normal._element.rPr.rFonts.set(qn("w:cs"), "Microsoft YaHei")

    for heading_style in ("Heading 1", "Heading 2"):
        style = doc.styles[heading_style]
        style.font.name = "Microsoft YaHei"
        style._element.rPr.rFonts.set(qn("w:ascii"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:hAnsi"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
        style._element.rPr.rFonts.set(qn("w:cs"), "Microsoft YaHei")


def _add_text_paragraph(doc: Document, text: str, style: str | None = None, size: int = 11, bold: bool = False):
    paragraph = doc.add_paragraph("", style=style)
    run = paragraph.add_run(text)
    _set_run_font(run, size=size, bold=bold)
    return paragraph


@router.get("/dashboard/metrics")
async def get_dashboard_metrics(db: Session = Depends(get_db), current_user: User = Depends(require_roles("teacher"))):
    """
    3.1 & 3.2: 模拟 Flink CDC + ClickHouse 聚合的实时大盘数据
    返回漏斗图、雷达图、热力地图需要的数据
    """
    return {"status": "success", **_dashboard_metrics_payload(db, current_user.id)}

@router.get("/warnings")
async def get_crisis_warnings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_teacher_role(current_user)
    warnings = db.query(CrisisWarning).filter(CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).order_by(CrisisWarning.created_at.desc()).all()
    res = []
    for w in warnings:
        msg_content = ""
        if w.chat_message_id:
            msg = db.query(AIChatMessage).join(AIChatSession).filter(AIChatMessage.id == w.chat_message_id, AIChatSession.user_id == w.student_id).first()
            if msg:
                msg_content = msg.content
        res.append({
            "id": w.id,
            "student_id": w.student_id,
            "student_name": w.student.name or w.student.username if w.student else "未知",
            "class_name": w.student.class_name if w.student else "未知",
            "trigger_keyword": w.trigger_keyword,
            "risk_level": w.risk_level,
            "status": w.status,
            "trigger_msg": msg_content,
            "created_at": w.created_at.strftime("%Y-%m-%d %H:%M:%S") if w.created_at else None,
            "processed_at": w.processed_at.strftime("%Y-%m-%d %H:%M:%S") if w.processed_at else None,
            "processed_by": w.processor.name or w.processor.username if w.processor else None
        })
    return {"status": "success", "data": res}

@router.post("/warnings/{warning_id}/process")
async def process_crisis_warning(warning_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_teacher_role(current_user)
    warning = db.query(CrisisWarning).filter(CrisisWarning.id == warning_id, CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")
    if warning.status == "processed":
        return {"status": "success", "message": "Already processed"}
    
    warning.status = "processed"
    warning.processed_at = func.now()
    warning.processed_by = current_user.id
    db.commit()
    db.refresh(warning)

    # 同步给学生端
    asyncio.create_task(manager.send_personal_message({
        "type": "warning_processed",
        "data": {
            "warning_id": warning.id,
            "message": "老师已收到您的预警信息，正在处理中，请保持通讯畅通。"
        }
    }, warning.student_id, "student"))

    return {"status": "success"}


@router.get("/audit/list")
async def get_audit_list(db: Session = Depends(get_db), current_user: User = Depends(require_roles("teacher"))):
    """
    2.2 后台审核台：获取高危对话记录及可视化解释链路
    """
    # 模拟脱敏后的数据
    return {"status": "success", "data": _audit_items_payload(db, current_user.id)}

@router.post("/audit/adjust")
async def submit_audit_adjustment(data: AuditAdjustment, db: Session = Depends(get_db), current_user: User = Depends(require_roles("teacher"))):
    if not data.chat_id.startswith("warning-") or not data.chat_id[8:].isascii() or not data.chat_id[8:].isdecimal():
        raise HTTPException(status_code=404, detail="Warning not found")
    warning_id = int(data.chat_id[8:])
    warning = db.query(CrisisWarning).filter(CrisisWarning.id == warning_id, CrisisWarning.student_id.in_(assigned_student_ids(db, current_user.id))).first()
    if warning is None:
        raise HTTPException(status_code=404, detail="Warning not found")
    delta = {key: data.adjusted_risk[key] - data.original_risk.get(key, 0) for key in data.adjusted_risk}
    return {"status": "success", "message": "仅计算调整预览，尚未持久保存", "persisted": False, "delta": delta}

@router.post("/export/compliance-report")
async def export_compliance_report(payload: ComplianceReportExportRequest, db: Session = Depends(get_db), current_user: User = Depends(require_roles("teacher"))):
    metrics = _dashboard_metrics_payload(db, current_user.id)
    items = _audit_items_payload(db, current_user.id)
    Path("temp").mkdir(exist_ok=True)
    file_path = str(Path("temp") / f"compliance-{current_user.id}-{uuid.uuid4().hex}.docx")
    doc = Document()
    _set_doc_styles(doc)
    _add_text_paragraph(doc, "学生预警审阅报告", style="Heading 1", size=18, bold=True)
    _add_text_paragraph(doc, "统计范围：仅包含明确分配给您的学生。风险等级来自预警记录，未生成临床评分。")
    _add_text_paragraph(doc, f"生成时间：{datetime.now().isoformat()}")
    metric_labels = {"pv": "对话消息数", "uv": "已分配学生数", "avg_session_rounds": "每会话用户消息均数", "crisis_alerts": "待处理预警数"}
    for key, value in metrics["realtime_stats"].items():
        _add_text_paragraph(doc, f"{metric_labels[key]}：{value}")
    for item in items:
        student = item["student_info"]
        _add_text_paragraph(doc, f"{student['name']} / {student.get('student_id') or ''}", style="Heading 2")
        _add_text_paragraph(doc, f"预警等级：{item['risk_type']}；处理状态：{item['status']}")
        _add_text_paragraph(doc, item.get("abnormal_behavior_summary") or "")
    if not items:
        _add_text_paragraph(doc, "当前分配范围内暂无预警记录。")
    for snapshot in payload.chart_snapshots:
        _add_text_paragraph(doc, snapshot.title, bold=True)
        try:
            doc.add_picture(_decode_data_url_image(snapshot.image_data_url), width=Inches(6.2))
        except Exception:
            _add_text_paragraph(doc, "图表暂未写入。")
    doc.save(file_path)
    return FileResponse(file_path, filename="学生预警审阅报告.docx",
                        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
                        background=BackgroundTask(Path(file_path).unlink, missing_ok=True))
