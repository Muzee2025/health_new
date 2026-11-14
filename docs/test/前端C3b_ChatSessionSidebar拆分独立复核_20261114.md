# 前端 C3b ChatSessionSidebar 拆分独立复核

> owner: 复核 ｜ version: 1.1 ｜ status: 组件契约、页面接线与 CI #140 复核通过 ｜ updated: 2026-11-14

## 范围与结论

复核提交 `f5e41a6`：从 `AdvancedAiChat.vue` 抽出 Sidebar 模板、筛选/时间显示逻辑和对应样式；检查组件契约、父页回调接线，以及原有会话业务是否留在父页。

**结论：本次审查范围通过，未发现阻断项。** 新组件只维护搜索输入并发出 create/select/rename/delete 事件；父页继续持有新建、加载、重命名/删除确认和远端/本地操作。C2 会话持久化与滚动逻辑未随本批移动。

## 独立复核证据

- 起点：分支 `codex/application-delivery`，HEAD `f5e41a6`。起始工作区有已暂存的 `docs/data/数据治理现状与差距.md`（数据 Bot 文件），本复核未修改、暂存或覆盖它。
- 独立执行：`npx vitest run src/views/student/chat/ChatSessionSidebar.test.js src/views/student/AdvancedAiChat.sessions.test.js --reporter=verbose`，exit 0，**2 files / 12 passed**（5 项 Sidebar 契约、7 项会话/页面集成；1.36s）。
- `git show --check --oneline f5e41a6`：exit 0。
- 提交者报告全量前端测试 **84 项 / 20 文件**，以及类型、格式、lint、build、素材门禁通过；本复核未独立重跑全量门禁。CI 由测试 Bot 核对，本报告不代报。
- 测试 Bot 按 SHA 确认 `f5e41a6` 对应 CI #140，frontend/backend jobs 均成功；后端基线、unittest、Ruff、编译、N+1、仓库与 Compose 步骤，以及前端测试和构建门禁均成功。CI 摘要未提供测试数量。

## 组件契约与页面接线

- `ChatSessionSidebar` props 为 `sessions/currentSessionId/loadingSessions/currentMode`；事件为 `create(mode)/select(id)/rename(session)/delete(session)`，与方案第 4.3.1 节 C3b 接口一致。
- 组件测试覆盖区分大小写的标题搜索、隐藏 archived 会话、活动态与 `aria-current`、点击/Enter/Space 选择、新建携带当前 mode、重命名/删除事件载荷及 loading 指令。
- 页面集成测试确认 create/select 接回父页 `createNewChat`/`loadSession`，rename/delete 接回父页 `handleSessionCommand`；父页中的确认流程和业务方法未迁入组件。
- `formatSessionTime`、搜索/筛选和 `.session-*` 样式随组件抽出；其余聊天页与 C2 持久化/滚动逻辑保留在父页。

## 限制

本次独立实测覆盖 Sidebar 契约与会话页面集成两个测试文件；没有独立执行全量前端门禁、浏览器 smoke。CI #140 状态由测试 Bot 确认，未报告摘要未提供的测试数量。未运行的门禁不计为复核者通过。
