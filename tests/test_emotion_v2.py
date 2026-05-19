#!/usr/bin/env python3
"""
测试 V2 7级情绪评分模型测试脚本
"""
import sys
from pathlib import Path

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from emotion_v2 import EmotionAnalyzerV2
from llm import DeepSeekLLMProvider, StockAnalyzer

def test_v2_emotion():
    """测试V2情绪分析"""
    print("=" * 80)
    print("测试 V2 7级情绪评分模型")
    print("=" * 80)

    # 加载配置
    config = get_config()

    # 模拟一些帖子数据
    sample_posts = [
        {
            "title": "今天抄底，结果挂山顶了",
            "content": "今天跌了5个点抄底，没想到还能继续跌，现在套牢了",
            "url": "https://guba.eastmoney.com/news,601012,1.html",
            "source_type": "forum",
            "reply_count": 35,
            "like_count": 18
        },
        {
            "title": "隆基这走势看不懂，大家怎么看",
            "content": "感觉还要继续下探，等企稳再说吧",
            "url": "https://guba.eastmoney.com/news,601012,2.html",
            "source_type": "forum",
            "reply_count": 12,
            "like_count": 5
        },
        {
            "title": "长期看好，准备分批建仓",
            "content": "虽然现在跌，但长期看还是有价值的，越跌越买",
            "url": "https://guba.eastmoney.com/news,601012,3.html",
            "source_type": "forum",
            "reply_count": 8,
            "like_count": 12
        }
    ]

    sample_news = [
        {
            "title": "隆基绿能发布一季度报告",
            "content": "公司一季度业绩报告发布，营收同比有所下降",
            "url": "https://news.eastmoney.com/news,1.html",
            "source_type": "news"
        }
    ]

    # 初始化LLM
    llm_provider = DeepSeekLLMProvider(
        api_key=config.DEEPSEEK_API_KEY,
        api_base=config.DEEPSEEK_API_BASE,
        model="deepseek-v4-pro",
        timeout=config.LLM_TIMEOUT,
        max_retries=config.LLM_MAX_RETRIES
    )

    analyzer = StockAnalyzer(llm_provider)

    # 调用V2情绪分析
    print(f"\n调用 DeepSeek-V4-Pro 进行情绪分析...")
    print(f"股票: 隆基绿能 (601012)")
    print(f"市值: 1000 亿")
    print(f"帖子数: {len(sample_posts)}")
    print(f"新闻数: {len(sample_news)}")
    print()

    llm_result = analyzer.analyze_emotion_v2(
        posts=sample_posts,
        news_list=sample_news,
        stock_name="隆基绿能",
        market_cap=1000.0,
        industry_score=None
    )

    if not llm_result:
        print("❌ LLM分析失败")
        return False

    print("✅ LLM分析成功！")
    print(f"\n单帖分析数: {len(llm_result.get('per_post_analysis', []))}")

    overall = llm_result.get('overall_analysis', {})
    print(f"原始评分: {overall.get('raw_score', 0)}")
    print(f"置信度: {overall.get('confidence', 0)}")

    # 计算最终评分
    emotion_v2_analyzer = EmotionAnalyzerV2(config)
    final_score = emotion_v2_analyzer.calculate_final_score(
        llm_result, sample_posts, 1000.0, None
    )

    print("\n" + "=" * 80)
    print("最终评分结果")
    print("=" * 80)
    print(f"最终评分: {final_score.final_score:.3f}")
    print(f"情绪评级: {final_score.rating_emoji} {final_score.rating_level}")
    print(f"置信度: {final_score.confidence:.1%}")
    print()
    print(f"原始评分: {final_score.raw_score:.3f}")
    print(f"市值调整: {final_score.market_cap_adjusted:.3f}")
    print(f"丰裕系数: {final_score.abundance_coefficient:.2f}")
    print()
    print(f"总帖子: {final_score.total_posts}")
    print(f"总互动: {final_score.total_interactions}")

    if final_score.trend_analysis:
        print(f"\n趋势分析: {final_score.trend_analysis}")

    if final_score.key_posts:
        print(f"\n关键帖子 ({len(final_score.key_posts)}):")
        for post in final_score.key_posts:
            print(f"  - {post.get('title', '')}")

    print("\n" + "=" * 80)
    print("测试完成！")
    print("=" * 80)

    return True


if __name__ == "__main__":
    try:
        success = test_v2_emotion()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
