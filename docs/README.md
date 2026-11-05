# 文档索引

> owner: A ｜ version: 3.8 ｜ status: 高校两学期模拟库已登记 ｜ updated: 2026-11-04

新增[高校两学期模拟库验收](test/高校两学期模拟库验收_20261104.md)和[机器记录](test/campus-simulation-verification-20261104.json)。同一批20,000名合成学生覆盖2025–2026两个学期，40,000条人学期和235,407条平台事件。[数据说明](../deliverables/心域智链_高校两学期模拟库_20261104/数据说明.md)记录学号编码、校历和CSV口径。

新增[合成问答入库验收](test/合成问答入库验收_20261102.md)、[独立复核](test/合成问答入库独立复核_20261102.md)与[机器记录](test/synthetic-dialogue-verification-20261102.json)：用户明确授权新创虚拟问答，首批96对/12主题/72场景写入新独立SQLite，全部合成候选、未经专业审核；保留旧476条资料，30项检查通过。原稿[登记](../backend/training_data/synthetic-qa-20261102/README.md)、[数据说明](../deliverables/心域智链_合成问答训练集_20261102/数据说明.md)及[逐条预览](../deliverables/心域智链_合成问答训练集_20261102/问答预览.md)。未训练、上传或切换网站数据。下方Excel样本0是此前仅整理已有文件的历史状态。

新增[Excel通用训练资料库验收](test/Excel通用训练库验收_20261102.md)、[独立复核](test/Excel通用训练库来源复核_20261102.md)与[机器记录](test/excel-training-database-verification-20261102.json)：用户已明确Excel来源及通用用途，在新目录建9表SQLite，导入476条资料记录，保留原来源。工作簿没有逐条训练样本，监督表/JSONL为空，未训练或上传。交付[使用说明](../deliverables/心域智链_通用训练资料包_20261102/使用说明.md)；旧待澄清记录保留为历史。

新增[虚拟训练源初查](test/虚拟训练数据初查_20261102.md)、[机器记录](test/synthetic-training-source-profile-20261102.json)与[独立复核](test/虚拟训练数据初查独立复核_20261102.md)：合成展示库42条消息仅1组重复占位问答，历史239条消息来源待核。用户已允许虚拟记录作为训练集候选，但具体源/用途待明确，未导出正文或训练。

当前[界面/分析优化验收](test/Sites界面优化验收_20261102.md)、[独立复核](test/Sites界面优化独立复核_20261102.md)、[机器记录](test/sites-refinement-verification-20261102.json)、[首页设计](design/首页分析与布局优化_20261102.md)与[报告五维设计](design/报告与五维状态优化_20261102.md)：修五维空态/对齐/等待与身份打印，新增同工具趋势摘要，前端41项、38页面与12布局检查通过，同一私有Site已更新；真实业务生产门禁保持。

新增[现有网站Sites私有预览](test/网站Sites预览验收.md)、[独立复核](test/网站预览独立复核.md)与[机器记录](test/sites-preview-verification.json)：复用原Vue界面，合成数据、双角色切换，19页两视口及最终定向交互验证；Sites最终私有发布成功。真实后端/登录/保存/AI未连接，原业务生产门禁不变。根目录误构建dist及环境发现边界见验收记录（2026-11-02）。

本索引覆盖源码仓库中的 Markdown 文档，并为 W0 基线和 W1 素材库提供入口。`.workbuddy/` 与 `backend/diagnostics_output/` 仅在本地保留，不纳入源码文档索引；这些目录可能含环境信息。历史文档已归档，内容中的状态、数字和实现说法未经本轮复核。路径均相对本文件所在目录。

## 项目入口

2026-11-01配图审阅续作：用户确认保留前面第2、3版模型协作示意图，见[保留登记](ppt/local-agents-20261101/retained-selection.json)；下一张新增[纵向记录与RAG检索候选](ppt/local-agents-20261101/rag-records-v1.md)，三模型分工和人工复核以PNG呈现，样式待审。已选图与原PPT字节保持。

