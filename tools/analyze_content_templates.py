#!/usr/bin/env python3
"""
分析内容模板，找出共同的模式
"""
import json
from collections import Counter

def analyze_content_templates(json_path):
    """分析内容模板"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 80)
    print("内容模板分析")
    print("=" * 80)

    all_items = []
    template_contents = []

    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        news_list = result.get('news_list', [])

        for item in news_list:
            all_items.append({
                'target': target_name,
                'url': item.get('url', ''),
                'title': item.get('title', ''),
                'content': item.get('content', '')
            })

    # 分析内容特征
    print(f"\n共 {len(all_items)} 条数据\n")
    print("=" * 80)
    print("分析内容长度分布")
    print("=" * 80)

    content_lengths = [len(item['content']) for item in all_items]
    content_lengths.sort()
    print(f"最短: {content_lengths[0]}")
    print(f"最长: {content_lengths[-1]}")
    print(f"中位数: {content_lengths[len(content_lengths)//2]}")

    print("\n" + "=" * 80)
    print("查找内容模板（内容非常相似的）")
    print("=" * 80)

    # 检查开头相同的内容
    content_prefixes = Counter()
    for item in all_items:
        content = item['content']
        if len(content) > 50:
            prefix = content[:100]
            content_prefixes[prefix] += 1

    print("\n常见开头模式（出现>=2次）:")
    for prefix, count in content_prefixes.most_common(20):
        if count >= 2:
            print(f"\n[{count}次] {repr(prefix[:150])}")

    print("\n" + "=" * 80)
    print("检查模板内容特征")
    print("=" * 80)

    # 检查包含大量"|"的内容（导航菜单）
    nav_items = []
    for item in all_items:
        content = item['content']
        if '|' in content and content.count('|') > 5:
            nav_items.append(item)

    print(f"\n发现 {len(nav_items)} 条可能是导航菜单的内容\n")

    for item in nav_items[:10]:
        print(f"\n标题: {item['title']}")
        print(f"URL: {item['url']}")
        print(f"内容前200字符: {repr(item['content'][:200])}")

    # 检查雪球行情页特征
    print("\n" + "=" * 80)
    print("雪球行情页特征分析")
    print("=" * 80)

    xueqiu_items = [i for i in all_items if 'xueqiu.com/S/SH' in i['url']]
    print(f"\n雪球个股页: {len(xueqiu_items)} 条\n")

    for item in xueqiu_items[:5]:
        print(f"\nURL: {item['url']}")
        print(f"标题: {item['title']}")
        print(f"内容: {repr(item['content'][:150])}")

    # 输出建议过滤的URL模式
    print("\n" + "=" * 80)
    print("建议过滤的URL模式（基于人工分析）")
    print("=" * 80)

    suggestions = [
        "data.eastmoney.com/gzfx/detail/",
        "data.eastmoney.com/stockdata/",
        "data.eastmoney.com/notice/",
        "quote.eastmoney.com/",
        "xueqiu.com/S/SH",
        "xueqiu.com/S/SZ",
        "xueqiu.com/S/",
        "vip.stock.finance.sina.com.cn/corp/go.php",
        "stock.finance.sina.com.cn/stock/go.php/vReport_List",
        "basic.10jqka.com.cn",
    ]

    for s in suggestions:
        count = sum(1 for i in all_items if s in i['url'])
        print(f"{s:<60} -> {count} 条")

    return all_items

if __name__ == '__main__':
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'
    analyze_content_templates(json_path)
