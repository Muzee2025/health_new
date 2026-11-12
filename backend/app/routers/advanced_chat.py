import asyncio
import json
import logging
import re
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AIChatMessage,
    AIChatSession,
    ChatHistoryArchive,
    CrisisWarning,
    TestResult,
    User,
)
from app.routers.auth import get_current_user
from app.services.dialogue_analysis_service import enqueue_dialogue_analysis
from app.services.nlp_engine import NLPModelsService
from app.services.qwen_service import QwenAiService
from app.services.rag_service import embedding_function
from app.services.zhipu_emohaa_service import ZhipuEmohaaService
from app.upload_security import read_image_upload
from app.utils.websocket_manager import manager

router = APIRouter()
logger = logging.getLogger(__name__)
qwen_service = QwenAiService()
zhipu_chat_service = ZhipuEmohaaService()
nlp_engine = NLPModelsService()

CRISIS_KEYWORDS = (
    "跳楼", "轻生", "自杀", "不想活", "不想再活下去", "结束生命", "结束这一切", "一了百了", "一死了之",
    "想死", "去死", "割腕", "服毒", "上吊"
)
CRISIS_SUPPORT_MESSAGE = (
    "听到你正经历这样的感受，请先保护自己的安全。若面临即时危险，请尽快联系身边可信任的人或当地紧急服务。"
    "校内心理支持请通过学校公布的官方渠道联系；本系统不能确认值守时段、教师是否已查看或是否已采取行动。"
)

# --- 模型 ---
class SessionCreate(BaseModel):
    mode: str = "daily" # daily or counseling
    conversation_id: Optional[str] = None
    title: Optional[str] = None

class SessionRename(BaseModel):
    title: str

class ChatRequest(BaseModel):
    session_id: Optional[str] = None
    message: str
    modality: str = "text"
    anonymous: bool = False
    mode: str = "daily"
    deep_think: bool = False
    history: Optional[List[Dict[str, Any]]] = None

class ChatResponse(BaseModel):
    id: str
    reply: str
    is_crisis: bool
    emotion_tags: Dict[str, float]
    keywords: List[Dict[str, Any]]
    attention_heatmap: List[Dict[str, Any]]
    risk_radar: Dict[str, int]
    language: str
    confidence: float
    model_invoked: bool = False
    model_latency_ms: float = 0.0
    trace_id: Optional[str] = None
    warning_state: str = "not_applicable"


def _default_emotion_tags() -> Dict[str, float]:
    return {
        "joy": 0.0,
        "sadness": 0.0,
        "neutral": 1.0,
        "fear": 0.0,
        "anxiety": 0.0,
        "anger": 0.0,
    }


def _keyword_crisis_detect(text: str) -> Tuple[bool, str]:
    source = str(text or "").strip()
    if not source:
        return False, ""
    for kw in CRISIS_KEYWORDS:
        if kw in source:
            return True, kw
    return False, ""


def _is_effective_emotion_input(text: str) -> bool:
    clean = str(text or "").strip()
    if not clean:
        return False
    return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", clean))


def _normalize_history_for_model(raw_history: List[Dict[str, Any]] | None, deep_think: bool) -> List[Dict[str, str]]:
    if not deep_think or not raw_history:
        return []
    history: List[Dict[str, str]] = []
    for item in raw_history[-10:]:
        role = str(item.get("role", "user"))
        if role == "ai":
            role = "assistant"
        if role not in ("user", "assistant", "system"):
            role = "user"
        history.append({"role": role, "content": str(item.get("content", ""))[:500]})
    return history

def _build_db_history_for_model(hist_msgs: List[AIChatMessage], deep_think: bool) -> List[Dict[str, str]]:
    if not deep_think:
        return []
    context_msgs = hist_msgs[:-1] if hist_msgs else hist_msgs
    return [
        {"role": "assistant" if m.role == "ai" else m.role, "content": m.content}
        for m in context_msgs[-10:]
    ]

def _format_deep_think_reply(
    raw_text: str,
    trace_id: str,
) -> str:
    text = (raw_text or "").strip()
    if not text:
        raise RuntimeError(f"deep_think_empty_response trace_id={trace_id}")
    return text


def _safe_json_loads(value: Any, default: Any = None) -> Any:
    """Parse a JSON text column, or `default` when it is empty or unreadable.

    The columns this reads (emotion_tags, heatmap) are unvalidated TEXT: a row
    may hold NULL, an empty string, `[]`, or a value written by an older
    release, so a bad one must degrade to `default` instead of failing the
    whole history response.
    """
    if value is None:
        return default
    if not isinstance(value, (str, bytes, bytearray)):
        # Some drivers hand back an already-decoded value; keep it as it is.
        return value
    text = value.decode("utf-8", "replace") if isinstance(value, (bytes, bytearray)) else value
    if not text.strip():
        return default
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return default


def _safe_datetime_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)

async def _emotion_pipeline(message: str) -> Dict[str, Any]:
    clean = str(message or "").strip()
    logger.info("emotion_pipeline_enter chars=%s", len(clean))
    if not _is_effective_emotion_input(clean):
        emotions = _default_emotion_tags()
        logger.info("emotion_pipeline_invalid_input")
        keywords = []
        heatmap = []
        radar = nlp_engine.calc_5d_risk_radar(emotions)
        is_crisis, crisis_score = False, 0.0
        return {
            "emotion_tags": emotions,
            "keywords": keywords,
            "attention_heatmap": heatmap,
            "risk_radar": radar,
            "is_crisis": is_crisis,
            "crisis_score": crisis_score,
            "label": "neutral",
            "total_ms": 0.0,
            "timings_ms": {"collect": 0.0, "preprocess": 0.0, "feature": 0.0, "infer": 0.0, "postprocess": 0.0},
            "cache_hit": False,
            "sla_300ms": True,
        }

    # emohaa 情绪分析：失败时内部会自动重试1次并返回默认兜底，不会为 null
    emotions = await zhipu_chat_service.analyze_emotion_tags(clean, retry=1)
    keywords = nlp_engine.extract_keywords_bert(message, top_k=5)
    max_emotion = max(emotions.values()) if emotions else 0.0
    is_crisis, crisis_score = nlp_engine.detect_crisis_albert(message, max_emotion)
    heatmap = nlp_engine.generate_attention_heatmap(message, keywords)
    radar = nlp_engine.calc_5d_risk_radar(emotions)
    logger.info("emotion_pipeline_exit")
    return {
        "emotion_tags": emotions,
        "keywords": keywords,
        "attention_heatmap": heatmap,
        "risk_radar": radar,
        "is_crisis": is_crisis,
        "crisis_score": crisis_score,
        "label": max(emotions, key=emotions.get) if emotions else "unknown",
        "total_ms": 0.0,
        "timings_ms": {"collect": 0.0, "preprocess": 0.0, "feature": 0.0, "infer": 0.0, "postprocess": 0.0},
        "cache_hit": False,
        "sla_300ms": False,
    }


