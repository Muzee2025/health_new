# 文档索引

> owner: A ｜ version: 0.2 ｜ status: 评审 ｜ updated: 2026-10-21

本索引覆盖源码仓库中的 Markdown 文档，并为 W0 基线和 W1 素材库提供入口。`.workbuddy/` 与 `backend/diagnostics_output/` 仅在本地保留，不纳入源码文档索引；这些目录可能含环境信息。历史文档已归档，内容中的状态、数字和实现说法未经本轮复核。路径均相对本文件所在目录。

## 项目入口

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [项目说明与启动](../README.md) | 评审 | 唯一主启动说明；当前未达到上线标准 |
| [快速启动](../QUICK_START.md) | 评审 | 指向主启动说明 |
| [旧启动指南兼容入口](../SETUP_AND_RUN.md) | 定稿 | 保留旧链接并跳转至 README |
| [协作规则](../AGENTS.md) | 定稿 | 仓库协作和安全边界 |
| [Codex 主提示词](../prompts/CODEX_MASTER_PROMPT.md) | 参考 | 任务与验收参考，历史统计以代码和实际结果为准 |

## 团队与决策

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [分工与 RACI](team/分工与RACI.md) | 草稿（待负责人确认） | A/B/C/D 角色占位，成员资料及确认待填写 |
| [决策记录](team/决策记录.md) | 草稿 | ADR-001 名称；ADR-002 部署目标；ADR-003 素材库与业务迁移边界 |
| [进度看板](team/进度看板.md) | 定稿 | W0/W1任务、阻塞与W2入口 |
| [门禁记录](team/门禁记录.md) | 定稿 | G0技术项、G1素材库技术项通过，真人签字待补 |

## 素材库与设计

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [设计方案](design/设计方案.md) | 定稿 | gpt-6.1-sol设计方向、布局与执行者自评 |
| [素材库规范](design/素材库规范.md) | 定稿 | token、主题、命名、来源、生成及使用规则 |
| [素材来源与许可](../src/assets/LICENSES.md) | 定稿 | 99项自制素材与7项待核实遗留素材逐项记录 |
| [W1验收记录](design/验收记录.md) | 定稿 | 静态校验、浏览器、回归与独立复核结果 |
| [截图与浏览器验证](design/screenshots/README.md) | 定稿 | 14页合成基线与4张展示页验证截图 |
| [PPT网格](design/ppt-kit/16x9-grid.md) | 定稿 | 16:9版式和安全区 |
| [PPT品牌引用](design/ppt-kit/logo-reference.md) | 定稿 | 复用源品牌文件，避免二次复制 |

其他入口：[独立展示页](design/library-preview.html)、[素材清单](../src/assets/manifest.json)、[截图基线清单](design/screenshots/before/baseline.json)、[展示页QA](design/screenshots/library-preview-qa.json)。展示页通过Vite开发服务器访问。

## 基线与测试

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [基线报告](test/基线报告.md) | 定稿 | 实际测试、构建、环境命令、退出码及阻塞 |
| [仓库基线](test/仓库基线.md) | 定稿 | 原始状态、数据保留、口径更正和后续风险 |

## 历史归档

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [归档说明](archive/README.md) | 归档索引 | 原路径及历史内容说明 |
| [心矩引擎项目书初稿](archive/心矩引擎_项目书_初稿.md) | 归档 | 项目书历史素材；旧名称只保留在历史原文 |
| [危机预警双向同步架构](archive/crisis_warning_sync_architecture.md) | 归档 | 历史架构说明 |
| [深度思考开关 E2E 用例](archive/deep_think_toggle_e2e_cases.md) | 归档 | 历史测试用例 |
| [模块拆分分析](archive/MODULE_SEPARATION_ANALYSIS.md) | 归档/设计参考 | 设计设想，不能作为已实现能力依据 |
| [心理报告模块运维清单](archive/psych_report_ops_checklist.md) | 归档 | 历史运维材料 |
| [Qwen 降级修复报告](archive/qwen3.6-plus_degrade_fix_report.md) | 归档 | 历史排障材料，未在本轮复验 |

## 其他仓库文档入口

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [后端启动指南](../backend/STARTUP_GUIDE.md) | 历史/待核实 | 旧机器路径或命令须先核实 |
| [心理学基础知识](../backend/psychology_docs/basic_knowledge.md) | 参考 | 后端心理学资料 |
| [后端部署说明](../deploy/backend/README.md) | 现有部署文档 | 以当前部署文件及实际环境核验 |
## 自检脚本

| 脚本 | 用途与运行方式 |
| --- | --- |
| [仓库静态检查](../scripts/check-repo.py) | 从仓库根目录运行 `py -3.12 scripts/check-repo.py`，检查跟踪文件、路径和仓库卫生；不会打印文件内容或密钥。 |
| [环境诊断](../scripts/check-env.ps1) | 从仓库根目录运行 `powershell -ExecutionPolicy Bypass -File scripts/check-env.ps1`；报告工具版本、依赖目录及环境变量是否设置，不输出变量值。 |
| [后端隔离基线](../scripts/run-backend-baseline.py) | 从仓库根目录运行 `.\.venv\Scripts\python.exe scripts/run-backend-baseline.py`；需要先安装 pytest，使用临时数据库并阻止外部网络。 |
| [素材构建](../scripts/build-design-assets.mjs) | `npm run assets:build`，使用已有sharp；模块定位参数见素材库规范。 |
| [素材校验](../scripts/check-assets.mjs) | `npm run assets:check` 或添加 `-- --json`，仅使用Node内置模块。 |
| [合成界面基线](../scripts/capture-ui-baseline.mjs) | `node scripts/capture-ui-baseline.mjs`，隔离后端/外部请求；参数见截图说明。 |
