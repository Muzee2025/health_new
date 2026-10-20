# 资源与 Skill 调研

> owner: R3 / Codex ｜ version: 1.0 ｜ status: 调研完成 ｜ updated: 2026-10-21

## 结论

本轮为 W1 素材库后续精修提供可复核的第三方资源来源。图标建议统一采用 Phosphor Regular 线性风格：线条清楚、端点圆润，适合健康支持产品中表达关怀、倾听和阅读。插画暂选 Pablo Stanley 的 Open Doodles `loving` 与 `reading-side` 两幅，分别支持情绪陪伴和自我阅读场景；两幅原始 SVG 及 CC0 法律文本已下载到 Git 忽略目录，供品牌执行者预览和整合。

UI UX Pro Max 已按固定提交安装到用户技能目录，供后续设计执行参考。项目原有 `frontend-design` skill 已存在，本轮只核验其原作者来源，没有覆盖。

## 资源来源与许可比较

检索日期均为 2026-10-21。许可判断以表中官方项目、原作者网站或该版本附带的许可原文为准。允许整合进项目素材包的判断以再分发原始或改编文件时携带要求的许可/版权声明为前提。

| 来源 / 作者 | 一手来源 | 许可 | 可下载与修改 | 可作为项目素材包再分发 | 归属与许可条款 | 本项目取舍 |
| --- | --- | --- | --- | --- | --- | --- |
| [Phosphor Core](https://github.com/phosphor-icons/core) / Phosphor Icons | [MIT 文件与 SVG 目录](https://github.com/phosphor-icons/core/tree/2b75f3ad12b420c9504ef05df8d2564a28f8500e)；revision `2b75f3ad12b420c9504ef05df8d2564a28f8500e` | MIT | 可以；仓库提供真实 SVG | 可以；分发时保留完整 MIT notice | `Copyright (c) 2023 Phosphor Icons`；版权与许可声明须随副本或实质部分保留 | **采用**。使用 Regular：`heart`、`hand-heart`、`chat-circle-dots`、`book-open`。外形柔和且线宽统一，能覆盖关怀、倾听、阅读场景。 |
| [Lucide](https://github.com/lucide-icons/lucide) / Lucide contributors；部分图标源自 Cole Bemis 的 Feather | [官方 LICENSE](https://github.com/lucide-icons/lucide/blob/c29c276f16590cf017126671535ad8c792be64d8/LICENSE)；revision `c29c276f16590cf017126671535ad8c792be64d8` | ISC；部分 Feather 派生图标附 MIT 条款 | 可以；项目发布 SVG 与图标库 | 可以；应携带完整 LICENSE，其中包含 ISC 和 Feather 来源声明/MIT 部分 | 保留完整上游 LICENSE；不要只截取 ISC 段，避免遗漏 Feather 派生作品条款 | 可作为备选。体系简洁成熟，但混合来源许可记录更繁琐；本轮选 Phosphor 以便维护同一套图标与单一 notice。 |
| [Open Doodles](https://opendoodles.com/) / [Pablo Stanley](https://opendoodles.com/about) | [作者关于页与源文件说明](https://opendoodles.com/about)；作者站链接的 [loving.svg](https://opendoodles.s3-us-west-1.amazonaws.com/loving.svg) 与 [reading-side.svg](https://opendoodles.s3-us-west-1.amazonaws.com/reading-side.svg) | CC0 1.0 Universal | 可以；作者页面提供 SVG、PNG 与源文件 | 可以；CC0 允许复制、修改和分发，不要求署名 | 作者注明 CC0；使用时不应暗示作者背书。CC0 法律文本保存在本轮临时 licenses 目录 | **采用两幅 SVG**：`loving.svg` 用于陪伴/关怀情境，`reading-side.svg` 用于阅读/自我照料情境。文件固定源 URL 与 SHA-256 见下文。 |
| [Open Peeps](https://openpeeps.com/) / [Pablo Stanley](https://openpeeps.com/) | [作者原站及可下载 SVG 示例](https://openpeeps.com/)；[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/) | CC0 1.0 Universal | 可以；原站给出可下载 SVG/PNG，完整组合库另有下载入口 | 可以；CC0 允许修改和分发 | 作者为 Pablo Stanley；不需要版权归属，但不可暗示作者支持项目 | **许可可接受，暂不下载**。其混搭人物组件适合后续扩展头像/人物场景；当前样例先保持 Open Doodles 两幅插画的风格统一。 |
| [unDraw](https://undraw.co/) / Katerina Limpitsouni | [官方许可](https://undraw.co/license) | 自定义免费版权许可 | 可以用于项目且可修改 | **不允许把插画打包再分发**；许可明确禁止以素材包等形式再分发 | 无需署名，但许可证排除了素材集/素材包再分发，并限制训练或开发 AI/ML | **排除，不纳入库**。本项目目标含可移交的 PPT/素材包，违反其明确限制。 |

### 已选资源文件与固定校验值

临时调研下载位于被Git忽略的 `tmp/design-research/`；最终选择的六份上游固定原稿及完整许可已另存入版本化的 `docs/design/ppt-kit/upstream/`，构建不依赖tmp。Phosphor以Git提交SHA固定源版本；Open Doodles记录作者站点指向的CDN源URL及下载时SHA-256，以摘要锁定本次使用的副本，不假定CDN URL永久不可变。下表SHA对应原始内容；正式素材的输出SHA、适配说明与sourceInput路径由manifest单独登记。检索与下载日期：2026-10-21。

| 文件 | 原始来源 URL | bytes | SHA-256 |
| --- | --- | ---: | --- |
| `assets/phosphor/heart.svg` | `https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/regular/heart.svg` | 489 | `312DEE73D1D969631D5498012F619CCF4EDBDF31E1BE3E65AF4F4F1B3AC1B2DD` |
| `assets/phosphor/hand-heart.svg` | `https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/regular/hand-heart.svg` | 928 | `8797F9CA2BC8620C56C9DEAD90C047724176A611D52E613C6412AA16745BF93E` |
| `assets/phosphor/chat-circle-dots.svg` | `https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/regular/chat-circle-dots.svg` | 473 | `2AF44E36757C90C999E070065AE61C495C66C8E88F43C5F07964DC3367CAD60D` |
| `assets/phosphor/book-open.svg` | `https://raw.githubusercontent.com/phosphor-icons/core/2b75f3ad12b420c9504ef05df8d2564a28f8500e/assets/regular/book-open.svg` | 396 | `B38CDB3A15DCF00CFA4811E318B021E25C6A87B47ACBB11888E16D107A5642DA` |
| `assets/open-doodles/loving.svg` | `https://opendoodles.s3-us-west-1.amazonaws.com/loving.svg` | 21041 | `EC2530045EACE13AA9D9F10FFC091CAB561233EC57564F04F045E6EC53BBD62A` |
| `assets/open-doodles/reading-side.svg` | `https://opendoodles.s3-us-west-1.amazonaws.com/reading-side.svg` | 60495 | `BC98D93429C03FE206050649841D0CECAB51C928FCB6F7E842FF4AF6A5585593` |

许可原文的正式副本：[Phosphor完整MIT](ppt-kit/upstream/PHOSPHOR-LICENSE.txt)（SHA-256 `B5B1F1DA112D18EA2147DECFD48DDC1BF2B5AEB6C265381579340E95B15A2BB2`）和[CC0全文](ppt-kit/upstream/CC0-1.0-legalcode.txt)（SHA-256 `A2010F343487D3F7618AFFE54F789F5487602331C0A8D03F49E9A7C547CF0499`）。CC0规范来源为[Creative Commons CC0 1.0 Legal Code](https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt)。4个Phosphor成品SVG也各自内嵌MIT全文注释；单独下载时许可不会与图形分离。其矢量路径与原稿相同，成品哈希因增加注释而与原始哈希不同。

## Skill 核验

| Skill | 来源与版本 | 许可 / 本地状态 | 结论 |
| --- | --- | --- | --- |
| `frontend-design` | [Anthropic Skills 官方仓库](https://github.com/anthropics/skills/tree/main/skills/frontend-design) | 当前用户 skill 目录已存在；本轮不覆盖、不更新 | 可供设计执行者沿用现有本地版本。 |
| `ui-ux-pro-max` | [NextLevelBuilder 官方仓库](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill/tree/56ea9cf174ed86786187daa9de0e6247cb0747e4/.claude/skills/ui-ux-pro-max)；仓库 `skill.json` 标记版本 `2.15.0`；固定提交 `56ea9cf174ed86786187daa9de0e6247cb0747e4` | MIT；由已读取的 Codex `skill-installer` helper 安装成功；Skill 路径：`C:\Users\14012\.codex\skills\ui-ux-pro-max\SKILL.md`；SHA-256 `EA087C341BFB5B23195C7302027268EDE86DA802554C18A5C4896A6017B439F9` | **建议设计执行者读取**。本回合可通过此绝对路径直接阅读并应用；它会在后续回合由本地 skills 目录自动发现，不宣称已在当前回合自动生效。提供本地可搜索的视觉规范、交互、无障碍与技术栈建议。Skill 声明其搜索只输出建议、不修改系统、不安装依赖；项目实施仍遵守本仓库范围。 |

### 方法与边界

安装命令使用 `py -3.12 C:\Users\14012\.codex\skills\.system\skill-installer\scripts\install-skill-from-github.py --repo nextlevelbuilder/ui-ux-pro-max-skill --path .claude/skills/ui-ux-pro-max --ref 56ea9cf174ed86786187daa9de0e6247cb0747e4`，返回成功；没有执行 npm CLI 或上游脚本。下载素材只访问作者/项目官方原始 URL。临时 SVG 检查未发现脚本、foreignObject 或外部 http(s) 引用。没有访问后端、学生数据、上传目录或秘密值，也没有更改业务页面、路由、API、数据库、依赖版本或全局样式入口。

本文件由R3调研、Lead整合。六项资源已按上述许可和固定来源纳入正式素材库；版本化原稿用于复建，适配成品及逐项来源见 `src/assets/manifest.json` 与 `LICENSES.md`。临时调研副本仍处于忽略目录，不作为唯一构建输入。文档入口由Lead登记至 `docs/README.md`。
