#!/usr/bin/env python3
"""
测试过滤逻辑，验证更新后的过滤器是否能正确识别模板页面
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from content_cleaner import ContentCleaner

def test_filter():
    """测试过滤器"""
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    cleaner = ContentCleaner()

    print("=" * 80)
    print("测试更新后的过滤器效果")
    print("=" * 80)

    all_filtered = []
    all_kept = []

    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        news_list = result.get('news_list', [])

        print(f"\n{target_name}: {len(news_list)} 条")

        filtered_news = cleaner.filter_results(news_list)

        print(f"  过滤后: {len(filtered_news)} 条")

        # 找出被过滤的条目用于分析
        kept_urls = set(n['url'] for n in filtered_news)
        filtered_items = [n for n in news_list if n['url'] not in kept_urls]

        if filtered_items:
            print(f"\n  被过滤的条目（{len(filtered_items)}条）:")
            for item in filtered_items[:5]:
                print(f"    - {item['title'][:60]}")
                print(f"      URL: {item['url'][:80]}")
                # 检查为什么被过滤
                url = item['url']
                title = item['title']
                content = item['content']

                reasons = []
                if cleaner.is_stock_quote_url(url) and not cleaner.has_valid_news_content(title, content) and not cleaner.is_likely_news_url(url):
                    reasons.append("个股数据页URL")
                if cleaner.is_stock_quote_title(title):
                    reasons.append("行情页标题")
                if cleaner.is_template_nav_content(content):
                    reasons.append("导航模板内容")
                if cleaner.is_likely_quote_content(content):
                    reasons.append("行情数据内容")

                if reasons:
                    print(f"      原因: {', '.join(reasons)}")
                print()

        all_filtered.extend(filtered_items)
        all_kept.extend(filtered_news)

    # 总体统计
    print("\n" + "=" * 80)
    print("总体统计")
    print("=" * 80)
    print(f"总共被过滤: {len(all_filtered)} 条")
    print(f"总共保留: {len(all_kept)} 条")

    # 保存过滤后的数据
    output_data = []
    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        news_list = result.get('news_list', [])
        filtered_news = cleaner.filter_results(news_list)
        output_data.append({
            'target_name': target_name,
            'news_list': filtered_news
        })

    output_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据-过滤后.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({'results': output_data}, f, ensure_ascii=False, indent=2)

    print(f"\n过滤后的数据已保存到: {output_path}")

    # 检查还有没有模板内容被保留
    print("\n" + "=" * 80)
    print("检查保留的内容中是否还有明显的模板")
    print("=" * 80)

    remaining_templates = []
    for item in all_kept:
        if cleaner.is_template_nav_content(item['content']) or cleaner.is_likely_quote_content(item['content']):
            remaining_templates.append(item)

    if remaining_templates:
        print(f"\n警告：仍有 {len(remaining_templates)} 条可能的模板内容被保留:")
        for item in remaining_templates[:10]:
            print(f"\n  - {item['title'][:60]}")
            print(f"    URL: {item['url'][:80]}")
            print(f"    内容前100字符: {repr(item['content'][:100])}")
    else:
        print("\n很好！没有发现明显的模板内容被保留")

if __name__ == '__main__':
    test_filter()
