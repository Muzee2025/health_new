import json
import logging
import math
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
from app.services.llm_fallback import _build_structured_fallback, is_local_fallback_url

LLM_URL = os.getenv("LLM_GENERATE_URL", "")
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
    key: "目前没有足够的可核验数据解释该图。空缺不代表零风险，规则线索也不是诊断概率。"
    for key in ("bar", "pie", "heatmap", "trend", "network", "histogram")
}


def _safe_json_loads(raw: str | None, fallback: Any):
    if not raw:
        return fallback
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _extract_keywords_from_heatmap(heatmap: List[Dict[str, Any]]) -> List[str]:
    if not isinstance(heatmap, list):
        return []
    return [str(item.get("token", "")).strip() for item in heatmap
            if isinstance(item, dict) and item.get("is_keyword")]


def _collect_messages(db: Session, user_id: int, max_messages: int | None = None) -> List[Dict[str, Any]]:
    # Select the most recent bounded window across sessions, then sort oldest first.
    rows = (db.query(models.AIChatMessage)
            .join(models.AIChatSession, models.AIChatMessage.session_id == models.AIChatSession.id)
            .filter(models.AIChatSession.user_id == user_id)
            .order_by(models.AIChatMessage.created_at.desc(), models.AIChatMessage.id.desc())
            .limit(max_messages or 5000).all())
    records: List[Dict[str, Any]] = []
    for msg in reversed(rows):
            emotion = _safe_json_loads(msg.emotion_tags, {})
            heatmap = _safe_json_loads(msg.heatmap, [])
            records.append(
                {
                    "session_id": msg.session_id,
                    "role": msg.role,
                    "content": msg.content,
                    "created_at": msg.created_at.isoformat() if msg.created_at else "",
                    "emotion_tags": emotion,
                    "keywords": _extract_keywords_from_heatmap(heatmap),
                    "is_crisis": bool(msg.is_crisis),
                }
            )
    return records


