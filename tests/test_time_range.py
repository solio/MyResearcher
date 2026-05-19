#!/usr/bin/env python3
"""
测试时间范围过滤是否生效
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from searcher import TavilySearchProvider


def test_search_with_time_range():
    config = get_config()

    provider = TavilySearchProvider(
        api_key=config.TAVILY_API_KEY,
        tavily_time_range_days=config.TAVILY_SEARCH_TIME_RANGE_DAYS
    )

    print("=" * 80)
    print("测试时间范围过滤")
    print("=" * 80)

    queries = [
        "光伏行业最新新闻",
        "房地产市场动态",
    ]

    for query in queries:
        print(f"\n\n搜索: {query}")
        print("-" * 80)

        results = provider.search(
            query,
            max_results=10,
            time_range_days=7  # 7天内
        )

        print(f"返回 {len(results)} 条结果")

        for i, r in enumerate(results, 1):
            print(f"\n{i}. {r.get('title', '')}")
            print(f"   {r.get('url', '')}")
            content = r.get('content', '')[:100]
            if content:
                print(f"   {content}...")

    print("\n" + "=" * 80)
    print("测试完成")
    print("=" * 80)


if __name__ == "__main__":
    test_search_with_time_range()
