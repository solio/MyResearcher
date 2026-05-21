#!/usr/bin/env python3
"""
简洁版测试脚本：验证情绪分析修复
"""
import sys
import json
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from emotion import EmotionAnalyzer, PostType


def test_emotion_fix():
    """测试情绪分析修复"""
    config = get_config()

    # 1. 加载之前的数据
    data_file = Path("output/20260507/20260507_173157-数据.json")
    if not data_file.exists():
        print(f"错误: 数据文件不存在 {data_file}")
        return False

    with open(data_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"✅ 加载数据成功，包含 {len(data.get('stocks', []))} 只股票")

    # 2. 测试一只股票的情绪分析流程
    stock_data = data["stocks"][0] if data["stocks"] else None
    if not stock_data:
        print("❌ 没有股票数据")
        return False

    print(f"\n📊 测试股票: {stock_data['name']} ({stock_data['code']})")

    analyzer = EmotionAnalyzer(config)

    # 3. 模拟帖子数据（从搜索结果）
    posts = stock_data.get("search_results", [])
    print(f"   搜索结果数: {len(posts)}")

    # 4. 分类帖子
    classified_posts = analyzer.classify_posts(posts, stock_data)
    print(f"   分类后帖子数: {len(classified_posts)}")

    # 统计各类型
    type_count = {}
    for p in classified_posts:
        t = p.post_type.value if p.post_type else "None"
        type_count[t] = type_count.get(t, 0) + 1

    print(f"   帖子类型分布: {type_count}")

    # 5. 检查是否有NEWS类型
    if "news" in type_count:
        print(f"   ✅ NEWS类型正常工作，有 {type_count['news']} 条新闻")
    else:
        print(f"   ⚠️  没有NEWS类型的帖子")

    # 6. 模拟LLM情绪评分（给每个帖子随机评分）
    import random
    for p in classified_posts:
        p.emotion_score = random.uniform(-0.8, 0.8)

    # 7. 计算综合情绪值
    emotion_score = analyzer.calculate_emotion_score(classified_posts, stock_data)
    print(f"\n🧮 计算出的情绪值: {emotion_score:.4f}")

    if emotion_score != 0.0:
        print("✅ 情绪值不为0，修复成功！")
        return True
    else:
        print("❌ 情绪值还是0，修复失败")
        return False


if __name__ == "__main__":
    success = test_emotion_fix()
    sys.exit(0 if success else 1)
