import json
import logging
from typing import Dict, Any, List
import openai

logger = logging.getLogger(__name__)

# 配置通义千问大模型客户端
client = openai.AsyncOpenAI(
    api_key="sk-6081658a77294de599b7e22980adf29c",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
)

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
            "并回复：'我感受到您现在非常痛苦，请务必保护好自己。请立即拨打校内24小时心理危机热线：400-123-4567。'"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if history:
            messages.extend(history)
        
        messages.append({"role": "user", "content": message})

        try:
            response = await client.chat.completions.create(
                model="qwen-plus",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Qwen API Error: {str(e)}")
            return "抱歉，我现在有些走神（网络波动），能重新说一遍吗？"

    async def generate_report_from_chats(self, chat_logs: List[str]) -> Dict[str, Any]:
        """
        基于用户近期的真实聊天记录，生成综合心理评估报告及图表解读
        """
        if not chat_logs:
            return {
                "overall_status": "数据不足，建议多和我聊聊天哦。",
                "chart_interpretations": {
                    "emotion_trend": "暂无足够数据分析情绪趋势。",
                    "stress_index": "暂无足够数据分析压力指数。",
                    "risk_level": "当前状态平稳。"
                }
            }

        chat_context = "\n".join(chat_logs[-30:]) # 取最近的聊天记录防止超长

        prompt = f"""
        请根据以下学生近期的真实聊天记录，生成一份心理健康评估报告，并对图表含义进行解读。
        聊天记录：
        {chat_context}

        请以严格的JSON格式返回，包含以下字段：
        1. "overall_status": 基于聊天记录的一段综合评价（不超过150字，以第二人称对学生说）。
        2. "chart_interpretations": 一个对象，包含对以下三个图表的具体解读（结合聊天内容）：
           - "emotion_trend": 情绪趋势图解读，说明为何有情绪波动。
           - "stress_index": 压力指数变化解读，点出压力主要来源。
           - "risk_level": 风险预警等级解读，解释当前处于什么等级（正常/关注/预警）以及建议。
        """

        try:
            response = await client.chat.completions.create(
                model="qwen-plus",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                response_format={"type": "json_object"}
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except Exception as e:
            logger.error(f"Qwen Report Generation Error: {str(e)}")
            return {
                "overall_status": "生成报告时遇到网络波动，请稍后再试。",
                "chart_interpretations": {
                    "emotion_trend": "AI 分析生成中...",
                    "stress_index": "AI 分析生成中...",
                    "risk_level": "AI 分析生成中..."
                }
            }
