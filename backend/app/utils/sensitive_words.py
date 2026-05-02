"""
本地敏感词过滤（简单子串匹配，可按业务扩展词库或改为远程审核）。
"""
from __future__ import annotations

from typing import Iterable, Optional

# 示例词库：实际项目可从文件/数据库加载
DEFAULT_SENSITIVE_WORDS: tuple[str, ...] = (
    "脏话",
    "法轮功",
    "赌博",
    "色情",
)


def find_sensitive_fragment(text: str, words: Optional[Iterable[str]] = None) -> Optional[str]:
    """
    若命中敏感词，返回命中的词（用于内部判断）；
    未命中返回 None。
    """
    if not text:
        return None
    word_list = tuple(words) if words is not None else DEFAULT_SENSITIVE_WORDS
    for w in word_list:
        if w and w in text:
            return w
    return None


def assert_text_clean(text: str, *, field_name: str = "内容") -> None:
    """含敏感词则抛出 ValueError，由路由层转为 HTTP 400。"""
    hit = find_sensitive_fragment(text or "")
    if hit:
        raise ValueError(f"{field_name}包含不当用语，请修改后重试")
