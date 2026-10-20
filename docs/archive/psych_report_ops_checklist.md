> owner: A ｜ version: 0.1 ｜ status: 定稿 ｜ updated: 2026-10-20

> 归档说明：历史文档完整保留，原路径为 `docs/psych_report_ops_checklist.md`。文中指标、标题与实现描述均为历史内容，未经本次核验，不代表当前状态。

# 心理报告模块运维清理清单

## 1) 缓存链路巡检

- Redis 键巡检：`report:*`
- 命中率指标：`report:load:hit_rate`、`report:load:miss`
- Prometheus 建议抓取间隔：15s
- 告警阈值：命中率 `< 95%`

## 2) Airflow 移除 DAG

在 Airflow 管理端下线并删除 DAG：

- `calculate_risk_level_daily`

可选命令行：

```bash
airflow dags delete calculate_risk_level_daily --yes
```

## 3) RabbitMQ 队列清理

确认无消费者后删除队列：

- `risk.level.score`

参考命令：

```bash
rabbitmqctl list_consumers
rabbitmqadmin purge queue name=risk.level.score
rabbitmqadmin delete queue name=risk.level.score
```

## 4) MR 附件清单

- 缓存命中率截图
- 风险等级组件清理 diff 截图
- `/report/visual` 录屏（下钻、排序、AI 解读）
- Lighthouse 报告 PDF
