#!/usr/bin/env python3
"""
检查0515和0518的数据是否有重叠重复
"""
import sys
import json
from pathlib import Path
from collections import defaultdict

# 确保能导入模块
sys.path.insert(0, str(Path(__file__).parent))


def load_data(date_str):
    """加载指定日期的数据"""
    data_dir = Path(__file__).parent / "output" / date_str

    # 找到数据文件
    data_files = list(data_dir.glob("*-数据.json"))
    if not data_files:
        print(f"❌ 找不到 {date_str} 的数据文件")
        return None

    data_file = sorted(data_files)[-1]  # 取最新的
    print(f"✅ 加载数据: {data_file}")

    with open(data_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def extract_urls(data):
    """从数据中提取所有URL"""
    all_urls = {}

    for result in data.get("results", []):
        target_name = result.get("target_name", "unknown")
        urls = []

        for news in result.get("news_list", []):
            url = news.get("url", "")
            if url:
                urls.append(url)

        all_urls[target_name] = urls

    return all_urls


def compare_urls(urls_0515, urls_0518):
    """比较URL重叠情况"""
    print("\n" + "=" * 80)
    print("URL重叠分析")
    print("=" * 80)

    all_targets = set(urls_0515.keys()) | set(urls_0518.keys())

    total_0515 = 0
    total_0518 = 0
    total_overlap = 0

    for target in sorted(all_targets):
        urls1 = set(urls_0515.get(target, []))
        urls2 = set(urls_0518.get(target, []))

        overlap = urls1 & urls2

        total_0515 += len(urls1)
        total_0518 += len(urls2)
        total_overlap += len(overlap)

        print(f"\n{target}:")
        print(f"  0515: {len(urls1)} 条")
        print(f"  0518: {len(urls2)} 条")
        print(f"  重叠: {len(overlap)} 条")

        if overlap:
            print(f"  重叠URL:")
            for url in sorted(overlap)[:5]:  # 只显示前5个
                print(f"    - {url}")
            if len(overlap) > 5:
                print(f"    ... 还有 {len(overlap) - 5} 条")

    print("\n" + "=" * 80)
    print("总结")
    print("=" * 80)
    print(f"0515 总URL数: {total_0515}")
    print(f"0518 总URL数: {total_0518}")
    print(f"重叠URL数: {total_overlap}")
    if total_0515 > 0:
        print(f"重叠率 (相对于0515): {total_overlap/total_0515*100:.1f}%")
    if total_0518 > 0:
        print(f"重叠率 (相对于0518): {total_overlap/total_0518*100:.1f}%")

    return total_overlap


def check_content_similarity(data_0515, data_0518):
    """检查内容相似度（通过标题比较）"""
    print("\n" + "=" * 80)
    print("标题相似性分析")
    print("=" * 80)

    titles_0515 = defaultdict(list)
    titles_0518 = defaultdict(list)

    for result in data_0515.get("results", []):
        target_name = result.get("target_name", "unknown")
        for news in result.get("news_list", []):
            title = news.get("title", "")
            if title:
                titles_0515[target_name].append(title)

    for result in data_0518.get("results", []):
        target_name = result.get("target_name", "unknown")
        for news in result.get("news_list", []):
            title = news.get("title", "")
            if title:
                titles_0518[target_name].append(title)

    for target in sorted(set(titles_0515.keys()) | set(titles_0518.keys())):
        t1 = set(titles_0515.get(target, []))
        t2 = set(titles_0518.get(target, []))

        overlap = t1 & t2

        if overlap:
            print(f"\n{target}:")
            print(f"  重叠标题: {len(overlap)} 个")
            for title in sorted(overlap)[:3]:
                print(f"    - {title}")
            if len(overlap) > 3:
                print(f"    ... 还有 {len(overlap) - 3} 个")

    print("\n✅ 分析完成")


def main():
    # 加载数据
    data_0515 = load_data("20260515")
    data_0518 = load_data("20260518")

    if not data_0515 or not data_0518:
        return 1

    # 提取URL
    urls_0515 = extract_urls(data_0515)
    urls_0518 = extract_urls(data_0518)

    # 比较URL
    compare_urls(urls_0515, urls_0518)

    # 检查内容相似性
    check_content_similarity(data_0515, data_0518)

    return 0


if __name__ == "__main__":
    sys.exit(main())