def _build_context_snapshot(history: List[Dict[str, str]]) -> Dict[str, Any]:
    trimmed = history[-8:] if history else []
    return {
        "turns": len(trimmed),
        "messages": trimmed,
    }


def _extract_topic_tags(text: str, top_k: int = 4) -> List[str]:
    source = (text or "").strip()
    if not source:
        return []
    try:
        kws = nlp_engine.extract_keywords_bert(source, top_k=top_k)
    except Exception:
        kws = []
    tags = []
    for item in kws or []:
        if isinstance(item, dict):
            t = str(item.get("word", "")).strip()
        else:
            t = str(item).strip()
        if t and t not in tags:
            tags.append(t[:16])
    if not tags:
        tags = _tokenize_for_match(source)[:top_k]
    return tags[:top_k]


def _calc_sentiment_score(emotions: Dict[str, float]) -> int:
    joy = float(emotions.get("joy", 0))
    neg = (float(emotions.get("sadness", 0)) + float(emotions.get("fear", 0)) + float(emotions.get("anger", 0))) / 3
    score = (joy * 0.65 + (1 - neg) * 0.35) * 100
    return max(0, min(100, int(round(score))))


def _archive_dialogue(
    db: Session,
    user_id: int,
    session_id: str,
    user_msg: AIChatMessage,
    ai_msg: AIChatMessage,
    history: List[Dict[str, str]],
    emotions: Dict[str, float],
):
    tags = _extract_topic_tags(f"{user_msg.content}\n{ai_msg.content}")
    semantic_summary = (user_msg.content or "").strip()[:80]
    if len(user_msg.content or "") > 80:
        semantic_summary += "..."
    row = ChatHistoryArchive(
        user_id=user_id,
        session_id=session_id,
        user_message_id=user_msg.id,
        ai_message_id=ai_msg.id,
        user_input=user_msg.content,
        ai_reply=ai_msg.content,
        context_json=json.dumps(_build_context_snapshot(history), ensure_ascii=False),
        topic_tags=",".join(tags),
        sentiment_score=_calc_sentiment_score(emotions),
        semantic_summary=semantic_summary or None,
    )
    db.add(row)


def _load_historical_archives(
    db: Session,
    user_id: int,
    current_session_id: Optional[str],
    days: int = 180,
    limit: int = 200,
) -> List[ChatHistoryArchive]:
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(ChatHistoryArchive).filter(
        ChatHistoryArchive.user_id == user_id,
        ChatHistoryArchive.created_at >= since,
    )
    if current_session_id:
        query = query.filter(ChatHistoryArchive.session_id != current_session_id)
    return query.order_by(ChatHistoryArchive.created_at.desc()).limit(limit).all()


def _build_historical_insight(
    archives: List[ChatHistoryArchive],
    current_question: str,
) -> Dict[str, Any]:
    if not archives:
        return {
            "memories": [],
            "topic_cluster": "暂无可用历史主题",
            "sentiment_desc": "暂无足够历史情绪数据",
        }

    q_tokens = set(_tokenize_for_match(current_question))
    scored: List[Tuple[float, ChatHistoryArchive]] = []
    for item in archives:
        txt = f"{item.user_input or ''} {item.ai_reply or ''}"
        overlap = len(q_tokens & set(_tokenize_for_match(txt)))
        freshness = 0.3 if item.created_at and (datetime.utcnow() - item.created_at.replace(tzinfo=None)).days <= 14 else 0.0
        scored.append((overlap + freshness, item))
    scored.sort(key=lambda x: x[0], reverse=True)
    memories = [f"用户: {x[1].user_input[:60]}" for x in scored[:3] if x[1].user_input]

    topic_counter: Counter = Counter()
    for item in archives:
        tags = [t.strip() for t in (item.topic_tags or "").split(",") if t.strip()]
        topic_counter.update(tags)
    top_topics = [x[0] for x in topic_counter.most_common(3)]
    topic_cluster = "、".join(top_topics) if top_topics else "暂无明显聚类主题"

    scores = [int(x.sentiment_score) for x in archives if x.sentiment_score is not None]
    if scores:
        recent_scores = scores[: min(7, len(scores))]
        prev_scores = scores[min(7, len(scores)): min(14, len(scores))]
        recent_avg = sum(recent_scores) / len(recent_scores)
        prev_avg = sum(prev_scores) / len(prev_scores) if prev_scores else recent_avg
        delta = recent_avg - prev_avg
        if abs(delta) < 1.2:
            direction = "整体平稳"
        elif delta > 0:
            direction = "近期情绪韧性略有回升"
        else:
            direction = "近期情绪承压略有增加"
        sentiment_desc = f"历史情绪指数均值 {recent_avg:.1f}（对比前周期 {prev_avg:.1f}），{direction}。"
    else:
        sentiment_desc = "暂无足够历史情绪数据"

    return {
        "memories": memories,
        "topic_cluster": topic_cluster,
        "sentiment_desc": sentiment_desc,
    }


