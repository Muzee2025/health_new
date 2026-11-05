# 方向矢量与PPT思维导图候选

> owner: AI-OUTLINE ｜ version: 1.0 ｜ status: 候选素材与关系图示例 待用户审阅 ｜ updated: 2026-10-27

按“方向、路径引导和思维导图”理解用户本轮需求，提供12个方向图标、3张按申报书内容整理的关系图，以及4个适合继续找素材或编辑关系图的官方入口。本轮只整理候选，未替换现有8页PPT。

[整体预览](preview.png) · [可点击预览页](preview.html) · [来源与文件登记](manifest.json)

## 建议放入PPT的图

| 示例 | 使用位置 | 文件 |
| --- | --- | --- |
| 项目概览思维导图 | 项目或产品概览，展示学生、教师、拟建AI和实施保障的关系 | [SVG](project-mindmap.svg) · [PNG预览](project-mindmap.png) · [draw.io源稿](project-mindmap.drawio) |
| AI分析流程图 | 第4页，区分字段检查、统计、检索、大模型与教师分工 | [SVG](ai-flow.svg) · [PNG预览](ai-flow.png) · [draw.io源稿](ai-flow.drawio) |
| 实施路径图 | 第6页，说明流程了解、合成演示、培训维护和获批后的任务验证 | [SVG](implementation-route.svg) · [PNG预览](implementation-route.png) · [draw.io源稿](implementation-route.drawio) |

三图均为本项目根据S5申报书原创整理，颜色取自既有`src/styles/tokens.css`。图片不含总图题，图题放在幻灯片正文；各图的内容映射及源稿哈希在manifest登记。思维导图连线表示关联，流程箭头表示先后，不把不同关系统一画成循环。替换相应主讲页时保持总计8页。

## 方向素材

12个Phosphor Regular SVG分别表示顺序推进、转向、折线、返回、分支、汇合、迭代、路径、处理流向、层级、支线和目标方向。与上一轮及项目既有Phosphor图标同源。固定上游版本`2b75f3ad12b420c9504ef05df8d2564a28f8500e`，原始路径和实际下载地址逐项登记；未改色、未改路径。[MIT版权与许可](LICENSE-PHOSPHOR-MIT.txt)随附。

## 推荐素材库与编辑入口

| 入口 | 适合寻找的内容 | 放到PPT的方式 |
| --- | --- | --- |
| [Phosphor](https://phosphoricons.com/?q=arrow) | 箭头、方向、分叉、合并、层级与流程标记 | 下载SVG，作为辅助图标使用 |
| [draw.io概念图与Maps模板](https://www.drawio.com/docs/diagram-types/concept-maps/) | 思维导图、概念图、层次结构和站点图 | 保留`.drawio`源稿，导出SVG插入PPT |
| [PowerPoint SmartArt](https://support.microsoft.com/en-us/office/graphics-visuals/choose-a-smartart-graphic) | 关系型、层次结构、流程与循环 | 直接在PPT内建立原生图形，便于改文字与结构 |
| [Xmind](https://xmind.com/user-guide/export-new) | 分支较多、需要先梳理层次的思维导图 | 官方说明支持SVG和PowerPoint等导出；使用权限以实际版本及套餐为准 |

draw.io模板入口可参看[官方模板说明](https://www.drawio.com/docs/manual/templates/insert-template-online-whiteboard/)，图形导出可参看[SVG导出说明](https://www.drawio.com/docs/manual/export/export-to-svg/)。这些链接是素材与工具入口，并未批量下载、重新分发第三方模板，也不把工具的软件许可直接当作所有社区模板的许可。

## 格式与修改方式

SVG是矢量图，插入PPT后可整体缩放。[Microsoft官方说明](https://support.microsoft.com/en-gb/office/graphics-visuals/edit-svg-images-in-microsoft-365)列明SVG插入与转换形状功能。它与PowerPoint原生可编辑节点不同，不能承诺任意SVG文字与连接关系均能在PPT内直接修改。逐节点修改可用[diagrams.net](https://app.diagrams.net/)打开本包的`.drawio`文件；若需要在PPT中持续改结构，宜用SmartArt或原生形状重建。

本包SVG使用原生`text`与路径，无`foreignObject`、内嵌位图或外部资源，中文字体选Microsoft YaHei。draw.io原稿与SVG保留相同节点、文字、位置和关系；编辑器中的自动连线与圆角效果可能略有差别。复杂标签的兼容限制见[draw.io官方说明](https://www.drawio.com/docs/manual/export/svg-export-text-problems/)。

## 内容与核验范围

AI图对应申报书1.4及第五章，明确是拟建设流程，不代表已经启用真实模型或通过专业有效性验证。路径图对应第四章与第六章，不填写未提供的人员、周期、经费或试点。概览图展示四类任务关系，不代替申报书或全部章节。

执行者联网核对上述官方入口，在隔离Edge中离线预览15个SVG（12图标和3关系图），检查3张1600×900页图及总体预览。浏览器文字边界检查通过；`.drawio`检查XML、节点ID及连线引用。未在draw.io编辑器或PowerPoint内实际编辑、保存及重开，不把XML和浏览器检查写成应用内验收。独立复核记录与生成脚本在私有`tmp/ai-outline-20261027/direction-map-v1/`保留。

本轮只写PPT候选目录、现有视觉清单及本次新素材包；申报书、原图、既有素材库入口、实时PPT、业务代码和运行数据/服务未操作。未暂存、提交或推送。候选由[视觉清单](../AI答辩大纲视觉清单.md)索引，共享记录由主对话Lead统筹。
