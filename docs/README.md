# 文档索引

> owner: A ｜ version: 0.8 ｜ status: 评审 ｜ updated: 2026-10-22

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
| [决策记录](team/决策记录.md) | 草稿 | ADR-001至011：W0/W1历史、W2身份与分配范围、依赖整改与显式数据操作 |
| [进度看板](team/进度看板.md) | 定稿 | W0/W1任务、阻塞与W2入口 |
| [门禁记录](team/门禁记录.md) | 定稿 | G0/G1技术项和W2本轮身份/权限/页面技术项通过；整体验收未放行 |

## 素材库与设计

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [设计方案](design/设计方案.md) | 历史W1 | 原始方向；本轮已由品牌升级方案替代 |
| [素材库规范](design/素材库规范.md) | 定稿 | token、主题、命名、来源、生成及使用规则 |
| [品牌升级方案](design/品牌升级方案.md) | 定稿 | 相伴/拥光/知音、人文色彩、源文件与可复建规则 |
| [工作台升级方案](design/展示页升级方案.md) | 定稿 | 搜索筛选、详情规格、复制下载和执行验证 |
| [图表升级方案](design/图表升级方案.md) | 定稿 | 8种图表、用途筛选、合成样例、数据与SVG导出 |
| [图表验收记录](design/图表验收记录.md) | 历史G1-C | 对应8c93e03的八图扩充、浏览器与独立复核 |
| [数据视觉精修](design/数据视觉精修方案.md) | 定稿 | 区间概览与表格；新增Data连续热力色标、水平直方边界、来源分母与本轮验收；固定数据不变 |
| [科研色卡与UI](design/科研色卡与UI方案.md) | 定稿 | 当前蓝绿/暖杏色卡、八图UI、复制/JSON下载及独立门禁 |
| [SCI绘图风格与脚本调研](design/SCI绘图风格与脚本调研.md) | 定稿 | 官方脚本比较、适用边界与可复用中文科研绘图提示词 |
| [科研绘图脚本说明](design/科研绘图脚本说明.md) | 定稿 | 共享色卡与现有数据源，Matplotlib多格式导出、真实运行与限制 |
| [资源与Skill调研](design/资源与Skill调研.md) | 调研完成 | 官方来源、许可、固定版本与实际采用记录 |
| [素材来源与许可](../src/assets/LICENSES.md) | 定稿 | 124项approved与7项待核实遗留素材；自制/MIT/CC0分别记录 |
| [设计优化验收](design/优化验收记录.md) | 定稿 | 当前工作台的实际下载、浏览器、Figma与独立复核 |
| [W1验收记录](design/验收记录.md) | 历史W1 | 对应4b2898f的初始G1验收 |
| [截图与浏览器验证](design/screenshots/README.md) | 定稿 | 原14页合成基线与新旧展示页验证入口 |
| [PPT网格](design/ppt-kit/16x9-grid.md) | 定稿 | 16:9版式和安全区 |
| [PPT品牌引用](design/ppt-kit/logo-reference.md) | 定稿 | 复用源品牌文件，避免二次复制 |

其他入口：[素材工作台](design/library-preview.html)、[素材清单](../src/assets/manifest.json)、[当前科研配色QA](design/screenshots/scientific-palette/qa.json)、[静态绘图证据](design/screenshots/scientific-palette/scientific-export-qa.json)、[科研配色完整性](design/scientific-palette-integrity.json)、[前轮Data QA](design/screenshots/data-analysis/qa.json)、[Data完整性](design/data-analysis-integrity.json)、[前轮数据精修QA](design/screenshots/data-polish/qa.json)、[八图扩充QA](design/screenshots/charts/qa.json)、[品牌优化QA](design/screenshots/refinement/qa.json)、[Figma交接](design/figma-refinement.json)、[初始14页基线](design/screenshots/before/baseline.json)、[历史展示页QA](design/screenshots/library-preview-qa.json)。展示页通过Vite开发服务器访问。

## 基线与测试

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [基线报告](test/基线报告.md) | 定稿 | 实际测试、构建、环境命令、退出码及阻塞 |
| [仓库基线](test/仓库基线.md) | 定稿 | 原始状态、数据保留、口径更正和后续风险 |
| [W2认证与权限](test/W2认证与权限.md) | 评审 | 单一身份、角色、上传限额、真实统计、明确师生分配与离线工具 |
| [W2安全独立复核](test/W2安全独立复核.md) | 独立复核 | 虚假账号与临时数据的安全/ACL矩阵，测试边界与结果 |
| [W2业务页面改造](design/W2业务页面改造.md) | 评审 | 既有品牌、科研配色、真实数据空态、XSS与跨账号缓存修复 |
| [W2开发与隔离验证](ops/W2开发与隔离验证.md) | 评审 | 新运行依赖、显式配置/初始化、隔离命令与尚未执行的发布工作 |

本轮机器证据：[W2验证摘要](test/w2-verification.json)、[客户端隔离](test/w2-client-qa.json)、[36业务页面状态](design/screenshots/w2-business/qa.json)、[升级后八图库回归](design/screenshots/w2-gallery/qa.json)。全部截图和API样例均为合成数据。

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
| [W2业务截图](../scripts/capture-w2-ui.mjs) | 18路由×2视口，合成API、XSS与布局检查，不连接真实后端。 |
| [客户端隔离浏览器测试](../scripts/check-client-isolation.mjs) | `node scripts/check-client-isolation.mjs`，验证IDB双身份、迟到401、Bearer下载和真实SW退休；默认结果写tmp，可显式指定W2_CLIENT_QA_OUTPUT。 |
| [图表数据检查](../scripts/check-chart-data.mjs) | `node scripts/check-chart-data.mjs`，验证6组固定合成数据的分母、分箱与跨图总量。 |
| [图表浏览器检查](../scripts/check-chart-gallery.mjs) | `node scripts/check-chart-gallery.mjs`，验证8图、URL、表格、实际SVG下载与手机布局；模块和输出参数见图表验收记录。 |
| [科研静态绘图](../scripts/render-scientific-figures.py) | 本机 `py -3.14 scripts/render-scientific-figures.py --range 14 --sample A`；需要已有Matplotlib/numpy/Pillow，5图SVG/PDF/300dpi PNG与灰度输出，SciencePlots可选。 |
| [合成界面基线](../scripts/capture-ui-baseline.mjs) | `node scripts/capture-ui-baseline.mjs`，隔离后端/外部请求；参数见截图说明。 |
