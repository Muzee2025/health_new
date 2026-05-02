import json
import logging
import os
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import Lock, Thread
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session

from app import models
from app.database import SessionLocal

LLM_URL = os.getenv("LLM_GENERATE_URL", "http://llm-internal:8000/generate")
logger = logging.getLogger(__name__)
JOB_LOCK = Lock()
ANALYSIS_JOBS: Dict[int, Dict[str, Any]] = {}
PERF_METRICS: Dict[str, Any] = {
    "analysis_total": 0,
    "analysis_success": 0,
    "analysis_failed": 0,
    "analysis_avg_ms": 0.0,
    "first_screen_breach": 0,
    "full_report_breach": 0,
}
DEFAULT_CHART_EXPLANATIONS: Dict[str, str] = {
    "bar": "当前风险维度整体偏高，建议优先处理睡眠和压力管理，每天固定放松时段并减少连续高压学习。",
    "pie": "负性情绪占比高于中性/积极，说明近期心理负荷偏重。建议增加稳定支持来源，如固定运动和社交支持。",
    "heatmap": "近7天高强度情绪有集中时段，提示存在阶段性压力峰值。建议在高峰日前提前安排减压活动。",
    "trend": "7天趋势若持续上升代表风险累积，若下降说明调节有效。建议保留有效策略并每周复盘一次情绪日志。",
    "network": "情绪与认知因子耦合明显，提示“想法-情绪”相互放大。建议使用认知重评法，先记录触发事件再修正自动化负面想法。",
    "histogram": "分布右偏说明高压力时段增多。建议设置预警阈值（如连续2天高分即主动预约咨询）。",
}


def _safe_json_loads(raw: str | None, fallback: Any):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _extract_keywords_from_heatmap(heatmap: List[Dict[str, Any]]) -> List[str]:
    return [str(item.get("token", "")).strip() for item in heatmap if item.get("is_keyword")]


def _collect_messages(db: Session, user_id: int, max_messages: int | None = None) -> List[Dict[str, Any]]:
    sessions = db.query(models.AIChatSession).filter(models.AIChatSession.user_id == user_id).all()
    records: List[Dict[str, Any]] = []
    for session in sessions:
        msgs = (
            db.query(models.AIChatMessage)
            .filter(models.AIChatMessage.session_id == session.id)
            .order_by(models.AIChatMessage.created_at.asc())
            .all()
        )
        for msg in msgs:
            emotion = _safe_json_loads(msg.emotion_tags, {})
            heatmap = _safe_json_loads(msg.heatmap, [])
            records.append(
                {
                    "session_id": session.id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                    "emotion_tags": emotion,
                    "keywords": _extract_keywords_from_heatmap(heatmap),
                    "is_crisis": bool(msg.is_crisis),
                }
            )
            if max_messages and len(records) >= max_messages:
                return records
    return records


def _score_from_message(message: Dict[str, Any]) -> Optional[float]:
    emotion = message.get("emotion_tags") or {}
    if not emotion:
        return None
    sadness = float(emotion.get("sadness", 0))
    fear = float(emotion.get("fear", 0))
    anger = float(emotion.get("anger", 0))
    joy = float(emotion.get("joy", 0))
    raw = (sadness + fear + anger) * 100 - joy * 40
    return max(0.0, min(100.0, raw))


