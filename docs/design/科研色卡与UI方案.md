# 科研色卡与图表 UI 方案

> owner: B / S2，A整合 ｜ version: 1.2 ｜ status: 定稿，独立门禁通过 ｜ updated: 2026-10-21

本轮只精修素材工作台图表区。阅读任务为时间变化、分类比较、组成、分布与二维读值；继续采用 ECharts SVG，表格为完整数值替代路径。没有统一的“SCI 配色标准”，本方案参考科研图形的清晰性原则，不声称期刊认证。

## 视觉方案

以白色 `#FFFFFF` 为绘图区，深蓝 `#276A8B` 为主序列，青绿 `#2B7C76` 为第二序列，暖杏 `#D6AA68` 为第三分类；深色正文 `#243B4A` 与灰蓝辅助文字 `#617580` 支持长时间阅读。保留品牌的人文标题和暖色点缀，去掉卡片粗彩顶边与大面积彩底，科研色卡成为图表区唯一有集中颜色的部位。

字号使用本地无衬线字体，正文与坐标最低 12px，标题 18px，数值对齐采用等宽数字特性。区间摘要保持可查口径，图表的绘图区、注释与操作各自对齐；桌面用趋势主图加组成侧图，手机单列，先标题摘要再图和值表。

12px为本项目网页的阅读约束，不是Nature图稿字号要求；静态论文尺寸与字体另按目标期刊指南确认。

分类色、风险色与连续色各有职责。情绪颜色只识别类别，不表达好坏；低中高分级始终带文字。热力矩阵使用亮到暗的单一蓝色顺序色，0 到当前快照最大值线性映射，保留数值及可见标尺；标签置于白底深色小底板，避免随格色变化丢失对比度。分类色不能替代文本，也不把色盲可辨性当成仅靠调色就已完成的保证。

```text
图表标题与说明
科研色卡：分类角色 / 连续色标 / 风险角色（点击复制）
阅读目的 + 时间范围 + 样例
当前区间 / 总量 / 日均
来源与口径（展开）
趋势主图             情绪组成
分级 / 预约 / 渠道 / 时段 / 时长 / 资源
```

## 技术与状态契约

- 复用 `chart-palette.json` 作为唯一色值源；`chart-style.js` 提供 ECharts theme、CSS role 和标签对比度 helper，Python 输出也读取 JSON。图表局部 CSS 不接入业务全局 token。
- 维持最多 8 个 SVG 实例与按可见区域尺寸重绘；不增加网络数据、依赖、动画或额外渲染器。当前 `current` 合成数据用于图、表与导出；6 组 A/B × 7/14/30 天数据及分母规则不变。
- `chart-use`、`chart-range`、`chart-sample` 保持 URL 状态，刷新、后退、无效参数回退保持；隐藏图在恢复显示后按现有生命周期 resize/setOption。
- 导出捕获点击时的数据快照，保留 pending 防重入、真实 SVG DOM 序列化、尺寸/标题/单位/合成来源；临时导出实例完成后 dispose。pagehide/pageshow 和 ResizeObserver 仍由原模块管理。
- 手机 320/390px 单列，矩阵字体不小于12px，主要交互最小44px；顺序色带为7个连续色格，最小高度44px，窄屏色格宽约36px，完整色值由可访问名称及复制状态提供。明细表独立滚动而不撑开页面。浏览器 SVG 适合当前小数据量和文字占比，不引入 Canvas/WebGL。
- 复制色值使用系统剪贴板；单次 pending 期间禁用全部科研色卡按钮并提示进度，不用超时竞速重新放行。失败时在可见文本框中提供精确 hex 与手动复制路径。dispose 后迟到结果不更新 DOM 或聚焦；无主题切换器，避免维护多套视觉状态。

## 验证与交接

执行语法检查、6组数据状态、320/390/1440布局、8图实际SVG下载、色值复制、热力当前最大值/数值/标尺与标签对比度。局部证据放 `tmp/sci-palette-design/`，由 Lead 执行独立门禁与文档索引登记。自评不替代独立复核。

