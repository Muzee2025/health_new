import os
from pathlib import Path

import requests
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path=Path(__file__).resolve().parents[2] / ".env")

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

def call_deepseek_api(prompt: str) -> str:
    """
    调用 DeepSeek API 的工具函数
    :param prompt: 用户的输入提示词
    :return: DeepSeek 的回复
    """
    if not DEEPSEEK_API_KEY or DEEPSEEK_API_KEY == "your_deepseek_api_key_here":
        return "DeepSeek API Key 未配置，请在 .env 文件中配置。"

    url = "https://api.deepseek.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }
    
    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        return data['choices'][0]['message']['content']
    except Exception as e:
        return f"调用 DeepSeek API 时发生错误: {str(e)}"
