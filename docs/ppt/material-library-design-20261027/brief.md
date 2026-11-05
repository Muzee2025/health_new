# 答辩PPT素材库设计探索

> owner: AI-OUTLINE ｜ version: 1.0 ｜ status: Product Design视觉探索 待选择 ｜ updated: 2026-10-27

用户要求继续丰富答辩PPT素材，并明确调用imagegen及Product Design设计素材库。目标为桌面端选材界面：按8页答辩内容或素材主题查找，预览对应场景，再取得原文件。目标用户为本项目答辩材料制作人。

## 视觉约束与参考

沿用`src/styles/tokens.css`的暖紫`#78558F`、深紫`#604372`、杏色`#E8B185`、鼠尾草绿`#8BA696`与白色基底。中文界面，文字清晰，留白充足。现有Open Doodles人物、Phosphor图标及项目原创关系图作为图像参考；不混用两套人物画风，不把生成图片称为真实SVG文件或已建成功能。

本次生成三幅独立界面预览，目标1440×1024，不含浏览器或设备外壳，不追加PPT页。方向为按页选材、场景图库和选材工作台；展示顺序以实际图像在对话中出现的顺序为准。选择视觉目标后再进入界面实现。

参考图路径：

- `docs/ppt/vector-assets-20261027/preview.png`
- `docs/ppt/direction-mindmap-20261027/preview.png`

## 文件属性

ImageGen产物仅为PNG界面概念稿。现有SVG、draw.io、许可与来源登记保留原文件和属性；界面预览不构成向量导出或交互验证。生成采用内置ImageGen，不调用模型API或读取密钥。

Product Design预检确认没有已保存的上下文，本轮仅使用当前会话与仓库中的素材/令牌。未请求保存跨会话偏好。业务页面、数据、配置、运行服务和8页实时PPT均不因设计探索改变。