2026-11-01新增[立项答辩本地多智能体配图候选](ppt/local-agents-20261101/README.md)：模型规划依据用户确认的Windows双4070/每卡12GB，但按后续反馈已删除图内硬件说明和右上角文字。当前v7为专家/模型名加粗、浅紫色朝内六框错位并紧贴中央粗折线的PNG，末尾只写“输出结果”；实际1672×941，无对应v7 SVG。Lead目视及文件核对通过，样式待用户审阅。历史图和原PPT保留，未部署或调用真实模型，不构成工程或专业门禁放行。

最新实施：[界面与AI解析升级验收](test/界面与AI解析升级验收.md)、[设计与四张合成截图](design/界面与AI解析升级.md)、[后端阶段交接](test/后端AI解析修复交接.md)、[独立复核](test/界面与AI升级独立复核.md)、[机器记录](test/interface-ai-verification.json)。服务器计分/当前ID解析、结构化说明与来源、草稿/轮询/空值、危机持久化及教师状态已修复。完整后端194通过/3条件跳过，最后图片保护另有41专项通过；前端29、隔离构建及两视口48项真实HTTP浏览器验证通过。未核验的多模态融合/图片解析停用，真实模型与专业/生产仍未获证；原运行数据、配置与服务未切换（2026-10-31）。

2026-10-31新增[项目补全与改进方案](plan/项目补全与改进方案_20261031.md)与[19项任务清单](plan/improvement-backlog-20261031.csv)：一项基线/方案任务、18项待实施工作包，优先服务端计分、版本追溯、当前答卷AI绑定、草稿隐私及真实联调，再推进知识依据、目标容器/恢复与受控试点。见[本轮验证](test/project-improvement-plan-verification.json)、[独立复核](test/项目补全方案独立复核.md)。本轮后端140通过/3条件跳过、前端22项及隔离构建/素材通过；没有重验浏览器、真实HTTP、Docker或真实模型，不放行整体上线。

本轮新增[心理问卷选型与上线准备](plan/questionnaire-research-20261029/README.md)，含[12组工具与许可](plan/questionnaire-research-20261029/instruments/instruments.md)、[隐私/政策/人工承接](plan/questionnaire-research-20261029/governance/governance.md)、[使用答疑](plan/questionnaire-research-20261029/问卷使用问题与答疑.md)、[现有代码差距](plan/questionnaire-research-20261029/code-observations.md)、[来源CSV](plan/questionnaire-research-20261029/source-catalog.csv)、[上线清单](plan/questionnaire-research-20261029/launch-checklist.csv)和[问卷登记模板](plan/questionnaire-research-20261029/questionnaire-register-template.csv)。[本地资料包](../deliverables/心域智链_心理问卷选型与上线准备资料_20261029.zip)只含公开来源摘要/元数据，不含原题本或答卷。材料检查见[验收](test/心理问卷资料验收.md)、[独立复核](test/心理问卷资料独立复核.md)及[机器记录](test/questionnaire-research-verification.json)；材料准确性无阻断，不表示选型、专业、学校或生产准入通过。

最新策划书：[40页内容完善修订稿](../deliverables/心域智链项目策划书_内容完善修订稿_20261029.docx)、[验收](test/策划书内容完善验收.md)、[独立复核](test/策划书内容完善独立复核.md)、[机器证据](test/project-plan-revision-verification.json)。保留介绍与第五章8图，补足项目进展、成果检查和阶段安排、26条既有参考；学校端规划与已有系统分清。用户原附件及37页前版保留（2026-10-29）。

前版附件补充：[37页Word](../deliverables/心域智链项目计划书_系统内容与截图补充_20261029.docx)、[验收](test/附件系统内容补充验收.md)、[独立复核](test/附件系统内容补充独立复核.md)、[机器证据](test/attachment-system-verification.json)、[八张系统截图登记](plan/application-ui-20261029/README.md)。项目介绍、当前功能、进展和第五章8图已补充；图中数据为合成演示，原附件保持（2026-10-29）。

文献数据新交付：[12表Excel](../deliverables/心域智链_文献数据下载与分析_20261028.xlsx)、[公开原文与聚合CSV资料包](../deliverables/心域智链_公开文献数据包_20261028.zip)、[数据来源与口径](plan/research-data-20261028/README.md)、[验收](test/文献数据下载与分析验收.md)、[独立复核](test/文献数据独立复核.md)、[机器证据](test/literature-data-verification.json)。6篇正式来源/26份去重下载；原始926访谈记录仅本地处理，交付包不含个人行（2026-10-28）。

