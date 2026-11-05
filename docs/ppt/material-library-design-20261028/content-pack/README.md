# 申报书专用答辩素材库

> owner: AI-OUTLINE ｜ version: 2.0 ｜ status: 内容已按申报书重排 界面预览网络阻塞 ｜ updated: 2026-10-28

本包按现有8页答辩大纲整理S5申报书原图、项目关系图、可编辑draw.io源稿和同源图标。素材取自已登记文件，复制后与原文件逐字节核对，没有把生成图片伪装成SVG。以下每项均附申报章节和使用边界。

这是可复用文件与内容索引，不是已实现的素材库网页。内置ImageGen生成新界面时连续两次遇到网络错误，本轮没有新界面图片；旧设计稿不代表本次内容已完整修正。

来源、哈希、主讲/备查属性与格式见[manifest.json](manifest.json)。全包含13张申报原图的SVG/PNG、3张项目图的SVG/PNG/drawio、8个Phosphor SVG和1张合成预约截图；合计24个SVG，不将备用图追加为PPT页。

## 01 项目概览

申报书对应：摘要、2.1、2.5。

关系图作为一项主要视觉，说明学生、教师和拟建AI的任务关系。

主素材：[project-mindmap](diagrams/project-mindmap.svg)

源稿/替换/备查：[project-mindmap.drawio](diagrams/project-mindmap.drawio)

内容口径：不将关系图中的拟建AI写成已完成能力。

## 02 背景需求

申报书对应：1.1、1.3，表1与图3。

主图使用咨询知晓/使用原图，竞争感知图留作替换或问答备查，避免一页堆两图。

主素材：[fig09-service](figures/fig09-service.svg)

源稿/替换/备查：[fig02-pressure.svg](figures/fig02-pressure.svg)

内容口径：80.0%与2.8%为2024年本科生调查不同题项；不画漏斗、不计算转化率。竞争感知不是患病率。

## 03 产品服务

申报书对应：2.1—2.4，表4、图7。

架构或关系图配学生本人记录、求助预约、教师查阅明确分配事项、人工答复和跟进的文字。预约截图作为合成示例。

主素材：[fig06-architecture](figures/fig06-architecture.svg)

源稿/替换/备查：[teacher-appointments-synthetic.webp](demo/teacher-appointments-synthetic.webp) · [project-mindmap.drawio](diagrams/project-mindmap.drawio)

内容口径：不写陪伴咨询、个别辅导、个性化指导或资源推荐已提供；示意插画不作为功能验收证据。

## 04 AI实现

申报书对应：1.4、5.1—5.3，表13/14、图13。

主讲用五步简图，申报原图留作详细备查。摘要按已有记录、尚缺信息、待核对问题、参考依据四部分展示。

主素材：[ai-flow](diagrams/ai-flow.svg)

源稿/替换/备查：[ai-flow.drawio](diagrams/ai-flow.drawio) · [fig07-ai-workflow.svg](figures/fig07-ai-workflow.svg)

内容口径：标题标拟建；模型根据已确认事实和审核资料起草，教师修改、采用或弃用；失败回原始记录和人工流程。

## 05 湖北市场

申报书对应：3.1、3.2、3.4，表7、图9/10。

主讲仍优先呈现2024年湖北133所普通/职业高校、191.52万本专科在校生及测评后求助、教师答复、记录整理等切入任务；软件、部署、维护和专业服务采购范围分开明确。比较图用于替换或备查，避免堆31地表。

主素材：[fig11-hubei-neighbours](figures/fig11-hubei-neighbours.svg)

源稿/替换/备查：[fig10-regional-college.svg](figures/fig10-regional-college.svg)

内容口径：教育规模为前期调研背景，不换算客户、实际服务量、心理风险需求或收入。

## 06 实施验证

申报书对应：4.1—4.3，表12、表16。

四阶段主图：流程了解、合成演示、培训维护、校内获批后的任务验证。4.4的后续中学适配留作问答，主讲按精简大纲省略。

主素材：[implementation-route](diagrams/implementation-route.svg)

源稿/替换/备查：[implementation-route.drawio](diagrams/implementation-route.drawio)

内容口径：不虚构周数、试点或效果；观察任务完成、耗时、错误和教师草稿修改。

## 07 组织预算

申报书对应：6.1、6.2，表15。