@router.get("/history/query")
async def query_chat_history(
    start_date: Optional[str] = Query(default=None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(default=None, description="结束日期 YYYY-MM-DD"),
    topic_tag: Optional[str] = Query(default=None, description="主题标签模糊匹配"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(ChatHistoryArchive).filter(ChatHistoryArchive.user_id == current_user.id)
    if start_date:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        query = query.filter(ChatHistoryArchive.created_at >= start_dt)
    if end_date:
        end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1) - timedelta(microseconds=1)
        query = query.filter(ChatHistoryArchive.created_at <= end_dt)
    if topic_tag:
        query = query.filter(ChatHistoryArchive.topic_tags.like(f"%{topic_tag.strip()}%"))
    rows = query.order_by(ChatHistoryArchive.created_at.desc()).limit(limit).all()
    return {
        "status": "success",
        "data": [
            {
                "id": r.id,
                "session_id": r.session_id,
                "user_input": r.user_input,
                "ai_reply": r.ai_reply,
                "topic_tags": (r.topic_tags or "").split(",") if r.topic_tags else [],
                "sentiment_score": r.sentiment_score,
                "semantic_summary": r.semantic_summary,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


def _sse_event(event: str, data: Any) -> str:
    payload = data if isinstance(data, str) else json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {payload}\n\n"


def _tokenize_for_match(text: str) -> List[str]:
    raw = (text or "").lower()
    chunks = re.findall(r"[\u4e00-\u9fff]{1,4}|[a-z0-9]{2,}", raw)
    return [c for c in chunks if len(c.strip()) >= 2]


def _extract_target_date(user_message: str) -> Optional[datetime]:
    text = (user_message or "").strip()
    if not text:
        return None
    match = re.search(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})", text)
    if not match:
        return None
    year, month, day = map(int, match.groups())
    try:
        return datetime(year, month, day)
    except ValueError:
        return None


def _day_range(target_day: datetime) -> Tuple[datetime, datetime]:
    day_start = datetime(target_day.year, target_day.month, target_day.day, 0, 0, 0)
    day_end = day_start + timedelta(days=1) - timedelta(microseconds=1)
    return day_start, day_end


def _format_dt(ts: Optional[datetime]) -> str:
    if not ts:
        return "未知时间"
    return ts.strftime("%Y-%m-%d %H:%M")


def _build_session_message_highlights(
    messages: List[AIChatMessage],
    query_text: str,
    max_items: int = 4,
) -> List[str]:
    keywords = set(_tokenize_for_match(query_text))
    if not messages:
        return []

    selected: List[str] = []
    for row in reversed(messages):
        content = (row.content or "").strip()
        if not content:
            continue
        role_prefix = "用户" if row.role == "user" else "助手"
        snippet = f"{role_prefix}: {content[:100]}"
        if keywords:
            tokens = set(_tokenize_for_match(content))
            if tokens & keywords:
                selected.append(snippet)
        if len(selected) >= max_items:
            break

    if not selected:
        for row in reversed(messages[-max_items:]):
            content = (row.content or "").strip()
            if not content:
                continue
            role_prefix = "用户" if row.role == "user" else "助手"
            selected.append(f"{role_prefix}: {content[:100]}")

    return list(reversed(selected[:max_items]))


def _build_historical_session_context(
    db: Session,
    user_id: int,
    current_session_id: Optional[str],
    user_message: str,
    max_sessions: int = 8,
    max_messages_per_session: int = 20,
) -> Dict[str, Any]:
    target_day = _extract_target_date(user_message)
    query = db.query(AIChatSession).filter(AIChatSession.user_id == user_id)
    if current_session_id:
        query = query.filter(AIChatSession.id != current_session_id)
    if target_day:
        day_start, day_end = _day_range(target_day)
        query = query.filter(
            AIChatSession.updated_at >= day_start,
            AIChatSession.updated_at <= day_end,
        )

    sessions = query.order_by(AIChatSession.updated_at.desc()).limit(max_sessions).all()
    if not sessions:
        return {
            "target_day": target_day.strftime("%Y-%m-%d") if target_day else None,
            "timeline_lines": [],
            "history_context": "未找到可用于深度思考的历史会话。",
        }

    timeline_lines: List[str] = []
    context_blocks: List[str] = []
    for session in sessions:
        msgs = (
            db.query(AIChatMessage)
            .filter(
                AIChatMessage.session_id == session.id,
                AIChatMessage.role.in_(["user", "ai"]),
            )
            .order_by(AIChatMessage.created_at.asc())
            .limit(max_messages_per_session)
            .all()
        )
        highlights = _build_session_message_highlights(msgs, user_message, max_items=4)
        timeline_lines.append(
            f"{_format_dt(session.updated_at)} | 会话《{(session.title or '新对话')[:30]}》 | 模式={session.mode} | session_id={session.id}"
        )
        if highlights:
            block = [
                f"[{_format_dt(session.updated_at)}][{session.mode}][{(session.title or '新对话')[:30]}]",
                *highlights,
            ]
            context_blocks.append("\n".join(block))

    history_context = "\n\n".join(context_blocks) if context_blocks else "历史会话存在，但暂无可提炼的消息片段。"
    return {
        "target_day": target_day.strftime("%Y-%m-%d") if target_day else None,
        "timeline_lines": timeline_lines,
        "history_context": history_context,
    }


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _embed_for_recall(user_message: str, candidates: List[str]) -> Tuple[List[float], List[List[float]]]:
    query_vec = [float(x) for x in embedding_function([user_message])[0]]
    cand_vecs = [[float(v) for v in vec] for vec in embedding_function(candidates)]
    return query_vec, cand_vecs


async def _vector_retrieve_memories(
    db: Session,
    user_id: int,
    user_message: str,
    session_id: Optional[str],
    trace_id: str,
    top_k: int = 3,
) -> Dict[str, Any]:
    timer_all = time.perf_counter()
    query_started = time.perf_counter()
    rows = (
        db.query(AIChatMessage.content, AIChatMessage.created_at, AIChatMessage.session_id)
        .join(AIChatSession, AIChatMessage.session_id == AIChatSession.id)
        .filter(
            AIChatSession.user_id == user_id,
            AIChatMessage.role.in_(["user", "ai"]),
            AIChatSession.id != (session_id or "__none__"),
        )
        .order_by(AIChatMessage.created_at.desc())
        .limit(160)
        .all()
    )
    query_ms = round((time.perf_counter() - query_started) * 1000, 2)
    candidate_rows = [r for r in rows if (r.content or "").strip()]
    if len(candidate_rows) > 64:
        candidate_rows = candidate_rows[:64]
    candidates = [(r.content or "").strip() for r in candidate_rows]
    if not candidates:
        return {
            "snippets": [],
            "timings_ms": {"query": query_ms, "embedding": 0.0, "recall": 0.0, "total": round((time.perf_counter() - timer_all) * 1000, 2)},
            "topk": [],
        }

    embedding_started = time.perf_counter()
    query_vec, cand_vecs = await asyncio.to_thread(_embed_for_recall, user_message, candidates)
    embedding_ms = round((time.perf_counter() - embedding_started) * 1000, 2)

    recall_started = time.perf_counter()
    scored: List[Tuple[float, str, str]] = []
    for idx, content in enumerate(candidates):
        score = _cosine_similarity(query_vec, cand_vecs[idx])
        scored.append((score, content[:160], str(candidate_rows[idx].session_id)))
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]
    recall_ms = round((time.perf_counter() - recall_started) * 1000, 2)
    total_ms = round((time.perf_counter() - timer_all) * 1000, 2)
    topk = [{"score": round(s, 6), "session_id": sid, "snippet": text} for s, text, sid in top]
    logger.info("vector_recall trace_id=%s count=%s latency_ms=%s", trace_id, len(topk), total_ms)
    return {
        "snippets": [x["snippet"] for x in topk],
        "timings_ms": {"query": query_ms, "embedding": embedding_ms, "recall": recall_ms, "total": total_ms},
        "topk": topk,
    }


async def _vector_retrieve_memories_with_timeout(
    db: Session,
    user_id: int,
    user_message: str,
    session_id: Optional[str],
    trace_id: str,
    top_k: int = 3,
    timeout_seconds: float = 20.0,
    retries: int = 1,
) -> Dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            return await asyncio.wait_for(
                _vector_retrieve_memories(
                    db=db,
                    user_id=user_id,
                    user_message=user_message,
                    session_id=session_id,
                    trace_id=trace_id,
                    top_k=top_k,
                ),
                timeout=timeout_seconds,
            )
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "vector_recall_attempt_failed trace_id=%s attempt=%s/%s error=%s",
                trace_id,
                attempt,
                retries + 1,
                type(exc).__name__,
            )
            if attempt <= retries:
                await asyncio.sleep(0.6 * attempt)
                continue
            break
    raise RuntimeError(f"vector_recall_failed trace_id={trace_id} cause={last_exc}")


async def _invoke_deep_think_with_retry(
    *,
    user_id: str,
    prompt: str,
    chat_context: str,
    mode: str,
    trace_id: str,
    timeout_seconds: float = 45.0,
    retries: int = 1,
) -> Tuple[str, int]:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 2):
        try:
            reply = await asyncio.wait_for(
                zhipu_chat_service.deep_think_with_student(
                    user_id=user_id,
                    prompt=prompt,
                    chat_context=chat_context,
                    mode=mode,
                    trace_id=trace_id,
                ),
                timeout=timeout_seconds,
            )
            return reply, attempt
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "deep_think_attempt_failed trace_id=%s attempt=%s/%s timeout=%ss error=%s",
                trace_id,
                attempt,
                retries + 1,
                timeout_seconds,
                type(exc).__name__,
            )
            if attempt <= retries:
                await asyncio.sleep(0.8 * attempt)
                continue
            break
    raise RuntimeError(f"deep_think_failed trace_id={trace_id} cause={last_exc}")


