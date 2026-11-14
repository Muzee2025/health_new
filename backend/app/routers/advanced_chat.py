import asyncio
import json
import logging
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
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    AIChatMessage,
    AIChatSession,
    ChatHistoryArchive,
    TestResult,
    User,
)
from app.routers.advanced_chat_helpers import (
    _build_context_snapshot,
    _calc_sentiment_score,
    _cosine_similarity,
    _day_range,
    _default_emotion_tags,
    _extract_target_date,
    _format_deep_think_reply,
    _format_dt,
    _is_effective_emotion_input,
    _normalize_history_for_model,
    _safe_datetime_str,
    _safe_json_loads,
    _sse_event,
    _tokenize_for_match,
)
from app.routers.advanced_chat_orchestration import (
    ChatOrchestrationRuntime,
)
from app.routers.advanced_chat_orchestration import (
    create_chat_stream_response as _create_chat_stream_response,
)
from app.routers.advanced_chat_orchestration import (
    run_chat_interaction as _run_chat_interaction,
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


def _keyword_crisis_detect(text: str) -> Tuple[bool, str]:
    source = str(text or "").strip()
    if not source:
        return False, ""
    for kw in CRISIS_KEYWORDS:
        if kw in source:
            return True, kw
    return False, ""


def _build_db_history_for_model(hist_msgs: List[AIChatMessage], deep_think: bool) -> List[Dict[str, str]]:
    if not deep_think:
        return []
    context_msgs = hist_msgs[:-1] if hist_msgs else hist_msgs
    return [
        {"role": "assistant" if m.role == "ai" else m.role, "content": m.content}
        for m in context_msgs[-10:]
    ]


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
    # One query for every selected session's messages, grouped afterwards, instead of
    # one query per session. The per-session cap and ordering are applied in Python so
    # each session still contributes at most max_messages_per_session oldest-first rows.
    messages_by_session: dict = {}
    for message in (
        db.query(AIChatMessage)
        .filter(
            AIChatMessage.session_id.in_([session.id for session in sessions]),
            AIChatMessage.role.in_(["user", "ai"]),
        )
        .order_by(AIChatMessage.created_at.asc())
        .all()
    ):
        messages_by_session.setdefault(message.session_id, []).append(message)

    for session in sessions:
        msgs = messages_by_session.get(session.id, [])[:max_messages_per_session]
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
            db.flush()

            remaining_session = db.query(AIChatSession).filter(
                AIChatSession.id == session_id,
                AIChatSession.user_id == current_user.id
            ).count()
            remaining_messages = db.query(AIChatMessage).filter(
                AIChatMessage.session_id == session_id
            ).count()
            remaining_archives = db.query(ChatHistoryArchive).filter(
                ChatHistoryArchive.session_id == session_id
            ).count()
            if remaining_session or remaining_messages > 0 or remaining_archives > 0:
                raise RuntimeError("delete_integrity_check_failed")

            db.commit()

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


def _chat_orchestration_runtime() -> ChatOrchestrationRuntime:
    return ChatOrchestrationRuntime(
        archive_dialogue=_archive_dialogue,
        build_db_history_for_model=_build_db_history_for_model,
        build_historical_insight=_build_historical_insight,
        build_historical_session_context=_build_historical_session_context,
        default_emotion_tags=_default_emotion_tags,
        emotion_pipeline=_emotion_pipeline,
        format_deep_think_reply=_format_deep_think_reply,
        generate_trend_description=_generate_trend_description,
        get_cached_mood_trend=_get_cached_mood_trend,
        invoke_deep_think_with_retry=_invoke_deep_think_with_retry,
        keyword_crisis_detect=_keyword_crisis_detect,
        load_historical_archives=_load_historical_archives,
        normalize_history_for_model=_normalize_history_for_model,
        sse_event=_sse_event,
        vector_retrieve_memories_with_timeout=_vector_retrieve_memories_with_timeout,
        crisis_support_message=CRISIS_SUPPORT_MESSAGE,
        chat_response_cls=ChatResponse,
        enqueue_dialogue_analysis=enqueue_dialogue_analysis,
        logger=logger,
        manager=manager,
        nlp_engine=nlp_engine,
        zhipu_chat_service=zhipu_chat_service,
    )


@router.post("/chat", response_model=ChatResponse)
async def ai_chat_interaction(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # 语言识别模拟
    return await _run_chat_interaction(req, background_tasks, db, current_user, _chat_orchestration_runtime())


@router.post("/chat/stream")
async def ai_chat_stream(
    req: ChatRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _create_chat_stream_response(req, background_tasks, db, current_user, _chat_orchestration_runtime)


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
