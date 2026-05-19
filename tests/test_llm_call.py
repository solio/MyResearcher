#!/usr/bin/env python3
"""测试LLM调用"""
import sys
import json
from pathlib import Path

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from llm import DeepSeekLLMProvider, StockAnalyzer

def main():
    print("=" * 80)
    print("测试LLM调用")
    print("=" * 80)

    # 加载配置
    config = get_config()

    # 加载一些测试帖子
    data_path = Path(__file__).parent / "output" / "20260515" / "20260515_163040-数据.json"
    with open(data_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    news_list = data["results"][0]["news_list"][:30]

    print(f"使用帖子数: {len(news_list)}")

    # 初始化
    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model="deepseek-v4-pro",
        timeout=120,
        max_retries=1
    )

    analyzer = StockAnalyzer(llm_provider)

    # 构建提示词
    posts_text = ""
    for i, post in enumerate(news_list[:20]):
        title = post.get("title", "")
        content = post.get("content", "")
        posts_text += f"[帖子{i+1}]\n标题: {title}\n内容: {content[:100]}\n\n"

    prompt = f"""你是一位专业的A股市场情绪分析师。

请分析以下帖子，给出情绪分析：

{posts_text}

请按以下JSON格式输出：
{{
    "analysis": "整体情绪分析",
    "sentiment_score": -2.0,
    "confidence": 0.85
}}

只输出JSON，不要其他文字。
"""

    print(f"\n提示词长度: {len(prompt)}")
    print(f"\n调用LLM...")

    messages = [{"role": "user", "content": prompt}]
    result = llm_provider.chat(messages, temperature=0.4, max_tokens=2000)

    print(f"\nLLM返回结果:")
    print("-" * 80)
    print(repr(result)[:500])
    print("-" * 80)

    if result:
        try:
            parsed = json.loads(result)
            print(f"\n✅ JSON解析成功: {parsed}")
        except Exception as e:
            print(f"\n❌ JSON解析失败: {e}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
