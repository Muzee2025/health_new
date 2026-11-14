"""Stateless helpers used by the advanced chat router."""

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


def _default_emotion_tags() -> Dict[str, float]:
    return {
        "joy": 0.0,
        "sadness": 0.0,
        "neutral": 1.0,
        "fear": 0.0,
        "anxiety": 0.0,
        "anger": 0.0,
    }


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


def _build_context_snapshot(history: List[Dict[str, str]]) -> Dict[str, Any]:
    trimmed = history[-8:] if history else []
    return {
        "turns": len(trimmed),
        "messages": trimmed,
    }


def _calc_sentiment_score(emotions: Dict[str, float]) -> int:
    joy = float(emotions.get("joy", 0))
    neg = (float(emotions.get("sadness", 0)) + float(emotions.get("fear", 0)) + float(emotions.get("anger", 0))) / 3
    score = (joy * 0.65 + (1 - neg) * 0.35) * 100
    return max(0, min(100, int(round(score))))


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


def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b, strict=True))
    norm_a = sum(a * a for a in vec_a) ** 0.5
    norm_b = sum(b * b for b in vec_b) ** 0.5
    if norm_a <= 0 or norm_b <= 0:
        return 0.0
    return dot / (norm_a * norm_b)