最新数据整理：[数据库变量与项目数据Excel](../deliverables/心域智链_数据库变量与项目数据_20261028.xlsx)、[整理验收](test/数据库变量整理验收.md)、[独立复核](test/数据库变量整理独立复核.md)、[机器记录](test/database-inventory-verification.json)。27表198字段为完整预览参考，历史库存在差异，运行服务绑定未核实（2026-10-28）。

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
| [决策记录](team/决策记录.md) | 草稿 | ADR-001至021：历史阶段、SUPPORT/W3、前端、独立数据库内容、文章分页预览与申报交付 |
| [进度看板](team/进度看板.md) | 定稿 | 前端优化当前结果、W0/W1/W2/W3历史、阻塞和交接 |
| [门禁记录](team/门禁记录.md) | 定稿 | 各阶段技术证据；目标镜像构建及整体验收仍未放行 |

## 素材库与设计

| 文档 | 状态 | 说明 |
| --- | --- | --- |
| [申报逻辑图HTML预览](design/申报逻辑图预览.html) | 待用户审核 | 白底细线四区图；桌面/手机技术检查通过，供确认申报配图风格 |
| [申报技术图示HTML](design/申报技术图示.html) | 审阅 | 同源简洁架构/AI流程/备用阶段图；均为工程原型和拟建设能力示意 |
| [设计方案](design/设计方案.md) | 历史W1 | 原始方向；本轮已由品牌升级方案替代 |
| [素材库规范](design/素材库规范.md) | 定稿 | token、主题、命名、来源、生成及使用规则 |
| [前端优化工作流](design/前端优化工作流.md) | 多agent实施与验收 | Luna唯一文件范围、任务优先、素材源及隔离浏览器门禁 |
| [内容体验优化](design/内容体验优化.md) | 技术验收通过 | 两端文章查找/分页与创建、删除反馈；实际QA见本轮验收 |
| [文章服务端分页](design/文章服务端分页.md) | 技术交接 | 摘要分页、搜索防抖与请求竞态、服务端页码夹紧及失败恢复 |
| [前端布局与导航](design/前端布局与导航优化.md) | 技术交接 | 六/五组导航、移动抽屉、焦点与背景隔离、共享响应式 |
| [学生端体验优化](design/学生端体验优化.md) | 技术交接 | 八页行动入口、数据空态、加载恢复和窄屏 |
| [教师端体验优化](design/教师端体验优化.md) | 技术交接 | 七页待办优先、审核/跟进、列表与表单 |
| [系统界面大纲](design/系统界面大纲.md) | v0.5 实现/规划分列 | 19叶页面、22路由记录、六/五导航、求助闭环和本轮前端落地；其余规划不代表已实现 |
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
| [内容体验与数据库验收](test/内容体验与数据库验收.md) | 本轮技术通过 | 搜索/分页/文章创建、8指南与独立库、128后端/38页/26交互及失败保留；[机器摘要](test/content-quality-verification.json) |
| [文章分页与预览验收](test/文章分页与预览验收.md) | 专项通过；完整集成受阻 | 摘要分页、新库预览、响应体积；Windows回环使完整后端/最新真实UI复验失败；[机器摘要](test/article-scaling-verification.json) |
| [文章分页独立复核](test/文章分页独立复核.md) | 局部通过；完整门禁阻塞 | 独立亲跑8+5+4专项与完整计数环境失败记录，浏览器/新库证据复核 |
| [内容质量独立复核](test/内容质量独立复核.md) | 独立评审 | Luna亲跑内容/API专项，复核指南、路径/幂等/事务及Lead浏览器证据 |
| [前端体验验收](test/前端体验验收.md) | 本轮技术证据 | 冻结基线/最终生产包、两视口19页、窄屏交互、冷加载与边界 |
| [前端体验独立复核](test/前端体验独立复核.md) | 独立角色复核 | Luna亲跑与Lead浏览器证据审阅分列、抽屉焦点问题闭合 |
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

