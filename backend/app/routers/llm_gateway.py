import json
import re
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["llm-gateway"])


class GenerateRequest(BaseModel):
    prompt: str


def _build_structured_fallback(prompt: str) -> Dict[str, Any]:
    negative_tokens = ("自杀", "自残", "崩溃", "绝望", "活不下去", "痛苦", "失眠", "焦虑", "抑郁")
    medium_tokens = ("压力", "烦躁", "紧张", "低落")
    level = "LOW"
    if any(token in prompt for token in negative_tokens):
        level = "HIGH"
    elif any(token in prompt for token in medium_tokens):
        level = "MEDIUM"

    base_map = {
        "LOW": (28, 35, 20),
        "MEDIUM": (56, 62, 35),
        "HIGH": (82, 86, 68),
    }
    depression, anxiety, suicide = base_map[level]
    emotion_score = min(100, max(depression, anxiety) - 10)
    cognition_score = min(100, max(20, anxiety - 8))
    behavior_score = min(100, max(20, depression - 5))

    return {
        "emotion_score": emotion_score,
        "cognition_score": cognition_score,
        "behavior_score": behavior_score,
        "depression_confidence": depression,
        "anxiety_confidence": anxiety,
        "suicide_confidence": suicide,
        "risk_level": level,
        "interventions": [
            "先把今天的目标缩减到1-2件最重要的小事，降低心理负荷。",
            "今晚固定留出20分钟放松时段（散步、拉伸或呼吸训练）。",
            "若连续两天情绪明显恶化，尽快预约学校心理咨询。",
        ],
        "chart_insights": {
            "bar": "风险维度呈中高压状态，建议优先处理睡眠与学习节奏。",
            "pie": "负性情绪占比偏高，近期需要增加恢复性活动和支持性互动。",
            "heatmap": "高压时段有聚集迹象，建议在高峰前安排短时减压。",
            "trend": "趋势存在波动，短期先以稳定作息与降低透支为目标。",
            "network": "情绪与认知互相放大，建议使用记录法中断反刍。",
            "histogram": "中高风险区出现频率提升，建议设置预警阈值并及时求助。",
        },
    }


def _build_interpretation_fallback(prompt: str) -> str:
    clean_text = re.sub(r"\s+", " ", prompt).strip()
    if len(clean_text) > 180:
        clean_text = clean_text[:180] + "..."
    return (
        "从这段对话看，你近期压力感偏高，情绪在疲惫和担忧之间波动。"
        "建议先把学习任务拆小并固定休息节律，每天留出可恢复精力的活动；"
        "如果连续出现失眠、明显低落或无助感，请尽快预约心理咨询。"
    )


@router.post("/generate")
def generate_text(req: GenerateRequest):
    prompt = req.prompt or ""
    wants_structured_json = "严格JSON" in prompt or "risk_level" in prompt or "chart_insights" in prompt
    if wants_structured_json:
        payload = _build_structured_fallback(prompt)
        text = json.dumps(payload, ensure_ascii=False)
        return {"text": text, "result": text}

    text = _build_interpretation_fallback(prompt)
    return {"text": text, "result": text}


@router.post("/api/llm/generate")
def generate_text_alias(req: GenerateRequest):
    return generate_text(req)
