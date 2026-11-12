"""
DeepSeek 对话与用户上下文封装。
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import List, Sequence

import requests
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from app import models

load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

DEEPSEEK_CHAT_URL = "https://api.deepseek.com/v1/chat/completions"
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# 简易情感相关词（用于帖子文本粗粒度线索，非专业心理评估）
POSITIVE_HINTS: tuple[str, ...] = (
    "开心",
    "快乐",
    "谢谢",
    "喜欢",
    "期待",
    "轻松",
    "棒",
    "好耶",
    "顺利",
)
NEGATIVE_HINTS: tuple[str, ...] = (
    "焦虑",
    "难过",
    "压力",
    "累",
    "失眠",
    "抑郁",
    "烦",
    "孤独",
    "害怕",
    "绝望",
    "崩溃",
    "不想活",
)


def _mean(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _trend_label(values: Sequence[float], label: str) -> str:
    """用前半段与后半段均值比较判断上升/下降/稳定。"""
    n = len(values)
    if n < 2:
        return f"{label}：数据不足，无法判断趋势"
    mid = n // 2
    first = values[:mid]
    second = values[mid:]
    a = _mean(first)
    b = _mean(second)
    if a == 0 and b == 0:
        return f"{label}趋势为「稳定」"
    if a == 0:
        trend = "上升" if b > 0 else "稳定"
        return f"{label}趋势为「{trend}」"
    ratio = b / a
    if ratio > 1.05:
        trend = "上升"
    elif ratio < 0.95:
        trend = "下降"
    else:
        trend = "稳定"
    return f"{label}趋势为「{trend}」（近段相对前段约 {ratio:.0%}）"


def _emotion_summary(text: str) -> str:
    if not text.strip():
        return "最近帖子内容较少，情绪关键词不明显。"
    pos_hits = [w for w in POSITIVE_HINTS if w in text]
    neg_hits = [w for w in NEGATIVE_HINTS if w in text]
    if not pos_hits and not neg_hits:
        return "从简单词库看，情绪倾向不明显；可关注用户具体表述。"
    if len(neg_hits) > len(pos_hits):
        return f"文本中出现偏沉重/负面线索词较多（示例：{', '.join(neg_hits[:5])}），需更多倾听与支持。"
    if len(pos_hits) > len(neg_hits):
        return f"文本中出现偏积极线索词较多（示例：{', '.join(pos_hits[:5])}）。"
    return f"正负面线索词并存（如 {', '.join((pos_hits + neg_hits)[:5])}），宜结合上下文理解。"


def get_user_context(db: Session, user_id: int, include_recent_conversations: bool = True) -> str:
    """
    汇总用户近期传感器、帖子、对话，形成一段供系统提示使用的文字描述。
    （需要数据库会话，由路由层注入。）
    """
    lines: List[str] = []

    end = date.today()
    start = end - timedelta(days=6)
    records = (
        db.query(models.SensorRecord)
        .filter(
            models.SensorRecord.user_id == user_id,
            models.SensorRecord.date >= start,
            models.SensorRecord.date <= end,
        )
        .order_by(models.SensorRecord.date.asc())
        .all()
    )
    if not records:
        lines.append("【运动与屏幕】近7天暂无传感器记录。")
    else:
        steps = [float(r.steps) for r in records]
        screens = [float(r.screen_time_hours) for r in records]
        lines.append(
            f"【运动与屏幕】近7天共{len(records)}天有记录；"
            f"步数日均约{int(_mean(steps))}步，屏幕时间日均约{_mean(screens):.1f}小时。"
            f"{_trend_label(steps, '步数')}；{_trend_label(screens, '屏幕时间')}。"
        )

    posts = (
        db.query(models.Post)
        .filter(models.Post.user_id == user_id)
        .order_by(models.Post.created_at.desc())
        .limit(3)
        .all()
    )
    if not posts:
        lines.append("【社区发帖】最近无帖子。")
    else:
        blob = " ".join(f"{p.title} {p.content}" for p in posts)
        lines.append("【社区发帖】最近3条帖子主题摘录（供感受线索，非诊断）：")
        for p in posts:
            snippet = (p.title + " " + p.content)[:120].replace("\n", " ")
            lines.append(f"  - {snippet}{'…' if len(p.title) + len(p.content) > 120 else ''}")
        lines.append(_emotion_summary(blob))

    if include_recent_conversations:
        convs = (
            db.query(models.Conversation)
            .filter(models.Conversation.user_id == user_id)
            .order_by(models.Conversation.created_at.desc())
            .limit(3)
            .all()
        )
        convs_chrono = list(reversed(convs))
        if not convs_chrono:
            lines.append("【历史对话】暂无最近对话记录。")
        else:
            lines.append("【历史对话】最近3轮摘要：")
            for i, c in enumerate(convs_chrono, 1):
                um = (c.message or "")[:80].replace("\n", " ")
                ar = (c.response or "")[:80].replace("\n", " ")
                lines.append(f"  {i}) 用户：{um}{'…' if len(c.message or '') > 80 else ''}")
                lines.append(f"     助手：{ar}{'…' if len(c.response or '') > 80 else ''}")
    else:
        lines.append("【历史对话】用户正在开启新对话，请以当下问题为中心，减少对过往具体对话的引用。")

    return "\n".join(lines)


def build_system_prompt(user_context: str) -> str:
    return (
        "你是一个温暖、亲切、体贴的校园心理助手，像值得信赖的学姐/学长一样陪伴用户。\n"
        "用户近期行为特征（来自应用内数据汇总，仅供参考，不能作为诊断依据）：\n"
        f"{user_context}\n\n"
        "请基于以上背景，先共情再建议，语气要有温度，避免机械化回答；\n"
        "回复中尽量包含：1句情绪接住 + 1句具体理解 + 2-3条可执行的小建议；\n"
        "必要时可用轻柔鼓励语，如“你愿意说出来已经很不容易”；\n"
        "不要进行医学诊断或贴心理疾病标签，不要替代专业心理咨询或危机干预；\n"
        "若涉及自伤、自杀或紧急风险，应温和鼓励用户尽快联系身边可信成年人、学校心理中心或当地紧急求助热线。\n"
        "语气简洁、温和、有边界感，长度约120-220字。"
    )


def call_deepseek(user_message: str, system_prompt: str) -> str:
    """
    调用 DeepSeek Chat Completions API，返回助手文本内容。
    """
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key or not api_key.strip() or api_key == "your_deepseek_api_key_here":
        raise RuntimeError("未配置有效的 DEEPSEEK_API_KEY，请在 backend/.env 中设置。")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
    }
    resp = requests.post(DEEPSEEK_CHAT_URL, json=payload, headers=headers, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"DeepSeek 返回格式异常: {data}") from e


def save_conversation(
    db: Session, *, user_id: int, message: str, response: str
) -> models.Conversation:
    row = models.Conversation(user_id=user_id, message=message, response=response)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
