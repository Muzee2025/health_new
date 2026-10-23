# 文档索引

> owner: A ｜ version: 1.5 ｜ status: 评审 ｜ updated: 2026-10-24

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
| [决策记录](team/决策记录.md) | 草稿 | ADR-001至017：历史阶段、SUPPORT交付及W3隔离全栈/恢复验收边界 |
| [进度看板](team/进度看板.md) | 定稿 | W0/W1/W2历史与W3当前任务、阻塞和交接 |
| [门禁记录](team/门禁记录.md) | 定稿 | 各阶段技术证据；目标镜像构建及整体验收仍未放行 |

## 素材库与设计

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [设计方案](design/设计方案.md) | 历史W1 | 原始方向；本轮已由品牌升级方案替代 |
| [素材库规范](design/素材库规范.md) | 定稿 | token、主题、命名、来源、生成及使用规则 |
| [系统界面大纲](design/系统界面大纲.md) | v0.4 实现/规划分列 | 19个现有叶页面、22路由记录、六/五导航分组与求助闭环；其余规划不代表已实现 |
| [求助与跟进页面接入](design/求助与跟进页面接入.md) | 技术交接 | 学生留言、教师工作区、预警历史与错误恢复、个体导出和预约状态契约 |
| [已上线平台导航对标](design/已上线平台导航对标.md) | 公开资料调研 | 五个平台官方来源、公开门户与产品说明的区别，以及可采用的目录组织方式 |
| [业务素材统一引用](design/素材库统一引用.md) | 技术验收通过 | 16角色/25图标、空态与图表共享源；动态业务数据边界与生产渲染验证 |
| [前端分包与加载优化](design/前端分包与加载优化.md) | 技术验收通过 | 冷认证JS减少81.4%、6个profile、EP本地导入、生命周期与可复跑门禁 |
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
| [素材引用独立复核](test/素材引用独立复核.md) | 独立复核通过 | Luna独立来源门禁及7负例、131素材校验和三份浏览器QA交叉核对 |
| [W2业务页面改造](design/W2业务页面改造.md) | 评审 | 既有品牌、科研配色、真实数据空态、XSS与跨账号缓存修复 |
| [W2开发与隔离验证](ops/W2开发与隔离验证.md) | 评审 | 新运行依赖、显式配置/初始化、隔离命令与尚未执行的发布工作 |
| [本地数据库与登录](ops/本地数据库部署与登录.md) | 本机技术通过 | SQLite私有副本/一致性备份、独立18080、启动与认证验证；历史孤儿记录保留 |
| [本地数据库独立复核](test/本地数据库与登录独立复核.md) | 独立复核 | Luna16项隔离测试与Lead部署/浏览器证据交叉核对，未使用真实账号 |
| [前端分包独立复核](test/前端分包独立复核.md) | 独立复核通过 | 来源/162标签导入检查、每文件raw/gzip与最终模块map复算；非延迟性能认证 |
| [本轮补齐验收](test/补齐任务验收.md) | 最终技术证据入口 | 求助/预警/跟进/导出、账号生命周期、私有副本、离线评测和交付物的边界与验证 |
| [补齐独立复核](test/补齐任务独立复核.md) | 独立技术复核 | Luna后端/AI评测独立复核；部署配置只作交叉核对，不自评放行 |
| [全栈隔离独立复核](test/全栈验收独立复核.md) | 部分通过；目标构建阻塞 | 工具/本机契约与缓存代理证据；固定目标容器未完成验收 |
| [AI评测与试点方案](test/AI评测与试点方案.md) | 待专业/校内确认 | 12合成案例、失败分母、评分记录、提供商与试点前置；无真实效果结论 |

## 运维、运营与申报交付

| 文档/工件 | 状态 | 说明 |
| --- | --- | --- |
| [全栈部署与恢复](ops/全栈部署与恢复.md) | 静态配置通过；镜像网络阻塞 | Linux Compose、TLS、迁移、SQLite一致性备份/恢复、CI与尚未通过的发布门禁 |
| [全栈隔离验收](ops/全栈隔离验收.md) | 工具/合成契约通过；目标构建阻塞 | 随机project、非root Nginx、HTTP恢复、缓存TLS/SSE/WebSocket与手动CI；[机器摘要](test/fullstack-verification.json) |
| [校内运营与隐私流程](ops/校内运营与隐私流程.md) | 待校内确认 | 离线教师账号与分配工具、值班/交接/审核、隐私与事件责任草案 |
| [隐私与服务告知](user/隐私与服务告知_草案.md) | 草案 | 可见范围、匿名边界、人工承接、模型传输与留存待确认项 |
| [申报计划书源稿](plan/心域智链申报计划书.md) | 待业务确认的评审稿 | 六板块、预算变量、五平台来源与未虚构的项目事实 |
| [申报证据与待确认清单](plan/申报证据与待确认清单.md) | 证据索引 | 工程与业务证据分开，人员/资格/金额/周期/校内批准留待确认 |
| [答辩方案](ppt/答辩方案.md) | 评审稿 | 14页叙事与逐页说明，讲稿同时保留于PPT备注 |
| [项目申报材料 Word](../deliverables/心域智链项目申报材料.docx) | 12页评审稿 | 申请表/简介表/模板封面及六板块；原附件保留 |
| [项目答辩稿 PowerPoint](../deliverables/心域智链项目答辩稿.pptx) | 14页可编辑评审稿 | 素材库token与approved品牌，逐页渲染核对，未知信息未填造 |