async def _get_cached_mood_trend(db: Session, user_id: int) -> Dict[str, Any]:
    tests = (
        db.query(TestResult.standard_score, TestResult.created_at)
        .filter(
            TestResult.user_id == user_id,
            TestResult.test_type.in_(["SDS", "SAS"]),
        )
        .order_by(TestResult.created_at.desc())
        .limit(14)
        .all()
    )
    points: List[int] = []
    for t in reversed(tests):
        if not t.standard_score:
            continue
        idx = int(max(0, min(100, 100 - (t.standard_score - 20))))
        points.append(idx)
    if not points:
        return {"recent_avg": 50, "prev_avg": 50, "delta": 0, "points": []}
    recent = points[-7:] if len(points) >= 7 else points
    prev = points[-14:-7] if len(points) >= 14 else points[: max(1, len(points) // 2)]
    recent_avg = sum(recent) / len(recent)
    prev_avg = sum(prev) / len(prev) if prev else recent_avg
    return {
        "recent_avg": round(recent_avg, 1),
        "prev_avg": round(prev_avg, 1),
        "delta": round(recent_avg - prev_avg, 1),
        "points": points,
    }


def _generate_trend_description(trend_data: Dict[str, Any]) -> str:
    delta = float(trend_data.get("delta", 0))
    recent_avg = trend_data.get("recent_avg", 0)
    prev_avg = trend_data.get("prev_avg", 0)
    if abs(delta) < 1.2:
        direction = "整体平稳"
    elif delta > 0:
        direction = "较上周有所回升"
    else:
        direction = "较上周有所下滑"
    return f"近7天情绪指数均值 {recent_avg}，上周约 {prev_avg}，当前趋势{direction}（变化 {delta:+.1f}）。"

# --- Session API ---
@router.get("/sessions")
async def get_chat_sessions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    try:
        sessions = (
            db.query(AIChatSession)
            .filter(AIChatSession.user_id == current_user.id)
            .order_by(AIChatSession.updated_at.desc())
            .all()
        )
        data = []
        for s in sessions:
            data.append(
                {
                    "id": str(s.id),
                    "title": (s.title or "新对话")[:100],
                    "mode": s.mode or "daily",
                    "updated_at": _safe_datetime_str(s.updated_at),
                }
            )
        return {"status": "success", "data": data}
    except Exception as exc:
        logger.error("get_chat_sessions_failed user_id=%s error=%s", getattr(current_user, "id", None), type(exc).__name__)
        raise HTTPException(status_code=500, detail="加载会话失败") from exc

@router.post("/sessions")
async def create_chat_session(
    req: SessionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session_id = req.conversation_id or str(uuid.uuid4())
    exist = db.query(AIChatSession).filter(
        AIChatSession.id == session_id,
        AIChatSession.user_id == current_user.id
    ).first()
    if exist:
        raise HTTPException(status_code=400, detail="Session id already exists")

    new_session = AIChatSession(
        id=session_id,
        user_id=current_user.id,
        mode=req.mode,
        title=(req.title or "新对话")[:100]
    )
    db.add(new_session)

    # 引导式聊天：AI 优先发起话题
    initial_prompt = "你好呀！我是心域智链。今天过得怎么样？有没有什么特别的事情想和我分享，或者只是想随便聊聊？" if req.mode == "daily" else "你好，我是你的专属AI心理助手。最近在学习、生活或是人际关系上，有没有遇到什么让你感到困扰或有压力的事情？我们可以一起探讨一下。"

    initial_msg = AIChatMessage(
        session_id=new_session.id,
        role="ai",
        content=initial_prompt
    )
    db.add(initial_msg)
    try:
        db.commit()
    except IntegrityError:
        # The lookup above and this insert are not one step: two requests that
        # carried the same conversation_id both saw nothing and both inserted.
        # The primary key settled it, so answer the duplicate the way the
        # lookup would have.
        db.rollback()
        raise HTTPException(status_code=400, detail="Session id already exists") from None
    return {"status": "success", "session_id": new_session.id, "initial_message": initial_prompt}

@router.patch("/sessions/{session_id}")
async def rename_chat_session(
    session_id: str,
    req: SessionRename,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(AIChatSession).filter(
        AIChatSession.id == session_id,
        AIChatSession.user_id == current_user.id
    ).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    title = (req.title or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Title cannot be empty")
    session.title = title[:100]
    session.updated_at = func.now()
    db.commit()
    return {"status": "success"}

@router.delete("/sessions/{session_id}")
async def delete_chat_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    max_retries = 2
    for attempt in range(max_retries + 1):
        try:
            session = db.query(AIChatSession).filter(
                AIChatSession.id == session_id,
                AIChatSession.user_id == current_user.id
            ).first()
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")

            deleted_messages = db.query(AIChatMessage).filter(
                AIChatMessage.session_id == session_id
            ).delete(synchronize_session=False)
            deleted_archives = db.query(ChatHistoryArchive).filter(
                ChatHistoryArchive.session_id == session_id
            ).delete(synchronize_session=False)
            db.delete(session)
            db.commit()

            remaining_session = db.query(AIChatSession).filter(
                AIChatSession.id == session_id,
                AIChatSession.user_id == current_user.id
            ).first()
            remaining_messages = db.query(AIChatMessage).filter(
                AIChatMessage.session_id == session_id
            ).count()
            remaining_archives = db.query(ChatHistoryArchive).filter(
                ChatHistoryArchive.session_id == session_id
            ).count()
            if remaining_session or remaining_messages > 0 or remaining_archives > 0:
                raise RuntimeError("delete_integrity_check_failed")

            return {
                "status": "success",
                "data": {
                    "session_id": session_id,
                    "deleted_messages": int(deleted_messages or 0),
                    "deleted_archives": int(deleted_archives or 0),
                    "attempt": attempt + 1,
                },
            }
        except HTTPException:
            db.rollback()
            raise
        except OperationalError as exc:
            db.rollback()
            logger.warning(
                "delete_session_retry user_id=%s session_id=%s attempt=%s error=%s",
                current_user.id,
                session_id,
                attempt + 1,
                type(exc).__name__,
            )
            if attempt < max_retries:
                await asyncio.sleep(0.2 * (attempt + 1))
                continue
            raise HTTPException(status_code=503, detail="服务端删除暂时失败，请稍后重试") from exc
        except SQLAlchemyError as exc:
            db.rollback()
            logger.error(
                "delete_session_db_error user_id=%s session_id=%s error=%s",
                current_user.id,
                session_id,
                type(exc).__name__,
            )
            raise HTTPException(status_code=500, detail="服务端删除失败（数据库异常）") from exc
        except Exception as exc:
            db.rollback()
            logger.error(
                "delete_session_integrity_error user_id=%s session_id=%s error=%s",
                current_user.id,
                session_id,
                type(exc).__name__,
            )
            raise HTTPException(status_code=500, detail="服务端删除失败（一致性校验未通过）") from exc

@router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    target_date: Optional[str] = Query(default=None, description="按自然日筛选，格式 YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    session = db.query(AIChatSession).filter(AIChatSession.id == session_id, AIChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    query = db.query(AIChatMessage).filter(AIChatMessage.session_id == session_id)
    if target_date:
        try:
            day = datetime.strptime(target_date, "%Y-%m-%d")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="target_date must be YYYY-MM-DD") from exc
        day_start, day_end = _day_range(day)
        query = query.filter(
            AIChatMessage.created_at >= day_start,
            AIChatMessage.created_at <= day_end,
        )
    messages = query.order_by(AIChatMessage.created_at.asc()).all()
    res = []
    for m in messages:
        emotion_tags = _safe_json_loads(m.emotion_tags, default=None)
        heatmap = _safe_json_loads(m.heatmap, default=None)
        if m.emotion_tags and emotion_tags is None:
            logger.warning("invalid_emotion_tags_json session_id=%s msg_id=%s", session_id, m.id)
        if m.heatmap and heatmap is None:
            logger.warning("invalid_heatmap_json session_id=%s msg_id=%s", session_id, m.id)
        res.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "emotion_tags": emotion_tags,
            "is_crisis": m.is_crisis,
            "heatmap": heatmap,
            "created_at": m.created_at
        })
    return {"status": "success", "data": res}

@router.post("/chat", response_model=ChatResponse)
async def ai_chat_interaction(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 语言识别模拟
    language = "中文"
    confidence = 0.98 if any("\u4e00" <= char <= "\u9fff" for char in req.message) else 0.85
    trace_id = str(uuid.uuid4())
    model_invoked = False
    model_latency_ms = 0.0

    try:
        analysis = await _emotion_pipeline(req.message)
    except Exception:
        logger.error("emotion_analyze_failed user_id=%s anonymous=%s", current_user.id, req.anonymous)
        analysis = {
            "emotion_tags": _default_emotion_tags(),
            "keywords": [],
            "attention_heatmap": [],
            "risk_radar": nlp_engine.calc_5d_risk_radar(_default_emotion_tags()),
            "is_crisis": False,
            "crisis_score": 0.0,
            "label": "neutral",
            "total_ms": 0.0,
            "timings_ms": {"collect": 0.0, "preprocess": 0.0, "feature": 0.0, "infer": 0.0, "postprocess": 0.0},
            "cache_hit": False,
            "sla_300ms": False,
        }

    keywords = analysis.get("keywords", [])
    emotions = analysis.get("emotion_tags", {})
    is_crisis = bool(analysis.get("is_crisis", False))
    kw_hit, kw_trigger = _keyword_crisis_detect(req.message)
    if kw_hit:
        is_crisis = True
    heatmap = analysis.get("attention_heatmap", [])
    radar = analysis.get("risk_radar", {})

    if req.anonymous:
        history = _normalize_history_for_model(req.history or [], req.deep_think)
    else:
        if not req.session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        session = db.query(AIChatSession).filter(AIChatSession.id == req.session_id, AIChatSession.user_id == current_user.id).first()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

        # 保存用户消息
        user_msg = AIChatMessage(
            session_id=session.id,
            role="user",
            content=req.message,
            emotion_tags=json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False),
        )
        db.add(user_msg)

        hist_msgs = db.query(AIChatMessage).filter(
            AIChatMessage.session_id == session.id
        ).order_by(AIChatMessage.created_at.asc()).all()
        history = _build_db_history_for_model(hist_msgs, req.deep_think)

        # 自动更新会话标题
        if session.title == "新对话":
            session.title = req.message[:15] + "..."

        # 更新用户消息的热图
        user_msg.heatmap = json.dumps(heatmap, ensure_ascii=False)

    warning_state = "not_applicable"
    if is_crisis:
        warning_state = "anonymous" if req.anonymous else "not_created"
        reply = CRISIS_SUPPORT_MESSAGE
        # 保存预警并广播
        if not req.anonymous and 'session' in locals() and session:
            try:
                # 记录用户消息
                ai_msg = AIChatMessage(
                    session_id=session.id,
                    role="ai",
                    content=reply,
                    is_crisis=True,
                    emotion_tags=json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False)
                )
                db.add(ai_msg)
                db.flush()

                trigger_kw = kw_trigger or (keywords[0]["word"] if keywords else "未知关键字")
                risk_level = "high"
                warning = CrisisWarning(
                    student_id=current_user.id,
                    chat_message_id=user_msg.id,
                    trigger_keyword=trigger_kw,
                    risk_level=risk_level,
                    status="pending"
                )
                db.add(warning)
                db.commit()
                warning_state = "created"
                db.refresh(warning)

                # 广播给教师端（实时链路）
                asyncio.create_task(manager.broadcast_to_teachers({
                    "type": "new_warning",
                    "data": {
                        "id": warning.id,
                        "student_id": current_user.id,
                        "studentId": str(current_user.student_id or current_user.id),
                        "session_id": session.id,
                        "student_name": current_user.name or current_user.username,
                        "studentName": current_user.name or current_user.username,
                        "class_name": current_user.class_name or "未知班级",
                        "className": current_user.class_name or "未知班级",
                        "trigger_keyword": trigger_kw,
                        "description": req.message,
                        "risk_level": risk_level,
                        "riskLevel": risk_level,
                        "trigger_msg": req.message,
                        "created_at": warning.created_at.strftime("%Y-%m-%d %H:%M:%S") if warning.created_at else None,
                        "createdAt": warning.created_at.strftime("%Y-%m-%d %H:%M:%S") if warning.created_at else None,
                        "status": "pending",
                    }
                }, db=db, student_id=current_user.id))
            except Exception as e:
                db.rollback()
                logger.error("Warning persistence unavailable (%s)", type(e).__name__)
    else:
        start_ts = time.perf_counter()
        if req.deep_think:
            vector_data = await _vector_retrieve_memories_with_timeout(
                db=db,
                user_id=current_user.id,
                user_message=req.message,
                session_id=req.session_id,
                trace_id=trace_id,
                top_k=3,
                timeout_seconds=20.0,
                retries=1,
            )
            archives = _load_historical_archives(
                db=db,
                user_id=current_user.id,
                current_session_id=req.session_id,
                days=365,
                limit=240,
            )
            insight = _build_historical_insight(archives, req.message)
            session_context = _build_historical_session_context(
                db=db,
                user_id=current_user.id,
                current_session_id=req.session_id,
                user_message=req.message,
                max_sessions=8,
                max_messages_per_session=24,
            )
            timeline_hint = (
                f"按会话更新时间（updated_at）匹配到 {session_context['target_day']} 当日记录：\n"
                if session_context.get("target_day")
                else "最近历史会话时间线（按 updated_at 倒序）：\n"
            )
            chat_context = (
                f"trace_id: {trace_id}\n"
                f"历史主题聚类: {insight['topic_cluster']}\n"
                f"历史情绪分析: {insight['sentiment_desc']}\n"
                f"历史相关回忆: {insight['memories']}\n\n"
                f"向量召回TopK: {vector_data.get('topk', [])}\n"
                f"{timeline_hint}{chr(10).join(session_context.get('timeline_lines', [])[:8])}\n\n"
                f"基于 ai_chat_sessions + ai_chat_messages 提取的历史对话片段:\n"
                f"{session_context.get('history_context', '暂无')}\n\n"
                "请优先依据以上历史内容回答“什么时候发生了哪些对话”；若未命中具体日期，请明确说明并给出最接近的时间线。"
            )
            try:
                raw_reply, attempt_used = await _invoke_deep_think_with_retry(
                    user_id=f"anon-{current_user.id}" if req.anonymous else str(current_user.id),
                    prompt=req.message,
                    chat_context=chat_context,
                    mode=req.mode if req.anonymous else session.mode,
                    trace_id=trace_id,
                    timeout_seconds=45.0,
                    retries=1,
                )
                model_invoked = True
                model_latency_ms = round((time.perf_counter() - start_ts) * 1000, 2)
                logger.info("deep_think_success trace_id=%s attempts=%s latency_ms=%s", trace_id, attempt_used, model_latency_ms)
                reply = _format_deep_think_reply(raw_reply, trace_id=trace_id)
            except Exception as exc:
                logger.error("deep_think_invoke_failed trace_id=%s user_id=%s error=%s", trace_id, current_user.id, type(exc).__name__)
                raise HTTPException(
                    status_code=500,
                    detail={"error": "deep_think_invoke_failed", "trace_id": trace_id, "cause": "model_unavailable"},
                ) from exc
        else:
            reply = await zhipu_chat_service.chat_with_student(
                user_id=f"anon-{current_user.id}" if req.anonymous else str(current_user.id),
                message=req.message,
                history=[],
                mode=req.mode if req.anonymous else session.mode
            )

    if not req.anonymous and not is_crisis:
        ai_msg = AIChatMessage(
            session_id=session.id,
            role="ai",
            content=reply,
            is_crisis=is_crisis,
            emotion_tags=json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False)
        )
        db.add(ai_msg)
        db.flush()
        _archive_dialogue(
            db=db,
            user_id=current_user.id,
            session_id=session.id,
            user_msg=user_msg,
            ai_msg=ai_msg,
            history=history,
            emotions=emotions,
        )
        session.updated_at = func.now()
        db.commit()
        background_tasks.add_task(enqueue_dialogue_analysis, current_user.id)

    return ChatResponse(
        id=str(uuid.uuid4()),
        reply=reply,
        is_crisis=is_crisis,
        emotion_tags=emotions,
        keywords=keywords,
        attention_heatmap=heatmap,
        risk_radar=radar,
        language=language,
        confidence=confidence,
        model_invoked=model_invoked,
        model_latency_ms=model_latency_ms,
        trace_id=trace_id if req.deep_think else None,
        warning_state=warning_state,
    )


@router.post("/chat/stream")
async def ai_chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    async def event_generator():
        language = "中文"
        confidence = 0.98 if any("\u4e00" <= char <= "\u9fff" for char in req.message) else 0.85
        trace_id = str(uuid.uuid4())
        model_invoked = False
        model_latency_ms = 0.0
        session = None
        user_msg = None
        history: List[Dict[str, str]] = []
        heatmap: List[Dict[str, Any]] = []
        radar: Dict[str, int] = {}
        emotions: Dict[str, float] = {}
        is_crisis = False

        try:
            try:
                analysis = await _emotion_pipeline(req.message)
            except Exception:
                logger.error("stream_emotion_analyze_failed user_id=%s", current_user.id)
                analysis = {
                    "emotion_tags": _default_emotion_tags(),
                    "keywords": [],
                    "attention_heatmap": [],
                    "risk_radar": nlp_engine.calc_5d_risk_radar(_default_emotion_tags()),
                    "is_crisis": False,
                    "crisis_score": 0.0,
                    "label": "neutral",
                    "total_ms": 0.0,
                    "timings_ms": {"collect": 0.0, "preprocess": 0.0, "feature": 0.0, "infer": 0.0, "postprocess": 0.0},
                    "cache_hit": False,
                    "sla_300ms": False,
                }
            heatmap = analysis.get("attention_heatmap", [])
            radar = analysis.get("risk_radar", {})
            emotions = analysis.get("emotion_tags", {})
            is_crisis = bool(analysis.get("is_crisis", False))
            kw_hit, kw_trigger = _keyword_crisis_detect(req.message)
            if kw_hit:
                is_crisis = True

            if req.anonymous:
                history = _normalize_history_for_model(req.history or [], req.deep_think)
            else:
                if not req.session_id:
                    yield _sse_event("error", {"text": "session_id is required"})
                    yield _sse_event("done", {"ok": False})
                    return
                session = db.query(AIChatSession).filter(
                    AIChatSession.id == req.session_id,
                    AIChatSession.user_id == current_user.id
                ).first()
                if not session:
                    yield _sse_event("error", {"text": "Session not found"})
                    yield _sse_event("done", {"ok": False})
                    return
                user_msg = AIChatMessage(session_id=session.id, role="user", content=req.message)
                db.add(user_msg)
                hist_msgs = db.query(AIChatMessage).filter(
                    AIChatMessage.session_id == session.id
                ).order_by(AIChatMessage.created_at.asc()).all()
                history = _build_db_history_for_model(hist_msgs, req.deep_think)
                if session.title == "新对话":
                    session.title = req.message[:15] + "..."
                user_msg.heatmap = json.dumps(heatmap, ensure_ascii=False)
                user_msg.emotion_tags = json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False)

            if is_crisis:
                crisis_reply = CRISIS_SUPPORT_MESSAGE
                yield _sse_event("phase", "response")
                for i in range(0, len(crisis_reply), 16):
                    yield _sse_event("message_chunk", {"text": crisis_reply[i:i+16]})
                    await asyncio.sleep(0.02)
                final_payload = {
                    "id": str(uuid.uuid4()),
                    "reply": crisis_reply,
                    "is_crisis": True,
                    "warning_state": "anonymous" if req.anonymous else "not_created",
                    "emotion_tags": emotions,
                    "keywords": analysis.get("keywords", []),
                    "attention_heatmap": heatmap,
                    "risk_radar": radar,
                    "language": language,
                    "confidence": confidence,
                }
                if not req.anonymous and session is not None:
                    try:
                        ai_msg = AIChatMessage(
                            session_id=session.id,
                            role="ai",
                            content=crisis_reply,
                            is_crisis=True,
                            emotion_tags=json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False),
                        )
                        db.add(ai_msg)
                        db.flush()

                        trigger_kw = kw_trigger or (analysis.get("keywords")[0]["word"] if analysis.get("keywords") else "未知关键字")
                        risk_level = "high"
                        warning = CrisisWarning(
                            student_id=current_user.id,
                            chat_message_id=user_msg.id,
                            trigger_keyword=trigger_kw,
                            risk_level=risk_level,
                            status="pending"
                        )
                        db.add(warning)
                        # Flush, not commit: the warning, the archived dialogue, and
                        # the session touch are one unit. Committing here left a
                        # warning behind whenever the archive below failed.
                        db.flush()
                        db.refresh(warning)

                        asyncio.create_task(manager.broadcast_to_teachers({
                            "type": "new_warning",
                            "data": {
                                "id": warning.id,
                                "student_id": current_user.id,
                                "studentId": str(current_user.student_id or current_user.id),
                                "session_id": session.id,
                                "student_name": current_user.name or current_user.username,
                                "studentName": current_user.name or current_user.username,
                                "class_name": current_user.class_name or "未知班级",
                                "className": current_user.class_name or "未知班级",
                                "trigger_keyword": trigger_kw,
                                "description": req.message,
                                "risk_level": risk_level,
                                "riskLevel": risk_level,
                                "trigger_msg": req.message,
                                "created_at": warning.created_at.strftime("%Y-%m-%d %H:%M:%S") if warning.created_at else None,
                                "createdAt": warning.created_at.strftime("%Y-%m-%d %H:%M:%S") if warning.created_at else None,
                                "status": "pending",
                            }
                        }, db=db, student_id=current_user.id))

                        if user_msg is not None:
                            _archive_dialogue(
                                db=db,
                                user_id=current_user.id,
                                session_id=session.id,
                                user_msg=user_msg,
                                ai_msg=ai_msg,
                                history=history,
                                emotions=emotions,
                            )
                        session.updated_at = func.now()
                        db.commit()
                        final_payload["warning_state"] = "created"
                        background_tasks.add_task(enqueue_dialogue_analysis, current_user.id)
                    except Exception as exc:
                        db.rollback()
                        logger.warning("Crisis stream storage unavailable (%s)", type(exc).__name__)
                yield _sse_event("done", final_payload)
                return

            mode = req.mode if req.anonymous else session.mode
            if req.deep_think:
                deep_phase_start = time.perf_counter()
                yield _sse_event("phase", "memory")
                yield _sse_event("memory_chunk", {"text": "正在翻阅我们之前的谈话记录..."})
                vector_data = await _vector_retrieve_memories_with_timeout(
                    db=db,
                    user_id=current_user.id,
                    user_message=req.message,
                    session_id=req.session_id,
                    trace_id=trace_id,
                    top_k=3,
                    timeout_seconds=20.0,
                    retries=1,
                )
                for _ in range(2):
                    await asyncio.sleep(0.25)
                    yield _sse_event("heartbeat", "ping")
                archives = _load_historical_archives(
                    db=db,
                    user_id=current_user.id,
                    current_session_id=req.session_id,
                    days=365,
                    limit=240,
                )
                insight = _build_historical_insight(archives, req.message)
                session_context = _build_historical_session_context(
                    db=db,
                    user_id=current_user.id,
                    current_session_id=req.session_id,
                    user_message=req.message,
                    max_sessions=8,
                    max_messages_per_session=24,
                )
                memories = vector_data.get("snippets", [])
                if memories:
                    yield _sse_event("memory_chunk", {"text": f"已定位 {len(memories)} 条相关回忆，正在抽取关键线索。"})
                else:
                    yield _sse_event("memory_chunk", {"text": "未找到强相关历史记录，将以当前问题为主进行深度分析。"})
                timeline_lines = session_context.get("timeline_lines", [])
                if session_context.get("target_day"):
                    if timeline_lines:
                        yield _sse_event(
                            "memory_chunk",
                            {"text": f"已按会话更新时间(updated_at)定位到 {session_context['target_day']} 的 {len(timeline_lines)} 条会话记录。"},
                        )
                    else:
                        yield _sse_event(
                            "memory_chunk",
                            {"text": f"你提到的日期 {session_context['target_day']} 未命中会话更新时间记录，将回退到最近历史会话。"},
                        )
                await asyncio.sleep(0.2)

                yield _sse_event("phase", "trend")
                yield _sse_event("trend_chunk", {"text": "对比了一下这周和上周的情绪状态..."})
                trend_desc = insight.get("sentiment_desc") or _generate_trend_description(await _get_cached_mood_trend(db, current_user.id))
                yield _sse_event("trend_chunk", {"text": trend_desc})
                await asyncio.sleep(0.3)

                yield _sse_event("phase", "response")
                timeline_hint = (
                    f"按会话更新时间（updated_at）匹配到 {session_context['target_day']} 当日记录：\n"
                    if session_context.get("target_day")
                    else "最近历史会话时间线（按 updated_at 倒序）：\n"
                )
                deep_context = (
                    f"[深度思考背景]\n历史相关片段: {memories}\n历史主题聚类: {insight.get('topic_cluster', '暂无')}\n近期情绪洞察: {trend_desc}\n\n"
                    f"trace_id: {trace_id}\n向量召回TopK: {vector_data.get('topk', [])}\n"
                    f"{timeline_hint}{chr(10).join(session_context.get('timeline_lines', [])[:8])}\n\n"
                    f"基于 ai_chat_sessions + ai_chat_messages 提取的历史对话片段:\n{session_context.get('history_context', '暂无')}\n\n"
                    f"[当前问题]\n{req.message}"
                )
                raw_reply = ""
                max_attempts = 2
                for attempt in range(1, max_attempts + 1):
                    deep_task = asyncio.create_task(
                        zhipu_chat_service.deep_think_with_student(
                            user_id=f"anon-{current_user.id}" if req.anonymous else str(current_user.id),
                            prompt=deep_context,
                            chat_context=(
                                "请优先依据历史会话回答用户关于“什么时候发生了什么对话”的问题，"
                                "必要时引用 updated_at 时间线并说明依据。"
                            ),
                            mode=mode,
                            trace_id=trace_id,
                        )
                    )
                    attempt_start = time.perf_counter()
                    try:
                        while not deep_task.done():
                            yield _sse_event("heartbeat", "ping")
                            await asyncio.sleep(0.5)
                            if time.perf_counter() - attempt_start > 45:
                                deep_task.cancel()
                                raise TimeoutError(f"deep_think_timeout trace_id={trace_id} attempt={attempt}")
                        raw_reply = await deep_task
                        break
                    except Exception as exc:
                        if not deep_task.done():
                            deep_task.cancel()
                        logger.warning(
                            "deep_think_stream_attempt_failed trace_id=%s attempt=%s/%s error=%s",
                            trace_id,
                            attempt,
                            max_attempts,
                            type(exc).__name__,
                        )
                        if attempt < max_attempts:
                            yield _sse_event("trend_chunk", {"text": f"模型响应较慢，正在进行第 {attempt + 1} 次重试..."})
                            await asyncio.sleep(0.8 * attempt)
                            continue
                        raise RuntimeError(f"deep_think_failed trace_id={trace_id} cause={exc}") from exc
                model_latency_ms = round((time.perf_counter() - deep_phase_start) * 1000, 2)
                model_invoked = True
                reply = _format_deep_think_reply(raw_reply, trace_id=trace_id)
            else:
                yield _sse_event("phase", "response")
                reply = await zhipu_chat_service.chat_with_student(
                    user_id=f"anon-{current_user.id}" if req.anonymous else str(current_user.id),
                    message=req.message,
                    history=[],
                    mode=mode,
                )

            for i in range(0, len(reply), 14):
                yield _sse_event("message_chunk", {"text": reply[i:i+14]})
                await asyncio.sleep(0.015)

            final_payload = {
                "id": str(uuid.uuid4()),
                "reply": reply,
                "is_crisis": False,
                "emotion_tags": emotions,
                "keywords": analysis.get("keywords", []),
                "attention_heatmap": heatmap,
                "risk_radar": radar,
                "language": language,
                "confidence": confidence,
                "model_invoked": model_invoked,
                "model_latency_ms": model_latency_ms,
                "trace_id": trace_id if req.deep_think else None,
            }

            if not req.anonymous and session is not None:
                ai_msg = AIChatMessage(
                    session_id=session.id,
                    role="ai",
                    content=reply,
                    is_crisis=False,
                    emotion_tags=json.dumps(emotions or _default_emotion_tags(), ensure_ascii=False),
                )
                db.add(ai_msg)
                db.flush()
                if user_msg is not None:
                    _archive_dialogue(
                        db=db,
                        user_id=current_user.id,
                        session_id=session.id,
                        user_msg=user_msg,
                        ai_msg=ai_msg,
                        history=history,
                        emotions=emotions,
                    )
                session.updated_at = func.now()
                db.commit()
                background_tasks.add_task(enqueue_dialogue_analysis, current_user.id)

            yield _sse_event("done", final_payload)
        except Exception as exc:
            logger.error("chat_stream_failed user_id=%s trace_id=%s error=%s", current_user.id, trace_id, type(exc).__name__)
            yield _sse_event("error", {"text": "深度思考流式处理失败", "trace_id": trace_id, "error": "model_unavailable"})
            yield _sse_event("done", {"ok": False})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )

