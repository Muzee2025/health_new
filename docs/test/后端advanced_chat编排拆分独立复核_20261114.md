# 后端 advanced_chat 编排拆分独立复核

> owner: 复核 · version: 1.1 · status: 本机独立复核与 CI 通过 · updated: 2026-11-14

## 范围与结论

复核提交 `2e7f243`：将 `/chat` 与 `/chat/stream` 的编排主体移入 `advanced_chat_orchestration.py`，`advanced_chat.py` 保留路由、签名和依赖兼容入口。

**结论：本次审查范围通过，未发现阻断项。** 两条路由的装饰器和参数签名与父提交 `48a8a7d` 一致；chat 主体与 SSE generator 主体在将新 `runtime.<dependency>` 映射回旧模块符号后 AST 相同。路由快照、定向测试、完整隔离基线和静态门禁均通过。

## 独立复核证据

- 路由签名：用 Python AST 对照 `48a8a7d` 与 `2e7f243`，`ai_chat_interaction`、`ai_chat_stream` 的 decorator 和 args 均一致；exit 0。
- 编排主体：chat 函数体归一化 AST 相同；流式 generator 在移除新增的 runtime factory 初始化语句并归一化依赖名后 AST 相同。SSE 事件、错误/结束帧、响应头、数据库 flush/commit/rollback 与重试流程因此保持原有语句顺序；exit 0。
- 依赖与兼容：`_chat_orchestration_runtime()` 在旧路由模块中按调用时的模块全局变量构造 runtime；流式路由把 factory 传入 generator，在迭代开始时取依赖。现有测试继续通过 `advanced_chat` 模块 monkeypatch `_emotion_pipeline`，并替换 `manager`、`zhipu_chat_service` 对象方法，说明旧注入入口仍可用。
- 定向隔离测试：
  `.\.venv\Scripts\python.exe scripts\run-backend-baseline.py backend\tests\test_advanced_chat_stream.py backend\tests\test_deep_think_mode.py backend\tests\test_deep_think_realtime_chain.py backend\tests\test_crisis_warning_sync.py`
  exit 0，**15 passed / 20 warnings**（9.11 秒）。
- 完整隔离基线：
  `.\.venv\Scripts\python.exe scripts\run-backend-baseline.py`
  exit 0，**231 passed / 3 skipped / 26 warnings**（100.02 秒）。runner 使用一次性 SQLite/文件目录，禁用 dotenv 与 RAG，并阻断 Python socket/DNS 出站。
- 路由顺序：
  `.\.venv\Scripts\python.exe backend\scripts\dump-route-table.py --check`
  exit 0，`IDENTICAL: 100 path+method pairs in the same order`；使用新建的临时 SQLite 路径。
- N+1：
  `.\.venv\Scripts\python.exe scripts\check-n1-queries.py --fail-on-findings`
  exit 0，`real=0 lazy=0 helper=1 benign=2`；唯一 helper 为既有 teacher crisis 序列化路径。
- 静态门禁：
  `.\.venv\Scripts\python.exe -m ruff check backend\app` exit 0；两个改动模块 `py_compile` exit 0；`git show --check --oneline 2e7f243` exit 0。
- 测试命令运行期间 HEAD 后续前进到前端提交 `6e73ecb`；复核已确认该提交相对 `2e7f243` 未修改两个后端目标文件，故上述测试覆盖的后端代码与目标提交一致。
- CI：测试成员确认 `2e7f243` 对应 CI #157，frontend、backend jobs 均成功；CI 摘要未提供测试数量。[查看 CI #157](https://github.com/Muzee2025/health_new/actions/runs/43578325615)

## 边界

本次是代码与隔离测试复核，不包含浏览器或真实模型服务验收。没有访问或修改存量数据库、上传文件或真实服务。
