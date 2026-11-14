# 前端 C3c ChatMessageList 拆分独立复核

> owner: 复核 ｜ version: 1.0 ｜ status: 主页面接线与滚动契约通过；组件危险检测默认值需修正 ｜ updated: 2026-11-14

## 范围与结论

复核提交 `8024faa`：将 AdvancedAiChat 的消息列表、危机提示、深度思考面板、typing 区域及对应 scoped 样式抽到 `ChatMessageList.vue`，检查展示契约、父页接线和 C2 草稿/滚动持久化边界。

**结论：主页面接线及滚动持久化行为通过；发现一个非当前父页路径触发的组件默认值缺陷，修复和回归断言补齐前不将组件契约记为完全通过。** 当前父页始终传入 `isDangerText`，因此本次未发现已接入聊天页的危险样式回归。组件单独使用且省略此 prop 时，所有用户消息会被错误地标成危险消息。

## 独立复核证据

- 起点：分支 `codex/application-delivery`，HEAD `8024faa`；`git status --short` 为空。
- 独立运行：`npx vitest run src/views/student/chat/ChatMessageList.test.js src/views/student/AdvancedAiChat.sessions.test.js --reporter=verbose`，exit 0，**2 files / 13 passed**。
- `git show --check --oneline 8024faa`：exit 0。
- 未独立重跑全量前端门禁或 CI；CI 状态由测试 Bot 核对。浏览器 smoke 未执行。

## 接线与行为核对

- 子组件按原序渲染用户/AI 消息，保留匿名头像、危险文本 class、危机横幅、思考锚点/阶段/日志和 typing/即时反馈。
- 子组件通过 `defineExpose` 暴露 `scrollElement` 与 `scrollToBottom()`。父页的 `computed(() => messageListRef.value?.scrollElement ?? null)` 仍为 `useChatSessions` 提供滚动 DOM 元素；草稿和 scrollTop 的保存/恢复仍使用同一元素引用。
- 父页继续拥有消息生成、危机计时、SSE 状态及会话编排；滚到底部通过子组件方法转发。独立目标测试覆盖组件的 nextTick 滚动和父页草稿/scrollTop 持久化与恢复接线。

## 待修项

1. `ChatMessageList.vue` 中 `isDangerText` 是 Function 类型 prop，默认值为 `() => () => false`。Vue 对 Function 类型 prop 不把默认函数当 factory 调用；实际默认 predicate 调用后返回一个函数对象，模板将其视作 truthy，导致每条用户消息都套用 `bubble-danger`。独立 Vue SSR 探针省略该 prop 后得到 `<div>truthy</div>`。建议将默认 predicate 改为 `() => false`，并新增省略 prop 时不标危险的组件断言。
2. 方案文档 C3c 接口表已列出消息列表 props，但漏列实际存在并由父页传入的 `isDangerText`。修复默认值时同步补齐接口表。

## 证据边界

测试结果证明本次独立运行的两个目标测试文件通过，不代表浏览器 smoke、全量前端门禁或 CI 通过。