@router.get("/report/chat-analysis")
async def get_chat_based_report(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    根据用户的所有聊天记录生成心理报告（不再基于测试量表）
    """
    # 1. 收集用户最近的聊天记录
    messages = (db.query(AIChatMessage)
                .join(AIChatSession, AIChatMessage.session_id == AIChatSession.id)
                .filter(AIChatSession.user_id == current_user.id)
                .order_by(AIChatMessage.created_at.desc(), AIChatMessage.id.desc())
                .limit(300).all())

    chat_logs = []
    emotion_history = []

    for m in reversed(messages):
            role_name = "学生" if m.role == "user" else "AI"
            chat_logs.append(f"{role_name}: {m.content}")
            if m.role == "ai" and m.emotion_tags:
                try:
                    emotion = json.loads(m.emotion_tags)
                    keys = ("sadness", "fear", "anger", "joy")
                    if not isinstance(emotion, dict) or not emotion:
                        continue
                    values = [emotion.get(key, 0) for key in keys]
                    if not all(isinstance(value, (int, float)) and not isinstance(value, bool)
                               and 0 <= value <= 1 for value in values):
                        continue
                    emotion_history.append((m.created_at.isoformat() if m.created_at else "", emotion))
                except (ValueError, TypeError):
                    pass

    # 2. 计算情感趋势和压力指数 (基于 RoBERTa 提取的历史 emotion_tags)
    # 模拟近7次对话的趋势
    recent_7_emotions = emotion_history[-7:]

    trend_data = {
        "dates": [date for date, _ in recent_7_emotions],
        "joy": [round(e.get("joy", 0), 2) for _, e in recent_7_emotions],
        "stress": [round((e.get("sadness", 0) + e.get("fear", 0) + e.get("anger", 0)) / 3, 2) for _, e in recent_7_emotions],
        "sample_count": len(recent_7_emotions),
        "method": "stored_rule_tags_not_clinical_scores",
    }

    # 风险预警等级
    risk_level = "待人工评估"

    # 3. 调用 Qwen AI 生成图表解读
    ai_report = await qwen_service.generate_report_from_chats(chat_logs)

    return {
        "status": "success",
        "data": {
            "overall_status": ai_report.get("overall_status", "暂无分析"),
            "trend_data": trend_data,
            "risk_level": risk_level,
            "interpretations": ai_report.get("chart_interpretations", {})
        },
        "data_status": "available" if messages else "insufficient",
        "generation": {"source": ai_report.get("source", "local_rules"),
                       "status": ai_report.get("status", "fallback" if messages else "insufficient"),
                       "model_id": ai_report.get("model_id")},
    }

@router.post("/chat/upload")
async def upload_image_or_audio(
    file: UploadFile = File(...), type: str = Form(...),
    current_user: User = Depends(get_current_user),
):
    if type != "image":
        raise HTTPException(status_code=400, detail="Invalid media type, only image is supported")
    # Authentication and bounded content validation happen before model work.
    await read_image_upload(file)
    raise HTTPException(status_code=503, detail="图片内容解析暂未开放，请使用文字描述；本次文件未保留。")
