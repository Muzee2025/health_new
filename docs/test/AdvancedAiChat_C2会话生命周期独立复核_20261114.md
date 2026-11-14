# AdvancedAiChat C2 会话生命周期迁移独立复核

> owner: 复核 ｜ version: 1.0 ｜ status: 自动化复核通过；隔离浏览器 smoke 待环境 ｜ updated: 2026-11-14

## 范围与结论

复核范围为 `6d263af`（会话生命周期迁入 `useChatSessions`）和 `9cd5d10`（账号切换/清理状态修复与缺口测试），并检查当前 `AdvancedAiChat.vue` 接线、私有会话保护、IndexedDB adapter 和方案文档。

**结论：C2 自动化测试及代码边界复核通过，未发现阻断项。** `sendMessage` 仍留在页面中；会话 API 与存储仍受 `createPrivateChatSession` 身份检查保护。404 清理、远端删除失败/成功、IndexedDB 级联和 A 身份迟到响应均有对应断言。实际浏览器 smoke 未执行，因此本结论不等同于交互环境验收。

## 独立复核证据

- 复核起点：分支 `codex/application-delivery`，HEAD `134ce7f`；起始 `git status --short` 为空。`git fetch origin` exit 0；复核提交 `9cd5d10` 已在当前远端历史中。
- 独立执行 `npx vitest run src/composables/useChatSessions.test.js src/views/student/AdvancedAiChat.sessions.test.js src/services/chatIndexedDb.test.ts --reporter=verbose`：exit 0，3 个测试文件通过，**13 项通过**。
- `git show --check --oneline 6d263af` 与 `git show --check --oneline 9cd5d10`：均 exit 0。
- GitHub Actions CI #125（提交 `9cd5d10`）：独立查询到 frontend、backend jobs 均 completed/success，所有可见步骤均 success；CI 摘要未提供测试数量。链接：[run #125](https://github.com/Muzee2025/health_new/actions/runs/43530952772)。

## 重点断言与实现边界

1. **A 身份的迟到响应**：`sessionHttp` 经 `chatSession.run` 执行，请求完成后再次校验当前 token；`loadSession` 在旧身份失效后直接退出。页面级 deferred-response 测试先挂起 A 的消息请求，再切换到 B 并返回 A 的响应，断言 B 页面历史和共享测试缓存不变，且未调用 `putMessage`。
2. **404 无 survivor**：404 分支先将当前会话 ID 清空，再级联清除本地 conversation、message、ui state；无未归档 survivor 时创建新会话。新测试预置三类旧记录，断言其清除且新会话成为当前会话。
3. **删除失败/成功**：远端删除失败时不调用本地清理，测试以 500 验证三次尝试后 conversation、message、ui state 均保留；远端确认删除后才清理本地。adapter 测试复用同一个内存 IndexedDB fake，确认 conversation、messages、ui state 均被删除。
4. **迁移边界**：`AdvancedAiChat.vue` 注入 `chatSession`、`sessionHttp`、`chatStorage` 与响应式状态给 composable；`sendMessage` 未迁出。`chatIndexedDb.test.ts` 覆盖跨 adapter 实例持久化、账号库隔离和删除级联，但使用自定义 IndexedDB fake，不是浏览器原生 IndexedDB。

## 证据归属与限制

前端报告：页面接入前执行 `npx vitest run src/composables/useChatSessions.test.js --reporter=verbose`，exit 0、4 项通过；另有 4 项 SFC 生命周期测试和 1 项 IndexedDB adapter 测试通过，但未提供这两组的独立命令记录。该先行时间顺序由执行者报告，提交 `6d263af` 同时包含迁移与测试，故不能仅由 Git 提交历史独立证明。

前端报告全量 `npm test` 为 66 项/18 文件通过，tsc、format、lint、build 均 exit 0；本复核者没有重跑这些全量门禁。前端报告 18080/18081 未监听，浏览器 smoke 未执行；本复核也未进行浏览器交互验收。上述限制不影响本次独立复跑的 13 项定向测试结论。
