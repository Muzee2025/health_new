import json
import logging
import os
from typing import Any, Dict, List

import openai

logger = logging.getLogger(__name__)

def _configured_client():
    """External provider calls stay disabled unless explicitly enabled and configured."""
    if os.getenv("AI_EXTERNAL_ENABLED", "").strip().lower() not in {"1", "true", "yes"}:
        return None
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        return None
    return openai.AsyncOpenAI(api_key=api_key, base_url="https://dashscope.aliyuncs.com/compatible-mode/v1", timeout=12.0, max_retries=0)


client = _configured_client()

class QwenAiService:
    """通义千问 LLM 交互服务，注入 3 层安全护栏与 CBT 话术"""

    async def chat_with_student(self, user_id: str, message: str, history: List[Dict] = None, mode: str = "daily") -> str:
        """
        调用 Qwen 进行日常闲聊与 CBT 心理干预
        """
        base_prompt = "你是一位高校心理老师的AI助手，名叫'心域智链'。"
        
        if mode == "daily":
            system_prompt = (
                f"{base_prompt} "
                "当前是【日常聊天模式】。你需要像朋友一样倾听，主动引导式聊天，发掘用户可能感兴趣的话题，让用户更愿意和你说话。"
                "要求：1. 语气温和活泼；2. 不用过于严肃；3. 适时抛出轻松的问题引导用户多说。"
            )
        else:
            system_prompt = (
                f"{base_prompt} "
                "当前是【心理咨询模式】。你需要使用CBT（认知行为疗法）倾听学生的心声，帮助他们识别负面自动思维。"
                "要求：1. 语气温和、共情；2. 绝不提供医学诊断；3. 引导用户深入剖析压力来源。"
            )

        system_prompt += (
            "【安全护栏】：如果用户提及自杀、自残、严重暴力或政治敏感话题，请立即停止心理分析，"
            "并回复：'我感受到您现在非常痛苦。请先联系身边可信任的人或当地紧急服务；如有校内心理服务，请通过学校公布的官方渠道联系。系统目前无法核验热线号码或值守时段。'"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": message})

        if client is None:
            return "当前未配置可用的外部模型服务，不能把本地回复标记为AI结果。你可以稍后再试，或通过学校公布的官方渠道联系心理服务人员。"
        try:
            response = await client.chat.completions.create(
                model="qwen-plus",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error("Qwen API unavailable (%s)", type(e).__name__)
            return "抱歉，我现在有些走神（网络波动），能重新说一遍吗？"

    async def generate_report_from_chats(self, chat_logs: List[str]) -> Dict[str, Any]:
        """
        基于用户近期的真实聊天记录，生成综合心理评估报告及图表解读
        """
        if not chat_logs:
            return {
                "status": "insufficient_data",
                "source": "local_rule",
                "model_id": None,
                "overall_status": "数据不足，暂不能形成综合判断。",
                "chart_interpretations": {
                    "emotion_trend": "暂无足够数据分析情绪趋势。",
                    "stress_index": "暂无足够数据分析压力指数。",
                    "risk_level": "暂无足够数据判断风险状态。"
                }
            }

        if client is None:
            return {"status": "fallback", "source": "local_rule", "model_id": None,
                "overall_status": "当前未配置可用的外部模型服务，未生成模型报告。", "chart_interpretations": {
                "emotion_trend": "数据仅供本人观察，当前未执行模型分析。", "stress_index": "资料不足，未执行模型分析。", "risk_level": "暂无足够数据判断风险状态。"}}

        record_count = sum(1 for entry in chat_logs if isinstance(entry, str) and entry.strip())
        if record_count == 0:
            return {"status": "insufficient_data", "source": "local_rule", "model_id": None,
                "overall_status": "数据不足，暂不能形成综合判断。", "chart_interpretations": {
                    "emotion_trend": "暂无足够数据分析情绪趋势。", "stress_index": "暂无足够数据分析压力变化。", "risk_level": "暂无足够数据判断风险状态。"}}

        # Only an aggregate count is sent. Chat text, names and identifiers stay local.
        prompt = json.dumps({
            "record_count": record_count,
            "instruction": "条数本身不足以推断心理状态、趋势、因果或风险；请明确资料不足，给出通用且非诊断性的自我观察提示。",
            "required_json": {"overall_status": "string, max 300 chars", "chart_interpretations": {
                "emotion_trend": "string", "stress_index": "string", "risk_level": "string"}},
        }, ensure_ascii=False)

        try:
            response = await client.chat.completions.create(
                model="qwen-plus",
                messages=[
                    {"role": "system", "content": "只输出满足要求的JSON。不得推断诊断、风险等级、趋势或因果；计数不是心理证据。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            result = json.loads(content)
            interpretations = result.get("chart_interpretations") if isinstance(result, dict) else None
            if (not isinstance(result, dict) or set(result) != {"overall_status", "chart_interpretations"}
                    or not isinstance(result.get("overall_status"), str)
                    or not result["overall_status"].strip() or len(result["overall_status"]) > 300
                    or not isinstance(interpretations, dict)
                    or set(interpretations) != {"emotion_trend", "stress_index", "risk_level"}
                    or any(not isinstance(interpretations.get(key), str) or not interpretations[key].strip() or len(interpretations[key]) > 300
                           for key in ("emotion_trend", "stress_index", "risk_level"))):
                raise ValueError("invalid report schema")
            all_text = " ".join([result["overall_status"], *interpretations.values()])
            unsupported_claims = ("平稳", "正常", "上升", "下降", "波动", "高风险", "低风险", "预警", "诊断", "导致", "因为", "主要来源", "概率")
            if any(claim in all_text for claim in unsupported_claims):
                raise ValueError("unsupported interpretation from aggregate-only input")
            model_id = getattr(response, "model", None)
            if not isinstance(model_id, str) or not model_id.strip() or len(model_id) > 120:
                model_id = None
            result.update({"status": "completed", "source": "provider", "model_id": model_id})
            return result
        except Exception as e:
            logger.error("Qwen report unavailable (%s)", type(e).__name__)
            return {
                "status": "fallback",
                "source": "local_rule",
                "model_id": None,
                "overall_status": "模型未返回符合约定的内容，已降级到本地说明。",
                "chart_interpretations": {
                    "emotion_trend": "资料不足，暂不能解读趋势。",
                    "stress_index": "资料不足，暂不能解读压力变化。",
                    "risk_level": "暂无足够数据判断风险状态。"
                }
            }
