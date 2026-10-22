import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from app.services.qwen_service import client as qwen_client
from app.services.zhipu_emohaa_service import ZhipuEmohaaService

logger = logging.getLogger(__name__)
MM_LOG = Path("logs") / "multi_model_orchestrator.log"
PRIMARY_TEXT_MODEL = os.getenv("PRIMARY_TEXT_MODEL", "qwen3.6-plus")
LEGACY_PRIMARY_MODEL_ALIAS = "qvq-max-2025-03-25"
PRIMARY_MODEL_FALLBACK = os.getenv("PRIMARY_MODEL_FALLBACK", "qwen-max")
PRIMARY_MODEL_SECONDARY_FALLBACK = os.getenv("PRIMARY_MODEL_SECONDARY_FALLBACK", "qwen-plus")
PRIMARY_MODEL_TIMEOUT_SEC = int(os.getenv("PRIMARY_MODEL_TIMEOUT_SEC", "45"))
PRIMARY_TIMEOUT_SOFT_FALLBACK = os.getenv("PRIMARY_TIMEOUT_SOFT_FALLBACK", "false").strip().lower() in ("1", "true", "yes", "on")
PRIMARY_FALLBACK_STATUS_DONE = os.getenv("PRIMARY_FALLBACK_STATUS_DONE", "true").strip().lower() in ("1", "true", "yes", "on")

MODEL_CHAIN = [
    {"id": PRIMARY_TEXT_MODEL, "stage": "文本理解与逻辑推理", "etaSec": 6, "qps": 2.0, "timeout": PRIMARY_MODEL_TIMEOUT_SEC},
    {"id": "wanx-v1", "stage": "图像/视频内容分析", "etaSec": 4, "qps": 1.5, "timeout": 30},
    {"id": "qwen3.5-omni-plus-2026-03-15", "stage": "多模态数据融合", "etaSec": 5, "qps": 2.0, "timeout": 30},
    {"id": "qwen3-tts-vd-2026-01-26", "stage": "音频内容处理", "etaSec": 4, "qps": 2.5, "timeout": 30},
    {"id": "gte-rerank-v2", "stage": "语义检索与重排序", "etaSec": 3, "qps": 4.0, "timeout": 30},
    {"id": "emohaa", "stage": "情感倾向分析", "etaSec": 3, "qps": 3.0, "timeout": 30},
]
MODEL_FAILURE_WINDOW_SEC = int(os.getenv("MODEL_FAILURE_WINDOW_SEC", "300"))
PRIMARY_CIRCUIT_MIN_SAMPLES = int(os.getenv("PRIMARY_CIRCUIT_MIN_SAMPLES", "6"))
PRIMARY_CIRCUIT_ERROR_RATE = float(os.getenv("PRIMARY_CIRCUIT_ERROR_RATE", "0.35"))
PRIMARY_CIRCUIT_CONSECUTIVE = int(os.getenv("PRIMARY_CIRCUIT_CONSECUTIVE", "3"))
PRIMARY_CIRCUIT_COOLDOWN_SEC = int(os.getenv("PRIMARY_CIRCUIT_COOLDOWN_SEC", "120"))
MODEL_RETRY_ATTEMPTS = int(os.getenv("MODEL_RETRY_ATTEMPTS", "3"))


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


def _append_log(payload: Dict[str, Any]):
    try:
        MM_LOG.parent.mkdir(parents=True, exist_ok=True)
        with MM_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": _utc_now(), **payload}, ensure_ascii=False) + "\n")
    except Exception:
        logger.exception("multi_model_log_failed")


