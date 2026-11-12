"""Pure local rule fallback, shared without HTTP self-calls or identity bypasses."""
import ipaddress
from typing import Any, Dict
from urllib.parse import urlsplit


def is_local_fallback_url(url: str) -> bool:
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        local = host in ("localhost", "llm-internal")
        try:
            local = local or ipaddress.ip_address(host).is_loopback
        except ValueError:
            pass
        return local and parsed.path.rstrip("/") in ("/generate", "/api/llm/generate")
    except ValueError:
        return True


def _build_structured_fallback(prompt: str) -> Dict[str, Any]:
    # Keywords in an instruction or a conversation are not calibrated scores.
    # In particular, never infer HIGH from the diagnostic words in the prompt.
    return {
        "emotion_score": None,
        "cognition_score": None,
        "behavior_score": None,
        "depression_confidence": None,
        "anxiety_confidence": None,
        "suicide_confidence": None,
        "risk_level": "UNKNOWN",
        "source": "local_rules",
        "status": "fallback",
        "model_id": None,
        "interventions": [
            "可以先记录此刻最想讨论的一件事，按自己的节奏决定是否继续。",
            "如果需要支持，可查看系统中的求助或预约入口，并确认实际服务时间。",
            "如果正面临即时安全危险，请尽快联系身边可信任的人或当地紧急服务。",
        ],
        "chart_insights": {key: "当前为本地说明，尚无足够依据解释该图；空缺记录不代表零风险。"
                           for key in ("bar", "pie", "heatmap", "trend", "network", "histogram")},
    }


def _build_interpretation_fallback(prompt: str) -> str:
    return (
        "当前显示本地支持性说明，未调用外部模型。有限的对话记录不足以判断心理状态或疾病风险。"
        "你可以先记录最想讨论的一件事，或通过求助、预约入口寻找人工支持；请确认实际服务时间。"
        "这段说明不是诊断，也不能替代专业人员与你的沟通。"
    )
