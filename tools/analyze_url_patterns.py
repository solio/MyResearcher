#!/usr/bin/env python3
"""
分析数据中的URL模式，找出模板页面
"""
import json
from collections import Counter, defaultdict
from urllib.parse import urlparse

def analyze_url_patterns(json_path):
    """分析JSON中的URL模式"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print("=" * 80)
    print("URL模式分析")
    print("=" * 80)

    all_urls = []
    url_contents = {}
    domain_counts = Counter()
    path_counts = Counter()

    for result in data.get('results', []):
        target_name = result.get('target_name', '')
        print(f"\n{target_name}")

        news_list = result.get('news_list', [])
        for item in news_list:
            url = item.get('url', '')
            title = item.get('title', '')
            content = item.get('content', '')

            if url:
                all_urls.append(url)
                url_contents[url] = {
                    'title': title,
                    'content': content,
                    'target': target_name
                }

                # 分析域名
                try:
                    parsed = urlparse(url)
                    domain = parsed.netloc
                    domain_counts[domain] += 1

                    # 分析路径模式
                    path = parsed.path
                    # 把数字替换为占位符，找模式
                    import re
                    path_pattern = re.sub(r'\d{6}', '[股票代码]', path)
                    path_pattern = re.sub(r'\d{4}', '[年份]', path_pattern)
                    path_counts[path_pattern] += 1
                except:
                    pass

    print(f"\n\n共发现 {len(all_urls)} 个URL\n")

    print("=" * 80)
    print("域名统计（Top 20）")
    print("=" * 80)
    for domain, count in domain_counts.most_common(20):
        print(f"{domain}: {count}")

    print("\n" + "=" * 80)
    print("路径模式统计（Top 30）")
    print("=" * 80)
    for path, count in path_counts.most_common(30):
        print(f"{path}: {count}")

    print("\n" + "=" * 80)
    print("查看每个域名的样本内容")
    print("=" * 80)

    # 按域名分组查看样本
    urls_by_domain = defaultdict(list)
    for url in all_urls:
        try:
            domain = urlparse(url).netloc
            urls_by_domain[domain].append(url)
        except:
            pass

    for domain, urls in sorted(urls_by_domain.items(), key=lambda x: -len(x[1]))[:10]:
        print(f"\n{'=' * 80}")
        print(f"域名: {domain} (共{len(urls)}个)")
        print(f"{'=' * 80}")

        # 看前3个样本
        for i, url in enumerate(urls[:3]):
            info = url_contents[url]
            print(f"\n[{i+1}] URL: {url}")
            print(f"    标题: {info['title'][:80]}")
            print(f"    内容: {info['content'][:150]}...")

    return url_contents

if __name__ == '__main__':
    json_path = '/Users/mac/Documents/trae_projects/prompt-engineering/output/20260507/20260507_091303-数据.json'
    analyze_url_patterns(json_path)
