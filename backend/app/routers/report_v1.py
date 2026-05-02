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
from pydantic import BaseModel
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
from app.services.multi_model_orchestrator import orchestrator

router = APIRouter(prefix="/api/v1/report", tags=["report-v1"])
logger = logging.getLogger(__name__)
LLM_URL = os.getenv("LLM_GENERATE_URL", "http://llm-internal:8000/generate")

FALLBACK_TEXT = "AI 解读生成中，请稍后再试"
THOUGHT_LOG = Path("logs") / "report_thought_process.log"


class AiInterpretRequest(BaseModel):
    recordId: int

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
    urls = [
        LLM_URL,
        "http://127.0.0.1:8000/generate",
        "http://127.0.0.1:8000/api/llm/generate",
    ]
    return list(dict.fromkeys([u for u in urls if u]))


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
        state = enqueue_dialogue_analysis(current_user.id, force=True)
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
            step2 = {"step": "风险评级", "model": "qwen", "promptTokens": 0, "status": "running", "thought": "正在进行风险评级与建议生成..."}
            _append_thought_log(current_user.id, request_id, step2)
            yield _sse("step", step2)

            try:
                full = build_structured_report(db, current_user.id, include_llm=True, deadline_ts=time.time() + 30, max_messages=5000)
                status = "done"
                thought = "模型风险评级完成。"
            except Exception as exc:
                full = quick
                status = "degraded"
                thought = f"模型调用超时或异常，已降级为规则分析：{str(exc)}"
            step2_ms = round((time.perf_counter() - step2_t0) * 1000, 2)
            step2_done = {
                "step": "风险评级",
                "model": "qwen",
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
            step3 = {"step": "建议生成", "model": "qwen", "promptTokens": 0, "status": "running", "thought": "正在整理可执行建议与干预优先级..."}
            _append_thought_log(current_user.id, request_id, step3)
            yield _sse("step", step3)

            interventions = (full.get("interventions") or [])[:5]
            step3_ms = round((time.perf_counter() - step3_t0) * 1000, 2)
            step3_done = {
                "step": "建议生成",
                "model": "qwen",
                "promptTokens": 0,
                "status": "done" if step3_ms <= 30000 else "degraded",
                "elapsedMs": step3_ms,
                "thought": "建议已生成。" if step3_ms <= 30000 else "建议生成耗时过长，已降级输出基础建议。",
                "result": {"interventions": interventions},
            }
            _append_thought_log(current_user.id, request_id, step3_done)
            yield _sse("step", step3_done)

            step4_t0 = time.perf_counter()
            step4 = {"step": "可视化摘要", "model": "qwen", "promptTokens": 0, "status": "running", "thought": "正在生成图表解读与摘要..."}
            _append_thought_log(current_user.id, request_id, step4)
            yield _sse("step", step4)

            full = ensure_chart_explanations(full)
            row = save_report(db, current_user.id, full)
            step4_ms = round((time.perf_counter() - step4_t0) * 1000, 2)
            step4_done = {
                "step": "可视化摘要",
                "model": "qwen",
                "promptTokens": 0,
                "status": "done" if step4_ms <= 30000 else "degraded",
                "elapsedMs": step4_ms,
                "thought": "图表解释已生成，准备输出最终报告。" if step4_ms <= 30000 else "图表解释耗时较长，已返回精简版摘要。",
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
        except Exception as exc:
            logger.exception("analysis_stream_failed request_id=%s user_id=%s", request_id, current_user.id)
            payload = {"step": "异常", "status": "failed", "thought": str(exc)}
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
        return {"text": FALLBACK_TEXT}
    report = json.loads(row.analysis_json or "{}")
    messages = report.get("source", {}).get("messages", [])
    sample = messages[max(0, req.recordId - 5): req.recordId + 1]
    prompt = "请用 200 字以内白话解释以下心理对话片段，说明情绪变化、潜在风险和可执行建议。\n" + json.dumps(
        sample, ensure_ascii=False
    )
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
                return {"text": text.strip()}
        except Exception:
            continue
    return {"text": FALLBACK_TEXT}


@router.get("/analysis/diagnostics")
def get_analysis_diagnostics(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    started = time.perf_counter()
    db_ok = True
    db_latency_ms = -1.0
    llm_ok = False
    llm_latency_ms = -1.0
    llm_error = ""
    try:
        db_t0 = time.perf_counter()
        db.execute(text("SELECT 1"))
        db_latency_ms = (time.perf_counter() - db_t0) * 1000
    except Exception:
        db_ok = False

    for llm_url in _llm_url_candidates():
        try:
            llm_t0 = time.perf_counter()
            resp = requests.post(llm_url, json={"prompt": "ping"}, timeout=0.8)
            llm_latency_ms = (time.perf_counter() - llm_t0) * 1000
            llm_ok = resp.status_code == 200
            if llm_ok:
                llm_error = ""
                break
            llm_error = f"{llm_url}:http_{resp.status_code}"
        except Exception as exc:
            llm_error = f"{llm_url}:{str(exc)}"

    snapshot = get_analysis_job_snapshot()
    total_ms = (time.perf_counter() - started) * 1000
    return {
        "user_id": current_user.id,
        "llm_url": LLM_URL,
        "llm_candidates": _llm_url_candidates(),
        "db": {"ok": db_ok, "latency_ms": round(db_latency_ms, 2)},
        "llm": {"ok": llm_ok, "latency_ms": round(llm_latency_ms, 2), "error": llm_error},
        "queue": snapshot.get("jobs", {}),
        "metrics": snapshot.get("metrics", {}),
        "response_ms": round(total_ms, 2),
        "sla": {"first_screen_seconds": 30, "full_report_seconds": 120},
    }


@router.post("/analysis/collab/submit")
async def submit_collab_analysis(
    req: MultiModelSubmitRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    report = build_structured_report(db, current_user.id, include_llm=False, max_messages=5000)
    payload = {
        "messages": report.get("source", {}).get("messages", []),
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
        "user_id": current_user.id,
        "metrics": orchestrator.get_metrics(),
    }
