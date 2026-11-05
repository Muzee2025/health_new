# 后端 AI 与测评解析修复交接

> owner: C / FIX-BE-01/02 ｜ version: 1.1 ｜ status: 工程交接，等待 Lead 整合与独立复核 ｜ updated: 2026-10-31

## 范围与输入

本任务基于 `docs/plan/项目补全与改进方案_20261031.md`、现有题本 `src/data/tests.js`、`TestSubmit`、学生端提交/报告路由与 Qwen 服务现状。仅修改 `backend/app/routers/student.py`、`backend/app/schemas.py`、`backend/app/services/qwen_service.py`，新增两项隔离测试及本交接文档；未改迁移、`rag_service.py`、环境配置、前端、运行数据库、服务或真实模型。其他聊天中已有未提交文档及交付物保持原位；未暂存、提交或切换分支。

## 冻结的前后端契约

### 提交测评

`POST /api/student/tests/submit`

```json
{
  "test_type": "SDS",
  "answers": {"0": 1, "1": 2},
  "submission_id": "稳定的客户端重试标识"
}
```

- `answers` 的键为本题本的 0-based 题目位置字符串，值为用户选择的原始选项；反向题也不由客户端反转。
- 客户端不得提交分数、等级、风险、描述或 result JSON；未知字段被拒绝。服务器检查工具、题数、题目编号、选项类型和值，并独立计分。
- 成功响应保留 `id`，并提供同值 `test_id`；保留历史字段并附 `assessment_status` 与 `scoring` provenance。SDS/SAS 返回服务器重算的粗分/标准分，但 `result_level="待专业复核"`、`risk_level=null`、`assessment_status="pending_professional_review"`，没有擅自应用正式界值。MBTI 与心理年龄标记 `entertainment_only`，不作为风险/报告测评依据。
- 相同学生、工具及 `submission_id` 的近期相同答卷可复用原记录；同 ID 不同答卷返回 409。现实现为进程内锁并扫描最近 200 条记录，**不保证跨 worker 并发或超过 200 条历史后的幂等性**，没有宣称数据库级幂等。

### AI 解释

`POST /api/student/tests/ai-analyze`

```json
{"test_id": 123}
```

- 必须指定当前记录 ID。记录必须属于当前学生；不存在或跨用户 ID 返回 404，不会改用“最新记录”。旧记录无计分 provenance 时说明“版本未知/资料不足”。
- 返回 `{status, source, model_id, test_id, content:{summary,observations,limitations,next_steps}, sources, notice}`。默认没有外部服务配置时返回 `status=fallback`、`source=local_rule`、`model_id=null`，明确说明本地规则而非模型生成。
- `test_id` 是严格正整数；字符串、布尔、零、负数以及未知请求字段被拒绝。provider 必须返回精确结构，summary 为非空字符串且最多 500 字；数组最多 8 项，每项为非空字符串且最多 240 字。错误、空值、错误 JSON/schema 降级为本地结构化结果。provider 的 `model_id` 只使用响应对象的真实 `model` 元数据，缺失时为 null。
- `sources` 是工程 provenance 数组，不是外部文献，例如 `{type:"scoring_provenance", label:"本地计分规则记录（非外部文献）", tool_id, form_version, scoring_version, form_hash, question_bank_source_sha256, external:false}`；旧记录缺少来源字段时为 null。
- 只有进程显式启用 `AI_EXTERNAL_ENABLED` 且 Qwen 客户端在启动时由有效配置建立后，才可能出站。输入为工具、服务器分数、资格状态及本地摘要；不含逐题选项、姓名、学号、联系方式、树洞原文。调用固定 12 秒超时且禁自动重试；异常或非结构化响应退回本地结构化说明。

## 实施内容

- 新提交 schema 禁止多余字段与客户端计分字段。服务器依据现有四个题本的题数、原始选项、SDS/SAS 反向题位置以及既有趣味题维度规则重算。保存 `result_json` 中的工具/题本版本、题本源文件 SHA-256、计分规则指纹、计分引擎版本、资格和提交标识；无需迁移。
- 趣味量表已从学生最新心理测评/图表与正式报告依据中排除；旧答卷没有可信版本标记时不进入新版本聚合，AI 解释明确版本未知。
- 报告不再固定声称 RAG 已命中；只有查询返回非空内容时才记录检索来源。报告上下文去除树洞原文，外部调用需显式开关；无依据的降级文本改为资料不足。树洞情绪规则不再命名为 AI，并将帖子与规则摘要写入同一数据库事务，失败回滚；无数据的红能量趋势返回空/当前实值，不制造历史曲线。
- 历史 `result_json` 只有合法 JSON 对象且 `provenance` 也是对象才被当作元数据；数组、null、标量、非法 JSON 或错误形状安全归为 unknown。AI、提交重试、学生聚合和报告路径共用该读取规则。报告逻辑明确当前工程计分、常模与解释待专业复核，不声称常模判定。
- Qwen 不再用硬编码 placeholder key 初始化客户端，默认关闭外部调用，去掉未核验的“校内 24 小时热线”号码；空记录不再报告“当前状态平稳”，降级数据有 `status/source/model_id`，原有方法签名及主要结果字段保持。
- Qwen 对话报告路径不发送聊天原文，只发送非空记录条数；要求精确 JSON 字段并校验内容类型/长度。只凭条数无法推断状态、风险、趋势或因果；检测到无依据的趋势/风险用语或错误 schema 时降级。

