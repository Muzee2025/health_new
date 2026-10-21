# SCI 绘图风格与脚本调研

> owner: B（调研交接：S1）｜version: 0.2｜status: 定稿（S1调研冻结）｜updated: 2026-10-21

## 任务范围与结论

任务 S1；输入为当前本地 ECharts 图表展台、W1 协作规则与科研可视化工具技能。唯一写入文件为本篇。开工时 `git status --short` 为空。本篇记录公开官方资料与可迁移原则，不安装 Python 包、不运行第三方绘图脚本、不接入真实数据，也不声称某种视觉样式能保证 SCI 录用。

**本轮实际路线：Matplotlib 显式配置，不要求 seaborn。** 用户已授权 S3 编写静态绘图脚本，因此以 Matplotlib 控制图形、轴、文字和导出；SciencePlots 仅作可选样式增强，缺少时继续走 Matplotlib 后备。S3 当前环境报告为 Python 3.14、已具备 Matplotlib、未安装 SciencePlots，实际走后备路线。统计口径、数据选择和共享色卡由项目代码/数据显式定义，不交给样式包默认值。Matplotlib 提供 PDF、SVG、PNG 等输出后端；应按最终稿件尺寸核对文字和标记。

Nature Research Figure Guide 是有用的公开实例：其图表建议包括显示轴线和刻度、轴标签写单位、可访问配色、可读文字、标准无衬线字体，以及保持图中文字可编辑并导出矢量图。具体尺寸和字号必须回到目标期刊最新作者指南确认；这些 Nature 规则不能外推为所有“SCI”期刊的共同标准。[Nature Research Figure Guide：图稿规范](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)；[Nature 初次投稿指南](https://www.nature.com/nature/for-authors/initial-submission)

## 绘图脚本路线比较

| 路线 | 可复现性与输出 | 许可与依赖 | 适用及限制 |
| --- | --- | --- | --- |
| **A. Matplotlib 显式配置（本轮实际路线）** | 在脚本中显式写尺寸、范围、刻度、图例、系列颜色和统计量；Matplotlib 官方列出 PDF、SVG、PNG 等输出后端。 | Matplotlib 使用基于 PSF 的许可，见[官方许可说明](https://matplotlib.org/stable/users/project/license.html)。本路线不依赖 seaborn。 | 适用于静态论文图、多面板和精确排版；对现有 ECharts 展台作为独立离线出图脚本，不取代浏览器交互。统计量由脚本从真实输入和已说明的方法计算，不调用默认估计。 |
| **B. Matplotlib + seaborn** | seaborn 提供统计绘图和色板工具；也可以只从 seaborn 选颜色、由 Matplotlib 绘制。 | seaborn 为 BSD 三条款许可，见[官方 LICENSE](https://github.com/mwaskom/seaborn/blob/master/LICENSE.md)。 | 可用作后续选装工具，但不是 S3 必需依赖。统计绘图的默认估计须核对；当前脚本路线由项目代码显式计算统计量。 |
| **C. Matplotlib + SciencePlots（可选样式层）** | 可组合 `science`、`ieee` 等样式，适合快速建立统一的轴与字体基线；样式不是论证、统计或投稿合规检查。 | SciencePlots 上游仓库为 MIT。上游说明提到 LaTeX 与 CJK 字体是额外环境条件。使用时导入 `scienceplots` 后可启用 `plt.style.context(['science', 'no-latex'])`；缺包或配置失败时退回显式 Matplotlib 参数。采用时固定版本并保留 MIT notice。[上游仓库与安装/用法](https://github.com/garrettj403/SciencePlots)；[MIT 许可](https://github.com/garrettj403/SciencePlots/blob/master/LICENSE) | 适合快速试稿，不是唯一实现或期刊官方样式。当前 S3 环境没有 SciencePlots，运行将使用 Matplotlib 后备，不为其安装依赖。SCI 期刊没有统一官方风格。 |
| **D. Matplotlib + Scientific colour maps（仅连续变量按需）** | 官方介绍其梯度为感知均匀、适合有序数值编码，且版本化、可引用；适合热图、连续场、空间/时间标量。只在具体数据型态与任务契约匹配时选一条顺序或发散色图。 | 由[作者官网](https://www.fabiocrameri.ch/colourmaps/)链接至版本档案 DOI；采用时按下载的**具体版本**档案元数据/许可文本归档作者、版本与许可，不从转存仓库推定许可。Matplotlib 内置 `viridis`、`cividis` 等可作为无需引入额外色图包的后备，依据[Matplotlib 配色指南](https://matplotlib.org/stable/tutorials/colors/colormaps.html)选择。 | 适用于连续有序数据；不适用于名义分类、情绪/风险状态等已有业务语义类别，也不应用于装饰性渐变。一个连续图只对应一个清楚的数据变量和色标。 |

### 建议的最小 Python 脚本骨架

用户已授权的 S3 静态绘图脚本采用 Matplotlib 显式参数；不为“像 SCI”自动安装额外依赖。字体必须使用目标机器实际存在且许可合适的字体。

```python
import matplotlib
matplotlib.use("Agg")  # 仅写文件时使用；不依赖桌面 GUI
import matplotlib.pyplot as plt

COLORS = ["#0072B2", "#E69F00", "#009E73", "#D55E00"]
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Liberation Sans", "DejaVu Sans"],
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.labelcolor": "#29332F",
    "text.color": "#29332F",
    "xtick.color": "#56625C",
    "ytick.color": "#56625C",
    "axes.prop_cycle": plt.cycler(color=COLORS),
})

# 在此显式载入经确认的真实数据、单位、分组和统计方法；不要在图形代码里猜字段。
# fig, ax = plt.subplots(figsize=(3.54, 2.65), layout="constrained")
# ... 以原始观测、预先定义的摘要及适当的不确定性绘制 ...
# fig.savefig("figure.pdf")
# fig.savefig("figure.svg")
# fig.savefig("figure.png", dpi=300)
```

此骨架只是可复用起点，不是完整统计分析，也未在仓库环境运行；最终宽度、字号、DPI、文件格式及嵌入字体依目标期刊和图像内容调整。连续变量的点估计/区间应由有来源的统计计算产生，`pdf.fonttype=42` 是 Nature 公开指南对 Matplotlib 可编辑文字的建议之一。纯文字/线稿优先保留矢量；显微照片等栅格内容单独按期刊分辨率要求导出。[Matplotlib 后端](https://matplotlib.org/stable/users/explain/figure/backends.html)

## 当前 ECharts/SVG 图库迁移建议

现有图表工作台采用确定性合成数据、ECharts SVG renderer、CSS token 主题、六类情绪字段语义色、图表表格对照和实际 SVG 下载。当前用户已授权素材库局部图表UI优化及S3静态绘图脚本；以下建议限于这些范围，不扩展到业务页、全局入口、真实数据或新增依赖。

1. **颜色按语义和数据类型分工。** 延续现有暖白 `#FCFAF7`、深墨 `#29332F`、柔和紫 `#78558F`、杏色 `#E8B185`、鼠尾草绿 `#8BA696` 作品牌/装饰层；图中主要数据系列使用有限、清楚且对比稳定的色相，重复使用时保持系列到颜色的固定映射。S2 正在定义蓝绿/暖杏共享色卡，后续实现应以共享 JSON 为权威来源。下方 Okabe–Ito HEX 仅为研究参考候选，**本轮没有采用该色板**。不要将红黄绿的业务风险语义误套到不相关变量。热力或连续数值用单调明度的顺序色标；正负偏差围绕有科学意义的中点时用发散色标。不要把类别色板当连续色图，也避免彩虹/jet。Matplotlib 与 seaborn 的官方指南均将类别、连续和发散配色按数据类型区分。[Matplotlib 配色指南](https://matplotlib.org/stable/tutorials/colors/colormaps.html)；[seaborn 配色原则](https://seaborn.pydata.org/tutorial/color_palettes.html)
2. **坐标与刻度表达数据。** 数值轴需包含单位；比例类柱状图从零起，只有范围截断且明确标示、并且不会夸大小差异时才例外。分类轴不得用连线暗示连续性。时间轴在确实有时间顺序时统一区间、时区与间隔说明；直方图标出边界闭开规则和单位；热图注明色标变量、范围和尺度。不要隐藏轴线/刻度，避免只靠颜色表达类别。
3. **图例与说明就近且可读。** 类别少且名称短时可内嵌直标，名称长或系列多时用图外或面板共享图例；始终使用深色文字加色块/线段，而非彩色小字。展示每组 `n`、缺失处理、聚合方式及分母口径；图例不能代替图注中对误差/区间的定义。
4. **留白由标签和最终尺寸驱动。** 先确定目标显示宽高，再调整字号、刻度密度与面板排列；不要把超长说明塞进绘图区，也别用无数据意义的阴影、卡片装饰和重网格争夺注意力。细浅网格只在读值确有帮助时保留，最终缩小到投稿尺寸核对标签重叠、裁切和图例占用。
5. **统计表达保持来源可追溯。** 先依据数据形态与问题选择图，再决定汇总统计。样本点可展示时优先保留点或分布；均值与不确定性范围必须说明计算方法、区间类型、每组样本量及独立单位。只有数据支持时才添加显著性、拟合线、相关或因果描述；不能从合成演示样例、配色或视觉趋势推断显著性，也不预设误差棒。比例的分母、重复测量/独立样本单位、缺失值处理和轴变换必须写明。

### 推荐参考色卡

**研究候选参考，不是本轮采用色卡。** 下表用于展示 Okabe–Ito 常用色盲友好离散色的备选，供比较；S2 负责定义并输出本轮实际共享蓝绿/暖杏 JSON 色卡。下列参考色不表示顺序、等级或风险。实际色值需按线宽、背景、印刷灰度及色觉模拟检查。

| 名称 | HEX | 推荐编码 |
| --- | --- | --- |
| 蓝 | `#0072B2` | 离散系列 |
| 橙 | `#E69F00` | 离散系列 |
| 蓝绿 | `#009E73` | 离散系列 |
| 朱红 | `#D55E00` | 离散系列 |
| 天蓝 | `#56B4E9` | 离散系列；浅色背景与细线需检查 |
| 紫红 | `#CC79A7` | 离散系列；不可仅靠颜色识别 |
| 黄色 | `#F0E442` | 大面积/强调填充；不作白底细线或文字 |
| 深墨 | `#29332F` | 文字、轴与基线；取自当前项目 token |
| 暖白 | `#FCFAF7` | 画布底色；取自当前项目 token |

Okabe–Ito 原始色板可追溯到作者发布的图表指南；Nature Figure Guide 明确把 Wong 的色盲友好示例列为可访问配色例子。[Wong, *Colour blindness*, Nature Methods (2011)](https://www.nature.com/articles/nmeth.1618)；[Nature 图稿规范](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)。Okabe–Ito 的不同复刻版本在黑色/浅蓝色项上可能有差异，具体取值应登记色板版本并统一团队色值，不应混用来源不明的截图/色卡。

## 中文 SCI 绘图提示词模板

复制后填入方括号。提示词只能指导绘图分析和视觉实现，不能替代原始数据、统计计划、目标期刊作者指南或研究者审阅。

```text
你是科研绘图助理。请仅使用我提供的真实数据、字段字典、统计方案和目标期刊最新作者指南，为下列研究问题设计一张可复现的图。

研究问题：[一句话；不得由数据外推新假设]
数据文件/表名：[路径或标识]
字段与单位：[列名、定义、单位；不清楚处标为待确认]
研究设计与独立统计单位：[实验/观察设计、受试单位、重复测量关系]
纳入/排除和缺失规则：[实际规则；没有时写“未提供，先不处理”]
目标期刊及作者指南版本/链接：[具体期刊；没有时写“未确定，不虚构期刊格式”]
最终版面尺寸与输出格式：[单栏/双栏宽度、最大高度、PDF/SVG/TIFF等]
期望图形或待比较图形：[可留空，由数据结构与论点决定]
统计分析计划：[估计量、模型、检验、区间方法及多重比较规则；无则标为“未提供”]
已有配色语义：[例如组别映射、项目token；没有时选色盲友好离散色或按数值类型选连续色图]

请依次完成：
1. 检查数据列类型、样本量、缺失、重复测量、分组分母、量纲和明显范围；只报告可从文件核实的内容。
2. 说明图形所支持的唯一结论、图型选择理由及一个备选；如数据或设计不支持预期图型/推断，先指出并给出更合适方案。
3. 生成完整绘图脚本，显式设置最终尺寸、坐标标签与单位、刻度、图例、字体、颜色、统计汇总和矢量/栅格导出；标注依赖和版本。无 LaTeX 环境也能运行，字体缺失时提供系统字体后备。
4. 图注写明每组 n、独立统计单位、数据汇总方式、误差或区间定义（仅在数据与统计方案支持时绘制）、检验/模型和显著性符号定义。任何未提供内容以 [待补：字段] 标记，不猜测或代填。
5. 严禁虚构或暗示 p 值、显著性星号、置信区间、标准差、标准误、样本量、效果量、拟合线、因果关系、单位、来源或期刊要求；不得把“未检验”写成“不显著”。
6. 输出后检查最终尺寸下的标签/图例/裁切、色觉差异、灰度可读性、单位和坐标范围；给出脚本、输出文件名、依赖版本、实际运行命令和未能验证项。不要声称未实际执行的检查已通过。
```

## 来源与许可核查

| 来源 | 本篇采用内容 | 许可/使用记录 |
| --- | --- | --- |
| [Nature Research Figure Guide](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/) | 轴/单位、文字、无障碍配色、可编辑矢量输出建议 | 指南文字用于概述并链接原文；不复制图像或图稿资产。指南仅适用于其投稿体系。 |
| [Matplotlib 官方配色指南](https://matplotlib.org/stable/tutorials/colors/colormaps.html)、[后端指南](https://matplotlib.org/stable/users/explain/figure/backends.html)、[许可说明](https://matplotlib.org/stable/users/project/license.html) | 顺序/发散/定性 colormap 的用途和 SVG/PDF/PNG 文件后端 | Matplotlib 许可基于 PSF；遵守其随包许可与第三方组件声明。 |
| [seaborn 官方配色教程](https://seaborn.pydata.org/tutorial/color_palettes.html)、[LICENSE](https://github.com/mwaskom/seaborn/blob/master/LICENSE.md) | 类别色相区分、数字变量明度编码、色觉/灰度冗余编码 | seaborn LICENSE 为 BSD 三条款，分发时保留版权、条款与免责声明。 |
| [SciencePlots 官方仓库](https://github.com/garrettj403/SciencePlots)、[LICENSE](https://github.com/garrettj403/SciencePlots/blob/master/LICENSE) | 可组合 Matplotlib 样式和 `no-latex` 使用方式 | MIT 许可；若以后纳入工程依赖，固定版本并保留许可通知；本次未安装或复制上游样式文件。 |
| [Scientific colour maps 作者官网与版本档案](https://www.fabiocrameri.ch/colourmaps/) | 连续科学数值映射的感知均匀/色觉友好设计目标 | 官网目前列出 8.0.1 与 Zenodo 永久版本档案；下载的版本档案许可才是分发依据。当前仅建议按需使用，没有复制文件或预设许可。 |
| [Wong (2011), Nature Methods](https://www.nature.com/articles/nmeth.1618) | 色盲友好颜色示例，供离散系列参考 | 只引用论文链接并采用候选 HEX 颜色，不复制图表图片；如果重新发布色板文件，记录来源和许可并检查来源版本。 |

## 不适用范围与下一步

本建议适用于静态研究数据图设计，不是临床、心理量表或生物统计咨询，不构成目标期刊格式审查；不能仅凭图形判定结论有效、统计显著或因果成立。ECharts 的交互展台继续服务于当前 W1 素材展示；Python 路线只适合未来明确要求的静态图源文件，不意味着现在新增依赖或替换前端图表引擎。Lead 整合时请将本文件加入 `docs/README.md` 索引，并由独立评审确认格式、链接与适用边界。