本轮AI融合前置盘点：[代码结合点与复现边界](plan/ai-application/ai-integration-20261027/code-scope.md)、[文献审计与AI融合建议](plan/ai-application/ai-integration-20261027/literature-audit.md)。两份为静态代码与限定文献审查记录，先用于向用户解释AI定位；尚未并入S5交付正文，原Word/HTML及其复核绑定保持不变。

| 文档/工件 | 状态 | 说明 |
| --- | --- | --- |
| [全栈部署与恢复](ops/全栈部署与恢复.md) | 静态配置通过；镜像网络阻塞 | Linux Compose、TLS、迁移、SQLite一致性备份/恢复、CI与尚未通过的发布门禁 |
| [数据库内容目录与导入](ops/数据库内容目录与导入.md) | 新独立库技术通过 | 原创8指南、默认计划、全新输出、只读备份、重复跳过/冲突拒绝与只读检查 |
| [文章指南本地预览](ops/文章指南本地预览.md) | 本机操作说明 | 5180/18081、指南新库与QA账号隔离、显式配置与上传目录、重启和新副本 |
| [全栈隔离验收](ops/全栈隔离验收.md) | 工具/合成契约通过；目标构建阻塞 | 随机project、非root Nginx、HTTP恢复、缓存TLS/SSE/WebSocket与手动CI；[机器摘要](test/fullstack-verification.json) |
| [校内运营与隐私流程](ops/校内运营与隐私流程.md) | 待校内确认 | 离线教师账号与分配工具、值班/交接/审核、隐私与事件责任草案 |
| [隐私与服务告知](user/隐私与服务告知_草案.md) | 草案 | 可见范围、匿名边界、人工承接、模型传输与留存待确认项 |
| [申报计划书源稿](plan/心域智链申报计划书.md) | 科研图与数学分析审阅 | 六板块、教育/文献地区表、13图16正文表、5公式27来源；说明在附录 |
| [AI申报书源稿与图表](plan/ai-application/README.md) | 审阅 | 六个Luna章稿、21项指标、来源与视觉登记、简化出图方法和统稿改动 |
| [申报书正文HTML审阅版](../deliverables/心域智链申报书正文审阅版.html) | 待用户样式审核 | 离线单文件，正文图表内嵌，章节跳转和手机显示已检查；Word附件表另保留 |
| [AI申报图表验收](test/AI申报图表验收.md) | 审阅文件就绪 | 26页DOCX/12居中三线表/8正文图；[机器摘要](test/ai-application-verification.json)和[独立复核](test/AI图表申报独立复核.md)；样式待用户审核 |
| [地区与附录修订输入](plan/ai-application/revision-20261027/README.md) | 六章冻结，统稿完成 | 新六章、31地CSV/来源、8地建设资料与正文移动记录 |
| [地区数据修订验收](test/申报书地区数据修订验收.md) | 本次修订交付 | R4 26页/15居中三线表/10图；[机器摘要](test/application-regional-revision-verification.json)、[独立复核](test/申报书地区比较与文风复核.md) |
| [科研图与分析输入](plan/ai-application/sci-revision-20261027/README.md) | 科研图审阅 | 数学计算、原文文献数据、13图规范、来源与导出格式 |
| [科研图与数学分析验收](test/申报书科研图与数学分析验收.md) | S5整稿独立复核完成 | 32页/19居中三线表/13图/5公式；[机器证据](test/application-sci-verification.json)、[独立复核v1.4](test/申报书数学分析与科研图复核.md)；交付字节保持 |
| [学生心理测评市场分析](plan/学生心理测评市场分析.md) | 来源核验完成 | 学生样本/学校建设、三学段统计及4项采购；[来源元数据](plan/市场分析来源.json)与[待填字段](plan/申报表字段.json) |
| [申报材料验收](test/申报材料验收.md) | 上轮格式交付 | 历史申报16页/8三线表及4页大纲，原生Word逐页核对；[机器摘要](test/application-delivery-verification.json)；不替代新增图表版验收 |
| [申报材料独立复核](test/申报材料独立复核.md) | 独立内容与结构复核 | 亲查来源/成品结构，区分Lead渲染证据；不代替资格及学校批准 |
| [申报证据与待确认清单](plan/申报证据与待确认清单.md) | 证据索引 | 工程与业务证据分开，人员/资格/金额/周期/校内批准留待确认 |
| [答辩大纲](ppt/答辩方案.md) | 仅文字大纲 | 16主题/48条要点，高校为主、初高中独立论证；用户暂不制作PPT |
| [项目申报材料 Word](../deliverables/心域智链项目申报材料.docx) | 16页，可手填 | 8表全部三线，含附件/封面；六板块正文及市场证据，原附件保留 |
| [答辩大纲 Word](../deliverables/心域智链项目答辩大纲.docx) | 4页可编辑 | 16个建议页面及要点，无表格，供后续自行制作PPT |

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
| [申报Word构建](../scripts/build-application-document.py) | 当前16页材料；只改模板指定正文槽位，输出必须为新路径。 |
| [答辩大纲构建](../scripts/build-application-outline.py) | 生成16主题Word/Markdown大纲，不制作幻灯片；新DOCX路径不可覆盖。 |
| [原生Word渲染](../scripts/render-application-word.ps1) | 隐藏只读打开并输出新PDF，用于16+4页QA；需本机Word。 |
| [申报工件校验](../scripts/verify-application-artifacts.py) | 结构、原文保持、全部三线边框、摘要/占位、大纲及哈希绑定的目视证据。 |
| [历史申报工件构建](../scripts/build-project-deliverables.py) | 前轮12/14页生成器，仅为历史复现保留；当前交付使用上述新工作流。 |
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


