#!/usr/bin/env python3
"""
检查两天数据中的trend_analysis
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_data(date_str):
    data_dir = Path(__file__).parent.parent / "output" / date_str
    data_files = list(data_dir.glob("*-数据.json"))
    if not data_files:
        return None
    with open(sorted(data_files)[-1], 'r', encoding='utf-8') as f:
        return json.load(f)


def get_longi_result(data):
    for result in data.get("results", []):
        target_name = result.get("target_name", "")
        if "隆基绿能" in target_name or "601012" in target_name:
            return result
    return None


def main():
    data_0518 = load_data("20260518")
    data_0519 = load_data("20260519")

    result_0518 = get_longi_result(data_0518)
    result_0519 = get_longi_result(data_0519)

    print("="*80)
    print("0518 V2数据:")
    print("="*80)
    if result_0518.get("use_v2_emotion") and result_0518.get("emotion_v2"):
        v2 = result_0518["emotion_v2"]
        print(f"评分: {v2.get('final_score')}")
        print(f"评级: {v2.get('rating_emoji')} {v2.get('rating_level')}")
        print(f"置信度: {v2.get('confidence')}")
        print(f"关键帖子: {v2.get('key_post_titles', [])[:3]}")
        print(f"\n趋势分析:\n{v2.get('trend_analysis', '')}")

    print("\n" + "="*80)
    print("0519 V2数据:")
    print("="*80)
    if result_0519.get("use_v2_emotion") and result_0519.get("emotion_v2"):
        v2 = result_0519["emotion_v2"]
        print(f"评分: {v2.get('final_score')}")
        print(f"评级: {v2.get('rating_emoji')} {v2.get('rating_level')}")
        print(f"置信度: {v2.get('confidence')}")
        print(f"关键帖子: {v2.get('key_post_titles', [])[:3]}")
        print(f"\n趋势分析:\n{v2.get('trend_analysis', '')}")

    print("\n" + "="*80)
    print("结论:")
    print("="*80)
    trend_0518 = result_0518.get("emotion_v2", {}).get("trend_analysis", "")
    trend_0519 = result_0519.get("emotion_v2", {}).get("trend_analysis", "")

    if trend_0518 == trend_0519:
        print("❌ 趋势分析完全相同 - 说明可能是缓存或重复数据")
    else:
        print("✅ 趋势分析不同 - 说明LLM确实分析了两天不同的数据")

    score_0518 = result_0518.get("emotion_v2", {}).get("final_score")
    score_0519 = result_0519.get("emotion_v2", {}).get("final_score")

    print(f"\n评分都是 {score_0518} - 这很可能是巧合，因为两天情绪确实都是恐慌")

    return 0


if __name__ == "__main__":
    sys.exit(main())
