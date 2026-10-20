# 截图与浏览器验证

> owner: A / E04 ｜ version: 1.1 ｜ status: 定稿 ｜ updated: 2026-10-21

## 当前前端基线

[before/baseline.json](before/baseline.json) 登记学生端8页、教师端6页的1440×900截图、SHA-256、浏览器消息和截获请求。14张图全部使用虚构账号、合成内容和浏览器内API响应，右下角水印由页面DOM注入。它们用于后续界面改造对照，不是后端联调、心理干预效果或真实用户使用证据。图内原有“真实对话”等文字是当前界面文案，不能据此认定截图数据真实。

捕获脚本拦截全部API（包括代码中固定的8000端口），未知接口返回501并令验收失败；拦截WebSocket，禁止Service Worker，外部图片与字体样式请求由本地合成资源替代。新浏览器上下文只写入虚构身份，不读取已有浏览器账号、数据库或上传目录。页面日期锚定为2026-10-20 09:00（上海），时钟继续递增以允许图表完成动画；`fixtureTime` 表示这个锚点，`generatedAt` 是实际运行时间。

本次结果：14/14页、未知API0、页面异常0、坏图0、超过300KB截图0、console error0。存在23条warning，来源包括主动隔离Service Worker及旧Vue、Element Plus、ECharts行为，不能写成业务页控制台全无消息。学生首页的30天→90天切换已实际执行，恢复30天并等待图表结束后截图。

## 复现方式

先运行 `npm run dev -- --host 127.0.0.1`。另一个终端运行 `node scripts/capture-ui-baseline.mjs`。脚本使用已安装的Playwright与sharp，不自动下载依赖；不支持普通包解析时，通过以下环境变量指定已安装模块和浏览器：

| 变量 | 含义 |
| --- | --- |
| PLAYWRIGHT_MODULE_PATH | Playwright包的绝对目录 |
| SHARP_MODULE_PATH | sharp包的绝对目录 |
| BASELINE_EXECUTABLE_PATH | 本机Edge或Chromium可执行文件绝对路径，优先于channel |
| BASELINE_BROWSER_CHANNEL | 默认msedge；仅在未指定可执行路径时使用 |
| BASELINE_BASE_URL | 默认 `http://127.0.0.1:5173`，应指向本地前端开发服务器 |

本次使用工作区依赖工具提供的Playwright 1.62.1、sharp和系统Microsoft Edge 155；没有安装新包。重新运行会覆盖本目录的合成基线文件，修改这些文件前应先核对Git差异。

## 新素材库展示页

本节下方四张展示截图为初始W1（4b2898f）证据。设计优化后的当前截图及QA见文末，原14页业务合成基线不变。

[library-preview-qa.json](library-preview-qa.json) 保存Lead的浏览器验证结果；展示页为 `/docs/design/library-preview.html`，与业务页面入口分开加载。只允许本地展示资源，不连接真实后端。

| 证据 | 内容 |
| --- | --- |
| [桌面展示](library-desktop.webp) | 1440×1000，品牌、设计令牌与标本墙 |
| [桌面图表](library-charts-desktop.webp) | 趋势、六类情绪、三级风险；切换后的示例B |
| [手机展示](library-mobile.webp) | 390×844，内容宽度390，无横向溢出 |
| [手机情绪图](library-mobile-chart.webp) | 六个完整标签与百分比，没有截断 |

实际检查包含头像分组3/4/6个、键盘Enter切换数据、三图的实际数据、响应式尺寸和减少动态偏好。三图在减少动态模式下关闭动画并显示最终数据，展示页错误0、warning0、外部请求0、坏图0。品牌PNG512/1024另通过sharp检查透明通道及透明像素；这项检查记录在QA JSON，不能冒充静态校验器提供的能力。

截图由浏览器原生捕获并仅转换为WebP，未修改画面元素。业务截图的水印是捕获前注入的DOM，非后期图像合成。

## 设计优化后的工作台

当前验证为[refinement/qa.json](refinement/qa.json)：桌面1440×1000、手机390×844，三候选九版本、搜索筛选、真实两尺寸下载哈希、复制成功/失败、Esc焦点与三图更新均通过；控制台error/warning、坏图、外部/后端请求均0。

图像入口：[桌面](refinement/desktop.webp)、[品牌比较](refinement/brand-comparison.webp)、[素材浏览](refinement/asset-browser.webp)、[手机](refinement/mobile.webp)、[手机详情](refinement/mobile-detail.webp)、[手机情绪图](refinement/mobile-emotion.webp)、[Figma原生导出](refinement/figma-brand-board.png)。具体命令与边界见[优化验收](../优化验收记录.md)。
