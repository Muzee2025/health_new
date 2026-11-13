# AdvancedAiChat C0/C1 拆分独立复核

> owner: 复核 ｜ version: 1.0 ｜ status: 代码复核通过；方案文档有 1 处行号待修 ｜ updated: 2026-11-14

## 复核范围

- 代码提交：`ad834b3`（提取 SSE/超时与重试 helper）
- 复核起点：分支 `codex/application-delivery`，HEAD `ad834b3`，工作区干净。
- 重点：抽取前后语义、两处重试参数、远端删除的 `sleep` 复用、新增 6 项单测与方案状态。

## 结论

代码抽取在本次复核范围内通过；发现方案指标表有一处未更新的样式区间，需由文档 owner 修正后才可称为源码完全一致。

1. **调用参数与旧用法保留。** `fetchSessions` 仍传 `retries=3`，`loadSessionMessages` 仍传 `retries=2`，两处新增的 `isActive` 回调都委托给 `chatSession.isActive()`。远端删除循环仍调用抽出的 `sleep(250 * (attempt + 1))`。`sendMessage` 和 `streamDeepThinkReply` 的主流程没有被移出。
2. **抽取逻辑保持。** 新模块保留多行 SSE `data:` 合并、JSON 解析失败时按会话活跃状态返回 `null`/`undefined`、超时后 abort、重试状态分类、400/800ms 递增延迟与原有重试日志。单测共 6 项：流模块 3 项覆盖默认/显式事件及多行 data、JSON 成功/坏 JSON 活跃与失活、超时 abort 与 timer 句柄；重试模块 3 项覆盖 503/429 和 400/800ms、错误分类与非重试 400、失活时不重试。
3. **隔离单测实跑通过。** `npm test -- src/services/advancedChatStream.test.ts src/services/advancedChatRetry.test.ts`：exit 0，2 个测试文件、6 项测试通过。测试对失活状态覆盖的是首次失败时已经失活；没有模拟等待重试期间状态才转为失活，也未测试超时 timer 在到期前被清除的情形，属于非阻断的边界覆盖空间。
4. **方案状态大体吻合，有一处明确偏差。** 当前组件为 1,623 行、45,321 字节；template 为 1–206，script 为 208–1061，顶层 `const` 为 60；`streamDeepThinkReply`/`loadSession`/`sendMessage` 分别仍在第 514/630/710 行，C0/C1 已标完成也符合提交。唯独指标表的 `<style scoped>` 仍写 1112–1672；当前实际起止为 1063–1623（同为 561 行）。需请 `前端` 修正文档该行。

## 其他验证与边界

- `git diff --check ad834b3^ ad834b3`：exit 0。
- 前端执行者报告的 `npx tsc --noEmit`、`npm run format:check`、全量 `npm test`（15 files / 53 tests）及 `npm run build` 均 exit 0；本复核者只重跑了本批 6 个目标测试，没有重跑全量验证。
- 前端报告 GitHub Actions #119 success；本复核报告生成时测试 Bot 的独立确认仍待回复。
- 浏览器交互冒烟未由本复核者执行；本结论不覆盖页面级交互验收。