def _normalize_to_utc(dt: datetime) -> datetime:
    """
    统一将 datetime 转为 UTC aware，避免 naive/aware 混算。
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _build_time_series(messages: List[Dict[str, Any]], days: int) -> List[Dict[str, Any]]:
    now = datetime.now(timezone.utc)
    bucket = defaultdict(list)
    for item in messages:
        try:
            raw_ts = str(item.get("created_at", "")).replace("Z", "+00:00")
            ts = datetime.fromisoformat(raw_ts)
            ts = _normalize_to_utc(ts)
        except Exception:
            continue
        if (now - ts).days >= days:
            continue
        score = _score_from_message(item)
        if score is None:
            continue
        bucket[ts.strftime("%Y-%m-%d")].append(score)

    series = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        scores = bucket.get(d, [])
        value = round(sum(scores) / len(scores), 2) if scores else 0.0
        series.append({"date": d, "score": value})
    return series


def _build_radar(messages: List[Dict[str, Any]]) -> Dict[str, int]:
    scored = [s for s in (_score_from_message(item) for item in messages) if s is not None]
    if not scored:
        return {"emotion": 0, "cognition": 0, "behavior": 0, "depression": 0, "anxiety": 0}
    avg = sum(scored) / len(scored)
    return {
        "emotion": int(max(0, min(100, avg))),
        "cognition": int(max(0, min(100, avg * 0.9 + 5))),
        "behavior": int(max(0, min(100, avg * 0.85 + 8))),
        "depression": int(max(0, min(100, avg * 0.95))),
        "anxiety": int(max(0, min(100, avg * 1.02))),
    }


def _build_heatmap(messages: List[Dict[str, Any]], days: int = 7) -> List[Dict[str, Any]]:
    base = _build_time_series(messages, days)
    data = []
    for row in base:
        score = row["score"]
        data.append(
            {
                "date": row["date"],
                "depression": round(score * 0.95, 2),
                "anxiety": round(min(100, score * 1.05), 2),
                "suicide": round(score * 0.65, 2),
            }
        )
    return data


def _llm_analyze(messages: List[Dict[str, Any]], *, deadline_ts: float | None = None) -> Dict[str, Any]:
    sample = messages[-30:]
    prompt = (
        "你是中文心理对话分析引擎。请基于输入的真实对话记录，输出严格JSON，字段必须包含："
        "emotion_score(0-100), cognition_score(0-100), behavior_score(0-100), "
        "depression_confidence(0-100), anxiety_confidence(0-100), suicide_confidence(0-100), "
        "risk_level(LOW|MEDIUM|HIGH), interventions(数组, 3条中文建议), "
        "chart_insights(对象，键为bar/pie/heatmap/trend/network/histogram；每项必须包含“趋势判断+对应建议”，每项<=120字)。\n"
        f"对话数据: {json.dumps(sample, ensure_ascii=False)}"
    )
    retry_timeouts = [1.0, 1.8, 3.0]
    llm_urls = [
        LLM_URL,
        "http://127.0.0.1:8000/generate",
        "http://127.0.0.1:8000/api/llm/generate",
    ]
    # 去重并保持顺序
    llm_urls = list(dict.fromkeys([u for u in llm_urls if u]))
    last_error = ""
    for timeout in retry_timeouts:
        if deadline_ts and (time.time() + timeout + 0.2) > deadline_ts:
            break
        for llm_url in llm_urls:
            try:
                resp = requests.post(llm_url, json={"prompt": prompt}, timeout=timeout)
                if resp.status_code != 200:
                    last_error = f"{llm_url}:http_{resp.status_code}"
                    continue
                payload = resp.json()
                text = payload.get("text") or payload.get("result") or "{}"
                parsed = _safe_json_loads(text, {})
                if isinstance(parsed, dict):
                    return parsed
                last_error = f"{llm_url}:non_dict_payload"
            except Exception as exc:
                last_error = f"{llm_url}:{str(exc)}"
                time.sleep(0.15)
    logger.warning("LLM analyze degraded to heuristic: primary_url=%s error=%s", LLM_URL, last_error)
    return {}


def ensure_chart_explanations(report: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(report or {})
    existing = output.get("chart_insights") or output.get("chart_explanations")
    merged = dict(existing) if isinstance(existing, dict) else {}
    for key, value in DEFAULT_CHART_EXPLANATIONS.items():
        if not merged.get(key):
            merged[key] = value
    output["chart_insights"] = merged
    output["chart_explanations"] = merged
    return output


def _series_direction(values: List[float]) -> str:
    if len(values) < 2:
        return "波动不明显"
    head = sum(values[: max(1, len(values) // 2)]) / max(1, len(values) // 2)
    tail = sum(values[max(1, len(values) // 2):]) / max(1, len(values) - max(1, len(values) // 2))
    delta = tail - head
    if delta >= 5:
        return "明显上升"
    if delta <= -5:
        return "明显下降"
    return "总体平稳"


def _build_trend_advice_payload(
    *,
    last7: List[Dict[str, Any]],
    last30: List[Dict[str, Any]],
    risk_level: str,
    depression: int,
    anxiety: int,
    suicide: int,
) -> Dict[str, str]:
    s7 = [float(x.get("score", 0)) for x in last7]
    s30 = [float(x.get("score", 0)) for x in last30]
    dir7 = _series_direction(s7)
    dir30 = _series_direction(s30)
    risk_peak = max(depression, anxiety, suicide)

    return {
        "trend": f"近7天风险趋势{dir7}，近30天{dir30}。建议每晚固定10分钟情绪复盘，若连续2天升高立即降低任务强度并寻求支持。",
        "heatmap": f"高强度情绪在近期出现聚集，提示短期压力峰值。建议在高峰时段前安排呼吸放松与短时步行，避免持续透支。",
        "bar": f"当前抑郁/焦虑风险峰值约{risk_peak}分，说明心理负荷偏高。建议优先修复睡眠与作息，减少夜间高认知任务。",
        "pie": f"当前情绪结构偏向负性占比，说明恢复资源不足。建议每周至少2次稳定社交或运动，增加积极体验输入。",
        "network": "因子联动较强，压力会通过认知反刍放大情绪波动。建议使用“触发事件-自动想法-替代想法”三步记录法。",
        "histogram": f"分布显示中高风险区间出现频率偏高（风险等级{risk_level}）。建议设置个人预警线并在超线时主动预约咨询。",
    }


def build_structured_report(
    db: Session,
    user_id: int,
    *,
    include_llm: bool = True,
    deadline_ts: float | None = None,
    max_messages: int | None = None,
) -> Dict[str, Any]:
    messages = _collect_messages(db, user_id, max_messages=max_messages)
    llm = _llm_analyze(messages, deadline_ts=deadline_ts) if include_llm else {}
    radar = _build_radar(messages)
    last7 = _build_time_series(messages, 7)
    last30 = _build_time_series(messages, 30)
    heatmap = _build_heatmap(messages, 7)

    depression = int(llm.get("depression_confidence", radar["depression"]))
    anxiety = int(llm.get("anxiety_confidence", radar["anxiety"]))
    suicide = int(llm.get("suicide_confidence", max(0, radar["depression"] - 20)))
    max_risk = max(depression, anxiety, suicide)
    risk_level = llm.get("risk_level")
    if risk_level not in {"LOW", "MEDIUM", "HIGH"}:
        risk_level = "HIGH" if max_risk >= 75 else "MEDIUM" if max_risk >= 45 else "LOW"
    chart_insights = llm.get("chart_insights", {}) if isinstance(llm.get("chart_insights"), dict) else {}
    if not chart_insights:
        chart_insights = _build_trend_advice_payload(
            last7=last7,
            last30=last30,
            risk_level=risk_level,
            depression=depression,
            anxiety=anxiety,
            suicide=suicide,
        )

    base_report = {
        "source": {
            "message_count": len(messages),
            "messages": messages,
        },
        "scores": {
            "emotion": int(llm.get("emotion_score", radar["emotion"])),
            "cognition": int(llm.get("cognition_score", radar["cognition"])),
            "behavior": int(llm.get("behavior_score", radar["behavior"])),
        },
        "risk": {
            "risk_level": risk_level,
            "depression_confidence": depression,
            "anxiety_confidence": anxiety,
            "suicide_confidence": suicide,
        },
        "trends": {
            "seven_days": last7,
            "thirty_days": last30,
            "heatmap": heatmap,
            "radar": radar,
        },
        "interventions": llm.get(
            "interventions",
            ["保持规律作息并记录情绪波动。", "每天安排一次低强度运动，降低生理紧张。", "当出现持续消极想法时，尽快联系校心理中心。"],
        ),
        "chart_insights": chart_insights,
        "chart_explanations": chart_insights,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "generated_mode": "full" if include_llm else "quick",
    }
    return ensure_chart_explanations(base_report)


def save_report(db: Session, user_id: int, report: Dict[str, Any]) -> models.PsychologicalReport:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    row = (
        db.query(models.PsychologicalReport)
        .filter(models.PsychologicalReport.user_id == user_id, models.PsychologicalReport.report_date == today)
        .first()
    )
    if not row:
        row = models.PsychologicalReport(user_id=user_id, report_date=today, analysis_json="{}")
        db.add(row)
    row.risk_level = report.get("risk", {}).get("risk_level", "LOW")
    row.analysis_json = json.dumps(report, ensure_ascii=False)
    db.commit()
    db.refresh(row)
    return row


def _update_perf_metric(success: bool, elapsed_ms: float):
    with JOB_LOCK:
        PERF_METRICS["analysis_total"] += 1
        if success:
            PERF_METRICS["analysis_success"] += 1
        else:
            PERF_METRICS["analysis_failed"] += 1
        total = PERF_METRICS["analysis_total"]
        prev_avg = float(PERF_METRICS["analysis_avg_ms"])
        PERF_METRICS["analysis_avg_ms"] = round(((prev_avg * (total - 1)) + elapsed_ms) / total, 2)


def get_analysis_job_snapshot(user_id: int | None = None) -> Dict[str, Any]:
    with JOB_LOCK:
        if user_id is not None:
            return dict(ANALYSIS_JOBS.get(user_id, {}))
        return {
            "jobs": {uid: dict(state) for uid, state in ANALYSIS_JOBS.items()},
            "metrics": dict(PERF_METRICS),
        }


def mark_first_screen_breach():
    with JOB_LOCK:
        PERF_METRICS["first_screen_breach"] += 1


def run_dialogue_analysis_for_user(user_id: int):
    started = time.perf_counter()
    deadline_ts = time.time() + 120
    db = SessionLocal()
    try:
        with JOB_LOCK:
            ANALYSIS_JOBS[user_id] = {
                "status": "running",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "deadline_seconds": 120,
                "error": "",
            }
        report = build_structured_report(db, user_id, include_llm=True, deadline_ts=deadline_ts)
        save_report(db, user_id, report)
        elapsed_ms = (time.perf_counter() - started) * 1000
        with JOB_LOCK:
            ANALYSIS_JOBS[user_id].update(
                {
                    "status": "success",
                    "finished_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": round(elapsed_ms, 2),
                }
            )
            if elapsed_ms > 120000:
                PERF_METRICS["full_report_breach"] += 1
        _update_perf_metric(True, elapsed_ms)
        logger.info("full_report_done user_id=%s duration_ms=%.2f", user_id, elapsed_ms)
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        with JOB_LOCK:
            ANALYSIS_JOBS[user_id] = {
                "status": "failed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": round(elapsed_ms, 2),
                "error": str(exc),
            }
        _update_perf_metric(False, elapsed_ms)
        logger.exception("full_report_failed user_id=%s error=%s", user_id, exc)
        raise
    finally:
        db.close()


def enqueue_dialogue_analysis(user_id: int, *, force: bool = False):
    with JOB_LOCK:
        state = ANALYSIS_JOBS.get(user_id, {})
        if not force and state.get("status") in {"queued", "running"}:
            return state
        ANALYSIS_JOBS[user_id] = {
            "status": "queued",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        }
    Thread(target=run_dialogue_analysis_for_user, args=(user_id,), daemon=True).start()
    return get_analysis_job_snapshot(user_id)
