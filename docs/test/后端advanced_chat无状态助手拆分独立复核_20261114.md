# 后端 advanced_chat 无状态助手拆分独立复核

> owner: 复核 ｜ version: 1.0 ｜ status: 兼容与专项测试复核通过；CI 待测试核对 ｜ updated: 2026-11-14

## 范围与结论

复核本地提交 `7cfaac2`：将 `advanced_chat.py` 中 14 个无状态 helper 移入 `advanced_chat_helpers.py`，检查旧模块导出、helper 可 monkeypatch 入口和路由处理函数是否保持。

**结论：本次审查范围通过，未发现阻断项。** 迁出函数 AST 14/14 与提交前一致，10 个路由处理函数 AST 全部未变；原模块直接导入并继续暴露迁出 helper，路由、模块级服务及可 monkeypatch 的实现入口没有随本批移动。

## 独立复核证据

- 起点：分支 `codex/application-delivery`，HEAD `7cfaac2`。`git status --short` 已有前端 `AdvancedAiChat.vue`、会话测试和 `ChatSessionSidebar` 组件/测试，以及 `docs/data/` 的并行改动；复核未修改或暂存这些路径。
- AST 对照：Python `ast` 分别解析父提交中的 `advanced_chat.py`、当前 `advanced_chat_helpers.py` 与当前 `advanced_chat.py`，迁出函数 **14/14 相同**，路由处理函数 **10/10 相同**，exit 0。
- 独立执行隔离测试：`\.venv\Scripts\python.exe scripts/run-backend-baseline.py backend/tests/test_advanced_chat_stream.py backend/tests/test_deep_think_mode.py`，exit 0，**12 passed / 14 warnings**（8.82s）。runner 使用一次性 SQLite/文件目录、关闭 dotenv 与 RAG、阻断 Python socket/DNS 出站。
- `\.venv\Scripts\python.exe -m ruff check backend/app/routers/advanced_chat.py backend/app/routers/advanced_chat_helpers.py`：exit 0，All checks passed。
- `git show --check --oneline 7cfaac2`：exit 0。
- 提交者报告全量隔离基线 **231 passed / 3 skipped / 26 warnings**、快照 100 对原序及 N+1 门禁通过；本复核未独立重跑全量基线、快照和 N+1，不把这些写成复核者实测。

## 兼容边界

- `advanced_chat.py` 仍导出 `_default_emotion_tags`、`_is_effective_emotion_input`、`_normalize_history_for_model`、`_format_deep_think_reply`、`_safe_json_loads`、`_safe_datetime_str`、`_build_context_snapshot`、`_calc_sentiment_score`、`_sse_event`、`_tokenize_for_match`、`_extract_target_date`、`_day_range`、`_format_dt`、`_cosine_similarity`。直接从旧模块导入或 monkeypatch 这些符号的调用方仍指向 router 模块名。
- `_emotion_pipeline`、`_vector_retrieve_memories` 和其余路由/服务代码留在 `advanced_chat.py`；本批仅迁移无状态转换、序列化及日期/相似度 helper。
- 专项测试覆盖 `advanced_chat_stream` 与 `deep_think_mode` 两个测试文件；全量基线和 CI 结论仍待测试 Bot 核对。
