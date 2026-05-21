#!/usr/bin/env python3
"""
分析0518和0519情绪值相同的问题
"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def load_data(date_str):
    """加载指定日期的数据"""
    data_dir = Path(__file__).parent.parent / "output" / date_str
    data_files = list(data_dir.glob("*-数据.json"))
    if not data_files:
        print(f"❌ 找不到{date_str}的数据文件")
        return None

    data_file = sorted(data_files)[-1]
    print(f"✅ 加载{date_str}数据: {data_file.name}")

    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_longi_result(data):
    """找到隆基绿能的结果"""
    for result in data.get("results", []):
        target_name = result.get("target_name", "")
        if "隆基绿能" in target_name or "601012" in target_name:
            return result
    return None


def main():
    # 加载两天的数据
    data_0518 = load_data("20260518")
    data_0519 = load_data("20260519")

    if not data_0518 or not data_0519:
        return 1

    # 找到隆基的数据
    longi_0518 = find_longi_result(data_0518)
    longi_0519 = find_longi_result(data_0519)

    if not longi_0518 or not longi_0519:
        print("❌ 找不到隆基绿能的数据")
        return 1

    print("\n" + "="*80)
    print("0518 vs 0519 隆基绿能情绪分析对比")
    print("="*80)

    print(f"\n0518:")
    print(f"  emotion_score: {longi_0518.get('emotion_score')}")
    print(f"  use_v2_emotion: {longi_0518.get('use_v2_emotion')}")
    if longi_0518.get('emotion_v2'):
        print(f"  V2:")
        v2 = longi_0518['emotion_v2']
        print(f"    final_score: {v2.get('final_score')}")
        print(f"    rating_level: {v2.get('rating_level')}")
        print(f"    total_posts: {v2.get('total_posts')}")

    print(f"\n0519:")
    print(f"  emotion_score: {longi_0519.get('emotion_score')}")
    print(f"  use_v2_emotion: {longi_0519.get('use_v2_emotion')}")
    if longi_0519.get('emotion_v2'):
        print(f"  V2:")
        v2 = longi_0519['emotion_v2']
        print(f"    final_score: {v2.get('final_score')}")
        print(f"    rating_level: {v2.get('rating_level')}")
        print(f"    total_posts: {v2.get('total_posts')}")

    # 对比帖子数据
    print("\n" + "="*80)
    print("对比帖子URL")
    print("="*80)

    news_0518 = longi_0518.get('news_list', [])
    news_0519 = longi_0519.get('news_list', [])

    urls_0518 = set(n.get('url', '') for n in news_0518 if n.get('url'))
    urls_0519 = set(n.get('url', '') for n in news_0519 if n.get('url'))

    print(f"\n0518 帖子数: {len(news_0518)}, 有效URL: {len(urls_0518)}")
    print(f"0519 帖子数: {len(news_0519)}, 有效URL: {len(urls_0519)}")

    overlap = urls_0518 & urls_0519
    print(f"\n相同URL: {len(overlap)} 个")

    if overlap:
        print(f"\n重叠的URL:")
        for url in sorted(overlap):
            print(f"  {url}")

    # 查看分类帖子
    print("\n" + "="*80)
    print("查看classified_posts")
    print("="*80)

    cp_0518 = longi_0518.get('classified_posts', [])
    cp_0519 = longi_0519.get('classified_posts', [])

    print(f"\n0518 classified_posts: {len(cp_0518)}")
    print(f"0519 classified_posts: {len(cp_0519)}")

    if cp_0518 and cp_0519:
        print(f"\n0518 前3个帖子标题:")
        for i, p in enumerate(cp_0518[:3]):
            print(f"  {i+1}. {p.get('title', '')[:50]}...")

        print(f"\n0519 前3个帖子标题:")
        for i, p in enumerate(cp_0519[:3]):
            print(f"  {i+1}. {p.get('title', '')[:50]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