设计执行者本地自检：`node --check docs/design/chart-library.js`、`node --check docs/design/chart-style.js` 均退出0；使用既有5173服务与Edge执行 `CHART_QA_OUTPUT=tmp/sci-palette-design/existing-qa node scripts/check-chart-gallery.mjs`（Playwright/sharp路径取已有运行时），退出0。实际为13组检查、6组样例、8个SVG下载、15份截图，浏览器error/warning均0。当前快照热力上界依次为7/13/25次，正文与白底对比11.67:1，辅助文字4.81:1，矩阵标签白底对比11.67:1。已目视桌面图库、色卡、手机热图；正式版本证据与门禁以Lead独立运行结果为准。

来源：[ECharts 样式概念](https://echarts.apache.org/handbook/en/concepts/style/)、[Nature figure guide](https://research-figure-guide.nature.com/figures/preparing-figures-our-specifications/)。参考原则经项目转化，未使用受限图像或照搬期刊版式。

正式门禁曾发现原青绿 `#31877F` 配白字仅4.28:1，旧局部自检未覆盖此段。已统一将第二序列、焦虑分类及低分级改为 `#2B7C76`，白字对比4.94:1；不更改统计值或分母。修复后另以实际浏览器 channel 系列的 `label.color` 与 `itemStyle.color` 配对计算三段对比，结果见最终门禁及局部 `tmp/sci-palette-design/channel-contrast.json`。

## Lead正式验收与S4独立复核

修复后的正式命令使用 `CHART_QA_OUTPUT=docs/design/screenshots/scientific-palette`、`CHART_QA_BASE_COMMIT=cacbff4`，其他模块/Edge参数沿用既有[图表验收记录](图表验收记录.md)。`node scripts/check-chart-gallery.mjs`退出0：13组检查、18截图、8份真实920×550 SVG及色卡JSON下载，1440×1000与390/320×844均通过。全部图形、六组快照、数据表、概览/分母、URL与键盘、生命周期事件/reload、旧头像真实下载回归通过；没有以事件模拟冒充实际BFCache命中。

新检查读取实际ECharts系列，验证trend/emotions/risks颜色与共享JSON一致；三段channel文字对比5.96/4.94/5.45，辅助文字对白4.81，热力168标签11.67，连续色带明度严格递减。色值复制用隔离浏览器mock测试成功、拒绝后的手动后备、pending全禁用及dispose迟到结果，不写系统剪贴板。热力灰阶/绿色弱、风险灰阶、情绪绿色弱均保留直接标签和明细，色觉模拟不等于完整无障碍认证。

Lead实际查看最终色卡、手机色卡/热图、绿色弱情绪，以及14/A彩色和30/B灰度静态总览，未发现重叠、缺字或裁切。S4 Luna独立运行6组数据校验、JS语法与Python AST，核对最终两次静态导出的输入/色卡/脚本及40文件哈希、SVG/PDF/PNG结构和DPI，再只读审阅Lead浏览器QA；S4没有亲跑浏览器。结论在已复核范围内通过。

`npm test -- --exclude "tmp/**"`退出0，3源码文件11测试；`npm run build`退出0（13.59秒），既有大分块warning保留。数据6组合与素材131/131校验退出0，7个legacy来源warning继续保留。本轮没有新增工程依赖或改动业务入口、生成器和品牌token。

完整性核对通过：366个既有受保护文件相同，历史证据不变；39份Markdown断链0，3份新文档均有状态头与索引。18浏览器截图与2静态预览的字节/SHA符合记录；两份静态manifest对应最终共享色卡及脚本hash。

交付：[共享色卡](chart-palette.json)、[ECharts样式helper](chart-style.js)、[SCI调研与提示词](SCI绘图风格与脚本调研.md)、[Python脚本说明](科研绘图脚本说明.md)、[正式浏览器QA](screenshots/scientific-palette/qa.json)、[静态输出证据](screenshots/scientific-palette/scientific-export-qa.json)、[源码完整性](scientific-palette-integrity.json)。原始静态SVG/PDF/300dpi PNG保留在忽略目录，当前版本化预览只做PNG→WebP编码转换；详细恢复点与Git卫生见[门禁记录](../team/门禁记录.md)。
