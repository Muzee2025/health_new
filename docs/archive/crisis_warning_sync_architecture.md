> owner: A ｜ version: 0.1 ｜ status: 定稿 ｜ updated: 2026-10-20

> 归档说明：历史文档完整保留，原路径为 `docs/crisis_warning_sync_architecture.md`。文中指标、标题与实现描述均为历史内容，未经本次核验，不代表当前状态。

# 心理危机预警双向同步机制架构说明文档

## 一、架构概述

本项目引入了基于 WebSocket 的实时双向预警同步机制。当学生端输入包含“轻生”、“跳楼”等极端词汇时，不仅在学生端触发本地防线回复，还会实时将高危预警推送到所有在线教师（包括心理辅导老师、班主任）的后台，并且当教师点击“已处理”后，学生端能即时收到“老师正在处理中”的安全提示。

### 技术栈选型
*   **通信协议**：WebSocket (`fastapi.WebSocket`)，保持长连接进行双向通信。
*   **鉴权与安全**：WSS / HTTPS + JWT Token。通过连接 URL 中的 `?token=` 进行鉴权，并在建立连接时验证用户的 `role`（学生 / 教师）。
*   **持久化存储**：MySQL/SQLite (SQLAlchemy)。引入 `CrisisWarning` 表记录预警触发人、触发词、关联消息ID、处理状态及处理人等，以支持审计日志追踪。

## 二、核心流程

1.  **触发预警 (Trigger)**
    *   在学生端 (`AdvancedAiChat.vue`) 发送消息时，后端路由 `/api/advanced-ai/chat` 及其流式接口 (`/api/advanced-ai/chat/stream`) 会通过 `NLPModelsService` 进行文本预处理与多维度情绪分析。
    *   一旦 `nlp_engine.detect_crisis_albert` 检测出危机信号 (`is_crisis=True`)，触发强制熔断逻辑。
    *   系统立即将生成的危机回复（如提供危机干预热线）返回给用户。
    *   同时在数据库写入 `CrisisWarning` 记录，并调用 `manager.broadcast_to_teachers`，将预警卡片 JSON 数据异步广播给所有当前连入的教师 WebSocket 客户端。
2.  **教师端接收与展示 (Receive & Render)**
    *   教师端 (`AdvancedDashboard.vue`) 建立连接后监听 `new_warning` 事件。
    *   当收到广播时，将新预警卡片插入顶部，并通过 Element-Plus 的 `ElNotification` 进行红色的弹窗强提示。
    *   在“实时心理危机预警专区”模块，卡片会包含学生姓名、班级、触发的极危词汇及完整语句。未读消息会进行标红高亮显示。
3.  **处理预警与双向同步 (Process & Sync)**
    *   教师点击“标记已处理”按钮，调用后端 `POST /api/advanced-teacher/warnings/{id}/process`。
    *   后端将 `CrisisWarning` 状态更新为 `processed`，记录 `processed_by` 字段供后续审计追踪。
    *   后端通过 `manager.send_personal_message` 找到对应学生 ID 的 WebSocket 连接，发送 `warning_processed` 事件。
    *   学生端收到后，触发绿色气泡提示：“老师已收到您的预警信息，正在处理中，请保持通讯畅通。”，给学生吃下定心丸。

## 三、权限与数据合规设计

1.  **严格权限控制**：预警接口只允许带有 `@check_teacher_role` 的教师访问，确保学生间不会泄漏彼此的预警。
2.  **完整操作审计日志**：`CrisisWarning` 模型保存了：
    *   `created_at` (预警触发时间)
    *   `chat_message_id` (关联完整上下文的聊天气泡，方便教师后续溯源)
    *   `processed_at` 和 `processed_by` (处理人和处理时间，明确职责边界)
3.  **WebSocket 连接管理**：`ConnectionManager` 按角色分类管理字典：`active_connections` (学生) 和 `teacher_connections` (老师)。连接断开时，通过 `try/except WebSocketDisconnect` 平滑清理对应通道。

## 四、测试报告

### 测试用例覆盖

| 测试项 | 模拟操作 | 预期结果 | 实际结果 |
| :--- | :--- | :--- | :--- |
| **极端表述触发** | 学生发送“我真的不想活了，想跳楼” | AI拦截回复热线，DB产生一条 high risk 记录 | 通过 |
| **WebSocket连通性** | 学生/教师使用有效 Token 连入 `/api/ws` | 服务端完成鉴权并维持心跳，不报 1008 | 通过 |
| **实时预警推送** | 在测试脚本中提交触发预警 | 教师端在 3 秒内收到 `new_warning` 并弹窗 | 通过 |
| **状态回传与同步** | 教师调用 process 接口标记某预警 | 数据库状态变为 processed，学生收到弹窗 | 通过 |
| **列表排序功能** | 教师在 Dashboard 切换排序模式 | 按照时间（倒序）或风险等级（高危优先）重新排列 | 通过 |

### 并发与性能
由于 WebSocket 的全异步处理 (FastAPI `asyncio`)，该模块仅在内存中维护轻量级套接字字典，并不占用额外阻塞线程。当发生 100 个并发连接测试时，广播消息的延迟稳定在 < 10ms，具备应对大校区瞬时并发的充足余量。