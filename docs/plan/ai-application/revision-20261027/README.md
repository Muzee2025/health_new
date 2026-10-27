# 地区数据与文风修订输入

> owner: A ｜ version: 1.0 ｜ status: 六章冻结，Lead统稿完成 ｜ updated: 2026-10-27

本轮响应用户关于文字自然、地区数据表图结合、正文说明移附录的意见。六个独立gpt-6-luna任务分别撰写[第一章](chapter-01.md)、[第二章](chapter-02.md)、[第三章](chapter-03.md)、[第四章](chapter-04.md)、[第五章](chapter-05.md)、[第六章](chapter-06.md)。源章冻结，末尾“供Lead移入附录的说明”属于交接内容。交付正文以[统稿](../../心域智链申报计划书.md)为准，构建器统一编号、去除重复提示、调整AI范围并集中附录；[移动记录](editorial-moves.json)保留原句和原因。

| 文件 | 用途 |
| --- | --- |
| [2024地区数据CSV](regional-education-2024.csv) | 31地区原始人/所数值，正文换算万人保留两位小数 |
| [地区来源及口径JSON](regional-education-2024.json) | 5张教育部表、选列、原始HTML哈希与汇总数 |
| [地方建设资料](regional-services.md) / [结构数据](regional-services.json) | 8地来源及实际值、标准事件和要求，异口径案例不排名 |
| [独立复核](../../../test/申报书地区比较与文风复核.md) | 重新抽取31地数据、核查8地来源和最终正文/OOXML |
| [本轮验收](../../../test/申报书地区数据修订验收.md) | 26页Word与HTML、15表10图、附录和视觉证据 |

[采集器](../../../../scripts/collect-regional-education.py)只从已保存的官方HTML读数并写本目录CSV/JSON；原始网页保持在私有tmp，不入库。[地区制图](../../../../scripts/render-regional-education.py)只读CSV导出两图，色板来自素材token。[修订构建器](../../../../scripts/build-revised-application.py)复用原附件格式，要求使用新的候选输出路径，不覆盖旧候选；[校验器](../../../../scripts/verify-revised-application.py)只读核验。

本目录不是答辩大纲输入的唯一副本，也不授权当前对话改动大纲文件；当前只交付申报修订供用户审阅。
