from types import SimpleNamespace

import pytest

from app.routers.advanced_chat import (
    _build_db_history_for_model,
    _build_session_message_highlights,
    _extract_target_date,
    _format_deep_think_reply,
    _normalize_history_for_model,
)


def test_normalize_history_off_returns_empty():
    raw = [{"role": "user", "content": "a"}, {"role": "ai", "content": "b"}]
    assert _normalize_history_for_model(raw, deep_think=False) == []


def test_normalize_history_on_maps_role_and_limits():
    raw = [{"role": "ai", "content": "x"} for _ in range(12)]
    out = _normalize_history_for_model(raw, deep_think=True)
    assert len(out) == 10
    assert all(x["role"] == "assistant" for x in out)


def test_build_db_history_off_returns_empty():
    msgs = [SimpleNamespace(role="user", content="u1"), SimpleNamespace(role="ai", content="a1")]
    assert _build_db_history_for_model(msgs, deep_think=False) == []


def test_build_db_history_on_excludes_latest_user_message():
    msgs = [
        SimpleNamespace(role="user", content="u1"),
        SimpleNamespace(role="ai", content="a1"),
        SimpleNamespace(role="user", content="latest-user"),
    ]
    out = _build_db_history_for_model(msgs, deep_think=True)
    assert out[-1]["role"] == "assistant"
    assert out[-1]["content"] == "a1"


def test_format_deep_think_reply_has_fixed_prefix_and_suffix():
    out = _format_deep_think_reply("这是分析正文", trace_id="t-1")
    assert out == "这是分析正文"


def test_format_deep_think_reply_empty_should_raise():
    with pytest.raises(RuntimeError):
        _format_deep_think_reply("", trace_id="t-2")


def test_extract_target_date_supports_chinese_date():
    dt = _extract_target_date("我想看2026年4月12日发生了什么对话")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 4
    assert dt.day == 12


def test_build_session_message_highlights_prefers_keyword_overlap():
    msgs = [
        SimpleNamespace(role="user", content="最近学习压力很大"),
        SimpleNamespace(role="ai", content="可以试试番茄钟缓解压力"),
        SimpleNamespace(role="user", content="昨晚失眠了，心情低落"),
    ]
    highlights = _build_session_message_highlights(msgs, "我什么时候聊过失眠问题", max_items=2)
    assert len(highlights) >= 1
    assert any("失眠" in line for line in highlights)
