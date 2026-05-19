#!/usr/bin/env python3
"""快速查看数据结构"""
import json
from pathlib import Path

data_path = Path(__file__).parent / "output" / "20260515" / "20260515_163040-数据.json"

with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print(f"数据日期: {data['date']}")
print(f"结果数量: {len(data['results'])}")
print("=" * 80)

for i, result in enumerate(data['results']):
    print(f"\n[{i}] {result['target_type']}: {result['target_name']}")
    print(f"    新闻数: {len(result.get('news_list', []))}")
    print(f"    情绪值: {result.get('emotion_score', 'N/A')}")

    news_list = result.get('news_list', [])
    if news_list:
        forum_count = sum(1 for n in news_list if n.get('source_type') == 'forum')
        news_count = sum(1 for n in news_list if n.get('source_type') == 'news')
        print(f"    论坛: {forum_count}, 新闻: {news_count}")
