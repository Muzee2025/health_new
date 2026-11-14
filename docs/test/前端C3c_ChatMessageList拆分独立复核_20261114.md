# 前端 C3c ChatMessageList 拆分独立复核

> owner: 复核 ｜ version: 1.2 ｜ status: `e6f12cf` 修复复验通过；CI #150 前后端 jobs 成功 ｜ updated: 2026-11-14

## 范围与结论

复核提交 `8024faa` 及修复 `e6f12cf`：将 AdvancedAiChat 的消息列表、危机提示、深度思考面板、typing 区域及对应 scoped 样式抽到 `ChatMessageList.vue`，检查展示契约、父页接线和 C2 草稿/滚动持久化边界，并复验危险检测默认值修复。

**结论：本次复核范围通过，未发现遗留阻断项。** `e6f12cf` 将 `isDangerText` 的默认 predicate 修正为返回 `false`，新增省略 prop 时普通用户消息不加危险样式的回归断言，并补齐方案接口表。当前父页仍显式传入检测函数。

## 独立复核证据

- 初审起点：分支 `codex/application-delivery`，HEAD `8024faa`；`git status --short` 为空。修复复验起点：HEAD `e6f12cf`。
- 修复后独立运行：`npx vitest run src/views/student/chat/ChatMessageList.test.js src/views/student/AdvancedAiChat.sessions.test.js --reporter=verbose`，exit 0，**2 files / 14 passed**；新增的省略 prop 默认行为断言通过。
- `git show --check --oneline e6f12cf`：exit 0。
- 测试 Bot 按 SHA 确认 `e6f12cf` 对应 CI #150，frontend/backend jobs 均成功；CI 摘要未提供测试数量。
- 未独立重跑全量前端门禁。浏览器 smoke 未执行。

## 接线与行为核对

- 子组件按原序渲染用户/AI 消息，保留匿名头像、危险文本 class、危机横幅、思考锚点/阶段/日志和 typing/即时反馈。
- 子组件通过 `defineExpose` 暴露 `scrollElement` 与 `scrollToBottom()`。父页的 `computed(() => messageListRef.value?.scrollElement ?? null)` 仍为 `useChatSessions` 提供滚动 DOM 元素；草稿和 scrollTop 的保存/恢复仍使用同一元素引用。
- 父页继续拥有消息生成、危机计时、SSE 状态及会话编排；滚到底部通过子组件方法转发。独立目标测试覆盖组件的 nextTick 滚动和父页草稿/scrollTop 持久化与恢复接线。

## 初审发现及修复

- 初审确认 `isDangerText` 是 Function 类型 prop，原默认值 `() => () => false` 被 Vue 作为实际 predicate 使用；调用后返回函数对象，模板将其判为 truthy。独立 Vue SSR 探针省略该 prop 后输出 `<div>truthy</div>`。
- `e6f12cf` 将默认值改为 `() => false`，增加省略 prop 的普通消息断言；方案 C3c props 列表已补 `isDangerText`。修复后两个目标测试文件独立复跑 **14/14 passed**，此项关闭。

## 证据边界

复验结果仅覆盖本次独立运行的两个目标测试文件和提交检查，不代表浏览器 smoke 或全量前端门禁由复核者独立通过。全量门禁为实施者报告；CI #150 仅按测试 Bot 报告的 job 状态记录，不补报未公开的测试数量。
