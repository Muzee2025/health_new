import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from app import models
from app.database import get_db
from app.routers.auth import get_current_user
from app.services.dialogue_analysis_service import (
    build_structured_report,
    enqueue_dialogue_analysis,
    ensure_chart_explanations,
    get_analysis_job_snapshot,
    mark_first_screen_breach,
    save_report,
)
from app.services.llm_fallback import _build_interpretation_fallback, is_local_fallback_url
from app.services.multi_model_orchestrator import orchestrator

router = APIRouter(prefix="/api/v1/report", tags=["report-v1"])
logger = logging.getLogger(__name__)
LLM_URL = os.getenv("LLM_GENERATE_URL", "")

FALLBACK_TEXT = "暂无可解释的对话记录。可先记录近况，或直接选择人工求助。"
THOUGHT_LOG = Path("logs") / "report_thought_process.log"


class AiInterpretRequest(BaseModel):
    recordId: int = Field(ge=0, le=5000)

class MultiModelSubmitRequest(BaseModel):
    visualHints: Optional[list] = None
    audioHints: Optional[list] = None


def _set_cache_header(resp: Response):
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"


def _append_thought_log(user_id: int, request_id: str, payload: dict):
    try:
        THOUGHT_LOG.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "user_id": user_id,
            "request_id": request_id,
            **payload,
        }
        with THOUGHT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("append_thought_log_failed")


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _latest_report_row(db: Session, user_id: int):
    return (
        db.query(models.PsychologicalReport)
        .filter(models.PsychologicalReport.user_id == user_id)
        .order_by(models.PsychologicalReport.updated_at.desc())
        .first()
    )


def _llm_url_candidates():
    if os.getenv("REPORT_AI_ENABLED", "false").lower() != "true":
        return []
    return [LLM_URL] if LLM_URL and not is_local_fallback_url(LLM_URL) else []


def _collaboration_enabled():
    # The legacy fusion fabricates multimodal confidence from absent inputs.
    # Do not expose that experimental chain until it has a validated task contract.
    # Single-assessment text explanation is available through its separate route.
    return False


@router.post("/analysis/trigger")
def trigger_dialogue_analysis(current_user: models.User = Depends(get_current_user)):
    request_id = str(uuid.uuid4())
    state = enqueue_dialogue_analysis(current_user.id, force=True)
    logger.info("analysis_triggered request_id=%s user_id=%s state=%s", request_id, current_user.id, state.get("status"))
    return {"status": "queued", "request_id": request_id, "job": state}


