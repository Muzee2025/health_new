# 深度思考模块诊断报告

生成时间（UTC）：2026-04-25T08:10:00Z  
样本输入：`我最近获得比赛第二名 我很开心`  
样本规模：10 次连续流式调用（`/api/advanced-ai/chat/stream`）  
独立情感模型：`SnowNLP 0.12.3`

## 1. 日志与链路审计

- 已采集每次请求的：
  - `started_at / ended_at`（UTC 时间戳）
  - `client_trace_id`（诊断注入）
  - `nonce`、`nonce_echo_ok`
  - `first_token_latency_ms`
  - `total_latency_ms`
  - `status_code / content_type`
- 结果文件：
  - `deep_think_runs.json`
  - `deep_think_runs.csv`
  - `traceid_index.json`
- 审计结论：
  - 后端深度思考接口当前**未输出服务端 traceId**，无法做到服务端-模型端闭环追踪。
  - 接口响应体当前**未包含 token 用量字段**。
  - 代码审计未发现 deep-think 路径下显式 `mock` 标记，但存在兜底返回与模板短路风险（见第 6 节）。

## 2. 语义一致性校验

- 输入文本情感（SnowNLP）：
  - positive = 0.8819
  - negative = 0.1181
- 回复文本情感（10 次）：
  - 与输入极性差值 `|polarity_in - polarity_out|` 在 `0.2195 ~ 0.2316`
  - 阈值为 `0.6`，因此 10/10 均**未触发逻辑冲突**
- 一级异常规则（开心→难受）检查：
  - 回复语义出现“很难受”模板句，但 SnowNLP 极性仍偏正，统计口径下未判定为阈值冲突。
  - 该语义不一致仍建议作为规则异常进行监控（语义层面）。

## 3. 深度调用验证（Nonce）

- 每次请求头注入：
  - `X-Diag-Nonce: <random>`
  - `X-Trace-Id: <client_trace_id>`
- 回显结果：
  - `nonce` 回显成功率：`0/10 = 0%`
  - 统计检验（H0: success >= 95%）：`p = 9.765625e-14`，显著拒绝 H0
- 关键说明：
  - 当前后端代码未读取请求头 nonce，也未透传到 `zhipu_emohaa_service` prompt，导致该校验机制天然失败。
- 耗时可疑阈值（<1s）检查：
  - 10 次均 > 1 秒，未触发二次重放。

## 4. 配置与开关检查

- 深度思考触发路径：
  - 接口请求体字段：`deep_think`（`ChatRequest.deep_think`）
  - 前端开关：`deepThinkEnabled`（localStorage 持久化）
- 后端环境变量（与 deep-think 相关）：
  - `ZHIPU_API_KEY`
  - `ZHIPU_BASE_URL`
- 实验桶/白名单：
  - 未检索到深度思考路径下 AB 实验桶、白名单、feature flag 分流实现。
  - 结论：当前默认“同一路径”，不存在可识别的对照组配置。

## 5. 复现与压测统计

- 延迟分布（ms）：
  - avg = 6897.92
  - min = 5235.48
  - p50 = 6874.35
  - p90 = 8356.14
  - max = 10031.19
- 情感矛盾率：`0%`
- nonce 回显率：`0%`

## 6. 根因定位与优先级

- P0：**nonce 验证链路缺失**
  - 后端未接收/透传 nonce，无法证明“请求与响应属于同一真实推理调用”。
- P0：**深度思考 fallback 文本语义与用户情绪可能冲突**
  - `_format_deep_think_reply` 对短回复直接拼接固定模板，模板包含“很难受”，会与“我很开心”等输入冲突。
- P1：**缺少服务端 traceId 与 token 审计字段**
  - 诊断可观测性不足，难以做线上问责与归因。
- P2：**缺少显式 cache/mock 标记**
  - 结果不可判别“实时推理 vs 缓存复用”。
- P3：**缺少专门回归用例**
  - 未覆盖“nonce 回显”“正向情绪输入语义一致”自动化测试。

## 7. 热修复建议

1. 配置层（P0）
   - 新增 `DEEP_THINK_NONCE_ECHO_REQUIRED`（默认 false，灰度开启）。
   - 新增 `DEEP_THINK_AUDIT_ENABLED`，统一输出 trace/timing/token 字段。

2. 代码层（P0/P1）
   - 在 `chat/stream` 与 `chat` 路由读取 `X-Diag-Nonce`/`X-Trace-Id`。
   - 将 nonce 明确写入 deep-think prompt，要求模型首段回显。
   - 响应 `done` payload 增加：
     - `trace_id`
     - `model_name/model_version`
     - `usage.prompt_tokens/completion_tokens/total_tokens`
     - `ttfb_ms/latency_ms`
     - `cache_hit/mock_hit/fallback_hit`
   - 修复 `_format_deep_think_reply` 的固定消极模板，改为“按输入情感极性生成中性模板”。

3. 发版与灰度（P1）
   - 5% 用户灰度 30 分钟，监控：
     - nonce 回显率
     - fallback_hit
     - 延迟 p95
     - 情感冲突率
   - 通过阈值后扩大到 30%、100%。

4. 回归测试（P1）
   - 新增自动化用例：
     - deep-think nonce 回显一致性
     - 正向输入（开心）不输出明显负向安抚模板
     - done payload 必含 trace/token/timing

