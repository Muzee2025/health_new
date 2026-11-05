# 界面与 AI 升级独立复核

> owner: 独立复核 Luna / FIX-AUDIT-01 ｜ version: 1.3 ｜ status: 独立源码复核与 Lead 本机回归/最终浏览器验收通过；专业与生产门禁未放行 ｜ updated: 2026-10-31

## 复核范围

对前后端 AI 与测评链路进行只读复核，重点检查题本原始选项与服务器计分、测评记录所有权、版本与重试标识、模型本地/外部来源、报告空值与状态、教师预警呈现及危机消息持久化。期间没有读 `.env`、现有运行数据库或真实个人记录，没有调用实际模型、服务或联网 provider；隔离后端 runner 使用临时 SQLite/文件，禁用 dotenv 与 RAG 并阻断 socket/DNS。

本复核不等于问卷专业认证、临床验证、外部模型审核或生产批准。浏览器与最终全量后端回归由 Lead 另行执行；本报告只读检查 Lead 保存的浏览器摘要，不代表复核者亲跑浏览器。

## 已复核的修复闭环

| 风险 | 当前实现与结论 |
|---|---|
| 客户端伪造分数、题目错位或选项越界 | 服务器按题本题数、0-based 原始选项与反向题独立计分；未知字段、缺失/额外题目、布尔及范围外选项拒绝。SDS/SAS 标记待专业复核，不推导风险级别；趣味问卷不作为风险依据。通过隔离测试。 |
| 跨记录解读与旧记录误认 | AI 说明须绑定当前学生拥有的严格正整数 `test_id`；跨用户/不存在返回 404。异常 JSON、非对象或异常 provenance 安全降为版本未知。响应来源对象说明是本地计分 provenance，不冒称外部文献。通过 fake provider 和隔离数据库测试。 |
| AI 来源及敏感字段泄漏 | 默认本地规则并带 fallback/source/status；provider 输入不含逐题答案、姓名、学号、树洞原文。Qwen 对话报告只发送记录条数，并校验 schema 与超出证据的风险/趋势表述。Fake provider 测试确认输入最小化与降级。未测试真实 provider。 |
| 无数据仍出分、风险或趋势 | 五维接口返回 `data_status=insufficient` 与空数据；报告风险为 `UNKNOWN`，无标签构念分数为 null，时间序列空日保留 null、无记录的热图为空。报告资料不足与本地规则来源显式传到 UI；图表 helper 保留 null 缺口，不把它转成 0。空图表按有数据时才展示，无图表数据时显示单个空状态及记录近况入口；模型比较仅在存在真实模型结果时展示，不支持的关系图已移除。通过后端与前端专项。 |
| 旧回退内容冒充 AI/量表结论 | LLM 网关将本地规则响应标作 fallback；报告不声称按常模判定，不再补造聊天趋势，也不把静态说明当 provider 成功。学生旧汇总报告返回 generation 与 data status。对协同多模型风险，业务入口被硬停用：health 返回 false，submit 在排队/外呼前返回 503；旧融合逻辑没有业务入口。 |
| 树洞与能量趋势的伪分析 | 树洞规则结果不再命名为 AI，并与帖子同事务写入；无历史事件时红能量接口不造随机过去曲线。通过相关报告证据测试。 |
| 危机提示虚构热线/虚称已经处置 | 固定热线及值守承诺已从回复中移除。危机 response 带 `warning_state`；只有预警写入成功才标记 `created`。持久化失败会回滚并返回 `not_created`。流式写入失败仍保留求助说明并返回 `not_created`。学生端提示人工服务是否接收未知，教师缺等级显示“待核验”，不默认映射为高危或低危。合成失败注入与正常闭环专项通过。 |
| 图片解析用占位值冒充特征 | 文件仍先经有界内容校验，但当前图像解析明确停用并返回 503，说明请用文字描述且文件未保留；不得执行旧的固定情绪向量占位函数。独立亲跑新 guard 单测通过。 |
| 报告无限轮询、异步状态冒报 | 前端最多 5 次指数退避检查，单处理周期只触发一次，支持手动重试、取消与身份变化清理。报告 SSE 步骤根据 generation 来源区分 provider 与本地降级。专项测试通过。 |

此前第一阶段只读检查记录的伪 LLM 固定响应、无数据五维合成值、聊天报告补点、随机红能量、树洞伪 AI 与分两次提交，以及报告轮询无界等问题，均在当前快照找到对应修复或入口禁用；不将旧快照结论当作当前缺陷。

## 独立亲跑结果

以下命令由复核者亲自执行，针对当前源码快照：