## PPT-R3：12项批注修订（2026-10-31）

[六章答辩PPT批注修订](ppt/six-chapters-20261029/revision-r3/README.md)：11页新副本及2页约4分钟Word配套稿，含逐条批注映射、31省统计图/政府截图来源、算法拟案和最终校验。原六章首版、统一字号空白版、用户旧稿及申报书保留。


## PPT-R4：图片比例与项目原理可视化（2026-10-31）

> owner: AI-OUTLINE ｜ version: 4.0 ｜ status: 完成，供用户审阅 ｜ updated: 2026-10-31

[修订与验证记录](ppt/six-chapters-20261029/revision-r4/README.md)、[23项素材/32处放置登记](ppt/six-chapters-20261029/revision-r4/selected-assets.json)。保留11页，第9页7节点原生原理图；整稿32张图无比例变形。交付11页PPT及2页约4分钟Word讲稿；逐页原生渲染及独立复核无阻断，旧文件与业务运行环境保留。


## PPT-R5：多智能体与专家模型扩展（2026-10-31）

> owner: AI-OUTLINE ｜ version: 5.0 ｜ status: 材料完成，供用户审阅 ｜ updated: 2026-10-31

[本轮记录](ppt/six-chapters-20261029/revision-r5/README.md)、[素材登记](ppt/six-chapters-20261029/revision-r5/selected-assets.json)。16页新副本已完成，新增第10—14页对应原123第6—10页主题：多智能体架构、六模型分工、情绪线索画像、纵向RAG和规则危机复核。42张图片均锁比例、0张变形；5表64格与原生图表保持可编辑，旧图表/源工作簿同字节。原生PowerPoint16页及独立Luna逐页复核无阻断；第15页仅保留旧保守安全区警告，原生无碰撞。


## PPT-R6：多智能体协作机制优化（2026-10-31）

> owner: AI-OUTLINE ｜ version: 6.0 ｜ status: 材料完成，供用户审阅 ｜ updated: 2026-10-31

[本轮记录](ppt/six-chapters-20261029/revision-r6/README.md)、[素材登记](ppt/six-chapters-20261029/revision-r6/selected-assets.json)。18页副本完成。第10—12页明确语义共同依据、情绪/认知/纵向并行、风险复核与资源草稿、虚构案例输入输出，以及冲突回查/失败降级/紧急独立优先人工路径。46图锁比例且0变形，6表92格、1原生图表；前版表格和图表源工作簿保持。原生18页与独立Luna逐页复核无阻断。