以责任文字与六项预算科目为主，图标仅辅助标题。需要图形时用PPT原生形状或SmartArt按源稿建立，当前未创建原生PPT图。

主素材：[roles-budget-source](roles-budget-source.txt)

源稿/替换/备查：[phosphor-database.svg](icons/phosphor-database.svg) · [phosphor-book-open.svg](icons/phosphor-book-open.svg) · [phosphor-shield-check.svg](icons/phosphor-shield-check.svg)

内容口径：人员、导师、周期、单价与金额待填写，不做虚构金额图或预算比例饼图。

## 08 预期成果

申报书对应：6.3、6.4，表16。

四项交付：可复验原型、统计图表、摘要与评测记录、培训治理与运行恢复材料；用少量图标辅助，文字标预期。

主素材：[phosphor-files](icons/phosphor-files.svg) · [phosphor-chart-line-up](icons/phosphor-chart-line-up.svg) · [phosphor-book-open](icons/phosphor-book-open.svg) · [phosphor-shield-check](icons/phosphor-shield-check.svg)

内容口径：不把预期交付、合成演示或技术复验写成专业有效性验证、校方采用或生产放行。

## 申报原图备查

下列原图用于按需查证，不表示全部放入8页主讲。图题由幻灯片正文承载，来源、统计范围和工程说明放备注或备查。文献筛查亚组及地区汇总不得解释为学生个人风险、地区代表患病率或因果关系。

- [2024年青少年抑郁筛查分组与学习状态。（a）上学意愿；（b）自陈学习行为](figures/fig01-youth.svg)（[PNG](figures/fig01-youth.png)）
- [2023年大学生学业竞争感知](figures/fig02-pressure.svg)（[PNG](figures/fig02-pressure.png)）
- [2024年大学生免费咨询知晓与使用](figures/fig09-service.svg)（[PNG](figures/fig09-service.png)）
- [不同学段抑郁症状筛查阳性的合并比例及95%置信区间](figures/fig12-literature-stage.svg)（[PNG](figures/fig12-literature-stage.png)）
- [纳入研究的31省份地区亚组合并比例与95%置信区间](figures/fig13-literature-regions.svg)（[PNG](figures/fig13-literature-regions.png)）
- [AI+高校心理测评与持续支持逻辑](figures/fig05-mindmap.svg)（[PNG](figures/fig05-mindmap.png)）
- [系统与AI能力的分层关系](figures/fig06-architecture.svg)（[PNG](figures/fig06-architecture.png)）
- [2025年高校与中学在校生规模](figures/fig03-education.svg)（[PNG](figures/fig03-education.png)）
- [2024年本专科在校生规模前12位省份](figures/fig10-regional-college.svg)（[PNG](figures/fig10-regional-college.png)）
- [2024年湖北及周边六省市在校生规模。（a）本专科；（b）普通高中；（c）初中](figures/fig11-hubei-neighbours.svg)（[PNG](figures/fig11-hubei-neighbours.png)）
- [2024年三个学段在校生规模的地区累计份额曲线](figures/fig14-education-lorenz.svg)（[PNG](figures/fig14-education-lorenz.png)）
- [2026年四项心理服务采购案例。（a）高校软件及系统；（b）区域测评与综合服务](figures/fig04-procurement.svg)（[PNG](figures/fig04-procurement.png)）
- [AI分析与大模型的人机协作流程](figures/fig07-ai-workflow.svg)（[PNG](figures/fig07-ai-workflow.png)）

## 使用与许可

申报书图表与三张项目图保留项目原创来源链；Phosphor采用MIT，随附[版权与许可](LICENSE-PHOSPHOR-MIT.txt)。数据图引用沿申报书来源登记，不把图像文件本身当作独立数据授权。合成截图的范围见[来源记录](demo/provenance.json)。

SVG可作为整体矢量图放入支持SVG的PPT版本。逐节点修改使用.drawio源稿；PPT内持续改结构可按内容源稿建立原生形状/SmartArt。本轮未在PowerPoint或draw.io编辑器内保存和重开，不作应用内验收声明。

## 本轮范围

只整理素材副本与章节索引。申报书、业务页面、库、配置、运行服务和实时8页PPT未改，未暂存、提交或推送。现有AI融合盘点尚未并入S5，本包依据当前S5正文，不推定额外能力或专业服务已获批准。
