# 纵向记录与RAG检索配图候选

> owner: A / Lead ｜ version: 1.0 ｜ status: 候选，待用户审阅 ｜ updated: 2026-11-01

用户确认保留前面第2、3版模型协作示意图后要求看其他配图。本轮以旧PPT第15页为内容上下文、第3版为视觉参考，使用内置image_gen.imagegen重新绘制[纵向记录与RAG检索PNG](rag-records-v1.png)，交付副本为[PNG](../../../deliverables/心域智链_纵向记录与RAG检索_示意图候选_20261101.png)。

图示为立项拟建流程：测评/主动表达/跟进三类本人授权记录，与本次问题进入权限及时间筛选；Qwen3-Embedding-0.6B召回、Qwen3-Reranker-0.6B重排、Qwen3-8B整理带引用和日期的摘要，交教师复核后输出。权限、时间和资料边界由应用实现，不是模型原生保证权限或已验证的临床能力。当前未改PPT正文、运行服务或模型配置。

候选模型原始依据沿本聊天已查的[Qwen3-8B](https://huggingface.co/Qwen/Qwen3-8B-GGUF)、[Embedding](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)与[Reranker](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)官方模型卡。此图不报告模型效果或真实部署结果。

## 实际提示词

```text
Create a clean Chinese technical diagram for a project-proposal presentation by redesigning Image 1 (the old RAG slide). Image 1 is CONTENT CONTEXT. Image 2 is a STYLE REFERENCE only: use its pale lavender blocks, white background, centered typography and bold technical labels; do not copy its six-agent wording or hardware subtitle.
Purpose: visually explain longitudinal records and Retrieval Augmented Generation as a PROPOSED workflow. It must be easy to understand without reading long paragraphs. Landscape 16:9. No slide border, page number, logo, icons, photographs, "5 技术创新" banner, metrics, probabilities, or lengthy footnotes.
One centered title: "纵向记录与RAG检索（拟建）".
Use three clear columns, readable Chinese text, uniform base font size. Names of steps and model names bold; explanatory and output lines normal. Thin-to-medium dark purple arrows with clean routing. Pale lavender rectangular process nodes and soft sage-green final output. Keep all node text centered and prevent overlap/clipping.
LEFT: three vertically stacked source boxes, each with only these labels:
"测评记录"
"主动表达"
"跟进反馈"
A short group heading "本人授权记录". Merge their arrows into the middle first stage. Keep a small top query label "本次问题" with an arrow to the middle process.
MIDDLE: three vertically stacked process boxes connected by arrows:
Box 1: bold "权限与时间筛选"; normal "限定可用记录".
Box 2: bold "向量召回"; bold "Qwen3-Embedding-0.6B"; normal "输出：相关记录".
Box 3: bold "相关性重排"; bold "Qwen3-Reranker-0.6B"; normal "输出：排序片段".
RIGHT: three vertically stacked boxes, connected top to bottom:
Box 1: bold "摘要生成"; bold "Qwen3-8B"; normal "保留原文引用与日期".
Box 2: bold "教师复核"; normal "核对原文与缺失信息".
Box 3: green final node containing ONLY "输出结果".
Connect the middle last stage to the right first stage. No added example conclusions or fabricated data. This is an illustration of a proposed application workflow, not a claim that the models inherently enforce permissions or provide clinical judgment. Avoid text such as "创新点二" and do not print any hardware or operating system line. Use spacious, intentional alignment, fewer words, and one obvious reading path.
```

## 保存与核对

原始生成文件：C:/Users/14012/.codex/generated_images/01a192d5-a2c8-7dd1-b6ab-ffd817e46f66/exec-8cd0cdbf-8992-47d6-a74c-13dfab056309.png。

Lead查看最终图片并逐项核对流程、三模型名称、文字及箭头，无可见裁切。Python读取实际图像、复制哈希并检查已选两图及原PPT哈希，退出0；准确尺寸与载荷见[机器登记](rag-records-v1.json)。当前仅PNG候选，无对应SVG，不称独立评审或用户已批准样式。

用户保留选择见[retained-selection.json](retained-selection.json)：第2版为居中统一字号图，第3版为首轮箭头框图。两图及其他历史版本保留，不覆盖或删除。