@router.get("/analysis/latest")
def get_latest_analysis(
    response: Response,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    _set_cache_header(response)
    row = _latest_report_row(db, current_user.id)
    if not row:
        quick = build_structured_report(db, current_user.id, include_llm=False, max_messages=300)
        row = save_report(db, current_user.id, quick)
        elapsed_ms = (time.perf_counter() - started) * 1000
        if elapsed_ms > 30000:
            mark_first_screen_breach()
            logger.warning("first_screen_sla_breach request_id=%s user_id=%s duration_ms=%.2f", request_id, current_user.id, elapsed_ms)
        state = (enqueue_dialogue_analysis(current_user.id) if quick["source"]["message_count"]
                 else {"status": "insufficient"})
        logger.info(
            "report_quick_fallback request_id=%s user_id=%s duration_ms=%.2f queue_status=%s",
            request_id,
            current_user.id,
            elapsed_ms,
            state.get("status"),
        )
        row = _latest_report_row(db, current_user.id)
    if not row:
        return {"status": "processing", "request_id": request_id, "data": {}, "job": get_analysis_job_snapshot(current_user.id)}
    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info("report_latest request_id=%s user_id=%s duration_ms=%.2f", request_id, current_user.id, elapsed_ms)
    data = ensure_chart_explanations(json.loads(row.analysis_json or "{}"))
    if data != json.loads(row.analysis_json or "{}"):
        row.analysis_json = json.dumps(data, ensure_ascii=False)
        db.commit()
    return {
        "status": "success",
        "request_id": request_id,
        "risk_level": row.risk_level,
        "data": data,
        "job": get_analysis_job_snapshot(current_user.id),
        "response_ms": round(elapsed_ms, 2),
    }


@router.get("/analysis/stream")
def stream_analysis(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    request_id = str(uuid.uuid4())

    def generate():
        started = time.perf_counter()
        try:
            step1_t0 = time.perf_counter()
            step1 = {"step": "情感识别", "model": "rules+nlp", "promptTokens": 0, "status": "running", "thought": "正在提取对话情绪标签与关键词..."}
            _append_thought_log(current_user.id, request_id, step1)
            yield _sse("step", step1)

            quick = build_structured_report(db, current_user.id, include_llm=False, max_messages=5000)
            step1_ms = round((time.perf_counter() - step1_t0) * 1000, 2)
            step1_done = {
                "step": "情感识别",
                "model": "rules+nlp",
                "promptTokens": 0,
                "status": "done",
                "elapsedMs": step1_ms,
                "thought": f"完成基础情绪提取，共处理 {quick.get('source', {}).get('message_count', 0)} 条对话。",
                "result": {"scores": quick.get("scores", {}), "risk": quick.get("risk", {})},
            }
            _append_thought_log(current_user.id, request_id, step1_done)
            yield _sse("step", step1_done)

            step2_t0 = time.perf_counter()
            step2 = {"step": "资料说明", "model": "pending", "promptTokens": 0, "status": "running", "thought": "正在核对资料范围与解释来源..."}
            _append_thought_log(current_user.id, request_id, step2)
            yield _sse("step", step2)

            try:
                full = build_structured_report(db, current_user.id, include_llm=True, deadline_ts=time.time() + 30, max_messages=5000)
                status = "done" if full.get("generation", {}).get("source") == "provider" else "degraded"
                thought = "模型支持性解释已生成，尚需人工核对。" if status == "done" else "已提供本地说明，未完成外部模型分析。"
            except Exception:
                full = quick
                status = "degraded"
                thought = "Model temporarily unavailable; using local rules."
            step2_ms = round((time.perf_counter() - step2_t0) * 1000, 2)
            step2_done = {
                "step": "资料说明",
                "model": full.get("generation", {}).get("model_id") or "local_rules",
                "promptTokens": 0,
                "status": status,
                "elapsedMs": step2_ms,
                "thought": thought,
                "result": {"risk": full.get("risk", {}), "interventions": full.get("interventions", [])[:3]},
            }
            if step2_ms > 30000 and step2_done["status"] == "done":
                step2_done["status"] = "degraded"
                step2_done["thought"] = "风险评级耗时超过30秒，已返回降级结果。"
            _append_thought_log(current_user.id, request_id, step2_done)
            yield _sse("step", step2_done)

            step3_t0 = time.perf_counter()
            explanation_model = full.get("generation", {}).get("model_id") or "local_rules"
            step3 = {"step": "建议生成", "model": explanation_model, "promptTokens": 0, "status": "running", "thought": "正在整理支持性建议与可选下一步..."}
            _append_thought_log(current_user.id, request_id, step3)
            yield _sse("step", step3)

            interventions = (full.get("interventions") or [])[:5]
            step3_ms = round((time.perf_counter() - step3_t0) * 1000, 2)
            step3_done = {
                "step": "建议生成",
                "model": explanation_model,
                "promptTokens": 0,
                "status": "done" if full.get("generation", {}).get("source") == "provider" and step3_ms <= 30000 else "degraded",
                "elapsedMs": step3_ms,
                "thought": "已整理支持性建议，请结合实际需求决定下一步。",
                "result": {"interventions": interventions},
            }
            _append_thought_log(current_user.id, request_id, step3_done)
            yield _sse("step", step3_done)

            step4_t0 = time.perf_counter()
            step4 = {"step": "可视化摘要", "model": explanation_model, "promptTokens": 0, "status": "running", "thought": "正在整理实际记录和图表说明..."}
            _append_thought_log(current_user.id, request_id, step4)
            yield _sse("step", step4)

            full = ensure_chart_explanations(full)
            row = save_report(db, current_user.id, full)
            step4_ms = round((time.perf_counter() - step4_t0) * 1000, 2)
            step4_done = {
                "step": "可视化摘要",
                "model": explanation_model,
                "promptTokens": 0,
                "status": "done" if full.get("generation", {}).get("source") == "provider" and step4_ms <= 30000 else "degraded",
                "elapsedMs": step4_ms,
                "thought": "已整理模型解释及资料局限。" if full.get("generation", {}).get("source") == "provider" else "已整理本地统计与资料不足说明，未执行模型解读。",
                "result": {"chart_insights": full.get("chart_insights", {})},
            }
            _append_thought_log(current_user.id, request_id, step4_done)
            yield _sse("step", step4_done)

            total_ms = round((time.perf_counter() - started) * 1000, 2)
            done_payload = {
                "status": "success",
                "request_id": request_id,
                "risk_level": row.risk_level,
                "data": full,
                "response_ms": total_ms,
            }
            _append_thought_log(current_user.id, request_id, {"step": "完成", "status": "success", "elapsedMs": total_ms})
            yield _sse("done", done_payload)
        except Exception:
            logger.exception("analysis_stream_failed request_id=%s user_id=%s", request_id, current_user.id)
            payload = {"step": "error", "status": "failed", "thought": "Analysis temporarily unavailable"}
            _append_thought_log(current_user.id, request_id, payload)
            yield _sse("error", payload)

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.post("/ai-interpret")
def generate_ai_interpret(
    req: AiInterpretRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    row = _latest_report_row(db, current_user.id)
    if not row:
        return {"text": FALLBACK_TEXT, "source": "local_rules", "status": "insufficient", "model_id": None}
    try:
        report = json.loads(row.analysis_json or "{}")
    except (ValueError, TypeError):
        report = {}
    if not isinstance(report, dict):
        report = {}
    # `source` is written by several generations of the report writer and may be
    # absent, null, or a plain string; only a dict carries the message list.
    source = report.get("source")
    messages = source.get("messages", []) if isinstance(source, dict) else []
    sample = messages[max(0, req.recordId - 5): req.recordId + 1] if isinstance(messages, list) else []
    if not sample:
        return {"text": FALLBACK_TEXT, "source": "local_rules", "status": "insufficient", "model_id": None}
    prompt = (f"当前选择范围包含{len(sample)}条已存对话，但未提供原文。请只说明资料局限与可选的求助下一步，"
              "不要推断心理状态、疾病、概率或虚构风险。")
    for llm_url in _llm_url_candidates():
        try:
            resp = requests.post(
                llm_url,
                json={"prompt": prompt},
                timeout=0.8,
            )
            if resp.status_code != 200:
                continue
            payload = resp.json()
            text = payload.get("text") or payload.get("result") or ""
            if text.strip():
                if payload.get("source") in {"local_rules", "local_rule"}:
                    break
                return {"text": text.strip(), "source": "provider", "status": "completed", "model_id": payload.get("model_id")}
        except Exception:
            continue
    return {"text": _build_interpretation_fallback(prompt), "source": "local_rules", "status": "fallback", "model_id": None}


@router.get("/analysis/diagnostics")
def get_analysis_diagnostics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    started = time.perf_counter()
    db_ok = True
    db_t0 = time.perf_counter()
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    db_latency_ms = (time.perf_counter() - db_t0) * 1000
    # Do not probe configured providers from this user-facing endpoint.
    local = not _llm_url_candidates()
    job = get_analysis_job_snapshot(current_user.id)
    safe_fields = {"status", "started_at", "finished_at", "deadline_seconds", "duration_ms"}
    own_job = {key: value for key, value in job.items() if key in safe_fields}
    return {
        "user_id": current_user.id,
        "db": {"ok": db_ok, "latency_ms": round(db_latency_ms, 2)},
        "llm": {"ok": local, "latency_ms": 0.0, "error": "" if local else "health_check_not_performed"},
        "queue": {str(current_user.id): own_job},
        "metrics": {},
        "response_ms": round((time.perf_counter() - started) * 1000, 2),
        "sla": {"first_screen_seconds": 30, "full_report_seconds": 120},
    }


@router.post("/analysis/collab/submit")
async def submit_collab_analysis(
    req: MultiModelSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if not _collaboration_enabled():
        raise HTTPException(status_code=503, detail="扩展模型解析当前未启用，可继续查看本地结果或选择人工求助。")
    report = build_structured_report(db, current_user.id, include_llm=False, max_messages=5000)
    if report.get("data_status") != "available":
        raise HTTPException(status_code=409, detail="暂无可用于扩展解析的记录。")
    payload = {
        "messages": [],
        "facts": {"message_count": report.get("source", {}).get("message_count", 0)},
        "visualHints": req.visualHints or [],
        "audioHints": req.audioHints or [],
    }
    task_id = await orchestrator.submit_task(current_user.id, payload)
    return {"status": "queued", "taskId": task_id}


@router.get("/analysis/collab/stream/{task_id}")
async def stream_collab_analysis(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
):
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    if int(task.get("user_id", -1)) != int(current_user.id):
        raise HTTPException(status_code=403, detail="forbidden")
    return StreamingResponse(
        orchestrator.stream_generator(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@router.get("/analysis/collab/result/{task_id}")
async def get_collab_result(
    task_id: str,
    current_user: models.User = Depends(get_current_user),
):
    task = orchestrator.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="task_not_found")
    if int(task.get("user_id", -1)) != int(current_user.id):
        raise HTTPException(status_code=403, detail="forbidden")
    return {
        "status": task.get("status"),
        "taskId": task_id,
        "progress": task.get("progress", 0),
        "result": task.get("result"),
        "error": task.get("error", ""),
        "metrics": orchestrator.get_metrics(),
    }


@router.get("/analysis/collab/health")
async def get_collab_health(
    current_user: models.User = Depends(get_current_user),
):
    return {
        "status": "ok",
        "collaboration_enabled": _collaboration_enabled(),
        "user_id": current_user.id,
        "metrics": orchestrator.get_metrics(),
    }
