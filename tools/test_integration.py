#!/usr/bin/env python3
"""
集成测试：验证股吧搜索 + 情绪分析全流程
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from guba_scraper import GubaScraper
from emotion import EmotionAnalyzer, PostType


def test_guba_scraper():
    """测试股吧爬虫"""
    print("=" * 60)
    print("测试1：股吧爬虫")
    print("=" * 60)

    scraper = GubaScraper()
    posts = scraper.scrape_stock_posts("601012", max_pages=2)

    print(f"\n✅ 获取到 {len(posts)} 个帖子")
    for i, post in enumerate(posts[:10], 1):
        print(f"{i}. {post.get('title', '')[:60]}")
        print(f"   URL: {post.get('url', '')}")
        if post.get('reply_count'):
            print(f"   评论数: {post.get('reply_count')}")

    return posts


def test_emotion_classification(posts):
    """测试情绪分类和情绪值计算"""
    print("\n" + "=" * 60)
    print("测试2：情绪分类和计算")
    print("=" * 60)

    config = get_config()
    analyzer = EmotionAnalyzer(config)

    stock = {"code": "601012", "name": "隆基绿能", "market_cap": 1000.0}

    # 分类帖子
    classified = analyzer.classify_posts(posts, stock)
    print(f"\n✅ 分类完成，共 {len(classified)} 个帖子")

    # 统计类型
    type_count = {}
    for p in classified:
        t = p.post_type.value if p.post_type else "None"
        type_count[t] = type_count.get(t, 0) + 1

    print(f"\n帖子类型分布:")
    for t, c in type_count.items():
        print(f"  {t}: {c}")

    # 模拟情绪评分
    import random
    for p in classified:
        p.emotion_score = random.uniform(-0.8, 0.8)

    # 计算综合情绪值
    emotion_score = analyzer.calculate_emotion_score(classified, stock)
    print(f"\n✅ 综合情绪值: {emotion_score:.4f}")

    if emotion_score != 0.0:
        print("✅ 情绪值计算正常！")
        return True
    else:
        print("❌ 情绪值为0，有问题")
        return False


def main():
    print("\n" + "=" * 60)
    print("股吧搜索 + 情绪分析 集成测试")
    print("=" * 60 + "\n")

    try:
        posts = test_guba_scraper()
        if posts:
            test_emotion_classification(posts)

        print("\n" + "=" * 60)
        print("✅ 所有测试完成！")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
