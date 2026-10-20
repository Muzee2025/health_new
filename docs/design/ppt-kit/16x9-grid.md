# 心域智链 PPT 16:9 网格

> owner: B / E03 ｜ version: 1.0 ｜ status: 定稿 ｜ updated: 2026-10-20

画布为1600×900（16:9；PowerPoint可选13.333×7.5英寸）。安全边距左右104、上下80；内容宽1392，采用12列、列间24。标题与正文左对齐，单行不超过约30个汉字；一页只表达一个主要判断，不使用无依据指标。

封面使用cover-bg.svg，标题放x104/y260附近，宽不超过820；标题建议36–44pt，副标题20–24pt，日期/来源14–16pt。章节页用section-divider.svg，白色标题置于左侧，40–44pt。内容页标题28–32pt，正文18–22pt，来源与图注14pt起；中文使用本地系统无衬线，不下载或嵌入许可不明字体。

图表使用chart-palette.json；其source为src/styles/tokens.css，颜色由assets:build生成，禁止维护第二套色值。情绪严格按emotions的字段key取色；风险严格按risks取色；标签配文字，不只依赖颜色。使用需要背景支撑的色块时以tokens规定的浅底/文字色配对。

截图使用screenshot-frames/screenshot-frame-16x9.svg；框内窗为x24/y80/宽1552/高796，以等比contain放入截图，留白优于拉伸。替换占位文字时必须遮蔽或删除它。截图只用明确标识的合成数据或已脱敏图，保留采集日期、页面及“合成示例”标识；本包不含真实学生数据。

图标来自icon-sheet.svg，与src/assets/icons/icon-domain-sprite-24.svg同源；建议24–36pt。logo引用见logo-reference.md。封面和章节底板的装饰图形集中在右侧，左侧文字区域不叠加无关纹理。所有素材只允许项目内部复用，对外授权/商用由负责人确认。
