> owner: A ｜ version: 1.0 ｜ status: 首批96组AI合成候选已冻结 ｜ updated: 2026-11-02

# 合成问答原稿

用户于2026-11-02明确要求逐条生成虚拟问答并录入数据库。本目录三个JSONL文件为本轮AI逐条原创的虚构成人大学生场景，不包含实际学生、历史聊天或咨询记录，不从Excel汇总统计生成个人标签。

|文件|作者角色|问答对数|主题数|场景数|
|---|---|---:|---:|---:|
|part-a.jsonl|dashboard_polish|32|4|24|
|part-b.jsonl|report_polish|32|4|24|
|part-c.jsonl|Lead|32|4|24|

作者的运行时精确模型标识未暴露，来源元数据如实记为 `unknown`。Lead整合时删除了B稿24处不必要的年龄前缀，改A稿一处具体楼栋追问，并同步连续对话的历史。独立AI复核不等于专业、临床或真人审核。所有记录的入库状态均为 `candidate`、`synthetic=true`、`professional_reviewed=false`、`split=unassigned`。

每行包含 `id/topic/scenario_id/turn_index/history/question/answer` 七个键。每主题4个单轮场景、2个双轮场景；同一场景的后续输入严格继承前轮问答。主题只是合成场景分类，不是临床标签。内容冻结后按原稿字节哈希登记，后续扩充应使用新批次，不能静默改写已发布来源。

建库工具：[import-synthetic-dialogues.py](../../../scripts/import-synthetic-dialogues.py)；专项：[test_synthetic_dialogues.py](../../../scripts/tests/test_synthetic_dialogues.py)；[验收记录](../../../docs/test/合成问答入库验收_20261102.md)。本轮不执行训练、上传或切换网站数据。