## 验收记录

最终命令（仓库根目录）：

```powershell
.\.venv\Scripts\python.exe scripts/run-backend-baseline.py backend/tests/test_assessment_integrity.py backend/tests/test_assessment_interpretation.py
```

- FIX-BE-02 最终退出码：`0`；`28 passed, 15 warnings`（2026-10-31）。使用项目既有隔离 runner：临时 SQLite/文件、dotenv 与 RAG 禁用、Python socket/DNS 阻断。
- 中间失败如实记录：FIX-BE-01 期间规则指纹序列化 `set` 曾有 2 failed；FIX-BE-02 一次执行因 synthetic provenance fixture 缺少 source hash 有 4 failed。修复后完整复跑通过。
- 测试覆盖服务器计分与伪造拒绝、提交重试、严格正整数 AI ID、旧记录 malformed JSON、报告无常模判定、来源对象格式、fake provider 成功/超时/错误 JSON/错误 schema/输入最小化，以及 Qwen 报告仅发送计数且对不支持的趋势/风险声明降级。
- 未运行完整后端测试、前端测试/构建、真实 HTTP/浏览器、真实模型或生产/容器验证；**本任务通过不代表完整后端、AI 提供商、专业问卷或生产门禁通过**。完整后端由 Lead 按项目规则另行执行。

## 限制与后续

- 当前 SDS/SAS 题数、选项、反向题与趣味规则镜像来自当前本地题库代码；其工程题本源哈希为 `ab811c96af47cb88e76a842beac42984aa6ab23d0047fb59386cd11dbc2822f8`。源题本或规则变化时，必须协同改版本/哈希并复核；工程哈希不等于权利/译本/人群/计分方法获批。
- 正式工具的题本权利、人群、界值、解释、告知与人工承接仍未确认。SDS/SAS 只生成数学计分，不能用于诊断、风险等级或绿灯排除；趣味工具只供自我探索。
- `AI_EXTERNAL_ENABLED`、提供商密钥、供应商/地区/留存与外部人工评估未在本任务实测。密钥变量值未读取或输出。Qwen 客户端在应用进程启动时加载；配置变更需要由获授权的运维流程管理。
- student.py 的提交重试仅进程内串行，不是多 worker 原子去重；实现只检查最近 200 条同工具结果。要获得跨进程幂等需后续方案批准唯一约束/迁移或独立 submission 表。
- 服务端问卷目前只支持四个登记类型，其他旧 `general` 测评提交会被 422 拒绝；这是防止未知工具落入风险统计的 fail-closed 处理。
- 已将冻结契约（含 0-based 原始选项、`id/test_id`、`submission_id` 与 AI 响应字段）交给前端 agent 与 Lead。前端不得静默改题本数据；题库变化需同步更新 provenance 指纹。

## 文件与源哈希

最终源文件 SHA-256（冻结后计算）：

| 文件 | SHA-256 |
| --- | --- |
| `backend/app/routers/student.py` | `53365f143a6d7cd312286b47355b4bc773423ad1ff29daa66bc59ac91a2de655` |
| `backend/app/schemas.py` | `5f16de5a5a3b7dfe7d553d0bf9201315af945f8051953515dea05e5aaf978337` |
| `backend/app/services/qwen_service.py` | `1d6195cf6a517314293d568344d26b9e2b786929776b7023f250ad7ffa8cbbe1` |
| `backend/tests/test_assessment_integrity.py` | `82f8b912029cf133313f9a09969ef06288842cf69d4cfb8af80e5af4e05cc3fb` |
| `backend/tests/test_assessment_interpretation.py` | `52653baa4238532bdb89a39233b312e9d428920ba73cb874c9565c2319686b26` |
| `src/data/tests.js`（源题库，仅只读） | `ab811c96af47cb88e76a842beac42984aa6ab23d0047fb59386cd11dbc2822f8` |

Lead 整合前若上述实现文件继续修改，应重算并更新本节哈希及交接状态。
