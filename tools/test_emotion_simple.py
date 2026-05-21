#!/usr/bin/env python3
"""
简单测试情绪分析修复
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from emotion import EmotionAnalyzer, PostType


def test():
    config = get_config()
    analyzer = EmotionAnalyzer(config)

    # 模拟一些帖子数据
    test_posts = [
        {
            "title": "隆基绿能一季度报",
            "url": "https://example.com/news1",
            "content": "隆基绿能一季度营收下降，但是BC电池出货量增长",
            "source_type": "news"
        },
        {
            "title": "股民讨论",
            "url": "https://xueqiu.com/post1",
            "content": "今天隆基涨了！",
            "source_type": "forum"
        },
        {
            "title": "股吧热帖",
            "url": "https://guba.eastmoney.com/post2",
            "content": "分析一下隆基未来走势",
            "source_type": "forum"
        }
    ]

    stock = {
        "code": "601012",
        "name": "隆基绿能",
        "market_cap": 1000.0
    }

    print("=== 测试分类帖子 ===")
    classified = analyzer.classify_posts(test_posts, stock)

    for i, post in enumerate(classified):
        print(f"{i+1}. {post.title}")
        print(f"   类型: {post.post_type.value if post.post_type else 'None'}")
        print()

    print("=== 检查NEWS类型是否被正确设置 ===")
    news_count = sum(1 for p in classified if p.post_type == PostType.NEWS)
    print(f"NEWS类型帖子数: {news_count}")

    print("\n=== 测试计算情绪值（先模拟一些emotion_score） ===")
    for post in classified:
        post.emotion_score = 0.5  # 模拟正面情绪

    score = analyzer.calculate_emotion_score(classified, stock)
    print(f"综合情绪值: {score:.4f}")

    if score != 0.0:
        print("\n✅ 修复成功！情绪值正常计算")
        return True
    else:
        print("\n❌ 修复失败！情绪值仍然为0")
        return False


if __name__ == "__main__":
    success = test()
    sys.exit(0 if success else 1)