```powershell
.\.venv\Scripts\python.exe scripts/run-backend-baseline.py backend/tests/test_crisis_warning_sync.py backend/tests/test_report_evidence_integrity.py backend/tests/test_assessment_integrity.py backend/tests/test_assessment_interpretation.py backend/tests/test_qwen_degrade_guard.py backend/tests/test_advanced_chat_stream.py
```

结果：退出码 0，`65 passed, 17 warnings in 105.32s`。覆盖当前危机预警同步与存储失败、报告证据、测评完整性/解释、Qwen 降级及既有聊天流式专项。Warnings 保留为 runner/依赖产生的警告；未据此宣称全量后端通过。

```powershell
npm test
```

结果：退出码 0，10 个测试文件、29 项通过，用时 513ms。覆盖测评提交流程、报告轮询及数值空值处理等前端纯逻辑测试。

Lead 在最终快照另行执行并报告以下证据（均为 Lead 结果，不是本复核者亲跑）：

- 全量后端：`194 passed, 3 skipped, 26 warnings`，254.54s，exit 0；3 项为条件符号链接跳过。
- 图片停用 guard、报告证据与 W2 安全专项：`41 passed, 15 warnings`，22.30s，exit 0。
- 前端：Lead 最新复验 10 个测试文件、29 项通过；隔离生产构建 9.78s。该结果由 Lead 执行，本复核者未亲跑构建或前端测试。
- Edge 浏览器 QA：Lead 对最终 `Report.vue` 候选版本复验 48/48 通过，覆盖 19 页在 1440/390 两视口的 38 组检查和 10 项交互；页面错误、意外外部请求、意外 API 错误及未注入的 5xx 均为 0，2 项 503 均为显式注入验收场景。复核者只读检查了 Lead 运行并保存的[最终浏览器摘要](../../tmp/interface-ai-20261031/browser-reviewed/summary.json)：`status=passed`、`synthetic_only=true`、48 项结果均通过。四张截图位于[浏览器截图目录](../design/screenshots/interface-ai-20261031/)；摘要和截图均为 Lead 的 QA 证据，不是复核者亲跑结果。

独立复核者另对最新图片解析 guard 做了源码检查，并亲跑 `.\.venv\Scripts\python.exe scripts/run-backend-baseline.py backend/tests/test_report_evidence_integrity.py::test_unimplemented_image_parser_never_reports_fabricated_features`：`1 passed, 10 warnings`，exit 0。未由独立复核者执行真实浏览器、HTTP 服务、生产构建、外部模型或容器测试。Lead 的本机通过不等于专业评估、外部提供商审核或生产批准。

## 尚存限制与门禁

- 测评 submission 幂等仍是进程内锁并扫描最近 200 条，同一标识的跨 worker 并发或超出扫描窗口不保证数据库级唯一。交接已披露；如需要多 worker 强幂等，应另行设计唯一约束/迁移。
- 正式题本权利、适用人群、常模、界值、解释与人工承接仍待专业确认。工程计分不代表心理测量有效性或风险排除能力。
- `AI_EXTERNAL_ENABLED`、供应商配置、地区、留存、授权与真实输出未实测。报告多模型协同目前硬停用；单测评的外部说明仍须按显式配置启用。
- 危机词规则的灵敏度、特异度和漏报/误报率没有临床或业务验证。本复核验证了状态与持久化契约，不验证危机识别质量或人工响应 SLA。
- SDS/SAS 正式题本权利、适用人群、计分解释与人工承接仍待专业确认；多模型协同入口维持硬停用；真实外部模型与生产环境未在本复核中验证。

## 当前复核源文件 SHA-256

下列 31 个源文件哈希已在本次报告收尾时逐一与工作树重新计算，均匹配；`src/data/tests.js` 题库哈希另列于表后，也已重新计算并匹配。若后续修改须重算。