本轮机器证据：[W2验证摘要](test/w2-verification.json)、[客户端隔离](test/w2-client-qa.json)、[36业务页面状态](design/screenshots/w2-business/qa.json)、[升级后八图库回归](design/screenshots/w2-gallery/qa.json)。全部截图和API样例均为合成数据。

素材统一来源追加证据：[机器摘要](test/library-source-verification.json)、[36开发场景](design/screenshots/library-source/dev/qa.json)、[10打包场景](design/screenshots/library-source/production/qa.json)、[图库13项](design/screenshots/library-source/gallery/qa.json)。历史截图保持原样。

本机登录追加证据：[数据库与认证机器摘要](test/local-db-login-verification.json)，包含60组合成响应与两视口真实临时SQLite认证结果；没有真实用户密码或截图。

前端性能追加证据：[加载与回归机器摘要](test/frontend-performance-verification.json)，含冻结基线/最终实际JS请求、模块来源与生产回归；截图和临时预览仅合成数据。

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
| [求助与账号增量迁移](../backend/scripts/migrate-support-workflow.py) | 仅对批准的新副本升级，显式新备份；五张新增表及六个追加事件触发器，拒绝不兼容schema。 |
| [教师账号生命周期](../backend/scripts/manage-teacher-accounts.py) | 离线新教师/停用/启用；全新备份、操作者和原因；隐藏交互密码，无学生提权。 |
| [SQLite备份与恢复](../scripts/backup-restore-database.py) | 只读SQLite backup API写新路径，含WAL、quick_check和外键异常计数；不会修删旧数据。 |
| [全栈隔离执行器](../scripts/verify-fullstack.py) | 默认只读计划；`--run`新QA配置/新卷，合成注册登录/问题/恢复对照与定向清理。 |
| [Nginx传输探针](../scripts/verify-nginx-transport.py) | 默认计划；`--run`使用已有缓存镜像、新合成证书/后端，验证HTTP/TLS/SSE/WebSocket，不接业务服务。 |
| [离线AI评测汇总](../scripts/evaluate-support-ai.py) | 从[合成案例](test/ai-evaluation-cases.jsonl)、实际响应和人工评分JSONL生成新证据，不调用提供商或虚构成本。 |
| [申报工件构建](../scripts/build-project-deliverables.py) | 分DOCX/PPTX阶段，以原附件为只读模板、素材库token/approved品牌为视觉源；按文档技能渲染QA。 |
| [本地数据库准备](../backend/scripts/prepare-local-database.py) | 只读源备份到新私有目录或新空库；拒绝覆盖及缺列旧schema，命令见本机部署说明。 |
| [本机后端启动](../scripts/start-local-backend.ps1) | 独立loopback18080隐藏进程，拒绝占用端口；读取Git忽略的current.json或显式部署目录。 |
| [性能审计构建](../scripts/build-frontend-audit.mjs) | `npm run perf:build`在新tmp目录编译并生成模块来源；不覆盖旧证据。 |
| [隔离gzip预览](../scripts/serve-frontend-audit.mjs) | `npm run perf:preview`只读编译产物，API固定503，不连接实际服务。 |
| [冷加载门禁](../scripts/check-frontend-loading.mjs) | `npm run perf:check`默认要求认证页JS≤250KiB gzip且没有图表引擎；配置与基线模式见分包说明。 |
| [素材构建](../scripts/build-design-assets.mjs) | `npm run assets:build`，使用已有sharp；模块定位参数见素材库规范。 |
| [素材校验](../scripts/check-assets.mjs) | `npm run assets:check` 或添加 `-- --json`，仅使用Node内置模块。 |
| [视觉来源门禁](../scripts/check-design-sources.mjs) | `npm run assets:source-check`；已集成素材校验。`npm run assets:source-test`运行7项隔离正/负例，不读取真实数据库。 |
| [W2业务截图](../scripts/capture-w2-ui.mjs) | 18路由×2视口，合成API、XSS与布局检查，不连接真实后端。 |
| [客户端隔离浏览器测试](../scripts/check-client-isolation.mjs) | `node scripts/check-client-isolation.mjs`，验证IDB双身份、迟到401、Bearer下载和真实SW退休；默认结果写tmp，可显式指定W2_CLIENT_QA_OUTPUT。 |
| [图表数据检查](../scripts/check-chart-data.mjs) | `node scripts/check-chart-data.mjs`，验证6组固定合成数据的分母、分箱与跨图总量。 |
| [图表浏览器检查](../scripts/check-chart-gallery.mjs) | `node scripts/check-chart-gallery.mjs`，验证8图、URL、表格、实际SVG下载与手机布局；模块和输出参数见图表验收记录。 |
| [科研静态绘图](../scripts/render-scientific-figures.py) | 本机 `py -3.14 scripts/render-scientific-figures.py --range 14 --sample A`；需要已有Matplotlib/numpy/Pillow，5图SVG/PDF/300dpi PNG与灰度输出，SciencePlots可选。 |
| [合成界面基线](../scripts/capture-ui-baseline.mjs) | `node scripts/capture-ui-baseline.mjs`，隔离后端/外部请求；参数见截图说明。 |
