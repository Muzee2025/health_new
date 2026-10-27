# 申报材料科学版图表

> owner: A ｜ version: 1.0 ｜ status: rendered-review ｜ updated: 2026-10-27

## 范围

本目录包含13幅重绘图的图表规格。原有数据图为fig01–04、fig09–11，概念图为fig05–07，新增分析图为fig12–14。fig08未纳入本次重绘范围。

图内不放总标题、来源、处理提示或免责声明；数据图只保留坐标指标、单位、简短图例、必要数值和面板字母。图题建议、面板解释、单位、图型、灰度说明及口径限制见[figure-spec.json](figure-spec.json)。

## 文件

- [figure-spec.json](figure-spec.json)：13图外部图题与面板语义。
- [figures-sci/](../figures-sci/)：每图含可编辑文字SVG、嵌入字体PDF和600 DPI、256色索引PNG；单个文件不超过2 MiB。
- [图表布局审计](../figures-sci/figure-layout-audit.json)：逐图布局审计与文件大小记录。
- [render-sci-application-figures.py](../../../../scripts/render-sci-application-figures.py)：确定性重绘脚本。

## 数据与呈现口径

数据图读取现有`chart-data.csv`与`revision-20261027/regional-education-2024.csv`；文献图读取本目录的`literature-data.json`；颜色读取`src/styles/tokens.css`。所有导出使用145 mm图宽、白底、Arial与SimSun、8–9 pt标签及0.6–0.8 pt线宽。

fig01仅绘制已报告的20.2%与45.4%精确值；“低于5%”无风险组不画柱，也不转换为精确值。图03依据原始教育统计总量，不添加置信区间。图04按不同采购标的和交付范围分面，龙泉驿测评与干预为堆叠金额，不计算均价。fig10按普通本科与职业本专科在校生合计排序；fig11为湖北与六个相邻省级地区分学段对照。

fig12显示同一系统综述的四个学段合并筛查比例和原报95%CI；各亚组的样本/研究可能重叠，不相加。fig13依2024教育统计CSV原序列出大陆31省级地区Meta分析结果，香港、台湾排除在外；k=1用空心点标记。它是文献研究汇总，不是省级人口风险地图。fig14为三学段洛伦兹曲线，横轴对省级地区等权，纵轴为学段在校生累计份额。

概念图仅表达项目构想、既有原型与拟增强模块边界、以及受控人机协作流程，不代表功能完成或模型效果验证。

## 重绘与检查

在仓库根目录运行：

```powershell
& 'C:\Users\14012\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts/render-sci-application-figures.py --out docs/plan/ai-application/figures-sci
```

本轮生成13图、39个矢量/栅格文件；逐图布局审计无问题。PNG为600 DPI、256色索引色，像素尺寸不变；13张PNG合计1,048,519字节。调色板量化只造成抗锯齿边缘的轻微色差；SVG/PDF保持矢量精度。PDF字体嵌入检查通过，SVG保留文本且无嵌入位图。已对全体图做缩略总览目视检查。


## 正文与数学分析

[数学分析](math-analysis.md)、[未舍入统计](math-analysis.json)和[31地区派生数据](regional-derived.csv)由标准库脚本生成；[文献证据](literature-evidence.md)、[文献数据](literature-data.json)与[CSV](literature-data.csv)保留原始点估计和区间。SciSpace检索仅作发现，来源核验使用出版商Table 1和Table S2。

[当前申报源稿](../../心域智链申报计划书.md)含五个公式，Word为原生可编辑OMML，HTML用本地数学字体；来源/限制与制图处理说明置于附录。构建器`scripts/build-sci-application.py`要求显式提供R4源稿和R4 Word作为`--source`及`--base-docx`，本轮私有输入在`tmp/sci-application-20261027/previous/`；两项输入也可从Git提交`573bbab`恢复到新的私有目录。输出应选择新候选路径。

[验收](../../../test/申报书科研图与数学分析验收.md)记录Lead逐页检查及浏览结果；[独立记录](../../../test/申报书数学分析与科研图复核.md)只覆盖数据和方法。最终整稿独立复核因子代理使用额度受限未完成，不把阶段核验称为全稿独立通过。当前交付仅供审阅。
