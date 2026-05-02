import base64
import io
import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List

from docx import Document
from docx.oxml.ns import qn
from docx.shared import Inches, Pt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, ChatHistoryArchive, AIChatSession, AIChatMessage, CrisisWarning
from app.routers.auth import get_current_user
from app.routers.teacher import check_teacher_role
from app.utils.websocket_manager import manager

router = APIRouter()

# --- 教师端大屏看板与审核工作台 API ---

class AuditAdjustment(BaseModel):
    chat_id: str
    original_risk: Dict[str, int]
    adjusted_risk: Dict[str, int]
    action: str # "pass", "reject", "escalate"


class ChartSnapshot(BaseModel):
    title: str
    image_data_url: str


class ComplianceReportExportRequest(BaseModel):
    chart_snapshots: List[ChartSnapshot] = []


def _dashboard_metrics_payload() -> Dict[str, Any]:
    """
    汇总大盘指标。原 T+1 数据源可在此被内部引用，但不再独立导出。
    """
    return {
        "realtime_stats": {
            "pv": 12450,
            "uv": 3200,
            "avg_session_rounds": 12.5,
            "crisis_alerts": 18,
        },
        "funnel_data": [
            {"value": 100, "name": "触发警报"},
            {"value": 85, "name": "老师接单"},
            {"value": 70, "name": "首次接触"},
            {"value": 50, "name": "完成干预"},
            {"value": 45, "name": "学生确认(降险)"},
        ],
        "campus_heatmap": [
            {"building": "1号楼", "risk_density": 0.8},
            {"building": "3号楼", "risk_density": 0.4},
            {"building": "7号楼", "risk_density": 0.9},
            {"building": "研究生公寓", "risk_density": 0.3},
        ],
        "emotion_trends_7d": {
            "dates": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            "joy": [0.6, 0.6, 0.5, 0.7, 0.8, 0.9, 0.8],
            "anxiety": [0.4, 0.5, 0.7, 0.6, 0.4, 0.3, 0.3],
        },
    }


def _audit_items_payload() -> List[Dict[str, Any]]:
    return [
        {
            "chat_id": "c_1001",
            "student_info": {
                "name": "李某某",
                "student_id": "2024001001",
                "grade": "大二",
                "gender": "女",
                "age": 20,
            },
            "trigger_msg": "我真的受不了我的室友了，每天晚上吵到凌晨，我考试又要挂科了，我好想跳下去一了百了。",
            "ai_reply": "我感受到您现在非常痛苦，请务必保护好自己。请立即拨打校内24小时心理危机热线：400-123-4567。",
            "heatmap": [
                {"token": "挂科", "weight": 0.6, "is_keyword": True},
                {"token": "跳下去", "weight": 0.95, "is_keyword": True},
            ],
            "risk_radar": {"academic": 80, "interpersonal": 90, "family": 20, "emotion": 95, "physical": 70},
            "risk_type": "危机倾向+学业压力",
            "risk_score": 92,
            "abnormal_behavior_summary": "连续深夜高危表达，出现自伤倾向语义，且学业压力显著升高。",
            "status": "pending",
            "timestamp": "2026-04-11 14:30:00",
        },
        {
            "chat_id": "c_1002",
            "student_info": {
                "name": "王某某",
                "student_id": "2024001002",
                "grade": "大一",
                "gender": "男",
                "age": 19,
            },
            "trigger_msg": "最近不想去上课，感觉怎么努力都没意义。",
            "ai_reply": "听起来你现在有明显的无力感，我们先从作息和支持资源开始慢慢调整。",
            "heatmap": [
                {"token": "没意义", "weight": 0.82, "is_keyword": True},
                {"token": "不想去上课", "weight": 0.75, "is_keyword": True},
            ],
            "risk_radar": {"academic": 78, "interpersonal": 65, "family": 35, "emotion": 80, "physical": 55},
            "risk_type": "抑郁倾向+退缩行为",
            "risk_score": 84,
            "abnormal_behavior_summary": "逃课意愿上升、情绪低落持续三天以上。",
            "status": "pending",
            "timestamp": "2026-04-12 10:20:00",
        },
        {
            "chat_id": "c_1003",
            "student_info": {
                "name": "赵某某",
                "student_id": "2024001003",
                "grade": "大三",
                "gender": "女",
                "age": 21,
            },
            "trigger_msg": "最近总和同学冲突，晚上也睡不好。",
            "ai_reply": "你已经意识到冲突和睡眠问题，这是改变的起点，我们可以制定沟通和睡眠计划。",
            "heatmap": [
                {"token": "冲突", "weight": 0.7, "is_keyword": True},
                {"token": "睡不好", "weight": 0.64, "is_keyword": False},
            ],
            "risk_radar": {"academic": 55, "interpersonal": 82, "family": 42, "emotion": 68, "physical": 60},
            "risk_type": "人际冲突+睡眠障碍",
            "risk_score": 76,
            "abnormal_behavior_summary": "人际摩擦频发，伴随睡眠质量下降。",
            "status": "pending",
            "timestamp": "2026-04-12 19:10:00",
        },
    ]


