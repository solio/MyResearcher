#!/usr/bin/env python3
"""简单测试"""
import sys
import json
from pathlib import Path

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from llm import DeepSeekLLMProvider

def main():
    print("=" * 80)
    print("简单LLM测试")
    print("=" * 80)

    # 加载配置
    config = get_config()

    # 初始化LLM
    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model="deepseek-v4-pro",
        timeout=120,
        max_retries=1
    )

    # 简单提示词
    prompt = """你好！请介绍一下你自己。"""

    print(f"提示词: {prompt[:100]}")
    print("\n调用LLM...")

    messages = [{"role": "user", "content": prompt}]
    result = llm_provider.chat(messages, temperature=0.7, max_tokens=500)

    print(f"\n返回结果:")
    print("-" * 80)
    if result:
        print(result[:300])
    else:
        print("None")
    print("-" * 80)

    return 0


if __name__ == "__main__":
    sys.exit(main())
