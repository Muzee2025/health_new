# 前端 C3a ChatComposer 拆分独立复核

> owner: 复核 ｜ version: 1.0 ｜ status: 组件契约与页面接线通过；CI 待测试核对 ｜ updated: 2026-11-14

## 范围与结论

复核提交 `9f8283b`，范围为 `ChatComposer.vue` 抽取、`AdvancedAiChat.vue` 接线、组件/页面测试及拆分方案更新。

**结论：本次审查范围通过，未发现阻断项。** 输入草稿仍由父页 `inputText` 持有；发送、深度思考、身份/会话判定及持久化仍在父页。新组件只显示/发出输入区交互，不增加 API 或本地存储副作用。C2 会话滚动持久化逻辑没有被本提交改动。

## 独立复核证据

- 起点：分支 `codex/application-delivery`，HEAD `9f8283b`，`git status --short` 为空。
- 独立执行：`npx vitest run src/views/student/chat/ChatComposer.test.js src/views/student/AdvancedAiChat.sessions.test.js --reporter=verbose`，exit 0，**2 files / 17 passed**（11 项组件契约、6 项页面会话/接线测试；1.38s）。
- `git show --check --oneline 9f8283b`：exit 0。
- 提交者报告全量前端测试 19 files / 78 passed，以及类型、格式、lint、build、素材门禁通过；本复核未独立重跑这些全量门禁。
- `9f8283b` 的 CI 结果由测试 Bot 核对，本报告不代报。

## 行为与父子接口

- `ChatComposer` props 包含 `modelValue/isAnonymous/currentSessionId/isTyping/deepThinkEnabled/lastReplyChars/lastReplyRatio`；emits 为 `update:modelValue/send/toggle-deep`。
- 契约测试覆盖草稿更新、Enter/按钮发送、匿名及会话状态下发送禁用规则、输入框会话门禁、typing 时禁用深度思考开关、统计文案与小数格式。
- 页面接线测试确认 `v-model` 更新父页 `inputText`，`send` 和 `toggle-deep` 分别接回父页既有 `sendMessage` 与 `toggleDeepThink`。
- 模板与对应样式（输入区、发送按钮、深度思考开关、回复统计、textarea 及移动端规则）一起迁移；父页的业务方法和状态没有随组件抽取。

## 非阻断文档差异与限制

- 拆分方案第 4.2 节组件总览行仍写 `canSend/deepThink`，与实际 props 不一致；第 4.3.1 节 C3a 详细接口已列出实际 props。本项是方案总览表的文档漂移，不影响实现与验收，建议下次更新时统一。
- 独立实测仅覆盖上述 2 个定向测试文件；全量门禁和 CI 仍以实施者/测试 Bot 的记录为准。未执行浏览器 smoke。
