> owner: A ｜ version: 0.1 ｜ status: 定稿 ｜ updated: 2026-10-20

> 归档说明：历史文档完整保留，原路径为 `docs/qwen3.6-plus_degrade_fix_report.md`。文中指标、标题与实现描述均为历史内容，未经本次核验，不代表当前状态。

# qwen3.6-plus 持续异常降级修复报告

## 1. 问题描述
- 现象：多模型协同分析链路中，`qwen3.6-plus` 在近 7 天内持续出现异常降级（fallback 到 `qwen-max`），导致主模型能力未稳定发挥。
- 影响：报告生成虽未完全失败，但主模型命中率下降、耗时波动增大，且异常归因信息不足。

## 2. 根因分析（近 7 天日志）
- 日志来源：`backend/logs/multi_model_orchestrator.log`。
- 时间窗口：近 7 天。
- 统计结果：
  - `qwen3.6-plus` 调用总数：16
  - 异常次数：5
  - 异常率：31.25%
- 关键特征：
  - 错误均表现为 `model_call_failed`，但原日志缺少细粒度错误类型，定位困难。
  - 异常耗时集中在约 37s、69s、91s，符合“上游超时/重试后超时”特征。
  - 异常呈簇状（部分时段集中爆发），符合上游抖动或瞬时限流模式。

## 3. 修复目标
- 增加细粒度监控：按模型统计错误率、连续失败数、熔断状态与告警事件。
- 增加熔断策略：当错误率/连续失败超过阈值时，自动打开熔断窗口，直接降级并告警。
- 增加稳态策略：指数退避 + 抖动，减少重试风暴。
- 保证不误降级：主模型正常时不触发熔断。

## 4. 改动清单

### 4.1 编排器核心增强
- 文件：`backend/app/services/multi_model_orchestrator.py`
- 新增能力：
  - 模型健康状态缓存（窗口统计、连续失败、熔断状态、打开次数）。
  - 错误分类：`timeout`、`rate_limit`、`auth`、`upstream_5xx`、`network`、`invoke_failed`。
  - 熔断策略（主模型）：
    - `MODEL_FAILURE_WINDOW_SEC`
    - `PRIMARY_CIRCUIT_MIN_SAMPLES`
    - `PRIMARY_CIRCUIT_ERROR_RATE`
    - `PRIMARY_CIRCUIT_CONSECUTIVE`
    - `PRIMARY_CIRCUIT_COOLDOWN_SEC`
  - 自动告警事件：`model_circuit_open`（记录在指标与日志）。
  - 重试策略升级为“指数退避 + 抖动”，并在 SSE 中输出 `errorType/backoffSec`。
  - 熔断打开时主模型直接降级到 `PRIMARY_MODEL_FALLBACK`，避免持续超时拖垮链路。

### 4.2 运行时可观测性接口
- 文件：`backend/app/routers/report_v1.py`
- 新增接口：
  - `GET /api/v1/report/analysis/collab/health`
  - 返回 `orchestrator.get_metrics()`，包含 alerts 与每模型健康状态。

### 4.3 配置项
- 文件：`backend/.env.example`
- 新增可配置项：
  - `PRIMARY_TEXT_MODEL`
  - `PRIMARY_MODEL_FALLBACK`
  - `QWEN_API_KEY`
  - `MODEL_FAILURE_WINDOW_SEC`
  - `PRIMARY_CIRCUIT_MIN_SAMPLES`
  - `PRIMARY_CIRCUIT_ERROR_RATE`
  - `PRIMARY_CIRCUIT_CONSECUTIVE`
  - `PRIMARY_CIRCUIT_COOLDOWN_SEC`
  - `MODEL_RETRY_ATTEMPTS`

## 5. 修复方案与对应场景
- 超时/推理失败：指数退避重试；超过阈值自动熔断，冷却期内直接降级，缩短尾延迟。
- 上游抖动/限流：错误分类沉淀到指标；告警事件可用于外部告警平台接入。
- 异常归因不清：结构化错误类型 + 告警 payload，便于运维定位。
- 误降级风险：仅当“样本数 + 错误率 + 连续失败”同时满足才熔断。

## 6. 测试与验证
- 新增测试：`backend/tests/test_qwen_degrade_guard.py`
  - `test_primary_degraded_fallback_opens_circuit`
  - `test_primary_success_does_not_false_degrade`
  - `test_run_task_integration_with_guard_and_metrics`
- 回归命令：
  - `python -m pytest tests/test_startup_compatibility.py tests/test_qwen_degrade_guard.py -q`
- 结果：
  - `5 passed`
  - 关键目标达成：
    - 正常路径：主模型稳定返回，不误降级。
    - 异常路径：持续降级触发熔断并生成告警事件。
    - 集成路径：任务流转与指标输出正常。

## 7. 性能对比（修复前 vs 修复后）
- 修复前：
  - 持续异常时会重复等待主模型超时，尾延迟明显放大。
  - 缺少错误分类与熔断，难以快速止损。
- 修复后：
  - 在达到阈值后，进入熔断冷却窗口，主模型调用时间由“超时级”降到“直接降级级”。
  - 通过窗口统计与告警机制，能够快速识别并外部联动。

## 8. 生产上线步骤（零回归）
1. 合并代码并发布到灰度环境。
2. 配置 `.env` 新增参数（建议先用默认值）。
3. 执行回归测试：
   - `python -m pytest tests/test_startup_compatibility.py tests/test_qwen_degrade_guard.py -q`
4. 验证健康接口：
   - `GET /api/v1/report/analysis/collab/health`
   - 关注 `metrics.models[qwen3.6-plus]` 与 `metrics.alerts`。
5. 灰度观察 24 小时：
   - 指标：错误率、熔断触发次数、平均响应时长、P95/P99。
6. 全量发布。

## 9. 后续建议
- 将 `metrics.alerts` 对接企业微信/钉钉告警通道。
- 增加按错误类型的仪表盘（timeout/5xx/rate_limit）。
- 逐步将历史 `model_call_failed` 统一替换为结构化错误码，进一步提升可观测性。
