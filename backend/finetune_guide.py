# ==============================================================================
# Qwen2.5-7B-Instruct LoRA 微调配置指南 (基于 LLaMA-Factory)
# ==============================================================================
#
# 1. 环境准备与 LLaMA-Factory 安装
# ------------------------------------------------------------------------------
# 建议在带有一张 24GB 显存以上显卡（如 RTX 3090/4090）的机器上运行
# 
# bash 命令:
# git clone https://github.com/hiyouga/LLaMA-Factory.git
# cd LLaMA-Factory
# pip install -e .[metrics]
# 
# ------------------------------------------------------------------------------
# 2. 准备 SoulChat 数据集
# ------------------------------------------------------------------------------
# 下载 SoulChat 数据集后，将其转换为 LLaMA-Factory 支持的 ShareGPT 格式。
# 在 LLaMA-Factory/data 目录下新建 soulchat.json，格式示例如下：
# [
#   {
#     "conversations": [
#       {"from": "human", "value": "我最近压力好大，感觉要崩溃了。"},
#       {"from": "gpt", "value": "听到你这么说我感到很抱歉。你愿意多分享一下是什么让你感到压力如此之大吗？我在这里听着。"}
#     ],
#     "system": "你是一个专业、富有共情心、不带有任何评判色彩的心理咨询师。"
#   }
# ]
#
# 然后在 LLaMA-Factory/data/dataset_info.json 中注册该数据集：
# "soulchat": {
#   "file_name": "soulchat.json",
#   "formatting": "sharegpt",
#   "columns": {
#     "messages": "conversations",
#     "system": "system"
#   }
# }
#
# ------------------------------------------------------------------------------
# 3. 编写 LoRA 微调配置与执行命令
# ------------------------------------------------------------------------------
# 你可以直接在 LLaMA-Factory 目录下执行以下 yaml 配置文件（如 train_qwen2.5_lora.yaml）
# 然后运行：llamafactory-cli train train_qwen2.5_lora.yaml

# train_qwen2.5_lora.yaml 内容示例：
"""
### model
model_name_or_path: Qwen/Qwen2.5-7B-Instruct
trust_remote_code: true

### method
stage: sft
do_train: true
finetuning_type: lora
lora_target: all
lora_rank: 8
lora_alpha: 16
lora_dropout: 0.1

### dataset
dataset: soulchat
template: qwen
cutoff_len: 2048
max_samples: 50000 # 根据实际数据集大小调整
overwrite_cache: true
preprocessing_num_workers: 16

### output
output_dir: saves/qwen2.5-7b/lora/soulchat_finetune
logging_steps: 10
save_steps: 500
plot_loss: true
overwrite_output_dir: true

### train
per_device_train_batch_size: 2
gradient_accumulation_steps: 8
learning_rate: 1.0e-4
num_train_epochs: 3.0
lr_scheduler_type: cosine
warmup_ratio: 0.1
bf16: true
ddp_timeout: 18000000
"""

# ------------------------------------------------------------------------------
# 4. 微调完成后合并模型或动态加载 LoRA
# ------------------------------------------------------------------------------
# LLaMA-Factory 训练完成后，权重会保存在 saves/qwen2.5-7b/lora/soulchat_finetune 目录下。
# 我们在 FastAPI 后端可以直接使用 transformers 或 vLLM 动态加载这个 LoRA 权重。
