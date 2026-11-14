"""Chat endpoint orchestration with dependencies supplied by the compatibility router."""

import asyncio
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List

from fastapi import BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import AIChatMessage, AIChatSession, CrisisWarning, User


@dataclass(frozen=True)
class ChatOrchestrationRuntime:
    archive_dialogue: Any
    build_db_history_for_model: Any
    build_historical_insight: Any
    build_historical_session_context: Any
    chat_response_cls: Any
    crisis_support_message: Any
    default_emotion_tags: Any
    emotion_pipeline: Any
    enqueue_dialogue_analysis: Any
    format_deep_think_reply: Any
    generate_trend_description: Any
    get_cached_mood_trend: Any
    invoke_deep_think_with_retry: Any
    keyword_crisis_detect: Any
    load_historical_archives: Any
    logger: Any
    manager: Any
    nlp_engine: Any
    normalize_history_for_model: Any
    sse_event: Any
    vector_retrieve_memories_with_timeout: Any
    zhipu_chat_service: Any


async def run_chat_interaction(req: Any, background_tasks: BackgroundTasks, db: Session, current_user: User, runtime: ChatOrchestrationRuntime) -> Any:
    language = "中文"
    confidence = 0.98 if any("\u4e00" <= char <= "\u9fff" for char in req.message) else 0.85
    trace_id = str(uuid.uuid4())
    model_invoked = False
    model_latency_ms = 0.0

    try:
        analysis = await runtime.emotion_pipeline(req.message)
    except Exception:
        runtime.logger.error("emotion_analyze_failed user_id=%s anonymous=%s", current_user.id, req.anonymous)
        analysis = {
            "emotion_tags": runtime.default_emotion_tags(),
            "keywords": [],
            "attention_heatmap": [],
            "risk_radar": runtime.nlp_engine.calc_5d_risk_radar(runtime.default_emotion_tags()),
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
    kw_hit, kw_trigger = runtime.keyword_crisis_detect(req.message)
    if kw_hit:
        is_crisis = True
    heatmap = analysis.get("attention_heatmap", [])
    radar = analysis.get("risk_radar", {})

    if req.anonymous:
        history = runtime.normalize_history_for_model(req.history or [], req.deep_think)
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
            emotion_tags=json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False),
        )
        db.add(user_msg)

        hist_msgs = db.query(AIChatMessage).filter(
            AIChatMessage.session_id == session.id
        ).order_by(AIChatMessage.created_at.asc()).all()
        history = runtime.build_db_history_for_model(hist_msgs, req.deep_think)

        # 自动更新会话标题
        if session.title == "新对话":
            session.title = req.message[:15] + "..."

        # 更新用户消息的热图
        user_msg.heatmap = json.dumps(heatmap, ensure_ascii=False)

    warning_state = "not_applicable"
    if is_crisis:
        warning_state = "anonymous" if req.anonymous else "not_created"
        reply = runtime.crisis_support_message
        # 保存预警并广播
        if not req.anonymous and 'session' in locals() and session:
            try:
                # 记录用户消息
                ai_msg = AIChatMessage(
                    session_id=session.id,
                    role="ai",
                    content=reply,
                    is_crisis=True,
                    emotion_tags=json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False)
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

                # Broadcast to the teacher side. ``db=None``: this coroutine is
                # detached via create_task, so it must not borrow the request
                # Session (get_db closes it when the response ends).
                asyncio.create_task(runtime.manager.broadcast_to_teachers({
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
                }, db=None, student_id=current_user.id))
            except Exception as e:
                db.rollback()
                runtime.logger.error("Warning persistence unavailable (%s)", type(e).__name__)
    else:
        start_ts = time.perf_counter()
        if req.deep_think:
            vector_data = await runtime.vector_retrieve_memories_with_timeout(
                db=db,
                user_id=current_user.id,
                user_message=req.message,
                session_id=req.session_id,
                trace_id=trace_id,
                top_k=3,
                timeout_seconds=20.0,
                retries=1,
            )
            archives = runtime.load_historical_archives(
                db=db,
                user_id=current_user.id,
                current_session_id=req.session_id,
                days=365,
                limit=240,
            )
            insight = runtime.build_historical_insight(archives, req.message)
            session_context = runtime.build_historical_session_context(
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
                raw_reply, attempt_used = await runtime.invoke_deep_think_with_retry(
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
                runtime.logger.info("deep_think_success trace_id=%s attempts=%s latency_ms=%s", trace_id, attempt_used, model_latency_ms)
                reply = runtime.format_deep_think_reply(raw_reply, trace_id=trace_id)
            except Exception as exc:
                runtime.logger.error("deep_think_invoke_failed trace_id=%s user_id=%s error=%s", trace_id, current_user.id, type(exc).__name__)
                raise HTTPException(
                    status_code=500,
                    detail={"error": "deep_think_invoke_failed", "trace_id": trace_id, "cause": "model_unavailable"},
                ) from exc
        else:
            reply = await runtime.zhipu_chat_service.chat_with_student(
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
            emotion_tags=json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False)
        )
        db.add(ai_msg)
        db.flush()
        runtime.archive_dialogue(
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
        background_tasks.add_task(runtime.enqueue_dialogue_analysis, current_user.id)

    return runtime.chat_response_cls(
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


def create_chat_stream_response(
    req: Any,
    background_tasks: BackgroundTasks,
    db: Session,
    current_user: User,
    runtime_factory: Callable[[], ChatOrchestrationRuntime],
) -> StreamingResponse:
    async def event_generator():
        runtime = runtime_factory()
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
                analysis = await runtime.emotion_pipeline(req.message)
            except Exception:
                runtime.logger.error("stream_emotion_analyze_failed user_id=%s", current_user.id)
                analysis = {
                    "emotion_tags": runtime.default_emotion_tags(),
                    "keywords": [],
                    "attention_heatmap": [],
                    "risk_radar": runtime.nlp_engine.calc_5d_risk_radar(runtime.default_emotion_tags()),
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
            kw_hit, kw_trigger = runtime.keyword_crisis_detect(req.message)
            if kw_hit:
                is_crisis = True

            if req.anonymous:
                history = runtime.normalize_history_for_model(req.history or [], req.deep_think)
            else:
                if not req.session_id:
                    yield runtime.sse_event("error", {"text": "session_id is required"})
                    yield runtime.sse_event("done", {"ok": False})
                    return
                session = db.query(AIChatSession).filter(
                    AIChatSession.id == req.session_id,
                    AIChatSession.user_id == current_user.id
                ).first()
                if not session:
                    yield runtime.sse_event("error", {"text": "Session not found"})
                    yield runtime.sse_event("done", {"ok": False})
                    return
                user_msg = AIChatMessage(session_id=session.id, role="user", content=req.message)
                db.add(user_msg)
                hist_msgs = db.query(AIChatMessage).filter(
                    AIChatMessage.session_id == session.id
                ).order_by(AIChatMessage.created_at.asc()).all()
                history = runtime.build_db_history_for_model(hist_msgs, req.deep_think)
                if session.title == "新对话":
                    session.title = req.message[:15] + "..."
                user_msg.heatmap = json.dumps(heatmap, ensure_ascii=False)
                user_msg.emotion_tags = json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False)

            if is_crisis:
                crisis_reply = runtime.crisis_support_message
                yield runtime.sse_event("phase", "response")
                for i in range(0, len(crisis_reply), 16):
                    yield runtime.sse_event("message_chunk", {"text": crisis_reply[i:i+16]})
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
                            emotion_tags=json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False),
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

                        asyncio.create_task(runtime.manager.broadcast_to_teachers({
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
                        }, db=None, student_id=current_user.id))

                        if user_msg is not None:
                            runtime.archive_dialogue(
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
                        background_tasks.add_task(runtime.enqueue_dialogue_analysis, current_user.id)
                    except Exception as exc:
                        db.rollback()
                        runtime.logger.warning("Crisis stream storage unavailable (%s)", type(exc).__name__)
                yield runtime.sse_event("done", final_payload)
                return

            mode = req.mode if req.anonymous else session.mode
            if req.deep_think:
                deep_phase_start = time.perf_counter()
                yield runtime.sse_event("phase", "memory")
                yield runtime.sse_event("memory_chunk", {"text": "正在翻阅我们之前的谈话记录..."})
                vector_data = await runtime.vector_retrieve_memories_with_timeout(
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
                    yield runtime.sse_event("heartbeat", "ping")
                archives = runtime.load_historical_archives(
                    db=db,
                    user_id=current_user.id,
                    current_session_id=req.session_id,
                    days=365,
                    limit=240,
                )
                insight = runtime.build_historical_insight(archives, req.message)
                session_context = runtime.build_historical_session_context(
                    db=db,
                    user_id=current_user.id,
                    current_session_id=req.session_id,
                    user_message=req.message,
                    max_sessions=8,
                    max_messages_per_session=24,
                )
                memories = vector_data.get("snippets", [])
                if memories:
                    yield runtime.sse_event("memory_chunk", {"text": f"已定位 {len(memories)} 条相关回忆，正在抽取关键线索。"})
                else:
                    yield runtime.sse_event("memory_chunk", {"text": "未找到强相关历史记录，将以当前问题为主进行深度分析。"})
                timeline_lines = session_context.get("timeline_lines", [])
                if session_context.get("target_day"):
                    if timeline_lines:
                        yield runtime.sse_event(
                            "memory_chunk",
                            {"text": f"已按会话更新时间(updated_at)定位到 {session_context['target_day']} 的 {len(timeline_lines)} 条会话记录。"},
                        )
                    else:
                        yield runtime.sse_event(
                            "memory_chunk",
                            {"text": f"你提到的日期 {session_context['target_day']} 未命中会话更新时间记录，将回退到最近历史会话。"},
                        )
                await asyncio.sleep(0.2)

                yield runtime.sse_event("phase", "trend")
                yield runtime.sse_event("trend_chunk", {"text": "对比了一下这周和上周的情绪状态..."})
                trend_desc = insight.get("sentiment_desc") or runtime.generate_trend_description(await runtime.get_cached_mood_trend(db, current_user.id))
                yield runtime.sse_event("trend_chunk", {"text": trend_desc})
                await asyncio.sleep(0.3)

                yield runtime.sse_event("phase", "response")
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
                        runtime.zhipu_chat_service.deep_think_with_student(
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
                            yield runtime.sse_event("heartbeat", "ping")
                            await asyncio.sleep(0.5)
                            if time.perf_counter() - attempt_start > 45:
                                deep_task.cancel()
                                raise TimeoutError(f"deep_think_timeout trace_id={trace_id} attempt={attempt}")
                        raw_reply = await deep_task
                        break
                    except Exception as exc:
                        if not deep_task.done():
                            deep_task.cancel()
                        runtime.logger.warning(
                            "deep_think_stream_attempt_failed trace_id=%s attempt=%s/%s error=%s",
                            trace_id,
                            attempt,
                            max_attempts,
                            type(exc).__name__,
                        )
                        if attempt < max_attempts:
                            yield runtime.sse_event("trend_chunk", {"text": f"模型响应较慢，正在进行第 {attempt + 1} 次重试..."})
                            await asyncio.sleep(0.8 * attempt)
                            continue
                        raise RuntimeError(f"deep_think_failed trace_id={trace_id} cause={exc}") from exc
                model_latency_ms = round((time.perf_counter() - deep_phase_start) * 1000, 2)
                model_invoked = True
                reply = runtime.format_deep_think_reply(raw_reply, trace_id=trace_id)
            else:
                yield runtime.sse_event("phase", "response")
                reply = await runtime.zhipu_chat_service.chat_with_student(
                    user_id=f"anon-{current_user.id}" if req.anonymous else str(current_user.id),
                    message=req.message,
                    history=[],
                    mode=mode,
                )

            for i in range(0, len(reply), 14):
                yield runtime.sse_event("message_chunk", {"text": reply[i:i+14]})
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
                    emotion_tags=json.dumps(emotions or runtime.default_emotion_tags(), ensure_ascii=False),
                )
                db.add(ai_msg)
                db.flush()
                if user_msg is not None:
                    runtime.archive_dialogue(
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
                background_tasks.add_task(runtime.enqueue_dialogue_analysis, current_user.id)

            yield runtime.sse_event("done", final_payload)
        except Exception as exc:
            runtime.logger.error("chat_stream_failed user_id=%s trace_id=%s error=%s", current_user.id, trace_id, type(exc).__name__)
            yield runtime.sse_event("error", {"text": "深度思考流式处理失败", "trace_id": trace_id, "error": "model_unavailable"})
            yield runtime.sse_event("done", {"ok": False})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
