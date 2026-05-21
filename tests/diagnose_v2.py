#!/usr/bin/env python3
"""
诊断V2情绪分析为什么两天返回相同结果
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config
from emotion_v2 import build_emotion_prompt, analyze_emotion_v2
from llm import DeepSeekLLMProvider


def load_data(date_str):
    data_dir = Path(__file__).parent.parent / "output" / date_str
    data_files = list(data_dir.glob("*-数据.json"))
    if not data_files:
        return None
    with open(sorted(data_files)[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def get_longi_posts(data):
    for result in data.get("results", []):
        target_name = result.get("target_name", "")
        if "隆基绿能" in target_name or "601012" in target_name:
            posts = [p for p in result.get("news_list", []) if p.get("source_type") == "forum"]
            return posts
    return []


def main():
    config = get_config()

    # 加载两天的数据
    data_0518 = load_data("20260518")
    data_0519 = load_data("20260519")

    if not data_0518 or not data_0519:
        print("无法加载数据")
        return 1

    # 获取帖子
    posts_0518 = get_longi_posts(data_0518)
    posts_0519 = get_longi_posts(data_0519)

    print(f"0518 帖子数: {len(posts_0518)}")
    print(f"0519 帖子数: {len(posts_0519)}")

    # 对比前10个帖子标题
    print("\n0518 前10个标题:")
    for i, p in enumerate(posts_0518[:10]):
        print(f"{i+1:2d}. {p.get('title', '')[:60]}")

    print("\n0519 前10个标题:")
    for i, p in enumerate(posts_0519[:10]):
        print(f"{i+1:2d}. {p.get('title', '')[:60]}")

    # 构建prompt并对比
    prompt_0518 = build_emotion_prompt(posts_0518, "隆基绿能", 1000.0)
    prompt_0519 = build_emotion_prompt(posts_0519, "隆基绿能", 1000.0)

    print(f"\nPrompt 0518 长度: {len(prompt_0518)}")
    print(f"Prompt 0519 长度: {len(prompt_0519)}")

    # 保存prompt到文件对比
    with open("/tmp/prompt_0518.txt", "w", encoding="utf-8") as f:
        f.write(prompt_0518)
    with open("/tmp/prompt_0519.txt", "w", encoding="utf-8") as f:
        f.write(prompt_0519)

    print(f"\nPrompts保存到 /tmp/prompt_0518.txt 和 /tmp/prompt_0519.txt")

    # 实际调用LLM测试
    print("\n" + "="*80)
    print("测试调用LLM分析0518的数据")
    print("="*80)

    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model=config.DEEPSEEK_MODEL,
        timeout=180,
        max_retries=2
    )

    result_0518 = analyze_emotion_v2(posts_0518, "隆基绿能", "601012", 1000.0, llm_provider)
    if result_0518:
        print(f"\n0518 结果:")
        print(f"  最终评分: {result_0518.final_score}")
        print(f"  评级: {result_0518.rating_level} {result_0518.rating_emoji}")
        print(f"  置信度: {result_0518.confidence}")
        print(f"  趋势分析: {result_0518.trend_analysis[:100]}...")

    print("\n" + "="*80)
    print("测试调用LLM分析0519的数据")
    print("="*80)

    result_0519 = analyze_emotion_v2(posts_0519, "隆基绿能", "601012", 1000.0, llm_provider)
    if result_0519:
        print(f"\n0519 结果:")
        print(f"  最终评分: {result_0519.final_score}")
        print(f"  评级: {result_0519.rating_level} {result_0519.rating_emoji}")
        print(f"  置信度: {result_0519.confidence}")
        print(f"  趋势分析: {result_0519.trend_analysis[:100]}...")

    if result_0518 and result_0519:
        print(f"\n对比: 0518评分={result_0518.final_score}, 0519评分={result_0519.final_score}, 是否相同: {result_0518.final_score == result_0519.final_score}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