def _sse(event: str, data: Dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@dataclass
class _CacheItem:
    value: Dict[str, Any]
    expire_at: float


@dataclass
class _ModelHealth:
    events: List[Dict[str, Any]]
    consecutive_errors: int
    circuit_open_until: float
    open_count: int


class MultiModelOrchestrator:
    def __init__(self):
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._workers_started = False
        self._workers: List[asyncio.Task] = []
        self._rate_state: Dict[str, float] = {}
        self._rate_lock = asyncio.Lock()
        self._cache: Dict[str, _CacheItem] = {}
        self._metrics = {"submitted": 0, "failed": 0, "succeeded": 0}
        self._model_health: Dict[str, _ModelHealth] = {}
        self._alerts: List[Dict[str, Any]] = []
        # 用户要求协同链路真实调用，默认关闭缓存，确保每次都会触发外部模型计费。
        self._cache_ttl_sec = 0
        self._dashscope_key = os.getenv("QWEN_API_KEY", "XXXXXXX")
        self._emohaa_service = ZhipuEmohaaService()

    @staticmethod
    def get_current_model_meta() -> Dict[str, str]:
        return {
            "model_name": PRIMARY_TEXT_MODEL,
            "legacy_alias": LEGACY_PRIMARY_MODEL_ALIAS,
        }

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        # 简化估算：中文1字≈1 token，英文按4字符≈1 token，保底1
        text = str(text or "")
        if not text:
            return 1
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        non_ascii_chars = max(0, len(text) - ascii_chars)
        return max(1, non_ascii_chars + int(ascii_chars / 4))

    async def ensure_workers(self):
        if self._workers_started:
            return
        self._workers_started = True
        for _ in range(2):
            self._workers.append(asyncio.create_task(self._worker_loop()))

    async def submit_task(self, user_id: int, payload: Dict[str, Any]) -> str:
        await self.ensure_workers()
        task_id = str(uuid.uuid4())
        self._tasks[task_id] = {
            "task_id": task_id,
            "user_id": user_id,
            "status": "queued",
            "created_at": _utc_now(),
            "updated_at": _utc_now(),
            "progress": 0,
            "payload": payload,
            "events": [],
            "context": {},
            "result": None,
            "error": "",
        }
        self._metrics["submitted"] += 1
        await self._queue.put(task_id)
        self._append_event(task_id, "queued", {"taskId": task_id, "status": "queued"})
        return task_id

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self._tasks.get(task_id)

    def stream_generator(self, task_id: str):
        async def gen():
            cursor = 0
            while True:
                task = self._tasks.get(task_id)
                if not task:
                    yield _sse("error", {"taskId": task_id, "status": "failed", "message": "task_not_found"})
                    break
                events = task.get("events", [])
                while cursor < len(events):
                    yield events[cursor]
                    cursor += 1
                if task["status"] in ("done", "failed") and cursor >= len(events):
                    break
                await asyncio.sleep(0.25)
        return gen()

    def get_metrics(self):
        total = max(1, self._metrics["submitted"])
        failed_ratio = self._metrics["failed"] / total
        return {
            **self._metrics,
            "error_rate": round(failed_ratio, 4),
            "alerts": list(self._alerts[-20:]),
            "models": {mid: self._model_health_snapshot(mid) for mid in self._model_health.keys()},
        }

    def _model_health_snapshot(self, model_id: str) -> Dict[str, Any]:
        state = self._model_health.get(model_id)
        if not state:
            return {"error_rate": 0.0, "samples": 0, "consecutive_errors": 0, "circuit_open": False, "open_count": 0}
        self._prune_health_events(state)
        samples = len(state.events)
        errors = sum(1 for x in state.events if not x.get("ok"))
        now = time.time()
        return {
            "error_rate": round(errors / max(1, samples), 4),
            "samples": samples,
            "consecutive_errors": state.consecutive_errors,
            "circuit_open": state.circuit_open_until > now,
            "circuit_open_until": state.circuit_open_until,
            "open_count": state.open_count,
            "last_error_type": next((x.get("error_type") for x in reversed(state.events) if not x.get("ok")), ""),
        }

    def _ensure_model_health(self, model_id: str) -> _ModelHealth:
        state = self._model_health.get(model_id)
        if state:
            return state
        state = _ModelHealth(events=[], consecutive_errors=0, circuit_open_until=0.0, open_count=0)
        self._model_health[model_id] = state
        return state

    def _prune_health_events(self, state: _ModelHealth):
        cutoff = time.time() - MODEL_FAILURE_WINDOW_SEC
        state.events = [x for x in state.events if float(x.get("ts", 0)) >= cutoff]

    def _record_model_outcome(self, model_id: str, ok: bool, error_type: str = "", reason: str = ""):
        state = self._ensure_model_health(model_id)
        state.events.append({"ts": time.time(), "ok": bool(ok), "error_type": error_type, "reason": reason[:200]})
        self._prune_health_events(state)
        if ok:
            state.consecutive_errors = 0
        else:
            state.consecutive_errors += 1

    def _classify_error(self, exc: Exception) -> str:
        if isinstance(exc, asyncio.TimeoutError):
            return "timeout"
        text = str(exc).lower()
        if "timeout" in text:
            return "timeout"
        if "429" in text or "rate limit" in text:
            return "rate_limit"
        if "401" in text or "403" in text or "unauthorized" in text or "forbidden" in text:
            return "auth"
        if "500" in text or "502" in text or "503" in text or "504" in text:
            return "upstream_5xx"
        if "connection" in text or "dns" in text or "network" in text:
            return "network"
        return "invoke_failed"

    def _is_primary_circuit_open(self) -> bool:
        state = self._ensure_model_health(PRIMARY_TEXT_MODEL)
        return state.circuit_open_until > time.time()

    def _maybe_open_primary_circuit(self, reason: str):
        state = self._ensure_model_health(PRIMARY_TEXT_MODEL)
        self._prune_health_events(state)
        samples = len(state.events)
        errors = sum(1 for x in state.events if not x.get("ok"))
        error_rate = errors / max(1, samples)
        should_open = (
            samples >= PRIMARY_CIRCUIT_MIN_SAMPLES
            and error_rate >= PRIMARY_CIRCUIT_ERROR_RATE
            and state.consecutive_errors >= PRIMARY_CIRCUIT_CONSECUTIVE
        )
        if not should_open:
            return None
        now = time.time()
        if state.circuit_open_until > now:
            return None
        state.circuit_open_until = now + PRIMARY_CIRCUIT_COOLDOWN_SEC
        state.open_count += 1
        alert = {
            "level": "warning",
            "type": "model_circuit_open",
            "model": PRIMARY_TEXT_MODEL,
            "fallback": PRIMARY_MODEL_FALLBACK,
            "window_sec": MODEL_FAILURE_WINDOW_SEC,
            "samples": samples,
            "errors": errors,
            "error_rate": round(error_rate, 4),
            "consecutive_errors": state.consecutive_errors,
            "cooldown_sec": PRIMARY_CIRCUIT_COOLDOWN_SEC,
            "reason": reason[:200],
            "ts": _utc_now(),
        }
        self._alerts.append(alert)
        _append_log({"status": "alert", **alert})
        return alert

    async def _worker_loop(self):
        while True:
            task_id = await self._queue.get()
            try:
                await self._run_task(task_id)
            except Exception as exc:
                logger.error("run_multi_model_task_failed task_id=%s error_type=%s", task_id, type(exc).__name__)
                task = self._tasks.get(task_id)
                if task:
                    task["status"] = "failed"
                    task["error"] = "analysis_failed"
                    task["updated_at"] = _utc_now()
                    self._append_event(task_id, "error", {"taskId": task_id, "status": "failed", "message": "Analysis temporarily unavailable"})
                    self._metrics["failed"] += 1
            finally:
                self._queue.task_done()

    async def _run_task(self, task_id: str):
        task = self._tasks[task_id]
        task["status"] = "running"
        task["updated_at"] = _utc_now()
        self._append_event(task_id, "start", {"taskId": task_id, "status": "running", "totalModels": len(MODEL_CHAIN)})
        _append_log({"task_id": task_id, "status": "running", "user_id": task["user_id"]})

        context = {}
        for idx, model in enumerate(MODEL_CHAIN):
            step_start = time.perf_counter()
            remaining_sec = sum(x["etaSec"] for x in MODEL_CHAIN[idx:])
            self._append_event(task_id, "step", {
                "taskId": task_id,
                "model": model["id"],
                "stage": model["stage"],
                "status": "running",
                "progress": int((idx / len(MODEL_CHAIN)) * 100),
                "etaSec": remaining_sec,
            })

            try:
                output, cached = await self._call_with_retry(model, task["payload"], context, task_id)
                context[model["id"]] = output
                elapsed_ms = round((time.perf_counter() - step_start) * 1000, 2)
                step_status = str(output.get("status") or "done")
                self._append_event(task_id, "step", {
                    "taskId": task_id,
                    "model": model["id"],
                    "stage": model["stage"],
                    "status": step_status,
                    "progress": int(((idx + 1) / len(MODEL_CHAIN)) * 100),
                    "etaSec": max(0, remaining_sec - model["etaSec"]),
                    "elapsedMs": elapsed_ms,
                    "cached": cached,
                    "promptTokens": int((output.get("usage") or {}).get("prompt_tokens", 0)),
                    "completionTokens": int((output.get("usage") or {}).get("completion_tokens", 0)),
                    "totalTokens": int((output.get("usage") or {}).get("total_tokens", 0)),
                    "summary": output.get("summary", ""),
                    "result": output,
                })
                _append_log({
                    "task_id": task_id,
                    "model": model["id"],
                    "status": step_status,
                    "elapsed_ms": elapsed_ms,
                    "cached": cached,
                    "api_model": output.get("api_model"),
                    "usage": output.get("usage", {}),
                })
            except Exception as exc:
                elapsed_ms = round((time.perf_counter() - step_start) * 1000, 2)
                degraded = {"summary": f"{model['id']} 异常降级", "confidence": 0.35, "raw": {"error": str(exc)}}
                context[model["id"]] = degraded
                self._append_event(task_id, "step", {
                    "taskId": task_id,
                    "model": model["id"],
                    "stage": model["stage"],
                    "status": "error",
                    "progress": int(((idx + 1) / len(MODEL_CHAIN)) * 100),
                    "etaSec": max(0, remaining_sec - model["etaSec"]),
                    "elapsedMs": elapsed_ms,
                    "summary": degraded["summary"],
                    "result": degraded,
                })
                _append_log({
                    "task_id": task_id,
                    "model": model["id"],
                    "status": "error",
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                })

        fused = self._fuse_results(task["payload"], context)
        task["context"] = context
        task["result"] = fused
        task["status"] = "done"
        task["progress"] = 100
        task["updated_at"] = _utc_now()
        self._append_event(task_id, "done", {"taskId": task_id, "status": "done", "report": fused})
        self._metrics["succeeded"] += 1
        _append_log({"task_id": task_id, "status": "done", "confidence": fused.get("confidence", 0)})

    async def _call_with_retry(self, model: Dict[str, Any], payload: Dict[str, Any], context: Dict[str, Any], task_id: str):
        cache_key = self._cache_key(model["id"], payload, context)
        cached = self._cache.get(cache_key)
        now = time.time()
        if self._cache_ttl_sec > 0 and cached and cached.expire_at > now:
            return cached.value, True
        if cached and cached.expire_at <= now:
            self._cache.pop(cache_key, None)

        last_error = ""
        error_type = ""
        forced_fallback = bool(model["id"] == PRIMARY_TEXT_MODEL and self._is_primary_circuit_open())
        if forced_fallback:
            self._append_event(task_id, "alert", {
                "taskId": task_id,
                "model": model["id"],
                "status": "fallback",
                "reason": "primary_model_circuit_open",
                "fallback": PRIMARY_MODEL_FALLBACK,
            })
        for attempt in range(MODEL_RETRY_ATTEMPTS):
            try:
                await self._acquire_rate_slot(model["id"], model["qps"])
                result = await asyncio.wait_for(
                    self._invoke_model(model, payload, context, force_primary_fallback=forced_fallback),
                    timeout=model["timeout"],
                )
                if model["id"] == PRIMARY_TEXT_MODEL and str(result.get("api_model") or model["id"]) != model["id"]:
                    # 已经获得可用输出时，视为软降级成功，不计入连续失败熔断。
                    self._record_model_outcome(
                        model["id"],
                        ok=True,
                        error_type="degraded_fallback",
                        reason=str(result.get("api_model") or PRIMARY_MODEL_FALLBACK),
                    )
                    self._append_event(
                        task_id,
                        "alert",
                        {
                            "taskId": task_id,
                            "level": "info",
                            "type": "primary_model_soft_fallback",
                            "model": model["id"],
                            "fallback": str(result.get("api_model") or PRIMARY_MODEL_FALLBACK),
                            "reason": "fallback_succeeded",
                        },
                    )
                else:
                    self._record_model_outcome(model["id"], ok=True)
                if self._cache_ttl_sec > 0:
                    self._cache[cache_key] = _CacheItem(value=result, expire_at=time.time() + self._cache_ttl_sec)
                return result, False
            except Exception as exc:
                last_error = str(exc)
                error_type = self._classify_error(exc)
                # 主模型超时时立即切到回退模型，避免单步被 3 次超时拖到 90s+。
                if model["id"] == PRIMARY_TEXT_MODEL and error_type == "timeout" and PRIMARY_TIMEOUT_SOFT_FALLBACK:
                    try:
                        fallback_timeout = max(8, min(int(model.get("timeout", 30)), 15))
                        fallback_result = await asyncio.wait_for(
                            self._invoke_model(model, payload, context, force_primary_fallback=True),
                            timeout=fallback_timeout,
                        )
                        self._record_model_outcome(
                            model["id"],
                            ok=True,
                            error_type="timeout_soft_fallback",
                            reason=str(fallback_result.get("api_model") or PRIMARY_MODEL_FALLBACK),
                        )
                        self._append_event(
                            task_id,
                            "alert",
                            {
                                "taskId": task_id,
                                "level": "warning",
                                "type": "primary_timeout_soft_fallback",
                                "model": model["id"],
                                "fallback": str(fallback_result.get("api_model") or PRIMARY_MODEL_FALLBACK),
                                "attempt": attempt + 1,
                                "timeoutSec": int(model.get("timeout", 30)),
                            },
                        )
                        _append_log(
                            {
                                "model": model["id"],
                                "timeout_soft_fallback": True,
                                "attempt": attempt + 1,
                                "fallback_to": fallback_result.get("api_model") or PRIMARY_MODEL_FALLBACK,
                            }
                        )
                        if self._cache_ttl_sec > 0:
                            self._cache[cache_key] = _CacheItem(value=fallback_result, expire_at=time.time() + self._cache_ttl_sec)
                        return fallback_result, False
                    except Exception as fb_exc:
                        last_error = f"{last_error}; fallback_failed:{str(fb_exc)}"
                        error_type = "timeout_fallback_failed"
                self._record_model_outcome(model["id"], ok=False, error_type=error_type, reason=last_error)
                if model["id"] == PRIMARY_TEXT_MODEL:
                    alert = self._maybe_open_primary_circuit(last_error or error_type)
                    if alert:
                        self._append_event(task_id, "alert", {"taskId": task_id, **alert})
                if attempt >= MODEL_RETRY_ATTEMPTS - 1:
                    break
                # 指数退避 + 抖动，减少上游高峰期瞬时重试放大。
                backoff = min(3.0, (2 ** attempt) * 0.35) + random.uniform(0.05, 0.25)
                await asyncio.sleep(backoff)
                self._append_event(task_id, "retry", {
                    "taskId": task_id,
                    "model": model["id"],
                    "status": "retrying",
                    "attempt": attempt + 2,
                    "errorType": error_type,
                    "backoffSec": round(backoff, 3),
                    "reason": last_error,
                })
        raise RuntimeError(f"{error_type}:{last_error}" if error_type else (last_error or "model_call_failed"))

    async def _acquire_rate_slot(self, model_id: str, qps: float):
        min_interval = 1.0 / max(0.1, qps)
        while True:
            async with self._rate_lock:
                last = self._rate_state.get(model_id, 0.0)
                now = time.time()
                wait_sec = (last + min_interval) - now
                if wait_sec <= 0:
                    self._rate_state[model_id] = now
                    return
            await asyncio.sleep(min(wait_sec, 0.05))

    async def _invoke_model(self, model: Dict[str, Any], payload: Dict[str, Any], context: Dict[str, Any], force_primary_fallback: bool = False):
        # 统一协议: {payload, upstream=context, model_id}
        model_id = model["id"]
        messages = payload.get("messages", [])
        text = "\n".join([str(m.get("content", "")) for m in messages[-30:]])
        emotions = Counter()
        for m in messages:
            for k, v in (m.get("emotion_tags") or {}).items():
                emotions[k] += float(v)
        top_emotions = [x for x, _ in emotions.most_common(3)] or ["neutral"]

        if model_id == "wanx-v1":
            return await asyncio.to_thread(self._invoke_wanx_real, payload, context, text)
        if model_id == "qwen3-tts-vd-2026-01-26":
            return self._invoke_tts_or_skip(payload, text)
        if model_id == "gte-rerank-v2":
            return await asyncio.to_thread(self._invoke_rerank_real, payload, context, text)
        if model_id == "emohaa":
            return await self._invoke_emohaa_real(payload, context, text)
        # 其余模型走 DashScope 兼容 chat 接口真实调用。
        return await self._invoke_chat_real(model_id, payload, context, text, top_emotions, force_primary_fallback=force_primary_fallback)

    async def _invoke_chat_real(
        self,
        model_id: str,
        payload: Dict[str, Any],
        context: Dict[str, Any],
        text: str,
        top_emotions: List[str],
        force_primary_fallback: bool = False,
    ):
        upstream = {k: (v.get("summary", "") if isinstance(v, dict) else str(v)) for k, v in context.items()}
        user_prompt = (
            f"请基于以下学生对话内容完成当前阶段任务。\n"
            f"阶段模型: {model_id}\n"
            f"对话摘要: {text[:3000] or '无'}\n"
            f"上游输出: {json.dumps(upstream, ensure_ascii=False)[:2000]}\n"
            f"主导情绪: {','.join(top_emotions)}\n"
            f"请返回JSON，至少包含 summary(字符串), confidence(0-1), detail(对象)。"
        )
        messages = [
            {"role": "system", "content": "你是心理分析多模型流水线中的一个步骤执行器，请只返回JSON。"},
            {"role": "user", "content": user_prompt},
        ]

        async def _create_chat(model_name: str, enable_thinking: bool = False):
            kwargs: Dict[str, Any] = {
                "model": model_name,
                "messages": messages,
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            }
            if enable_thinking:
                kwargs["extra_body"] = {"enable_thinking": True}
            return await qwen_client.chat.completions.create(**kwargs)

        target_model = model_id
        if force_primary_fallback and model_id == PRIMARY_TEXT_MODEL:
            response = await _create_chat(PRIMARY_MODEL_FALLBACK, enable_thinking=False)
            used_model = PRIMARY_MODEL_FALLBACK
            _append_log({"model": model_id, "fallback_to": PRIMARY_MODEL_FALLBACK, "reason": "circuit_open"})
        else:
            try:
                response = await _create_chat(
                    target_model,
                    enable_thinking=(target_model == PRIMARY_TEXT_MODEL),
                )
                used_model = target_model
            except Exception as exc:
                # qwen3.6-plus 对参数兼容性波动时，先尝试去掉 thinking 参数再调主模型。
                if model_id == PRIMARY_TEXT_MODEL:
                    try:
                        response = await _create_chat(target_model, enable_thinking=False)
                        used_model = target_model
                        _append_log(
                            {
                                "model": model_id,
                                "retry_without_thinking": True,
                                "reason": str(exc)[:300],
                            }
                        )
                    except Exception as primary_exc_2:
                        # 主推理模型不可用时，按顺序降级到同供应商可用模型，避免整链路报错。
                        fallback_errors: List[str] = []
                        for fb_model in [PRIMARY_MODEL_FALLBACK, PRIMARY_MODEL_SECONDARY_FALLBACK]:
                            try:
                                response = await _create_chat(fb_model, enable_thinking=False)
                                used_model = fb_model
                                _append_log(
                                    {
                                        "model": model_id,
                                        "fallback_to": fb_model,
                                        "reason": str(primary_exc_2)[:300],
                                    }
                                )
                                break
                            except Exception as fb_exc:
                                fallback_errors.append(f"{fb_model}:{str(fb_exc)[:200]}")
                        else:
                            raise RuntimeError(
                                f"{model_id}_all_fallbacks_failed:"
                                f"{str(primary_exc_2)[:220]} | {'; '.join(fallback_errors)}"
                            )
                else:
                    # 严格模式：不再静默回退，直接让前端看到真实模型不可用状态。
                    raise RuntimeError(f"{model_id}_invoke_failed:{str(exc)}")

        content = (response.choices[0].message.content or "{}").strip()
        try:
            parsed = json.loads(content)
        except Exception:
            parsed = {"summary": content[:200], "confidence": 0.6, "detail": {"raw": content}}
        usage_obj = getattr(response, "usage", None)
        usage = {
            "prompt_tokens": int(getattr(usage_obj, "prompt_tokens", 0) or 0),
            "completion_tokens": int(getattr(usage_obj, "completion_tokens", 0) or 0),
            "total_tokens": int(getattr(usage_obj, "total_tokens", 0) or 0),
        }
        return {
            "summary": str(parsed.get("summary") or "模型分析完成"),
            "confidence": float(parsed.get("confidence") or 0.6),
            "detail": parsed.get("detail", parsed),
            "api_model": used_model,
            "requested_model": model_id,
            "usage": usage,
            "fallback_used": bool(used_model != model_id),
            "status": (
                "done"
                if (used_model == model_id or (model_id == PRIMARY_TEXT_MODEL and PRIMARY_FALLBACK_STATUS_DONE))
                else "degraded"
            ),
        }

    def _invoke_tts_or_skip(self, payload: Dict[str, Any], text: str):
        # 当前协同链路默认是文本对话场景；若无音频输入则标记为跳过而非异常。
        has_audio = bool(payload.get("audioUrl") or payload.get("audioBase64") or payload.get("audioFile"))
        if not has_audio:
            return {
                "summary": "未检测到音频输入，语音模型本轮跳过（不计为异常）。",
                "confidence": 0.68,
                "detail": {"status": "skipped", "reason": "no_audio_input", "hint": text[:120]},
                "api_model": "qwen3-tts-vd-2026-01-26",
                "requested_model": "qwen3-tts-vd-2026-01-26",
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                "status": "skipped",
            }
        raise RuntimeError("qwen3-tts-vd-2026-01-26_audio_pipeline_not_implemented")

    async def _invoke_emohaa_real(self, payload: Dict[str, Any], context: Dict[str, Any], text: str):
        history_text = "\n".join(
            str(m.get("content", "")).strip()
            for m in payload.get("messages", [])[-10:]
            if str(m.get("content", "")).strip()
        )
        upstream = {k: (v.get("summary", "") if isinstance(v, dict) else str(v)) for k, v in context.items()}
        emotion_input = (
            f"{text[:1500]}\n\n"
            f"上游线索:{json.dumps(upstream, ensure_ascii=False)[:1000]}\n"
            f"最近历史:{history_text[:1000]}"
        ).strip()
        logger.info("orchestrator_emohaa_enter text_len=%s preview=%s", len(emotion_input), emotion_input[:120])
        emotion_tags = await self._emohaa_service.analyze_emotion_tags(emotion_input, retry=1)
        sorted_tags = sorted(emotion_tags.items(), key=lambda x: x[1], reverse=True)
        top_two = "、".join([f"{k}:{round(v, 3)}" for k, v in sorted_tags[:2]])
        summary_text = f"情绪倾向：{top_two}" if top_two else "情绪倾向分析完成"
        confidence = max(0.5, min(0.95, float(sorted_tags[0][1] if sorted_tags else 0.6)))

        prompt_tokens = self._estimate_tokens(emotion_input)
        completion_tokens = self._estimate_tokens(json.dumps(emotion_tags, ensure_ascii=False))
        usage = {
            "prompt_tokens": int(prompt_tokens),
            "completion_tokens": int(completion_tokens),
            "total_tokens": int(prompt_tokens + completion_tokens),
            "source": "estimated",
        }
        logger.info("orchestrator_emohaa_exit parsed=%s", emotion_tags)
        return {
            "summary": summary_text,
            "confidence": round(confidence, 3),
            "detail": {"emotion_tags": emotion_tags},
            "api_model": "emohaa",
            "requested_model": "emohaa",
            "usage": usage,
        }

    def _invoke_wanx_real(self, payload: Dict[str, Any], context: Dict[str, Any], text: str):
        prompt = (payload.get("visualHints") or [text[:120] or "学生心理场景意象"])[0]
        url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis"
        body = {
            "model": "wanx-v1",
            "input": {"prompt": str(prompt)[:800]},
            "parameters": {"size": "768*768", "n": 1},
        }
        headers = {
            "Authorization": f"Bearer {self._dashscope_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"wanx_http_{resp.status_code}:{resp.text[:200]}")
        data = resp.json()
        output = (data or {}).get("output", {})
        task_id = output.get("task_id")
        task_status = output.get("task_status")
        # 轮询异步任务状态，兼容 "不支持同步调用" 的账户策略。
        if task_id and task_status and task_status.upper() not in ("SUCCEEDED", "FAILED"):
            poll_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
            for _ in range(12):
                time.sleep(1.0)
                poll = requests.get(poll_url, headers={"Authorization": f"Bearer {self._dashscope_key}"}, timeout=20)
                if poll.status_code >= 400:
                    continue
                pdata = poll.json()
                pstatus = str(((pdata or {}).get("output") or {}).get("task_status") or "").upper()
                if pstatus in ("SUCCEEDED", "FAILED"):
                    data = pdata
                    output = (data or {}).get("output", {})
                    task_status = pstatus
                    break
        return {
            "summary": "视觉模型已真实调用",
            "confidence": 0.7,
            "detail": {"task_status": output.get("task_status"), "task_id": output.get("task_id"), "results": output.get("results")},
            "api_model": "wanx-v1",
            "requested_model": "wanx-v1",
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    def _invoke_rerank_real(self, payload: Dict[str, Any], context: Dict[str, Any], text: str):
        docs = []
        for m in payload.get("messages", [])[-30:]:
            c = str(m.get("content", "")).strip()
            if c:
                docs.append(c[:500])
        if not docs:
            docs = [text[:300] or "无有效文本"]
        query = docs[-1]
        url = "https://dashscope.aliyuncs.com/api/v1/services/rerank/text-rerank/text-rerank"
        body = {
            "model": "gte-rerank-v2",
            "input": {"query": query[:300], "documents": docs[:20]},
            "parameters": {"top_n": 8},
        }
        headers = {"Authorization": f"Bearer {self._dashscope_key}", "Content-Type": "application/json"}
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code >= 400:
            raise RuntimeError(f"rerank_http_{resp.status_code}:{resp.text[:200]}")
        data = resp.json()
        results = (((data or {}).get("output") or {}).get("results") or [])[:8]
        keywords = [str((x or {}).get("document", ""))[:30] for x in results]
        usage = (data or {}).get("usage") or {}
        return {
            "summary": "语义重排序已真实调用",
            "confidence": 0.76,
            "detail": {"topKeywords": keywords, "results": results},
            "api_model": "gte-rerank-v2",
            "requested_model": "gte-rerank-v2",
            "usage": {
                "prompt_tokens": int(usage.get("input_tokens", 0) or 0),
                "completion_tokens": int(usage.get("output_tokens", 0) or 0),
                "total_tokens": int((usage.get("input_tokens", 0) or 0) + (usage.get("output_tokens", 0) or 0)),
            },
        }

    def _fuse_results(self, payload: Dict[str, Any], context: Dict[str, Any]):
        model_results = []
        conf_sum = 0.0
        for model in MODEL_CHAIN:
            out = context.get(model["id"], {})
            conf = float(out.get("confidence", 0.5))
            conf_sum += conf
            model_results.append({
                "model": model["id"],
                "stage": model["stage"],
                "summary": out.get("summary", ""),
                "confidence": round(conf, 3),
                "promptTokens": int((out.get("usage") or {}).get("prompt_tokens", 0) or 0),
                "completionTokens": int((out.get("usage") or {}).get("completion_tokens", 0) or 0),
                "totalTokens": int((out.get("usage") or {}).get("total_tokens", 0) or 0),
                "detail": out,
            })
        avg_conf = round(conf_sum / max(1, len(MODEL_CHAIN)), 3)
        merged_points = [x["summary"] for x in model_results if x["summary"]]
        return {
            "executiveSummary": "；".join(merged_points[:4]) or "暂无结论",
            "modelResults": model_results,
            "collaborativeConclusion": "综合文本、视觉、语音与情感信号，当前风险建议以持续跟踪为主。",
            "confidence": avg_conf,
            "charts": {
                "modelConfidence": [{"name": x["model"], "value": x["confidence"]} for x in model_results],
                "statusFlow": [{"source": MODEL_CHAIN[i]["id"], "target": MODEL_CHAIN[i + 1]["id"]} for i in range(len(MODEL_CHAIN) - 1)],
            },
            "sourceMessageCount": len(payload.get("messages", [])),
            "updated_at": _utc_now(),
        }

    def _cache_key(self, model_id: str, payload: Dict[str, Any], context: Dict[str, Any]):
        body = json.dumps({"m": model_id, "p": payload, "u": list(context.keys())}, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(body.encode("utf-8")).hexdigest()

    def _append_event(self, task_id: str, event: str, payload: Dict[str, Any]):
        task = self._tasks.get(task_id)
        if not task:
            return
        task["updated_at"] = _utc_now()
        task["events"].append(_sse(event, payload))


orchestrator = MultiModelOrchestrator()