def _score_from_message(message: Dict[str, Any]) -> Optional[float]:
    emotion = message.get("emotion_tags") or {}
    if not isinstance(emotion, dict) or not emotion:
        return None
    try:
        values = [float(emotion.get(key, 0)) for key in ("sadness", "fear", "anger", "joy")]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) and 0 <= value <= 1 for value in values):
        return None
    sadness, fear, anger, joy = values
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
        if ts > now or (now - ts).days >= days:
            continue
        score = _score_from_message(item)
        if score is None:
            continue
        bucket[ts.strftime("%Y-%m-%d")].append(score)

    series = []
    for i in range(days - 1, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        scores = bucket.get(d, [])
        value = round(sum(scores) / len(scores), 2) if scores else None
        series.append({"date": d, "score": value, "sample_count": len(scores)})
    return series


def _build_radar(messages: List[Dict[str, Any]]) -> Dict[str, int]:
    scored = [s for s in (_score_from_message(item) for item in messages) if s is not None]
    if not scored:
        return {key: None for key in ("emotion", "cognition", "behavior", "depression", "anxiety")}
    avg = sum(scored) / len(scored)
    return {
        "emotion": int(max(0, min(100, avg))),
        "cognition": None,
        "behavior": None,
        "depression": None,
        "anxiety": None,
    }


def _build_heatmap(messages: List[Dict[str, Any]], days: int = 7) -> List[Dict[str, Any]]:
    # Dialogue tags do not measure these clinical constructs separately.
    return []


def _llm_analyze(messages: List[Dict[str, Any]], *, deadline_ts: float | None = None) -> Dict[str, Any]:
    fallback = _build_structured_fallback("")
    fallback["_generation"] = {"source": "local_rules", "status": "fallback", "model_id": None}
    if not messages:
        fallback["_generation"]["status"] = "insufficient"
        return fallback
    if os.getenv("REPORT_AI_ENABLED", "false").lower() != "true":
        return fallback
    # External explanation uses aggregate facts only, never conversation text.
    facts = {"message_count": len(messages),
             "tagged_message_count": sum(_score_from_message(item) is not None for item in messages)}
    prompt = (
        "请根据以下统计事实输出支持性说明，严格JSON：summary、interventions（最多3条）、"
        "chart_insights（只解释有依据的图）。不得推断症状、疾病、风险概率、因果或虚构趋势。"
        "没有内容依据时明确资料不足，不生成评分。\n"
        f"统计事实: {json.dumps(facts, ensure_ascii=False)}"
    )
    retry_timeouts = [1.0, 1.8, 3.0]
    llm_urls = [LLM_URL] if LLM_URL and not is_local_fallback_url(LLM_URL) else []
    if not llm_urls:
        return fallback
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
                if not isinstance(payload, dict) or payload.get("source") in {"local_rules", "local_rule"}:
                    continue
                text = payload.get("text") or payload.get("result") or "{}"
                parsed = _safe_json_loads(text, {})
                if isinstance(parsed, dict) and isinstance(parsed.get("summary"), str) and parsed["summary"].strip():
                    advice = parsed.get("interventions")
                    insights = parsed.get("chart_insights")
                    return {
                        "summary": parsed["summary"].strip()[:1500],
                        "interventions": [s[:500] for s in advice[:3] if isinstance(s, str) and s.strip()]
                            if isinstance(advice, list) else fallback["interventions"],
                        "chart_insights": {key: value[:500] for key, value in insights.items()
                            if key in DEFAULT_CHART_EXPLANATIONS and isinstance(value, str) and value.strip()}
                            if isinstance(insights, dict) else {},
                        "_generation": {"source": "provider", "status": "completed",
                                        "model_id": payload.get("model_id") if isinstance(payload.get("model_id"), str) else None},
                    }
                last_error = f"{llm_url}:non_dict_payload"
            except Exception as exc:
                last_error = f"{llm_url}:{type(exc).__name__}"
                time.sleep(0.15)
    logger.warning("LLM analyze degraded to local rule fallback last_error=%s", last_error or "none")
    return fallback


def ensure_chart_explanations(report: Dict[str, Any]) -> Dict[str, Any]:
    output = dict(report) if isinstance(report, dict) else {}
    if not isinstance(output.get("generation"), dict):
        output["generation"] = {"source": "unknown", "status": "unverified", "model_id": None}
        output["data_status"] = "insufficient"
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
    s7 = [float(x["score"]) for x in last7 if x.get("score") is not None]
    s30 = [float(x["score"]) for x in last30 if x.get("score") is not None]
    dir7 = _series_direction(s7)
    return {
        "trend": (f"近7天有{len(s7)}个有效日期，近30天有{len(s30)}个有效日期。"
                  + (f"规则标签展示值近7天{dir7}；" if len(s7) >= 2 else "有效日期不足，暂不判断趋势；")
                  + "空缺日期未补零，该展示不能说明疾病风险或改善效果。"),
        **{key: value for key, value in DEFAULT_CHART_EXPLANATIONS.items() if key != "trend"},
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

    # Neither a generic LLM nor heuristic tags provide calibrated disease risk.
    depression = anxiety = suicide = None
    risk_level = "UNKNOWN"
    chart_insights = llm.get("chart_insights", {}) if isinstance(llm.get("chart_insights"), dict) else {}
    if not chart_insights or llm.get("_generation", {}).get("source") != "provider":
        chart_insights = _build_trend_advice_payload(
            last7=last7,
            last30=last30,
            risk_level=risk_level,
            depression=depression,
            anxiety=anxiety,
            suicide=suicide,
        )

    base_report = {
        "data_status": "available" if messages else "insufficient",
        "summary": llm.get("summary") or (f"本次汇总{len(messages)}条对话记录，仅提供统计事实与本地支持性说明。"
                                         if messages else "暂无可分析的对话记录。你可以先记录自己的近况，或直接选择人工求助。"),
        "generation": llm.get("_generation", {"source": "local_rules", "status": "fallback" if messages else "insufficient", "model_id": None}),
        "source": {
            "message_count": len(messages),
            "messages": messages,
            "method": "dialogue_tag_rules_v1",
            "score_meaning": "规则标签展示值，不是临床量表或疾病概率",
        },
        "scores": {
            "emotion": radar["emotion"],
            "cognition": radar["cognition"],
            "behavior": radar["behavior"],
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
        "generated_mode": ("provider" if llm.get("_generation", {}).get("source") == "provider"
                           else "local_rules" if include_llm else "quick"),
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
    row.risk_level = report.get("risk", {}).get("risk_level", "UNKNOWN")
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
        if state.get("status") in {"queued", "running"}:
            return state
        ANALYSIS_JOBS[user_id] = {
            "status": "queued",
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "error": "",
        }
    Thread(target=run_dialogue_analysis_for_user, args=(user_id,), daemon=True).start()
    return get_analysis_job_snapshot(user_id)
