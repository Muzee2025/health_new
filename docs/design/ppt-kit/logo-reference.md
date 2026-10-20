# PPT 品牌引用映射

> owner: B / R1 ｜ version: 2.0 ｜ status: 定稿 ｜ updated: 2026-10-21

以下直接复用本地approved源，不另复制一套logo。将SVG插入PowerPoint时保持比例；透明PNG用于不支持SVG的工具。文字已经包含在logo中，不另行加不同字体的品牌字标。

| 用途 | 本地源 | 建议 |
| --- | --- | --- |
| 浅底页头 | [横版SVG](../../../src/assets/brand/brand-logo-horizontal.svg) | 宽240起，四周至少留标志高度的1/4 |
| 封面/结束页 | [竖版SVG](../../../src/assets/brand/brand-logo-vertical.svg) | 保持180:190比例 |
| 黑白打印 | [单色SVG](../../../src/assets/brand/brand-logo-mono.svg) | 浅色背景 |
| 深色区域 | [反白SVG](../../../src/assets/brand/brand-logo-reverse.svg) | 自带品牌深色底板 |
| 位图备用 | [PNG512](../../../src/assets/brand/brand-logo-vertical-512.png)、[PNG1024](../../../src/assets/brand/brand-logo-vertical-1024.png) | 透明方形画布，建议浅色底 |

来源及授权状态以src/assets/manifest.json与LICENSES.md为准；不引用legacy-unverified头像。未经负责人确认，不向外部授予商业素材许可。

推荐品牌为「相伴」：不对称书页之间留出向前的开放路径。品牌独立符号使用 [彩色](../../../src/assets/brand/brand-mark-color.svg)、[单色](../../../src/assets/brand/brand-mark-mono.svg)、[反白](../../../src/assets/brand/brand-mark-reverse.svg)；彩色用灰紫和杏色，单色与反白均为单一实色。16/24/32px应使用 `brand-mark-small-{size}` 光学校正版，不能直接缩小含字标组合。候选「拥光」「知音」仅供比较，不与推荐标志混用。

[可编辑Figma品牌板](https://www.figma.com/design/YkGFX4cjB37CT8q8zgl0AL?node-id=2-12) 提供原生矢量与可编辑文字。Figma使用实际可用的Noto Sans SC；本地SVG使用系统Microsoft YaHei，不嵌入或分发字体。

第三方Phosphor及Open Doodles是独立通用图标/插画，不是品牌标记。`upstream/`中的`.svg.txt`是校验哈希的原始输入归档，不能按成品图片直接引用；完整版权与CC0条款随包保留。构建会从原始输入精简坐标与映射品牌色，不要求在线下载。
