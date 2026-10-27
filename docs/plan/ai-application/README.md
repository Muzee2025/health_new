# AI申报书源稿与图表

> owner: A ｜ version: 1.0 ｜ status: 正文与图表评审中，HTML样式待审核 ｜ updated: 2026-10-27

本目录保存图表增强版申报书的证据与六章输入。六章分别由六个`gpt-6-luna`任务编写，源稿冻结后由Lead统稿；源章中的建议、旧表编号和未采纳文字不直接作为交付。当前正文以[统稿](../心域智链申报计划书.md)为准，改动依据见[统稿记录](editorial-notes.json)。原附件保留申请表、项目简介、封面三表；真实人员、导师、周期、经费和签章后期填写。

## 文字与数据入口

| 文件 | 用途 |
| --- | --- |
| [第一章](chapter-01.md)、[第二章](chapter-02.md)、[第三章](chapter-03.md) | 问题背景、产品与市场；不同学段及调查口径分开 |
| [第四章](chapter-04.md)、[第五章](chapter-05.md)、[第六章](chapter-06.md) | 实施、AI架构与预算成果；工程基础与拟建能力分开 |
| [来源与视觉登记](visual-manifest.json) | 原作者调查、教育部统计、四项官方采购公告；每图口径、来源、许可、审核状态 |
| [制图数据](chart-data.csv) | 21项登记指标，其中一项仅报告`<5%`边界；行数不是调查样本量 |
| [独立复核](../../test/AI图表申报独立复核.md) | 来源、AI边界、原型风险与成品检查，更正记录保留 |

## 简化后的出图方法

[统计图脚本](../../../scripts/render-application-figures.py)只读取CSV和视觉登记，统一调用同源色板并导出5张PNG/SVG，不再包含思维导图、流程图或硬编码的采购数据。[HTML导出脚本](../../../scripts/export-application-diagrams.mjs)单独渲染4张可编辑图示，使用新浏览器上下文，不访问业务接口。

统计图的目的分别为：青少年抑郁筛查分组与学习体验的样本内差异、大学生竞争感知、教育场景体量、不同采购范围的公告金额、免费咨询两道独立问题。数据均为公开汇总，没有个体记录或连续时间序列，故采用柱形比较与采购分面，不为图型多样而构造趋势、相关性或误差棒。`<5%`只写说明，不画成精确5%；80.0%与2.8%不组成漏斗或转化率；学校/学生总量不换算客户或收入；采购案例不计算均价或本项目预算。

所有PNG按300DPI导出；5张统计图同时提供可编辑文字SVG，4张概念图以HTML保留编辑源。配色、字体与边框取自`src/styles/tokens.css`。概念图是方案示意，实线/虚线用于区分既有工程原型与拟增强/可选能力；图示不证明效果或放行。

正文采用5张数据图和3张概念图，共8幅；阶段安排已有原生表格，故第4张阶段概念图只保留为备用素材。当前[Word审阅稿](../../../deliverables/心域智链项目申报材料_图表增强审阅稿.docx)为26页，另有[完整正文HTML审阅版](../../../deliverables/心域智链申报书正文审阅版.html)，可下载后直接打开。

在仓库根目录，用依赖加载器返回的捆绑Python/Node运行：

```powershell
& $pythonRuntime scripts/render-application-figures.py
& $nodeRuntime scripts/export-application-diagrams.mjs
& $pythonRuntime scripts/build-ai-application.py --output tmp/ai-application-20261027/new-draft.docx
```

`$pythonRuntime`、`$nodeRuntime`须先指向实际捆绑可执行文件；当前Matplotlib是仅装入`tmp/ai-application-20261027/pydeps`的任务依赖，没有修改项目依赖。脚本的运行环境路径属于本机复现配置，不作为业务代码或服务器安装方案。

## 样式审核与交付

用户否定Figma样式后，使用[简洁HTML逻辑图](../../design/申报逻辑图预览.html)及[技术图示HTML](../../design/申报技术图示.html)。浏览器地址无法在用户端显示时，已直接在对话展示截图，并提供[内嵌样式HTML](../../../deliverables/心域智链申报逻辑图预览.html)。Figma仅保留为旧设计参考，未作为获认可的最终图。

`userStyleApproved`当前为`false`；内部候选可构建，`--final`会拒绝发布。用户确认后还需将最终DOCX重新渲染、逐页查看并交独立复核，不能把旧16页验收或内部候选检查当作新版完成。内部PDF、页图、旧图和原始QA证据均保存在忽略目录`tmp/ai-application-20261027/`。

答辩大纲已按用户要求在独立对话处理，本目录不生成PPT，也不修改该对话独占的大纲文件。
