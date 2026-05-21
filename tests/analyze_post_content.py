#!/usr/bin/env python3
"""
分析两天帖子的具体内容
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


def find_longi_result(data):
    for result in data.get("results", []):
        target_name = result.get("target_name", "")
        if "隆基绿能" in target_name or "601012" in target_name:
            return result
    return None


def main():
    data_0518 = load_data("20260518")
    data_0519 = load_data("20260519")

    longi_0518 = find_longi_result(data_0518)
    longi_0519 = find_longi_result(data_0519)

    news_0518 = longi_0518.get('news_list', [])
    news_0519 = longi_0519.get('news_list', [])

    print("="*80)
    print("0518 帖子标题前20个")
    print("="*80)
    for i, n in enumerate(news_0518[:20]):
        print(f"{i+1:2d}. {n.get('title', '')[:60]}")

    print("\n" + "="*80)
    print("0519 帖子标题前20个")
    print("="*80)
    for i, n in enumerate(news_0519[:20]):
        print(f"{i+1:2d}. {n.get('title', '')[:60]}")

    # 检查V2分析的具体内容
    print("\n" + "="*80)
    print("V2分析详情")
    print("="*80)

    v2_0518 = longi_0518.get('emotion_v2')
    v2_0519 = longi_0519.get('emotion_v2')

    if v2_0518:
        print(f"\n0518 V2:")
        print(f"  final_score: {v2_0518.get('final_score')}")
        print(f"  confidence: {v2_0518.get('confidence')}")
        print(f"  trend_analysis: {v2_0518.get('trend_analysis', '')[:200]}...")
        print(f"  key_post_titles: {v2_0518.get('key_post_titles', [])[:5]}")

    if v2_0519:
        print(f"\n0519 V2:")
        print(f"  final_score: {v2_0519.get('final_score')}")
        print(f"  confidence: {v2_0519.get('confidence')}")
        print(f"  trend_analysis: {v2_0519.get('trend_analysis', '')[:200]}...")
        print(f"  key_post_titles: {v2_0519.get('key_post_titles', [])[:5]}")

    # 检查股吧爬虫的时间过滤
    print("\n" + "="*80)
    print("检查帖子发布时间")
    print("="*80)

    print(f"\n0518 前5个帖子:")
    for i, n in enumerate(news_0518[:5]):
        print(f"  {i+1}. title={n.get('title', '')[:40]}, source={n.get('source_type')}")

    print(f"\n0519 前5个帖子:")
    for i, n in enumerate(news_0519[:5]):
        print(f"  {i+1}. title={n.get('title', '')[:40]}, source={n.get('source_type')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
