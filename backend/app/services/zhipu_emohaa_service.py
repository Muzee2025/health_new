import asyncio
import json
import logging
import os
import re
import sys
import time
from typing import Any, Dict, List

import requests

logger = logging.getLogger(__name__)


class ZhipuEmohaaService:
    """使用 Zhipu emohaa 作为学生端心理助手对话模型。"""

    EMOTION_KEYS = ("joy", "sadness", "neutral", "fear", "anxiety", "anger")
    DEFAULT_EMOTION_TAGS = {
        "joy": 0.0,
        "sadness": 0.0,
        "neutral": 1.0,
        "fear": 0.0,
        "anxiety": 0.0,
        "anger": 0.0,
    }

    def __init__(self) -> None:
        # 优先读取环境变量，未配置时使用当前项目默认值
        api_key = os.getenv("ZHIPU_API_KEY", "").strip()
        self.api_key = api_key
        self.base_url = os.getenv("ZHIPU_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
        self.client = None
        self.provider = "http"

        # zai-sdk 在 Python 3.14+ 下会触发 pydantic.v1 兼容警告，改为 HTTP 模式避免告警与潜在不稳定。
        if self.api_key and sys.version_info < (3, 14):
            try:
                from zai import ZhipuAiClient  # 延迟导入，避免 3.14 启动时触发 pydantic.v1 warning

                self.client = ZhipuAiClient(api_key=api_key)
                self.provider = "zai_sdk"
            except Exception:  # noqa: BLE001
                logger.warning("zai_sdk_unavailable_fallback_to_http")

    def _http_chat_completion(
        self,
        messages: List[Dict[str, Any]],
        stream: bool,
        meta: Dict[str, str] | None = None,
        trace_id: str | None = None,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("Emotion provider is not configured")
        url = f"{self.base_url}/chat/completions"
        payload: Dict[str, Any] = {
            "model": "emohaa",
            "messages": messages,
            "stream": stream,
        }
        if meta:
            payload["meta"] = meta
        req_started = time.perf_counter()
        logger.info("emohaa_http_request trace_id=%s message_count=%s", trace_id or "-", len(messages))

        resp = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=60,
        )
        req_elapsed_ms = round((time.perf_counter() - req_started) * 1000, 2)
        logger.info("emohaa_http_response trace_id=%s status=%s latency_ms=%s", trace_id or "-", resp.status_code, req_elapsed_ms)
        resp.raise_for_status()
        if stream:
            parts: List[str] = []
            for line in resp.text.splitlines():
                raw = line.strip()
                if not raw or not raw.startswith("data:"):
                    continue
                data = raw[5:].strip()
                if data == "[DONE]":
                    break
                try:
                    obj = json.loads(data)
                except Exception:
                    continue
                delta = (((obj.get("choices") or [{}])[0].get("delta") or {}).get("content") or "")
                if delta:
                    parts.append(delta)
            return "".join(parts).strip()

        obj = resp.json()
        return str((((obj.get("choices") or [{}])[0].get("message") or {}).get("content") or "")).strip()

    @staticmethod
    def _meta_for_mode(mode: str) -> Dict[str, str]:
        if mode == "counseling":
            return {
                "user_info": "一位高校学生，近期希望获得心理支持与压力疏导",
                "bot_info": "专业的心理咨询师，擅长情绪支持、认知重建和压力管理",
                "bot_name": "心理咨询师",
                "user_name": "学生",
            }
        return {
            "user_info": "一位高校学生，正在进行日常聊天，可能有学习和生活压力",
            "bot_info": "温和、共情的校园心理助手，擅长主动引导式聊天",
            "bot_name": "心域智链",
            "user_name": "学生",
        }

    @staticmethod
    def _convert_history(history: List[Dict[str, Any]] | None) -> List[Dict[str, str]]:
        if not history:
            return []
        converted: List[Dict[str, str]] = []
        for item in history[-10:]:
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "ai":
                role = "assistant"
            if role not in ("user", "assistant", "system"):
                role = "user"
            converted.append({"role": role, "content": content})
        return converted

    def _chat_sync(self, message: str, history: List[Dict[str, Any]] | None, mode: str) -> str:
        messages = self._convert_history(history)
        messages.append({"role": "user", "content": message})

        if self.provider == "zai_sdk" and self.client is not None:
            stream = self.client.chat.completions.create(
                model="emohaa",
                messages=messages,
                meta=self._meta_for_mode(mode),
                stream=True,
            )
            parts: List[str] = []
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except Exception:
                    delta = None
                if delta:
                    parts.append(delta)
            text = "".join(parts).strip()
        else:
            text = self._http_chat_completion(messages=messages, stream=True, meta=self._meta_for_mode(mode))
        return text or "我在这里，愿意继续听你说。你现在最想先聊哪件事？"

    @staticmethod
    def _is_effective_text(text: str) -> bool:
        clean = str(text or "").strip()
        if not clean:
            return False
        # 至少要有一个中文、字母或数字，过滤纯符号输入
        return bool(re.search(r"[\u4e00-\u9fffA-Za-z0-9]", clean))

    def _normalize_emotion_tags(self, raw: Dict[str, Any] | None) -> Dict[str, float]:
        if not isinstance(raw, dict):
            return dict(self.DEFAULT_EMOTION_TAGS)

        alias_map = {
            "happy": "joy",
            "happiness": "joy",
            "depression": "sadness",
            "depressed": "sadness",
            "worry": "anxiety",
            "worried": "anxiety",
            "anxious": "anxiety",
            "panic": "fear",
            "scared": "fear",
            "mad": "anger",
        }

        normalized: Dict[str, float] = {}
        for key in self.EMOTION_KEYS:
            normalized[key] = 0.0

        for k, v in raw.items():
            key = alias_map.get(str(k).strip().lower(), str(k).strip().lower())
            if key not in normalized:
                continue
            try:
                value = float(v)
            except Exception:
                continue
            normalized[key] += max(0.0, min(1.0, value))

        total = sum(normalized.values())
        if total <= 0:
            return dict(self.DEFAULT_EMOTION_TAGS)

        # 归一化到总和约等于1
        for key in normalized:
            normalized[key] = round(normalized[key] / total, 4)

        # 防止浮点误差，收敛到 1.0
        fixed_total = round(sum(normalized.values()), 4)
        if abs(1.0 - fixed_total) > 1e-6:
            normalized["neutral"] = round(min(1.0, max(0.0, normalized["neutral"] + (1.0 - fixed_total))), 4)
            fixed_total2 = round(sum(normalized.values()), 4)
            if abs(1.0 - fixed_total2) > 0.02:
                return dict(self.DEFAULT_EMOTION_TAGS)
        return normalized

    @staticmethod
    def _extract_json_text(raw_text: str) -> str:
        text = str(raw_text or "").strip()
        if not text:
            return ""
        if text.startswith("```json"):
            return text[7:].replace("```", "").strip()
        if text.startswith("```"):
            return text[3:].replace("```", "").strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return match.group(0)
        return text

    def _parse_emotion_payload(self, raw_text: str) -> Dict[str, float]:
        candidate = self._extract_json_text(raw_text)
        if not candidate:
            return dict(self.DEFAULT_EMOTION_TAGS)
        try:
            parsed = json.loads(candidate)
        except Exception:
            logger.warning("emohaa_emotion_parse_failed")
            return dict(self.DEFAULT_EMOTION_TAGS)
        return self._normalize_emotion_tags(parsed if isinstance(parsed, dict) else {})

    def _analyze_emotion_sync(self, text: str, retry: int = 1) -> Dict[str, float]:
        clean = str(text or "").strip()
        logger.info("emohaa_emotion_enter chars=%s", len(clean))

        if not self._is_effective_text(clean):
            logger.info("emohaa_emotion_skip_invalid_input")
            return dict(self.DEFAULT_EMOTION_TAGS)

        prompt = (
            "请分析以下文本的情绪，并严格返回JSON对象，键必须且仅能包含："
            "joy,sadness,neutral,fear,anxiety,anger。"
            "每个值为0到1之间的小数，总和约等于1。"
            f"\n文本：{clean}\n"
            "只返回JSON，不要返回任何解释。"
        )
        for attempt in range(retry + 1):
            try:
                if self.provider == "zai_sdk" and self.client is not None:
                    response = self.client.chat.completions.create(
                        model="emohaa",
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                    )
                    raw_output = str(response.choices[0].message.content or "").strip()
                else:
                    raw_output = self._http_chat_completion(
                        messages=[{"role": "user", "content": prompt}],
                        stream=False,
                    )
                parsed = self._parse_emotion_payload(raw_output)
                logger.info("emohaa_emotion_exit attempt=%s", attempt + 1)
                return parsed
            except Exception as exc:
                logger.warning("emohaa_emotion_call_failed attempt=%s error=%s", attempt + 1, type(exc).__name__)
                if attempt < retry:
                    continue
        logger.error("emohaa_emotion_fallback")
        return dict(self.DEFAULT_EMOTION_TAGS)

    def _deep_think_sync(self, prompt: str, chat_context: str, mode: str, trace_id: str | None = None) -> str:
        system_prompt = (
            "你是高校心理支持场景下的深度分析助手。"
            "请基于给定聊天记录和历史洞察给出‘最终回应正文’，不要输出“思考过程”与“扩展反思”标题。"
            "要求：1) 先共情当前情绪；2) 给2-4条可执行建议；3) 结尾给一句温和支持。"
            "整体控制在180-320字，避免冗长说教。"
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"【聊天记录】\n{chat_context}\n\n"
                    f"【用户本次深度思考诉求】\n{prompt}\n\n"
                    "请直接给出分析结果。"
                ),
            },
        ]
        logger.info("emohaa_deep_think_request trace_id=%s provider=%s", trace_id or "-", self.provider)

        if self.provider == "zai_sdk" and self.client is not None:
            stream = self.client.chat.completions.create(
                model="emohaa",
                messages=messages,
                meta=self._meta_for_mode(mode),
                stream=True,
            )
            parts: List[str] = []
            for chunk in stream:
                try:
                    delta = chunk.choices[0].delta.content
                except Exception:
                    delta = None
                if delta:
                    parts.append(delta)
            text = "".join(parts).strip()
            logger.info("emohaa_deep_think_response trace_id=%s chars=%s", trace_id or "-", len(text))
        else:
            text = self._http_chat_completion(
                messages=messages,
                stream=True,
                meta=self._meta_for_mode(mode),
                trace_id=trace_id,
            )
        if not text.strip():
            raise RuntimeError(f"emohaa_empty_response trace_id={trace_id or '-'}")
        return text

    async def chat_with_student(
        self,
        user_id: str,
        message: str,
        history: List[Dict[str, Any]] | None = None,
        mode: str = "daily",
    ) -> str:
        try:
            return await asyncio.to_thread(self._chat_sync, message, history, mode)
        except Exception as e:
            logger.error("emohaa_request_failed error_type=%s", type(e).__name__)
            return "抱歉，我现在有些走神（网络波动），能重新说一遍吗？"

    async def deep_think_with_student(
        self,
        user_id: str,
        prompt: str,
        chat_context: str,
        mode: str = "daily",
        trace_id: str | None = None,
    ) -> str:
        try:
            return await asyncio.to_thread(self._deep_think_sync, prompt, chat_context, mode, trace_id)
        except Exception as e:
            logger.error("emohaa_deep_think_failed trace_id=%s error_type=%s", trace_id or "-", type(e).__name__)
            raise

    async def analyze_emotion_tags(self, text: str, retry: int = 1) -> Dict[str, float]:
        """
        使用 emohaa 提取 6 维情绪标签。
        - 输出维度: joy/sadness/neutral/fear/anxiety/anger
        - 输出范围: 0-1 且总和约等于1
        - 异常兜底: 返回 DEFAULT_EMOTION_TAGS
        """
        return await asyncio.to_thread(self._analyze_emotion_sync, text, retry)