def _intervention_level(risk_score: int) -> str:
    if risk_score >= 90:
        return "紧急干预"
    if risk_score >= 80:
        return "重点关注"
    return "持续观察"


def _decode_data_url_image(image_data_url: str) -> io.BytesIO:
    if "," not in image_data_url:
        raise HTTPException(status_code=400, detail="图表图片格式非法")
    _, encoded = image_data_url.split(",", 1)
    try:
        raw = base64.b64decode(encoded)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"图表图片解码失败: {exc}") from exc
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
async def get_dashboard_metrics():
    """
    3.1 & 3.2: 模拟 Flink CDC + ClickHouse 聚合的实时大盘数据
    返回漏斗图、雷达图、热力地图需要的数据
    """
    return {"status": "success", **_dashboard_metrics_payload()}

@router.get("/warnings")
async def get_crisis_warnings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    check_teacher_role(current_user)
    warnings = db.query(CrisisWarning).order_by(CrisisWarning.created_at.desc()).all()
    res = []
    for w in warnings:
        msg_content = ""
        if w.chat_message_id:
            msg = db.query(AIChatMessage).filter(AIChatMessage.id == w.chat_message_id).first()
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
    warning = db.query(CrisisWarning).filter(CrisisWarning.id == warning_id).first()
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
async def get_audit_list():
    """
    2.2 后台审核台：获取高危对话记录及可视化解释链路
    """
    # 模拟脱敏后的数据
    return {"status": "success", "data": _audit_items_payload()}

@router.post("/audit/adjust")
async def submit_audit_adjustment(data: AuditAdjustment):
    """
    心理老师拖拽调整风险分值，系统记录 Δ 值用于后续 RLHF 模型微调
    """
    delta = {k: data.adjusted_risk[k] - data.original_risk.get(k, 0) for k in data.adjusted_risk}
    # 模拟写入日志库
    # db.execute("INSERT INTO rl_feedback_logs ...")
    return {
        "status": "success",
        "message": f"已记录校正动作: {data.action}",
        "delta": delta
    }

@router.post("/export/compliance-report")
async def export_compliance_report(payload: ComplianceReportExportRequest):
    """
    导出合规审计报告（仅 Word），并支持嵌入前端传入的高清图表快照。
    """
    os.makedirs("temp", exist_ok=True)

    audit_items = _audit_items_payload()
    metrics = _dashboard_metrics_payload()
    high_risk_students = sorted(audit_items, key=lambda x: x.get("risk_score", 0), reverse=True)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    file_path = "temp/compliance_audit_report.docx"
    doc = Document()
    _set_doc_styles(doc)
    _add_text_paragraph(doc, "合规审计风险干预报告", style="Heading 1", size=18, bold=True)
    _add_text_paragraph(doc, f"生成时间：{generated_at}")

    _add_text_paragraph(doc, "合规审计关键指标汇总", style="Heading 2", size=14, bold=True)
    _add_text_paragraph(doc, f"预警触发频次：{metrics['realtime_stats']['crisis_alerts']} 次")
    _add_text_paragraph(doc, f"今日独立访客(UV)：{metrics['realtime_stats']['uv']}")
    _add_text_paragraph(doc, f"人均会话轮次：{metrics['realtime_stats']['avg_session_rounds']}")
    _add_text_paragraph(doc, f"违纪事件数（模拟）：{len([x for x in audit_items if x['risk_score'] >= 80])}")

    _add_text_paragraph(doc, "高风险学生清单", style="Heading 2", size=14, bold=True)
    for item in high_risk_students:
        stu = item["student_info"]
        level = _intervention_level(item["risk_score"])
        _add_text_paragraph(
            doc,
            f"{stu['name']} / {stu['student_id']} | 风险类型：{item['risk_type']} | "
            f"风险评分：{item['risk_score']} | 干预级别建议：{level}",
            style="List Bullet",
        )
        _add_text_paragraph(doc, f"异常行为摘要：{item['abnormal_behavior_summary']}")

    _add_text_paragraph(doc, "需要干预学生分级建议", style="Heading 2", size=14, bold=True)
    for item in high_risk_students:
        stu = item["student_info"]
        _add_text_paragraph(
            doc,
            f"{stu['name']}（{stu['student_id']}）：{_intervention_level(item['risk_score'])}",
            style="List Number",
        )

    _add_text_paragraph(doc, "可视化图表快照", style="Heading 2", size=14, bold=True)
    for snap in payload.chart_snapshots:
        _add_text_paragraph(doc, snap.title, bold=True)
        try:
            img_buf = _decode_data_url_image(snap.image_data_url)
            doc.add_picture(img_buf, width=Inches(6.2))
        except Exception:
            _add_text_paragraph(doc, "图表写入失败")

    doc.save(file_path)
    return FileResponse(
        file_path,
        filename="合规审计风险干预报告.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