| 文件 | SHA-256 |
|---|---|
| `backend/app/routers/advanced_chat.py` | `588b820e553cb5480e4cfb273b2233e4e99e2de7b028d3ca7e9a73009c36cacb` |
| `backend/app/routers/assistant_v1.py` | `bb6f0172a8b6d7171a9c2b17fabeab768999b5934a1a6416e499a80e844c2368` |
| `backend/app/routers/llm_gateway.py` | `574a3e556655ceaa23425843cbd1e5d36fe47ddeb96f92b9b170a118aa88ccad` |
| `backend/app/routers/report_v1.py` | `14998096bb7dfcd02cc309974cb5a3808112f7a8d308afd719d447817d18d8d3` |
| `backend/app/routers/student.py` | `335fb85fce52494e53bb0a14b5df0d1eff5d25d3eb2b9ca68c8d04d7a5ad9fe7` |
| `backend/app/routers/teacher.py` | `bf1836616eab0051136e541c54618bcdcbc5a50e66c890e02a7b73f318312784` |
| `backend/app/schemas.py` | `5f16de5a5a3b7dfe7d553d0bf9201315af945f8051953515dea05e5aaf978337` |
| `backend/app/services/dialogue_analysis_service.py` | `210df9db06a90eb2328b6fc43dac2c243d6ab9d79777a91003f26dd72d674fe6` |
| `backend/app/services/llm_fallback.py` | `e81712de52334a5542b930e768a8857db61dbf05a1981207f0ba4bb19f3fc549` |
| `backend/app/services/multi_model_orchestrator.py` | `e20303e7dca4b41dd539ff4f5b89ea489dafdbbcb5e89e1aa34e46dfa5834c83` |
| `backend/app/services/qwen_service.py` | `1d6195cf6a517314293d568344d26b9e2b786929776b7023f250ad7ffa8cbbe1` |
| `backend/app/services/rag_service.py` | `5c5d98c9bdea6e63d37386e75653578949ae2bf1d227b8e943917602f8b2da9b` |
| `src/components/AIInterpretCard.vue` | `20101a6916ac2335a06a1d2ec7b958fa7fb21d51f0a0bbbaf7f58dbdd4e89ee3` |
| `src/components/RiskFactorFiveDimension.vue` | `62c19ebbe27ce13049a4d23c28b8e432932fc3c2ab0d92a4ccde9028dcadef50` |
| `src/services/assessmentFlow.js` | `d1b9a141e76cb2cda1ff3a9320624d5d14c65a66f095409f8b2c265be98d912b` |
| `src/services/assessmentFlow.test.js` | `da4f357228a7862e62e751c10629126f614d563eadfa34879a8d4cdf1fccf20a` |
| `src/services/reportNumbers.js` | `0de60f5ff2a24f5f47dbd3792eab4a8e6c5dfd9e3f27c7d97939bd2341ca16be` |
| `src/services/reportNumbers.test.js` | `9eeb2c1951729b948ebf1c073eea81dc87cbcfd205963d0aef3740c847101aef` |
| `src/views/student/AdvancedAiChat.vue` | `f0bbba7d35aece866c050bb2b0c530bee0baee0024e8e09ab07b7370e2ff7cdb` |
| `src/views/student/Dashboard.vue` | `f8d7300a1fa34bdf7c46a2fb08e50a20962561e61c9ca6d5da7d2fceeb965536` |
| `src/views/student/Report.vue` | `e09848a3303e23c96f420ce75ffb2b77a21c4a78cb192cd09be4b017dda1e74a` |
| `src/views/student/Test.vue` | `865db21475320dbc322c349fe7e06f2644fe48e752d5dd08f929ce25195d4087` |
| `src/views/teacher/AdvancedDashboard.vue` | `ef7634231c7be97f23b48cb8578a9dccb7c299dae98491cc45cc83b02f44d29f` |
| `src/views/teacher/Layout.vue` | `a0638d23d1fcf1708e763fc6a5f22a648004070e961e061f6198a4a310ad5e08` |
| `src/views/teacher/StudentDetail.vue` | `d4446141db9e4003b89de7efac965250128a085e22971eb214e3b9c73a8f06ff` |
| `src/views/teacher/StudentManagement.vue` | `41a09c60c83c3b0581035ac9b60ec12ef7faf35b24182f4d0f683001bbd50bfb` |
| `backend/tests/test_assessment_integrity.py` | `82f8b912029cf133313f9a09969ef06288842cf69d4cfb8af80e5af4e05cc3fb` |
| `backend/tests/test_assessment_interpretation.py` | `52653baa4238532bdb89a39233b312e9d428920ba73cb874c9565c2319686b26` |
| `backend/tests/test_report_evidence_integrity.py` | `be4498faeaafb025cfbfb3ffe37e6cb1bfef8fa3e6708a531a1ae6a93ea98f37` |
| `backend/tests/test_crisis_warning_sync.py` | `dabb5f61bec291f3e328e658a16eb54e5797aff5146299c2cbf0a0b0330c3d33` |
| `backend/tests/test_emotion_trend_adjustment.py` | `8ddeca7df56ba47441c81f87fdcaaf1a037646c9cb9a146f7f3f4ee18b415046` |

`src/data/tests.js` 的题库 SHA-256 为 `ab811c96af47cb88e76a842beac42984aa6ab23d0047fb59386cd11dbc2822f8`，与服务端登记哈希一致。
